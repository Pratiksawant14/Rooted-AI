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

app = FastAPI(title="ROOTED AI - Backend")
supabase = get_supabase_client()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
         raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    try:
        token = authorization.replace("Bearer ", "")
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
             raise HTTPException(status_code=401, detail="Invalid User Token")
        return user_response.user
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Authentication")

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
        context_str = f"""
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
