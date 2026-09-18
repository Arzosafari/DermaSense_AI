# backend/app/api/v1/auth.py - MySQL Database Version
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
import json
import os
import hashlib
import secrets
from datetime import datetime
import logging

from app.core.database_service import database_service
from app.core.database import is_database_initialized, init_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

USERS_FILE = "app/data/users.json"
TOKENS_FILE = "app/data/tokens.json"

# Force database initialization on module load
try:
    init_database()
    logger.info("Database initialized successfully in auth module")
except Exception as e:
    logger.warning(f"Database initialization failed in auth module: {e}")

USE_DATABASE = is_database_initialized()

# ============================================================
# Fallback File Storage Functions
# ============================================================

def _load_json(filepath: str) -> dict:
    """Load JSON file"""
    os.makedirs("app/data", exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({}, f)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_json(filepath: str, data: dict):
    """Save JSON file"""
    os.makedirs("app/data", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _load_users() -> dict:
    return _load_json(USERS_FILE)

def _save_users(users: dict):
    _save_json(USERS_FILE, users)

def _load_tokens() -> dict:
    return _load_json(TOKENS_FILE)

def _save_tokens(tokens: dict):
    _save_json(TOKENS_FILE, tokens)

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _generate_token() -> str:
    return secrets.token_hex(32)

def _create_session_token(username: str) -> str:
    tokens = _load_tokens()
    tokens = {k: v for k, v in tokens.items() if v != username}
    token = _generate_token()
    tokens[token] = username
    _save_tokens(tokens)
    return token

def _validate_token(token: str) -> Optional[str]:
    tokens = _load_tokens()
    return tokens.get(token)

def _delete_token(token: str):
    tokens = _load_tokens()
    if token in tokens:
        del tokens[token]
        _save_tokens(tokens)


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
    
    if USE_DATABASE:
        username = database_service.validate_token(token)
        if not username:
            return None
        user_data = database_service.get_user_by_username(username)
        if user_data:
            user_data["username"] = username
            return user_data
    else:
        username = _validate_token(token)
        if not username:
            return None
        users = _load_users()
        if username in users:
            user_data = users[username].copy()
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
    
    if USE_DATABASE:
        username = database_service.validate_token(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        user_data = database_service.get_user_by_username(username)
        if not user_data:
            raise HTTPException(status_code=401, detail="User not found")
        user_data["username"] = username
    else:
        username = _validate_token(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        users = _load_users()
        if username not in users:
            raise HTTPException(status_code=401, detail="User not found")
        user_data = users[username].copy()
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
    
    profile_dict = data.profile.dict() if data.profile else {}
    
    if USE_DATABASE:
        # Create user in database
        try:
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
    else:
        # Create user in file storage
        users = _load_users()
        if data.username in users:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        users[data.username] = {
            "password_hash": _hash_password(data.password),
            "profile": profile_dict,
            "created_at": datetime.utcnow().isoformat(),
            "sessions": []
        }
        _save_users(users)
        
        # Create session token
        token = _create_session_token(data.username)
    
    return {
        "token": token,
        "username": data.username,
        "profile": profile_dict,
        "message": "Registration successful"
    }


@router.post("/login")
async def login(data: LoginRequest):
    """Login with username and password"""
    if USE_DATABASE:
        user_data = database_service.verify_user_credentials(data.username, data.password)
        if not user_data:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create session token
        token = database_service.create_session_token(data.username)
        
        # Get user profile
        profile = database_service.get_user_profile(data.username) or {}
        
        # Get user sessions
        sessions = database_service.get_user_sessions(data.username)
    else:
        # File-based login
        users = _load_users()
        if data.username not in users:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user = users[data.username]
        if user["password_hash"] != _hash_password(data.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create session token
        token = _create_session_token(data.username)
        
        profile = user.get("profile", {})
        sessions = user.get("sessions", [])
    
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
        if USE_DATABASE:
            database_service.delete_token(token)
        else:
            _delete_token(token)
    
    return {"message": "Logged out successfully"}


@router.get("/profile")
async def get_profile(user: dict = Depends(require_user)):
    """Get current user's profile"""
    if USE_DATABASE:
        profile = database_service.get_user_profile(user["username"])
        sessions = database_service.get_user_sessions(user["username"])
    else:
        users = _load_users()
        user_data = users.get(user["username"], {})
        profile = user_data.get("profile", {})
        sessions = user_data.get("sessions", [])
    
    return {
        "username": user["username"],
        "profile": profile or {},
        "sessions": sessions
    }


@router.put("/profile")
async def update_profile(data: UpdateProfileRequest, user: dict = Depends(require_user)):
    """Update user profile"""
    profile_dict = data.profile.dict()
    
    if USE_DATABASE:
        updated_profile = database_service.update_user_profile(user["username"], profile_dict)
    else:
        users = _load_users()
        if user["username"] not in users:
            raise HTTPException(status_code=404, detail="User not found")
        
        users[user["username"]]["profile"] = profile_dict
        _save_users(users)
        updated_profile = profile_dict
    
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
    
    if USE_DATABASE:
        profile = database_service.get_user_profile(user["username"]) or {}
    else:
        users = _load_users()
        user_data = users.get(user["username"], {})
        profile = user_data.get("profile", {})
    
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
    
    if USE_DATABASE:
        database_service.save_user_session(user["username"], session_dict)
        sessions = database_service.get_user_sessions(user["username"])
    else:
        users = _load_users()
        if user["username"] not in users:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_sessions = users[user["username"]].get("sessions", [])
        
        # Update or add session
        existing_idx = None
        for i, s in enumerate(user_sessions):
            if s.get("session_id") == session.session_id:
                existing_idx = i
                break
        
        if existing_idx is not None:
            user_sessions[existing_idx] = session_dict
        else:
            user_sessions.insert(0, session_dict)
        
        # Limit to 50 sessions
        if len(user_sessions) > 50:
            user_sessions = user_sessions[:50]
        
        users[user["username"]]["sessions"] = user_sessions
        _save_users(users)
        sessions = user_sessions
    
    return {"message": "Session saved", "sessions_count": len(sessions)}


@router.get("/sessions")
async def get_sessions(user: dict = Depends(require_user)):
    """Get all sessions for the user"""
    if USE_DATABASE:
        sessions = database_service.get_user_sessions(user["username"])
    else:
        users = _load_users()
        user_data = users.get(user["username"], {})
        sessions = user_data.get("sessions", [])
    
    return {
        "sessions": sessions
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(require_user)
):
    """Delete a session"""
    if USE_DATABASE:
        success = database_service.delete_user_session(user["username"], session_id)
    else:
        users = _load_users()
        if user["username"] not in users:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_sessions = users[user["username"]].get("sessions", [])
        users[user["username"]]["sessions"] = [
            s for s in user_sessions if s.get("session_id") != session_id
        ]
        _save_users(users)
        success = True
    
    if success:
        return {"message": "Session deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")
