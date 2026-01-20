from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str

class AnalyzedContext(BaseModel):
    domains: List[str]
    category: str  # identity | habit | emotion | event
    time_scale: str  # one_time | repeated | long_term
    importance: str  # low | medium | high
    core_content: str
    confidence: float

class ChatResponse(BaseModel):
    response: str
    memory_used: Dict[str, Any] # root (dict), stem, branch, leaf (lists)
