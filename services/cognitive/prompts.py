"""
LLM System Prompts and Few-Shot Examples for the Cognitive Processor.

This module contains carefully crafted prompts for:
1. Entity Extraction
2. Causal Relationship Mapping
3. Impact Summarization

These prompts use chain-of-thought reasoning and few-shot learning
to maximize accuracy and minimize hallucinations.
"""

# ============================================================================
# ENTITY EXTRACTION PROMPT
# ============================================================================

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an expert financial news analyst specializing in extracting structured entities from business articles.

Your task is to identify and classify entities into these categories:
- **Companies**: Business entities (include industry)
- **People**: Individuals (include their role/title)
- **Locations**: Countries, cities, regions (include geopolitical context)
- **Events**: Significant occurrences (include severity: low/medium/high/critical)

CRITICAL RULES:
1. Only extract entities EXPLICITLY mentioned in the text
2. DO NOT infer or hallucinate entities not present
3. For companies, always research their primary industry
4. Assign confidence scores: 0.9+ for explicit mentions, 0.7-0.9 for inferred context
5. If unsure about an entity's type, mark confidence < 0.7

Output format: JSON array of entities with:
{
  "name": "string",
  "type": "company|person|location|event",
  "confidence": 0.0-1.0,
  "metadata": {
    "industry": "string" (for companies),
    "role": "string" (for people),
    "country": "string" (for locations),
    "severity": "low|medium|high|critical" (for events)
  }
}
"""

ENTITY_EXTRACTION_FEW_SHOT_EXAMPLES = [
    {
        "article": "Tesla CEO Elon Musk announced a $25 billion investment in a new Gigafactory in Austin, Texas. The move comes as the EV manufacturer faces increased competition from Chinese automaker BYD.",
        "entities": [
            {
                "name": "Tesla",
                "type": "company",
                "confidence": 0.98,
                "metadata": {"industry": "Electric Vehicles"}
            },
            {
                "name": "Elon Musk",
                "type": "person",
                "confidence": 0.98,
                "metadata": {"role": "CEO of Tesla"}
            },
            {
                "name": "Austin",
                "type": "location",
                "confidence": 0.95,
                "metadata": {"country": "United States"}
            },
            {
                "name": "Texas",
                "type": "location",
                "confidence": 0.95,
                "metadata": {"country": "United States"}
            },
            {
                "name": "BYD",
                "type": "company",
                "confidence": 0.92,
                "metadata": {"industry": "Electric Vehicles"}
            },
            {
                "name": "Gigafactory Investment",
                "type": "event",
                "confidence": 0.90,
                "metadata": {"severity": "high"}
            }
        ]
    }
]

# ============================================================================
# CAUSAL RELATIONSHIP MAPPING PROMPT
# ============================================================================

CAUSAL_RELATIONSHIP_SYSTEM_PROMPT = """You are an expert in causal analysis for business and financial news.

Your task is to extract causal relationships in the format:
**Subject → Action → Object**

Where:
- **Subject**: The actor/cause (an entity that initiates change)
- **Action**: The relationship verb (e.g., ACQUIRES, REJECTS, INVESTS_IN, DISRUPTS)
- **Object**: The affected entity (what/who is impacted)

For each relationship, provide:
1. **Sentiment**: -1.0 (very negative) to +1.0 (very positive)
2. **Confidence**: 0.0 (uncertain) to 1.0 (certain)
3. **Reasoning**: Explain your chain-of-thought in 1-2 sentences

CRITICAL RULES:
1. Only extract DIRECT causal relationships stated in the text
2. Use standardized action verbs (uppercase): ACQUIRES, REJECTS, INVESTS_IN, DISRUPTS, PARTNERS_WITH, etc.
3. Sentiment should reflect the impact on the OBJECT entity
4. If the relationship is ambiguous, set confidence < 0.7

Output format: JSON array of relationships
"""

CAUSAL_RELATIONSHIP_FEW_SHOT_EXAMPLES = [
    {
        "article": "The Federal Reserve raised interest rates by 0.25%, impacting mortgage lenders and tech companies reliant on cheap debt.",
        "relationships": [
            {
                "subject": {
                    "name": "Federal Reserve",
                    "type": "organization",
                    "confidence": 0.98
                },
                "action": "RAISES_RATES_FOR",
                "object": {
                    "name": "Mortgage Lenders",
                    "type": "industry",
                    "confidence": 0.90
                },
                "sentiment": -0.6,
                "confidence": 0.92,
                "reasoning": "Higher interest rates directly reduce mortgage demand, negatively impacting lenders' revenue."
            },
            {
                "subject": {
                    "name": "Federal Reserve",
                    "type": "organization",
                    "confidence": 0.98
                },
                "action": "RAISES_RATES_FOR",
                "object": {
                    "name": "Tech Companies",
                    "type": "industry",
                    "confidence": 0.88
                },
                "sentiment": -0.7,
                "confidence": 0.89,
                "reasoning": "Tech firms relying on debt for growth face higher borrowing costs, constraining expansion."
            }
        ]
    },
    {
        "article": "Amazon Web Services announced a $10B partnership with Anthropic to develop enterprise AI solutions, directly challenging Microsoft's OpenAI integration.",
        "relationships": [
            {
                "subject": {
                    "name": "Amazon Web Services",
                    "type": "company",
                    "confidence": 0.98
                },
                "action": "PARTNERS_WITH",
                "object": {
                    "name": "Anthropic",
                    "type": "company",
                    "confidence": 0.98
                },
                "sentiment": 0.8,
                "confidence": 0.95,
                "reasoning": "Strategic partnership brings significant capital and distribution to Anthropic."
            },
            {
                "subject": {
                    "name": "Amazon Web Services",
                    "type": "company",
                    "confidence": 0.98
                },
                "action": "COMPETES_WITH",
                "object": {
                    "name": "Microsoft",
                    "type": "company",
                    "confidence": 0.95
                },
                "sentiment": -0.4,
                "confidence": 0.87,
                "reasoning": "This partnership creates direct competitive pressure on Microsoft's AI strategy."
            }
        ]
    }
]

# ============================================================================
# IMPACT SUMMARIZATION PROMPT
# ============================================================================

IMPACT_SUMMARIZATION_SYSTEM_PROMPT = """You are a business analyst creating executive summaries of news impact.

