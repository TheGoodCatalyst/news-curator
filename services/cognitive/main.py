"""
Main Cognitive Processor Service

Orchestrates the AI pipeline:
1. Consumes RawArticleEvent from Kafka
2. Runs entity extraction → causal mapping → fact checking → impact summary
3. Publishes StructuredGraphEvent to Kafka
"""
import json
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from datetime import datetime

from entity_extractor import EntityExtractor
from causal_mapper import CausalMapper
from fact_checker import FactChecker
from impact_summarizer import ImpactSummarizer

from shared.models import RawArticleEvent, StructuredGraphEvent
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("cognitive-processor", settings.log_level)


class CognitiveProcessor:
    """
    Main service orchestrator for AI-powered news analysis.
    """
    
    def __init__(self):
        """Initialize all AI components and Kafka clients"""
        logger.info("Initializing Cognitive Processor service...")
        
        # Initialize AI components
        self.entity_extractor = EntityExtractor()
        self.causal_mapper = CausalMapper()
        self.fact_checker = FactChecker()
        self.impact_summarizer = ImpactSummarizer()
        
        # Initialize Kafka consumer
        self.consumer = KafkaConsumer(
            settings.kafka_topic_raw_news,
            bootstrap_servers=settings.kafka_bootstrap_servers.split(','),
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='cognitive-processor-group',
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )
        
        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(','),
            value_serializer=lambda m: json.dumps(m).encode('utf-8'),
            acks='all',  # Wait for all replicas
            retries=3
        )
        
        logger.info("Cognitive Processor initialized successfully")
    
    def process_article(self, article_event: RawArticleEvent) -> StructuredGraphEvent:
        """
        Process a single article through the full AI pipeline.
        
        Args:
            article_event: Raw article event from ingestion service
        
        Returns:
            Structured graph event ready for Neo4j insertion
        """
        start_time = datetime.utcnow()
        
        log_with_context(
            logger, "info",
            "Processing article",
            article_id=article_event.article_id,
            source=article_event.source,
            title=article_event.title[:100]
        )
        
        try:
            # Step 1: Extract entities
            logger.info("Step 1/4: Extracting entities...")
            entities = self.entity_extractor.extract(article_event.content)
            
            if not entities:
                logger.warning(f"No entities extracted from article {article_event.article_id}")
                # Return minimal event
                return StructuredGraphEvent(
                    article_id=article_event.article_id,
                    entities=[],
                    relationships=[],
                    impact_summary={
                        "summary": "No significant entities or impact detected.",
                        "severity": 1,
                        "affected_sectors": []
                    },
                    fact_check_passed=True,
                    hallucination_flags=[]
                )
            
            # Step 2: Extract causal relationships
            logger.info("Step 2/4: Mapping causal relationships...")
            relationships = self.causal_mapper.extract_relationships(
                article_event.content,
                entities
            )
            
            # Filter low-confidence relationships
            relationships = self.causal_mapper.filter_by_confidence(
                relationships,
                threshold=0.7
            )
            
            # Step 3: Fact-check entities
            logger.info("Step 3/4: Fact-checking entities...")
            validated_entities, hallucination_flags = self.fact_checker.validate_batch(entities)
            
            fact_check_passed = len(hallucination_flags) == 0
            
            if not fact_check_passed:
                log_with_context(
                    logger, "warning",
                    "Hallucinations detected",
                    article_id=article_event.article_id,
                    hallucination_count=len(hallucination_flags),
                    flags=hallucination_flags
                )
            
            # Step 4: Generate impact summary
            logger.info("Step 4/4: Generating impact summary...")
            impact_summary = self.impact_summarizer.generate_summary(
                article_event.content,
                validated_entities,
                relationships
            )
            
            # Create structured event
            structured_event = StructuredGraphEvent(
                article_id=article_event.article_id,
                entities=validated_entities,
                relationships=relationships,
                impact_summary=impact_summary,
                processing_timestamp=datetime.utcnow(),
                llm_model_used=settings.openai_model,
                fact_check_passed=fact_check_passed,
                hallucination_flags=hallucination_flags
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            log_with_context(
                logger, "info",
                "Article processing complete",
                article_id=article_event.article_id,
                processing_time_seconds=processing_time,
                entity_count=len(validated_entities),
                relationship_count=len(relationships),
                severity=impact_summary.severity
            )
            
            return structured_event
        
        except Exception as e:
            logger.error(
                f"Failed to process article {article_event.article_id}: {e}",
                exc_info=True
            )
            raise
    
    def publish_structured_event(self, event: StructuredGraphEvent):
        """
        Publish structured event to Kafka.
        
        Args:
            event: Structured graph event to publish
        """
        try:
            # Convert Pydantic model to dict
            event_dict = event.model_dump(mode='json')
            
            # Publish to Kafka
            future = self.producer.send(
                settings.kafka_topic_structured_graph,
                value=event_dict
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            log_with_context(
                logger, "info",
                "Published structured event to Kafka",
                article_id=event.article_id,
                topic=record_metadata.topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset
            )
        
        except KafkaError as e:
            logger.error(f"Failed to publish event to Kafka: {e}")
            raise
    
    def run(self):
        """
        Main event loop: consume, process, publish.
        """
        logger.info(f"Starting Cognitive Processor - listening to topic: {settings.kafka_topic_raw_news}")
        
        try:
            for message in self.consumer:
                try:
                    # Parse raw article event
                    raw_event_data = message.value
                    article_event = RawArticleEvent(**raw_event_data)
                    
                    # Process through AI pipeline
                    structured_event = self.process_article(article_event)
                    
                    # Publish result
                    self.publish_structured_event(structured_event)
                
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Continue processing other messages
                    continue
        
        except KeyboardInterrupt:
            logger.info("Shutting down Cognitive Processor...")
        
        finally:
            self.consumer.close()
            self.producer.close()
            logger.info("Cognitive Processor stopped")


if __name__ == "__main__":
    processor = CognitiveProcessor()
    processor.run()
