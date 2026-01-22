import json
from openai import OpenAI
from core.config import get_settings
from schemas import MemoryCandidate, AnalysisResult

settings = get_settings()

# Check for OpenRouter Key
if settings.OPENAI_API_KEY.startswith("sk-or-v1"):
    base_url = "https://openrouter.ai/api/v1"
    model_name = "openai/gpt-4o-mini"
else:
    base_url = None # Default to OpenAI
    model_name = "gpt-4o-mini"

client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=base_url)

SYSTEM_PROMPT_EXTRACT = """
You are the Cognitive Extraction Engine for ROOTED AI.
Analyze the user's message and extract a LIST of potential memory candidates and the general CONVERSATION CONTEXT.

OUTPUT FORMAT (JSON):
{
  "domains": ["education", "health", "fitness", "general", etc.],
  "candidates": [
    {
      "category": "identity" | "habit" | "emotion" | "event" | "belief",
      "time_scale": "one_time" | "repeated" | "long_term",
      "importance": "low" | "medium" | "high",
      "core_content": "Concise, standalone fact (3rd person perspective)",
      "confidence": 0.0 to 1.0,
      "domain": "specific domain for this fact (e.g. fitness)"
    }
  ]
}

RULES:
1.  **Split Contexts**: If a user says "I ran today and I love running", split into two candidates:
    - Event: "User ran today" (domain: fitness)
    - Identity/Habit: "User loves running" (domain: fitness)
2.  **Ignore Noise**: Do NOT extract candidates for greetings, thanks, or simple acknowledgments. Return empty list of candidates if no substance.
3.  **Third Person**: Convert "I am..." to "User is...".
4.  **Domains**: Identify the broad topics of the message for retrieval context.

DEFINITIONS:
- identity: Core beliefs, personality traits, long-term goals.
- habit: Recurring actions or routines.
- emotion: Temporary feelings or states.
- event: Specific occurrences with a timestamp.
- belief: Opinions, values, or mental models.
"""

def extract_memory_candidates(message: str) -> AnalysisResult:
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini" if base_url else "gpt-4o-mini",  
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACT},
                {"role": "user", "content": message}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=600
        )
        
        data = json.loads(response.choices[0].message.content)
        # Ensure we handle empty or malformed lists safely
        candidates = data.get("candidates", [])
        domains = data.get("domains", ["general"])
        return AnalysisResult(
            candidates=[MemoryCandidate(**c) for c in candidates],
            domains=domains
        )
    except Exception as e:
        print(f"Error in extract_memory_candidates: {e}")
        return AnalysisResult(candidates=[], domains=["general"])

def check_storage_eligibility(candidate: MemoryCandidate) -> bool:
    """
    Gate 3: Memory Worthiness
    Filters out questions, meta-talk, and non-useful info.
    """
    # Simple heuristic checks first
    content = candidate.core_content.lower()
    
    # Check for meta-conversational markers (questions about self, system)
    if "?" in candidate.core_content and ("who are you" in content or "what is" in content):
        return False
        
    # Check for low importance events that aren't habits
    if candidate.importance == "low" and candidate.category == "event":
        return False
        
    return True


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
def check_root_eligibility(candidate: MemoryCandidate) -> dict:
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
        candidate.category == "identity" or 
        candidate.time_scale == "long_term" or 
        "upbringing" in candidate.core_content.lower() or
        "family" in candidate.core_content.lower() or
        "origin" in candidate.core_content.lower()
    )
    
    if not is_potentially_root:
        return {"is_eligible": False}

    # 2. LLM Verification
    prompt = f"""
    You are the ROOT GATEKEEPER.
    Your job is to identify immutable facts about the user's CORE IDENTITY.

    CANDIDATE MEMORY:
    "{candidate.core_content}"
    
    METADATA:
    Category: {candidate.category}
    Time Scale: {candidate.time_scale}

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