Your task is to generate a 2-sentence summary that answers:
1. **What happened?** (First sentence: The core event)
2. **Who cares?** (Second sentence: The stakeholders/industries affected)

Additionally, provide:
- **Severity**: Integer from 1-10
  - 1-3: Minor operational news
  - 4-6: Significant market movement
  - 7-8: Major industry disruption
  - 9-10: Economy-wide crisis
- **Affected Sectors**: List of industries impacted
- **Key Stakeholders**: Main parties who should care

CRITICAL RULES:
1. Be concise (max 2 sentences total)
2. Focus on BUSINESS IMPACT, not just the event itself
3. Severity should match the actual economic consequence
4. List specific industries, not vague categories

Output format: JSON object
{
  "summary": "string (2 sentences, max 500 chars)",
  "severity": 1-10,
  "affected_sectors": ["Industry1", "Industry2"],
  "key_stakeholders": ["Stakeholder1", "Stakeholder2"]
}
"""

IMPACT_SUMMARIZATION_FEW_SHOT_EXAMPLES = [
    {
        "article": "The FDA rejected PharmaCorp's new cancer drug application due to insufficient clinical trial data. The company's stock dropped 15% in after-hours trading.",
        "impact_summary": {
            "summary": "FDA's rejection of PharmaCorp's cancer drug halts a major revenue stream and threatens the company's growth trajectory. This affects pharmaceutical investors, oncology research partners, and potentially delays treatment options for cancer patients.",
            "severity": 7,
            "affected_sectors": [
                "Pharmaceuticals",
                "Healthcare",
                "Biotechnology",
                "Clinical Research"
            ],
            "key_stakeholders": [
                "PharmaCorp shareholders",
                "Pharmaceutical supply chain partners",
                "Cancer treatment facilities",
                "Healthcare investors"
            ]
        }
    },
    {
        "article": "Apple announced a new color option for the iPhone 15. The midnight blue variant will be available next month.",
        "impact_summary": {
            "summary": "Apple introduced a new iPhone color variant as part of its routine product refresh cycle. This is a minor cosmetic update with negligible business impact beyond potential marginal sales increases.",
            "severity": 2,
            "affected_sectors": [
                "Consumer Electronics",
                "Retail"
            ],
            "key_stakeholders": [
                "Apple retail partners",
                "Consumer electronics analysts"
            ]
        }
    }
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_entity_extraction_prompt(article_text: str) -> list:
    """
    Build the full prompt for entity extraction with few-shot examples.
    
    Args:
        article_text: The news article content
    
    Returns:
        List of messages for OpenAI chat completion
    """
    messages = [
        {"role": "system", "content": ENTITY_EXTRACTION_SYSTEM_PROMPT}
    ]
    
    # Add few-shot examples
    for example in ENTITY_EXTRACTION_FEW_SHOT_EXAMPLES:
        messages.append({
            "role": "user",
            "content": f"Article: {example['article']}"
        })
        messages.append({
            "role": "assistant",
            "content": str(example['entities'])
        })
    
    # Add the actual article
    messages.append({
        "role": "user",
        "content": f"Article: {article_text}\n\nExtract all entities as JSON array:"
    })
    
    return messages


def build_causal_mapping_prompt(article_text: str, entities: list) -> list:
    """
    Build the prompt for causal relationship extraction.
    
    Args:
        article_text: The news article content
        entities: List of already-extracted entities
    
    Returns:
        List of messages for OpenAI chat completion
    """
    messages = [
        {"role": "system", "content": CAUSAL_RELATIONSHIP_SYSTEM_PROMPT}
    ]
    
    # Add few-shot examples
    for example in CAUSAL_RELATIONSHIP_FEW_SHOT_EXAMPLES:
        messages.append({
            "role": "user",
            "content": f"Article: {example['article']}"
        })
        messages.append({
            "role": "assistant",
            "content": str(example['relationships'])
        })
    
    # Add the actual task
    messages.append({
        "role": "user",
        "content": f"""Article: {article_text}

Known Entities: {entities}

Extract causal relationships between these entities as JSON array:"""
    })
    
    return messages


def build_impact_summary_prompt(article_text: str, entities: list, relationships: list) -> list:
    """
    Build the prompt for impact summarization.
    
    Args:
        article_text: The news article content
        entities: Extracted entities
        relationships: Extracted causal relationships
    
    Returns:
        List of messages for OpenAI chat completion
    """
    messages = [
        {"role": "system", "content": IMPACT_SUMMARIZATION_SYSTEM_PROMPT}
    ]
    
    # Add few-shot examples
    for example in IMPACT_SUMMARIZATION_FEW_SHOT_EXAMPLES:
        messages.append({
            "role": "user",
            "content": f"Article: {example['article']}"
        })
        messages.append({
            "role": "assistant",
            "content": str(example['impact_summary'])
        })
    
    # Add the actual task
    messages.append({
        "role": "user",
        "content": f"""Article: {article_text}

Entities: {entities}
Relationships: {relationships}

Generate impact summary as JSON:"""
    })
    
    return messages
