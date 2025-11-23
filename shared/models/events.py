"""
Pydantic models for Kafka event messages.
These ensure type safety and validation across microservices.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class EventSeverity(str, Enum):
    """Event impact severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RawArticleEvent(BaseModel):
    """
    Event published by Ingestion Service after fetching an article.
    This is the initial entry point into the processing pipeline.
    """
    article_id: str = Field(..., description="Unique identifier (hash of URL)")
    url: HttpUrl = Field(..., description="Source URL of the article")
    title: str = Field(..., description="Article headline")
    content: str = Field(..., description="Full article text")
    source: str = Field(..., description="Publisher name (e.g., 'Reuters', 'Bloomberg')")
    published_date: datetime = Field(..., description="When the article was published")
    fetch_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When we fetched it")
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list, description="Publisher-provided tags")
    raw_html: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": "a1b2c3d4e5f6",
                "url": "https://www.reuters.com/business/fda-rejects-drug-x",
                "title": "FDA Rejects PharmaCorp's New Drug X Application",
                "content": "The Food and Drug Administration announced today...",
                "source": "Reuters",
                "published_date": "2024-01-15T14:30:00Z",
                "fetch_timestamp": "2024-01-15T14:35:22Z",
                "author": "Jane Smith",
                "tags": ["healthcare", "FDA", "pharmaceuticals"]
            }
        }


class Entity(BaseModel):
    """Extracted entity from article"""
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type: company, person, location, event")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional entity data")
    
    # Type-specific fields
    industry: Optional[str] = None  # For companies
    role: Optional[str] = None  # For people
    country: Optional[str] = None  # For locations
    severity: Optional[EventSeverity] = None  # For events


class CausalRelationship(BaseModel):
    """
    Represents a causal edge in the knowledge graph.
    Format: Subject → Action → Object
    """
    subject: Entity = Field(..., description="The actor/cause")
    action: str = Field(..., description="The verb/relationship type")
    object: Entity = Field(..., description="The affected entity")
    sentiment: float = Field(..., ge=-1.0, le=1.0, description="Sentiment: -1 (negative) to +1 (positive)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in this relationship")
    reasoning: str = Field(..., description="Chain-of-thought explanation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "subject": {
                    "name": "FDA",
                    "type": "organization",
                    "confidence": 0.95,
                    "metadata": {"full_name": "Food and Drug Administration"}
                },
                "action": "REJECTS",
                "object": {
                    "name": "PharmaCorp",
                    "type": "company",
                    "confidence": 0.92,
                    "industry": "Pharmaceuticals"
                },
                "sentiment": -0.8,
                "confidence": 0.89,
                "reasoning": "The FDA's rejection is a negative regulatory action directly impacting PharmaCorp's drug approval."
            }
        }


class ImpactSummary(BaseModel):
    """2-sentence business impact summary"""
    summary: str = Field(..., max_length=500)
    severity: int = Field(..., ge=1, le=10, description="Impact severity (1=minimal, 10=catastrophic)")
    affected_sectors: List[str] = Field(..., description="Industries/sectors impacted")
    key_stakeholders: List[str] = Field(default_factory=list, description="Main affected parties")


class StructuredGraphEvent(BaseModel):
    """
    Event published by Cognitive Processor after AI analysis.
    Contains structured data ready for graph insertion.
    """
    article_id: str
    entities: List[Entity] = Field(..., description="All extracted entities")
    relationships: List[CausalRelationship] = Field(..., description="Causal relationships")
    impact_summary: ImpactSummary
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    llm_model_used: str = Field(default="gpt-4-turbo-preview")
    fact_check_passed: bool = Field(default=False)
    hallucination_flags: List[str] = Field(default_factory=list, description="Entities that failed validation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "article_id": "a1b2c3d4e5f6",
                "entities": [
                    {
                        "name": "FDA",
                        "type": "organization",
                        "confidence": 0.95,
                        "metadata": {}
                    }
                ],
                "relationships": [
                    {
                        "subject": {"name": "FDA", "type": "organization", "confidence": 0.95},
                        "action": "REJECTS",
                        "object": {"name": "PharmaCorp", "type": "company", "confidence": 0.92},
                        "sentiment": -0.8,
                        "confidence": 0.89,
                        "reasoning": "Direct regulatory action"
                    }
                ],
                "impact_summary": {
                    "summary": "FDA's rejection significantly impacts PharmaCorp's revenue projections. This affects pharmaceutical supply chain partners.",
                    "severity": 7,
                    "affected_sectors": ["Pharmaceuticals", "Healthcare"]
                }
            }
        }


class UserFeedEvent(BaseModel):
    """
    Event for updating a user's personalized feed.
    Published by Curator Service after matching.
    """
    user_id: str
    article_id: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    match_reasons: List[str] = Field(..., description="Why this article matched (e.g., 'Follows PharmaCorp')")
    graph_depth: int = Field(..., description="Degrees of separation from user's interests")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
