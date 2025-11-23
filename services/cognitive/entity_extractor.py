"""
Entity Extractor: Combines Spacy NER with LLM refinement for high-accuracy entity extraction.

Pipeline:
1. Spacy NER for fast initial detection
2. LLM-based categorization and enrichment
3. Confidence scoring
"""
import spacy
from typing import List, Dict, Any
import json
from openai import OpenAI

from prompts import build_entity_extraction_prompt
from shared.models import Entity
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("entity-extractor")


class EntityExtractor:
    """
    Extracts and classifies entities from news articles.
    Uses a hybrid approach: Spacy for initial detection, LLM for refinement.
    """
    
    def __init__(self):
        """Initialize Spacy model and OpenAI client"""
        try:
            self.nlp = spacy.load("en_core_web_lg")
            logger.info("Loaded Spacy model: en_core_web_lg")
        except OSError:
            logger.warning("Spacy model not found, downloading...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_lg"])
            self.nlp = spacy.load("en_core_web_lg")
        
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        
        # Entity type mapping from Spacy to our schema
        self.spacy_type_map = {
            "ORG": "company",
            "PERSON": "person",
            "GPE": "location",  # Geopolitical entity
            "LOC": "location",
            "EVENT": "event",
            "MONEY": "financial_instrument",
            "PRODUCT": "product"
        }
    
    def extract_with_spacy(self, text: str) -> List[Dict[str, Any]]:
        """
        First pass: Extract entities using Spacy NER.
        
        Args:
            text: Article content
        
        Returns:
            List of entities with basic categorization
        """
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            if ent.label_ in self.spacy_type_map:
                entities.append({
                    "name": ent.text,
                    "type": self.spacy_type_map[ent.label_],
                    "confidence": 0.75,  # Base confidence for Spacy
                    "spacy_label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char
                })
        
        log_with_context(
            logger, "info",
            f"Spacy extracted {len(entities)} initial entities",
            entity_count=len(entities)
        )
        
        return entities
    
    def refine_with_llm(self, text: str, spacy_entities: List[Dict]) -> List[Entity]:
        """
        Second pass: Use LLM to refine, categorize, and enrich entities.
        
        Args:
            text: Article content
            spacy_entities: Entities from Spacy (for context)
        
        Returns:
            List of refined Entity objects
        """
        try:
            # Build prompt with few-shot examples
            messages = build_entity_extraction_prompt(text)
            
            log_with_context(
                logger, "info",
                "Calling LLM for entity refinement",
                model=self.model,
                spacy_entity_count=len(spacy_entities)
            )
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for factual extraction
                response_format={"type": "json_object"}
            )
            
            # Parse response
            content = response.choices[0].message.content
            entities_data = json.loads(content)
            
            # Handle both array and object with 'entities' key
            if isinstance(entities_data, dict) and "entities" in entities_data:
                entities_data = entities_data["entities"]
            
            # Convert to Pydantic models
            entities = []
            for entity_dict in entities_data:
                try:
                    # Map metadata fields to top-level for specific types
                    metadata = entity_dict.get("metadata", {})
                    
                    entity = Entity(
                        name=entity_dict["name"],
                        type=entity_dict["type"],
                        confidence=entity_dict["confidence"],
                        metadata=metadata,
                        industry=metadata.get("industry"),
                        role=metadata.get("role"),
                        country=metadata.get("country"),
                        severity=metadata.get("severity")
                    )
                    entities.append(entity)
                except Exception as e:
                    logger.warning(f"Failed to parse entity: {entity_dict}. Error: {e}")
            
            log_with_context(
                logger, "info",
                f"LLM refined to {len(entities)} entities",
                refined_count=len(entities),
                tokens_used=response.usage.total_tokens
            )
            
            return entities
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            return []
        
        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")
            return []
    
    def extract(self, article_text: str) -> List[Entity]:
        """
        Main extraction pipeline: Spacy + LLM.
        
        Args:
            article_text: Full article content
        
        Returns:
            List of high-confidence Entity objects
        """
        # Step 1: Spacy initial detection
        spacy_entities = self.extract_with_spacy(article_text)
        
        # Step 2: LLM refinement
        refined_entities = self.refine_with_llm(article_text, spacy_entities)
        
        # Step 3: Filter by confidence threshold
        high_confidence_entities = [
            e for e in refined_entities if e.confidence >= 0.7
        ]
        
        log_with_context(
            logger, "info",
            "Entity extraction complete",
            total_extracted=len(refined_entities),
            high_confidence=len(high_confidence_entities)
        )
        
        return high_confidence_entities


# Example usage
if __name__ == "__main__":
    extractor = EntityExtractor()
    
    sample_article = """
    Tesla CEO Elon Musk announced a $25 billion investment in a new Gigafactory 
    in Austin, Texas. The move comes as the EV manufacturer faces increased 
    competition from Chinese automaker BYD. The factory is expected to create 
    10,000 jobs and produce 500,000 vehicles annually.
    """
    
    entities = extractor.extract(sample_article)
    
    print("\n=== Extracted Entities ===")
    for entity in entities:
        print(f"- {entity.name} ({entity.type}): {entity.confidence:.2f}")
        if entity.industry:
            print(f"  Industry: {entity.industry}")
        if entity.role:
            print(f"  Role: {entity.role}")
