import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env before imports that might need it
load_dotenv()

from schemas import ChatRequest, ChatResponse
from services.llm_service import extract_memory_candidates, generate_ai_response
from services.memory_service import process_memory_candidates, retrieve_relevant_memory, decay_memories
from core.database import get_supabase_client
from core.config import get_settings
from core.security import get_current_user

app = FastAPI(title="ROOTED AI - Backend")
supabase = get_supabase_client()
settings = get_settings()

# CORS Configuration
# Explicitly list known origins to avoid regex pitfalls
explicit_origins = [
    "http://localhost:3000",
    "http://localhost:8000", 
    "http://localhost:5173",
    "https://rooted-ai.vercel.app",
    "https://rooted-ai-tau.vercel.app",
]

# Add middleware with BOTH explicit list and regex for Vercel previews
app.add_middleware(
    CORSMiddleware,
    allow_origins=explicit_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# User authentication handled by core.security.get_current_user

@app.get("/")
def health_check():
    return {"status": "ok", "system": "Rooted AI MVP"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, authorization: str = Header(None), user=Depends(get_current_user)):
    try:
        user_id = user.id
        token = authorization.replace("Bearer ", "")
        
        # Create an authenticated Supabase client for this request
        # We can re-use the global 'supabase' client but we need to set the session, 
        # but supabase-py client is stateful. It's safer to create a new client or use the headers.
        # Actually, best practice with standard supabase-py is:
        # client = create_client(url, key)
        # client.postgrest.auth(token)
        
        auth_client = get_supabase_client()
        auth_client.postgrest.auth(token)
        
        # Lifecycle: Decay old memories first
        decay_memories(user_id, auth_client)

        # 1. Analyze Context & Extract Candidates
        analysis_result = extract_memory_candidates(request.message)
        
        # 2. Process Candidates (Root Gate, Storage Gate, Priority, Store)
        process_memory_candidates(user_id, analysis_result.candidates, auth_client)
        
        # 3. Retrieve Tree-Structured Memory
        memory_map = await retrieve_relevant_memory(user_id, request.message, analysis_result.domains, auth_client)
        
        # Format context for LLM
        # Format context for LLM
        # Format context for LLM with explicit ROOT injection
        root_data = memory_map.get('root', {})
        
        context_str = f"""
        ========== RETRIEVED MEMORY CONTEXT ==========
        
        [ROOT LAYER - CORE PERSONA (Highest Authority)]
        Summary: {root_data.get('persona_summary', 'Not established')}
        Traits & Facts: {root_data.get('traits', {})}
        Core Values: {root_data.get('values', [])}
        
        [STEM LAYER - IDENTITY & ROLES]
        {memory_map['stem']}
        
        [BRANCH LAYER - HABITS & PATTERNS]
        {memory_map['branch']}
        
        [LEAF LAYER - RECENT DISCOVERY]
        {memory_map['leaf']}
        ==============================================
        """
        
        # 4. Generate Response
        ai_response = generate_ai_response(request.message, "", context_str)
        
        return ChatResponse(
            response=ai_response,
            memory_used=memory_map
        )
        
    except Exception as e:
        print(f"Error processing chat: {e}")
        # Return a valid error response structure if possible, or raise HTTP exc
        raise HTTPException(status_code=500, detail=str(e))
