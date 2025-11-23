"""
Fact Checker: Validates extracted entities against trusted external sources.

This layer prevents hallucinations by verifying entities exist in:
1. Crunchbase (for companies)
2. Wikidata (for people, locations, events)

Entities that fail validation are flagged for human review.
"""
from typing import List, Dict, Any, Optional
import requests
from time import sleep
from functools import lru_cache

from shared.models import Entity
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("fact-checker")


class FactChecker:
    """
    Validates extracted entities against external knowledge bases.
    Flags potential hallucinations.
    """
    
    def __init__(self):
        """Initialize API clients"""
        self.crunchbase_api_key = settings.crunchbase_api_key
        self.wikidata_endpoint = settings.wikidata_api_endpoint
        
        # Cache to avoid redundant API calls
        self.validation_cache: Dict[str, bool] = {}
    
    @lru_cache(maxsize=1000)
    def validate_company_crunchbase(self, company_name: str) -> Dict[str, Any]:
        """
        Validate a company exists in Crunchbase.
        
        Args:
            company_name: Company name to validate
        
        Returns:
            Dict with validation result and metadata
        """
        if not self.crunchbase_api_key:
            logger.warning("Crunchbase API key not configured, skipping validation")
            return {"validated": False, "reason": "no_api_key", "metadata": {}}
        
        try:
            # Crunchbase Autocomplete API (free tier)
            url = "https://api.crunchbase.com/api/v4/autocompletes"
            params = {
                "query": company_name,
                "user_key": self.crunchbase_api_key,
                "limit": 5
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                entities = data.get("entities", [])
                
                # Check for exact or close match
                for entity in entities:
                    if entity.get("identifier", {}).get("value", "").lower() == company_name.lower():
                        return {
                            "validated": True,
                            "confidence": 0.95,
                            "metadata": {
                                "crunchbase_uuid": entity["identifier"]["uuid"],
                                "permalink": entity["identifier"]["permalink"],
                                "short_description": entity.get("short_description", "")
                            }
                        }
                
                # Partial match
                if len(entities) > 0:
                    return {
                        "validated": True,
                        "confidence": 0.75,
                        "metadata": {"partial_match": True}
                    }
            
            return {"validated": False, "reason": "not_found", "metadata": {}}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Crunchbase API error for '{company_name}': {e}")
            return {"validated": False, "reason": "api_error", "metadata": {}}
    
    @lru_cache(maxsize=1000)
    def validate_entity_wikidata(self, entity_name: str, entity_type: str) -> Dict[str, Any]:
        """
        Validate an entity exists in Wikidata.
        
        Args:
            entity_name: Entity name to validate
            entity_type: Type hint (person, location, event)
        
        Returns:
            Dict with validation result
        """
        try:
            # Wikidata search API
            params = {
                "action": "wbsearchentities",
                "format": "json",
                "language": "en",
                "search": entity_name,
                "limit": 5
            }
            
            response = requests.get(self.wikidata_endpoint, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("search", [])
                
                # Check for matches
                for result in results:
                    label = result.get("label", "").lower()
                    description = result.get("description", "").lower()
                    
                    # Exact match
                    if label == entity_name.lower():
                        return {
                            "validated": True,
                            "confidence": 0.92,
                            "metadata": {
                                "wikidata_id": result["id"],
                                "description": result.get("description", "")
                            }
                        }
                    
                    # Type-based validation (e.g., "person" in description for people)
                    if entity_type in description or label in entity_name.lower():
                        return {
                            "validated": True,
                            "confidence": 0.80,
                            "metadata": {"fuzzy_match": True}
                        }
                
                return {"validated": False, "reason": "not_found", "metadata": {}}
            
            return {"validated": False, "reason": "api_error", "metadata": {}}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Wikidata API error for '{entity_name}': {e}")
            return {"validated": False, "reason": "api_error", "metadata": {}}
    
    def validate_entity(self, entity: Entity) -> Dict[str, Any]:
        """
        Validate a single entity based on its type.
        
        Args:
            entity: Entity to validate
        
        Returns:
            Validation result with confidence adjustment
        """
        cache_key = f"{entity.name}:{entity.type}"
        
        # Check cache first
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]
        
        result = {"validated": False, "metadata": {}}
        
        # Route to appropriate validator
        if entity.type == "company":
            result = self.validate_company_crunchbase(entity.name)
        elif entity.type in ["person", "location", "event"]:
            result = self.validate_entity_wikidata(entity.name, entity.type)
        else:
            # Unknown type, skip validation
            result = {"validated": True, "confidence": entity.confidence, "metadata": {"skipped": True}}
        
        # Cache result
        self.validation_cache[cache_key] = result
        
        # Rate limiting
        sleep(0.1)  # Be nice to APIs
        
        return result
    
    def validate_batch(self, entities: List[Entity]) -> tuple[List[Entity], List[str]]:
        """
        Validate a batch of entities.
        
        Args:
            entities: List of entities to validate
        
        Returns:
            Tuple of (validated_entities, hallucination_flags)
        """
        validated_entities = []
        hallucination_flags = []
        
        for entity in entities:
            validation_result = self.validate_entity(entity)
            
            if validation_result["validated"]:
                # Adjust confidence based on validation
                if "confidence" in validation_result:
                    entity.confidence = min(entity.confidence, validation_result["confidence"])
                
                # Merge metadata
                entity.metadata.update(validation_result.get("metadata", {}))
                validated_entities.append(entity)
                
                log_with_context(
                    logger, "info",
                    f"Entity validated: {entity.name}",
                    entity_name=entity.name,
                    entity_type=entity.type,
                    validated_confidence=entity.confidence
                )
            else:
                # Flag as potential hallucination
                hallucination_flags.append(
                    f"{entity.name} ({entity.type}): {validation_result.get('reason', 'unknown')}"
                )
                
                logger.warning(f"Entity failed validation: {entity.name} - {validation_result.get('reason')}")
        
        log_with_context(
            logger, "info",
            "Batch validation complete",
            total_entities=len(entities),
            validated=len(validated_entities),
            hallucinations=len(hallucination_flags)
        )
        
        return validated_entities, hallucination_flags


# Example usage
if __name__ == "__main__":
    checker = FactChecker()
    
    test_entities = [
        Entity(name="Tesla", type="company", confidence=0.9, metadata={}),
        Entity(name="FakeCompanyCorp", type="company", confidence=0.85, metadata={}),
        Entity(name="Elon Musk", type="person", confidence=0.95, metadata={}),
        Entity(name="Austin", type="location", confidence=0.90, metadata={})
    ]
    
    validated, flags = checker.validate_batch(test_entities)
    
    print("\n=== Validated Entities ===")
    for e in validated:
        print(f"✓ {e.name} ({e.type}): {e.confidence:.2f}")
    
    print("\n=== Hallucination Flags ===")
    for flag in flags:
        print(f"✗ {flag}")
