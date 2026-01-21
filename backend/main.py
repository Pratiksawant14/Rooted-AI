import os
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env before imports that might need it
load_dotenv()

from schemas import ChatRequest, ChatResponse
from services.llm_service import analyze_message, generate_ai_response
from services.memory_service import store_memory, retrieve_relevant_memory, decay_memories
from core.database import get_supabase_client
from core.config import get_settings
from core.security import get_current_user

app = FastAPI(title="ROOTED AI - Backend")
supabase = get_supabase_client()
settings = get_settings()

# --- MANUAL CORS OVERRIDE START ---
from fastapi import Request, Response

@app.middleware("http")
async def cors_handler(request: Request, call_next):
    # Handle preflight OPTIONS requests directly
    if request.method == "OPTIONS":
        response = Response()
    else:
        try:
            response = await call_next(request)
        except Exception as e:
            # If app crashes, still send CORS headers so we can see the 500 in browser
            print(f"Request Error: {e}")
            response = Response(status_code=500, content="Internal Server Error")

    # Force CORS Headers on ALL responses
    origin = request.headers.get("origin")
    response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, x-requested-with"
    
    return response
# --- MANUAL CORS OVERRIDE END ---

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

        # 1. Analyze Context
        analyzed_ctx = analyze_message(request.message)
        
        # 2. Store Memory (returns None if noise)
        stored_node = store_memory(user_id, analyzed_ctx, auth_client)
        
        # 3. Retrieve Tree-Structured Memory
        memory_map = retrieve_relevant_memory(user_id, request.message, analyzed_ctx.domains, auth_client)
        
        # Format context for LLM
        # Format context for LLM
        context_str = f"""
        ROOT (Core Persona): {memory_map.get('root', {}).get('persona_summary', 'Not established')}
        STEM (Core Identity): {memory_map['stem']}
        BRANCH (Habits/Patterns): {memory_map['branch']}
        LEAF (Recent Events): {memory_map['leaf']}
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
