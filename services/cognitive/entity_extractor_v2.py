"""
Enhanced Entity Extractor using HuggingFace Transformers

Supports multiple model backends:
1. HuggingFace transformers for NER (better than Spacy)
2. OpenAI GPT-4
3. Local LLMs (Llama 3, Mistral)
"""
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForTokenClassification,
    pipeline,
    AutoModelForCausalLM
)
from typing import List, Dict, Any, Optional
import json
from enum import Enum

from prompts import build_entity_extraction_prompt
from shared.models import Entity
from shared.config import settings
from shared.utils import get_logger, log_with_context

logger = get_logger("entity-extractor-v2")


class ModelBackend(str, Enum):
    """Available model backends"""
    HUGGINGFACE_NER = "huggingface_ner"  # Transformer NER models
    OPENAI = "openai"  # GPT-4
    LOCAL_LLM = "local_llm"  # Llama 3, Mistral, etc.
    HYBRID = "hybrid"  # HF NER + LLM refinement


class EnhancedEntityExtractor:
    """
    Enhanced entity extraction with multiple model backends.
    
    Recommended models:
    - NER: "dslim/bert-base-NER" or "Davlan/xlm-roberta-base-ner-hrl"
    - LLM: "meta-llama/Meta-Llama-3-8B-Instruct" or "mistralai/Mistral-7B-Instruct-v0.2"
    """
    
    # Recommended HuggingFace NER models
    RECOMMENDED_NER_MODELS = {
        "bert-base": "dslim/bert-base-NER",  # Fast, English
        "xlm-roberta": "Davlan/xlm-roberta-base-ner-hrl",  # Multilingual, high accuracy
        "distilbert": "dslim/distilbert-NER",  # Lighter, faster
    }
    
    # Recommended local LLM models
    RECOMMENDED_LLM_MODELS = {
        "llama3-8b": "meta-llama/Meta-Llama-3-8B-Instruct",
        "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
        "phi-3": "microsoft/Phi-3-mini-4k-instruct",  # Smaller, efficient
    }
    
    def __init__(
        self,
        backend: ModelBackend = ModelBackend.HYBRID,
        ner_model: str = "dslim/bert-base-NER",
        llm_model: Optional[str] = None,
        use_gpu: bool = True
    ):
        """Initialize entity extractor with model backend selection"""
        self.backend = backend
        self.device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        
        logger.info(f"Initializing Enhanced Entity Extractor (backend: {backend}, device: {self.device})")
        
        # Initialize NER pipeline (if needed)
        if backend in [ModelBackend.HUGGINGFACE_NER, ModelBackend.HYBRID]:
            self._init_ner_pipeline(ner_model)
        
        # Initialize LLM (if needed)
        if backend in [ModelBackend.OPENAI, ModelBackend.LOCAL_LLM, ModelBackend.HYBRID]:
            self._init_llm(llm_model)
    
    def _init_ner_pipeline(self, model_name: str):
        """Initialize HuggingFace NER pipeline"""
        try:
            logger.info(f"Loading NER model: {model_name}")
            
            self.ner_pipeline = pipeline(
                "ner",
                model=model_name,
                tokenizer=model_name,
                aggregation_strategy="simple",
                device=0 if self.device == "cuda" else -1
            )
            
            logger.info(f"NER model loaded successfully on {self.device}")
        
        except Exception as e:
            logger.error(f"Failed to load NER model: {e}")
            raise
    
    def _init_llm(self, model_name: Optional[str]):
        """Initialize LLM (OpenAI or local)"""
        if self.backend == ModelBackend.OPENAI or model_name is None:
            from openai import OpenAI
            self.llm_client = OpenAI(api_key=settings.openai_api_key)
            self.llm_model = settings.openai_model
            self.llm_type = "openai"
            logger.info(f"Using OpenAI: {self.llm_model}")
        
        else:
            logger.info(f"Loading local LLM: {model_name}")
            
            self.llm_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.llm_model_obj = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )
            self.llm_model = model_name
            self.llm_type = "local"
            
            logger.info(f"Local LLM loaded on {self.device}")
    
    def extract(self, article_text: str) -> List[Entity]:
        """
        Main extraction pipeline.
        
        Args:
            article_text: Article content
        
        Returns:
            List of Entity objects
        """
        if self.backend == ModelBackend.HUGGINGFACE_NER:
            # NER only
            ner_entities = self.extract_with_ner(article_text)
            return self._convert_ner_to_entities(ner_entities)
        
        elif self.backend == ModelBackend.OPENAI or self.backend == ModelBackend.LOCAL_LLM:
            # LLM only
            return self.refine_with_llm(article_text, [])
        
        else:  # HYBRID
            # NER + LLM refinement
            ner_entities = self.extract_with_ner(article_text)
            return self.refine_with_llm(article_text, ner_entities)
    
    def extract_with_ner(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using HuggingFace NER model"""
        try:
            ner_results = self.ner_pipeline(text)
            
            entities = []
            for result in ner_results:
                entity_type = self._map_ner_label(result['entity_group'])
                
                entities.append({
                    "name": result['word'],
                    "type": entity_type,
                    "confidence": result['score'],
                })
            
            log_with_context(
                logger, "info",
                f"NER extracted {len(entities)} entities",
                entity_count=len(entities)
            )
            
            return entities
        
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return []
    
    def _map_ner_label(self, label: str) -> str:
        """Map NER labels to our entity types"""
        label_map = {
            "PER": "person",
            "PERSON": "person",
            "ORG": "company",
            "ORGANIZATION": "company",
            "LOC": "location",
            "LOCATION": "location",
            "GPE": "location",
            "MISC": "event",
        }
        
        return label_map.get(label.upper(), "unknown")
    
    def _convert_ner_to_entities(self, ner_entities: List[Dict]) -> List[Entity]:
        """Convert NER results to Entity objects"""
        entities = []
        for ent in ner_entities:
            try:
                entity = Entity(
                    name=ent["name"],
                    type=ent["type"],
                    confidence=ent["confidence"],
                    metadata={}
                )
                entities.append(entity)
            except:
                continue
        return entities
    
    def refine_with_llm(self, text: str, ner_entities: List[Dict]) -> List[Entity]:
        """Refine entities using LLM"""
        try:
            messages = build_entity_extraction_prompt(text)
            
            if ner_entities:
                ner_summary = f"\nPre-identified entities: {[e['name'] for e in ner_entities]}"
                messages[-1]['content'] += ner_summary
            
            if self.llm_type == "openai":
                entities_data = self._call_openai(messages)
            else:
                entities_data = self._call_local_llm(messages)
            
            entities = []
            for entity_dict in entities_data:
                try:
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
                    logger.warning(f"Failed to parse entity: {e}")
            
            return entities
        
        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
            return []
    
    def _call_openai(self, messages: List[Dict]) -> List[Dict]:
        """Call OpenAI API"""
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        entities_data = json.loads(content)
        
        if isinstance(entities_data, dict) and "entities" in entities_data:
            return entities_data["entities"]
        return entities_data if isinstance(entities_data, list) else []
    
    def _call_local_llm(self, messages: List[Dict]) -> List[Dict]:
        """Call local LLM model"""
        prompt = self._format_messages_for_local(messages)
        
        inputs = self.llm_tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.llm_model_obj.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.1,
                do_sample=True,
                pad_token_id=self.llm_tokenizer.eos_token_id
            )
        
        response = self.llm_tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        
        try:
            import re
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if json_match:
                entities_data = json.loads(json_match.group(0))
                
                if isinstance(entities_data, dict) and "entities" in entities_data:
                    return entities_data["entities"]
                return entities_data if isinstance(entities_data, list) else []
        except:
            logger.warning("Failed to parse LLM JSON response")
            return []
    
    def _format_messages_for_local(self, messages: List[Dict]) -> str:
        """Format OpenAI-style messages for local LLM"""
        formatted = ""
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            if role == "system":
                formatted += f"<|system|>\n{content}\n\n"
            elif role == "user":
                formatted += f"
