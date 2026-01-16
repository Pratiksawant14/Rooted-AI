from fastapi import Header, HTTPException, Depends
from core.database import get_supabase_client
from typing import Any

supabase = get_supabase_client()

async def get_current_user(authorization: str = Header(None)) -> Any:
    """
    Verifies the Supabase JWT from the Authorization header.
    Returns the user object if valid, raises 401 otherwise.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    try:
        if not authorization.startswith("Bearer "):
             raise HTTPException(status_code=401, detail="Invalid Authorization Header Format")
             
        token = authorization.replace("Bearer ", "")
        
        # Verify token using Supabase Auth
        user_response = supabase.auth.get_user(token)
        
        if not user_response.user:
             raise HTTPException(status_code=401, detail="Invalid or Expired Token")
             
        return user_response.user
        
    except Exception as e:
        print(f"Auth Verification Failed: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
