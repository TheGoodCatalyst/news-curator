"""
Impact Summarizer: Generates executive-level summaries of news impact.

Creates concise 2-sentence summaries with severity scoring and stakeholder identification.
"""
from typing import List
import json
from openai import OpenAI

from prompts import build_impact_summary_prompt
from shared.models import Entity, CausalRelationship, ImpactSummary
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("impact-summarizer")


class ImpactSummarizer:
    """
    Generates business impact summaries from analyzed articles.
    """
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    def generate_summary(
        self,
        article_text: str,
        entities: List[Entity],
        relationships: List[CausalRelationship]
    ) -> ImpactSummary:
        """
        Generate impact summary for an article.
        
        Args:
            article_text: Full article content
            entities: Extracted entities
            relationships: Causal relationships
        
        Returns:
            ImpactSummary object
        """
        try:
            # Prepare simplified context for LLM
            entity_context = [
                {"name": e.name, "type": e.type, "industry": e.industry}
                for e in entities
            ]
            
            relationship_context = [
                {
                    "subject": r.subject.name,
                    "action": r.action,
                    "object": r.object.name,
                    "sentiment": r.sentiment
                }
                for r in relationships
            ]
            
            # Build prompt
            messages = build_impact_summary_prompt(
                article_text,
                entity_context,
                relationship_context
            )
            
            log_with_context(
                logger, "info",
                "Generating impact summary",
                model=self.model,
                entity_count=len(entities),
                relationship_count=len(relationships)
            )
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Balanced for creativity + accuracy
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            summary_data = json.loads(content)
            
            # Convert to Pydantic model
            impact_summary = ImpactSummary(
                summary=summary_data["summary"],
                severity=summary_data["severity"],
                affected_sectors=summary_data["affected_sectors"],
                key_stakeholders=summary_data.get("key_stakeholders", [])
            )
            
            log_with_context(
                logger, "info",
                "Impact summary generated",
                severity=impact_summary.severity,
                sectors=len(impact_summary.affected_sectors),
                tokens_used=response.usage.total_tokens
            )
            
            return impact_summary
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response content: {content}")
            # Return default low-impact summary
            return ImpactSummary(
                summary="Unable to generate impact summary due to processing error.",
                severity=1,
                affected_sectors=["Unknown"],
                key_stakeholders=[]
            )
        
        except Exception as e:
            logger.error(f"Impact summarization failed: {e}")
            return ImpactSummary(
                summary="Processing error occurred.",
                severity=1,
                affected_sectors=["Unknown"],
                key_stakeholders=[]
            )


# Example usage
if __name__ == "__main__":
    from entity_extractor import EntityExtractor
    from causal_mapper import CausalMapper
    
    extractor = EntityExtractor()
    mapper = CausalMapper()
    summarizer = ImpactSummarizer()
    
    sample_article = """
    The FDA rejected PharmaCorp's new cancer drug application due to insufficient 
    clinical trial data. The company's stock dropped 15% in after-hours trading, 
    wiping out $5 billion in market capitalization. Analysts expect delays of 
    at least 18 months for resubmission, affecting the company's oncology pipeline.
    """
    
    # Extract entities
    entities = extractor.extract(sample_article)
    
    # Extract relationships
    relationships = mapper.extract_relationships(sample_article, entities)
    
    # Generate impact summary
    impact = summarizer.generate_summary(sample_article, entities, relationships)
    
    print("\n=== Impact Summary ===")
    print(f"Summary: {impact.summary}")
    print(f"Severity: {impact.severity}/10")
    print(f"Affected Sectors: {', '.join(impact.affected_sectors)}")
    print(f"Key Stakeholders: {', '.join(impact.key_stakeholders)}")
