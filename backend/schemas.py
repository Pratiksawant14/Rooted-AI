from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str

class MemoryCandidate(BaseModel):
    category: str  # identity | habit | emotion | event
    time_scale: str  # one_time | repeated | long_term
    importance: str  # low | medium | high
    core_content: str
    confidence: float
    domain: str = "general" # Primary domain of this specific fact

class AnalysisResult(BaseModel):
    candidates: List[MemoryCandidate]
    domains: List[str] # Context of the current conversation

class ChatResponse(BaseModel):
    response: str
    memory_used: Dict[str, Any] # root (dict), stem, branch, leaf (lists)
