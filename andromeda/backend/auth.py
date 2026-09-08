import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Query, status
from pydantic import BaseModel, Field

from .db import (
    create_user,
    authenticate_user,
    create_user_token,
    get_user_by_token,
    revoke_user_token,
    get_user_preferences,
    set_user_preference
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: Optional[str] = None
    preferred_model: Optional[str] = "llama3.2:latest"

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class PreferenceUpdateRequest(BaseModel):
    key: str
    value: str

def extract_token(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> Optional[str]:
    """Extracts bearer token from Authorization header or query param."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if token:
        return token.strip()
    return None

def get_current_user_optional(token: Optional[str] = Depends(extract_token)) -> Optional[dict]:
    """Returns user dict if valid token, or None."""
    if not token:
        return None
    user = get_user_by_token(token)
    return user

def get_current_user(token: Optional[str] = Depends(extract_token)) -> dict:
    """Requires authentication, raising 401 if missing or invalid."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.post("/signup")
async def signup(payload: SignupRequest):
    # Username format validation
    if not re.match(r"^[a-zA-Z0-9_-]+$", payload.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username may only contain letters, numbers, hyphens, and underscores."
        )

    # Email format validation
    if "@" not in payload.email or "." not in payload.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    try:
        user = create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            preferred_model=payload.preferred_model or "llama3.2:latest"
        )
    except Exception as e:
        err_msg = str(e)
        if "UNIQUE constraint failed" in err_msg:
            if "users.username" in err_msg:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken.")
            if "users.email" in err_msg:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")

    token = create_user_token(user["id"])
    return {
        "status": "ok",
        "message": "Account created successfully.",
        "token": token,
        "user": user
    }

@router.post("/login")
async def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password."
        )

    token = create_user_token(user["id"])
    prefs = get_user_preferences(user["id"])
    return {
        "status": "ok",
        "message": "Authentication successful.",
        "token": token,
        "user": {**user, "preferences": prefs}
    }

@router.post("/guest")
async def guest_login():
    """Generates a guest session token for quick evaluation and demos."""
    token = create_user_token("guest", days_valid=7)
    user = get_user_by_token(token)
    return {
        "status": "ok",
        "message": "Signed in as Guest Explorer.",
        "token": token,
        "user": user
    }

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    prefs = get_user_preferences(user["id"])
    return {
        "status": "ok",
        "user": {**user, "preferences": prefs}
    }

@router.post("/logout")
async def logout(token: Optional[str] = Depends(extract_token)):
    if token:
        revoke_user_token(token)
    return {"status": "ok", "message": "Successfully signed out."}

@router.put("/preferences")
async def update_preference(payload: PreferenceUpdateRequest, user: dict = Depends(get_current_user)):
    set_user_preference(user["id"], payload.key, payload.value)
    return {"status": "ok", "updated": {payload.key: payload.value}}
