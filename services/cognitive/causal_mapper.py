"""
Causal Mapper: Extracts Subject → Action → Object relationships using LLMs.

This is the core "understanding" layer that builds the knowledge graph structure.
"""
from typing import List
import json
from openai import OpenAI

from prompts import build_causal_mapping_prompt
from shared.models import Entity, CausalRelationship
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("causal-mapper")


class CausalMapper:
    """
    Extracts causal relationships between entities in news articles.
    Uses chain-of-thought prompting to identify: Subject → Action → Object
    """
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    def extract_relationships(
        self,
        article_text: str,
        entities: List[Entity]
    ) -> List[CausalRelationship]:
        """
        Extract causal relationships from article text.
        
        Args:
            article_text: Full article content
            entities: Already-extracted entities (provides context to LLM)
        
        Returns:
            List of CausalRelationship objects
        """
        if len(entities) < 2:
            logger.info("Not enough entities to form relationships")
            return []
        
        try:
            # Convert entities to simple dict for prompt
            entity_summary = [
                {"name": e.name, "type": e.type}
                for e in entities
            ]
            
            # Build prompt
            messages = build_causal_mapping_prompt(article_text, entity_summary)
            
            log_with_context(
                logger, "info",
                "Calling LLM for causal relationship extraction",
                model=self.model,
                entity_count=len(entities)
            )
            
            # Call OpenAI with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,  # Slightly higher for reasoning
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            relationships_data = json.loads(content)
            
            # Handle both array and object with 'relationships' key
            if isinstance(relationships_data, dict):
                if "relationships" in relationships_data:
                    relationships_data = relationships_data["relationships"]
                else:
                    # If dict but no 'relationships' key, might be single relationship
                    relationships_data = [relationships_data]
            
            # Convert to Pydantic models
            relationships = []
            for rel_dict in relationships_data:
                try:
                    relationship = CausalRelationship(
                        subject=Entity(**rel_dict["subject"]),
                        action=rel_dict["action"].upper(),  # Normalize to uppercase
                        object=Entity(**rel_dict["object"]),
                        sentiment=rel_dict["sentiment"],
                        confidence=rel_dict["confidence"],
                        reasoning=rel_dict["reasoning"]
                    )
                    relationships.append(relationship)
                except Exception as e:
                    logger.warning(f"Failed to parse relationship: {rel_dict}. Error: {e}")
            
            log_with_context(
                logger, "info",
                f"Extracted {len(relationships)} causal relationships",
                relationship_count=len(relationships),
                tokens_used=response.usage.total_tokens
            )
            
            return relationships
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            return []
        
        except Exception as e:
            logger.error(f"Causal relationship extraction failed: {e}")
            return []
    
    def filter_by_confidence(
        self,
        relationships: List[CausalRelationship],
        threshold: float = 0.7
    ) -> List[CausalRelationship]:
        """
        Filter relationships by confidence score.
        
        Args:
            relationships: All extracted relationships
            threshold: Minimum confidence to keep
        
        Returns:
            High-confidence relationships only
        """
        filtered = [r for r in relationships if r.confidence >= threshold]
        
        log_with_context(
            logger, "info",
            f"Filtered relationships by confidence >= {threshold}",
            original_count=len(relationships),
            filtered_count=len(filtered)
        )
        
        return filtered


# Example usage
if __name__ == "__main__":
    from entity_extractor import EntityExtractor
    
    extractor = EntityExtractor()
    mapper = CausalMapper()
    
    sample_article = """
    The Federal Reserve raised interest rates by 0.25%, impacting mortgage 
    lenders and tech companies reliant on cheap debt. Chair Jerome Powell 
    stated that inflation remains a concern despite recent economic data.
    """
    
    # First extract entities
    entities = extractor.extract(sample_article)
    
    print("\n=== Extracted Entities ===")
    for e in entities:
        print(f"- {e.name} ({e.type})")
    
    # Then extract relationships
    relationships = mapper.extract_relationships(sample_article, entities)
    
    print("\n=== Causal Relationships ===")
    for rel in relationships:
        print(f"\n{rel.subject.name} --[{rel.action}]--> {rel.object.name}")
        print(f"  Sentiment: {rel.sentiment:.2f} | Confidence: {rel.confidence:.2f}")
        print(f"  Reasoning: {rel.reasoning}")
