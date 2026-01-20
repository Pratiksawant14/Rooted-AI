import json
from openai import OpenAI
from core.config import get_settings
from schemas import AnalyzedContext

settings = get_settings()

# Check for OpenRouter Key
if settings.OPENAI_API_KEY.startswith("sk-or-v1"):
    base_url = "https://openrouter.ai/api/v1"
    model_name = "openai/gpt-4o-mini"
else:
    base_url = None # Default to OpenAI
    model_name = "gpt-4o-mini"

client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=base_url)

SYSTEM_PROMPT_ANALYZE = """
You are the Context Extraction Engine for ROOTED AI.
Analyze the user's message and extract structured metadata.

OUTPUT FORMAT (JSON):
{
  "domains": ["education", "health", "fitness", "general", etc.],
  "category": "identity" | "habit" | "emotion" | "event",
  "time_scale": "one_time" | "repeated" | "long_term",
  "importance": "low" | "medium" | "high",
  "core_content": "Summarized fact to store in memory",
  "confidence": 0.0 to 1.0
}

DEFINITIONS:
- identity: Core beliefs, personality traits, long-term goals.
- habit: Recurring actions or routines.
- emotion: Temporary feelings or states.
- event: Specific occurrences with a timestamp.

NOISE FILTERING:
If the message is small talk (hi, ok, thanks) or filler, mark domains as ["general"] and importance as "low".
"""

def analyze_message(message: str) -> AnalyzedContext:
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini" if base_url else "gpt-4o-mini",  
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ANALYZE},
                {"role": "user", "content": message}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=500
        )
        
        data = json.loads(response.choices[0].message.content)
        return AnalyzedContext(**data)
    except Exception as e:
        print(f"Error in analyze_message: {e}")
        # Return a safe default
        return AnalyzedContext(
            domains=["general"],
            category="event",
            time_scale="one_time",
            importance="low",
            core_content=message,
            confidence=0.5
        )

def check_root_relevance(context_content: str, root_profile: dict) -> str:
    """
    Checks if the new memory aligns with, matches, or contradicts the ROOT persona.
    """
    if not root_profile:
        return "neutral"

    root_summary = root_profile.get("persona_summary", "Unknown")
    root_traits = root_profile.get("traits", {})
    root_values = root_profile.get("values", {})

    prompt = f"""
    You are the ROOT Alignment Engine.
    
    ROOT PERSONA:
    Summary: {root_summary}
    Traits: {root_traits}
    Values: {root_values}
    
    NEW MEMORY CANDIDATE:
    "{context_content}"
    
    TASK:
    Determine alignment of candidate with ROOT.
    
    RULES:
    - "aligned": Supports or exemplifies existing root traits/values.
    - "contradictory": Directly opposes specific root traits/values.
    - "neutral": Unrelated or doesn't strongly interact with root.
    - "redefining": A massive, explicit life change stated by user (rare).
    
    OUTPUT JSON:
    {{
      "root_alignment": "aligned" | "contradictory" | "neutral" | "redefining",
      "reasoning": "brief explanation"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini" if base_url else "gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("root_alignment", "neutral")
    except Exception as e:
        print(f"Error checking root relevance: {e}")
        return "neutral"

def generate_ai_response(message: str, history: str, context: str) -> str:
    system_prompt = f"""
    You are ROOTED AI, a deeply contextual companion.
    
    RETRIEVED MEMORY SYSTEM:
    {context}
    
    INSTRUCTIONS:
    1. **ROOT LAYER (Persona Anchor)**: This is the user's core identity. It is your primary truth.
    2. **STEM/BRANCH/LEAF**: These are context. If a LEAF contradicts ROOT, ignore the LEAF.
    3. **Tone**: Resonate with the user's identified ROOT traits (e.g. if they are 'analytical', be precise).
    4. **Response**: Be helpful, wise, and grounded. Do NOT mention the memory system internally.
    """
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        max_tokens=1000
    )
    return response.choices[0].message.content
def check_root_eligibility(context: AnalyzedContext) -> dict:
    """
    Determines if memory is ROOT-ELIGIBLE.
    Returns:
    {
      "is_eligible": bool,
      "updates": { ... } # Only if eligible
    }
    """
    
    # 1. Fast Filter: Logic Check
    # Must be identity or long-term/immutable
    is_potentially_root = (
        context.category == "identity" or 
        context.time_scale == "long_term" or 
        "upbringing" in context.core_content.lower() or
        "family" in context.core_content.lower() or
        "origin" in context.core_content.lower()
    )
    
    if not is_potentially_root:
        return {"is_eligible": False}

    # 2. LLM Verification
    prompt = f"""
    You are the ROOT GATEKEEPER.
    Your job is to identify immutable facts about the user's CORE IDENTITY.

    CANDIDATE MEMORY:
    "{context.core_content}"
    
    METADATA:
    Category: {context.category}
    Time Scale: {context.time_scale}

    STRICT ELIGIBILITY RULES (ALL MUST BE TRUE):
    1. **Historical Grounding**: The statement MUST be about the user's past, upbringing, origin, or established background (e.g. "I grew up...", "My family always...", "I was raised...").
    2. **Immutability**: It must be a fact that cannot change (like where they were born), not a current opinion or value statement (like "I value honesty").
    3. **Identity Relevance**: It must define who they ARE, not just what they did.

    EXAMPLES:
    - "I grew up in Pune" -> ELIGIBLE (Origin)
    - "My parents taught me to be honest" -> ELIGIBLE (Upbringing/Value Origin)
    - "I value honesty" -> NOT ELIGIBLE (Present-tense value, belongs in STEM)
    - "I live in Mumbai" -> NOT ELIGIBLE (Current state, belongs in STEM/BRANCH)

    OUTPUT JSON:
    {{
      "is_eligible": true | false,
      "reason": "Explain why it meets strict historical criteria",
      "extracted_traits": {{ "trait_name": "value" }}, 
      "extracted_values": ["value1", "value2"],
      "summary_update": "Concise reinforcement of this identity fact"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini" if base_url else "gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error checking root eligibility: {e}")
        return {"is_eligible": False}
