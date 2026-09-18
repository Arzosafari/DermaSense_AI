# backend/app/api/v1/auth.py - MySQL Database Version
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
from app.core.database_service import database_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================
# Models
# ============================================================

class UserProfile(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    skin_type: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    profile: Optional[UserProfile] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    profile: UserProfile


class SessionInfo(BaseModel):
    session_id: str
    title: str
    last_message: str
    date: str


# ============================================================
# Helper Functions
# ============================================================

async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """
    Dependency: Extract user from token (optional - returns None if not authenticated)
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    username = database_service.validate_token(token)
    
    if not username:
        return None
    
    user_data = database_service.get_user_by_username(username)
    if user_data:
        user_data["username"] = username
        return user_data
    return None


async def require_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency: Require authentication (raises 401 if not authenticated)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = authorization.replace("Bearer ", "")
    username = database_service.validate_token(token)
    
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_data = database_service.get_user_by_username(username)
    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")
    
    user_data["username"] = username
    return user_data


# ============================================================
# Routes
# ============================================================

@router.post("/register")
async def register(data: RegisterRequest):
    """Register a new user"""
    # Validate username
    if not data.username or len(data.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    
    if not data.password or len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    
    # Create user
    try:
        profile_dict = data.profile.dict() if data.profile else {}
        user_data = database_service.create_user(
            username=data.username,
            password=data.password,
            profile=profile_dict
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=400, detail="Username already exists")
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create session token
    token = database_service.create_session_token(data.username)
    
    return {
        "token": token,
        "username": data.username,
        "profile": profile_dict,
        "message": "Registration successful"
    }


@router.post("/login")
async def login(data: LoginRequest):
    """Login with username and password"""
    user_data = database_service.verify_user_credentials(data.username, data.password)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session token
    token = database_service.create_session_token(data.username)
    
    # Get user profile
    profile = database_service.get_user_profile(data.username) or {}
    
    # Get user sessions
    sessions = database_service.get_user_sessions(data.username)
    
    return {
        "token": token,
        "username": data.username,
        "profile": profile,
        "sessions": sessions,
        "message": "Login successful"
    }


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """Logout - delete token"""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        database_service.delete_token(token)
    
    return {"message": "Logged out successfully"}


@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)):
    """Get current user's profile"""
    profile = database_service.get_user_profile(user["username"])
    sessions = database_service.get_user_sessions(user["username"])
    
    return {
        "username": user["username"],
        "profile": profile or {},
        "sessions": sessions
    }


@router.put("/profile")
async def update_profile(data: UpdateProfileRequest, user: dict = Depends(require_user)):
    """Update user profile"""
    profile_dict = data.profile.dict()
    updated_profile = database_service.update_user_profile(user["username"], profile_dict)
    
    return {
        "message": "Profile updated successfully",
        "profile": updated_profile
    }


@router.get("/check")
async def check_auth(user: Optional[dict] = Depends(get_current_user)):
    """Check if user is authenticated (returns null if not)"""
    if not user:
        return {
            "authenticated": False,
            "user": None,
            "profile": None
        }
    
    profile = database_service.get_user_profile(user["username"]) or {}
    
    return {
        "authenticated": True,
        "user": {
            "username": user["username"],
        },
        "profile": profile
    }


@router.post("/sessions/save")
async def save_session(
    session: SessionInfo,
    user: dict = Depends(require_user)
):
    """Save a chat session for the user"""
    session_dict = session.dict()
    database_service.save_user_session(user["username"], session_dict)
    
    # Get updated sessions list
    sessions = database_service.get_user_sessions(user["username"])
    
    return {"message": "Session saved", "sessions_count": len(sessions)}


@router.get("/sessions")
async def get_sessions(user: dict = Depends(require_user)):
    """Get all sessions for the user"""
    sessions = database_service.get_user_sessions(user["username"])
    
    return {
        "sessions": sessions
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(require_user)
):
    """Delete a session"""
    success = database_service.delete_user_session(user["username"], session_id)
    
    if success:
        return {"message": "Session deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")
