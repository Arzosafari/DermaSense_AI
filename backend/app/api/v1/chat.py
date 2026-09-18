# backend/app/api/v1/chat.py
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import logging
import traceback
import asyncio
import json
import os
import base64
import io
import time
from PIL import Image

from app.core.agent_orchestrator import AgentOrchestrator
from app.core.agent_context import AgentContext
from app.core.medical_context_service import medical_context_service
from app.core.database_service import database_service
from app.core.analysis_history_service import AnalysisHistoryService

logger = logging.getLogger(__name__)

# DEBUG LOG TO VERIFY CHANGES
print("=== CHAT.PY LOADED WITH CHAT HISTORY FIX ===")

router = APIRouter(prefix="/chat", tags=["Chat"])

# Initialize analysis history service
analysis_history_service = AnalysisHistoryService()

# DEBUG: Log when module is loaded
logger.info("🚨🚨🚨 CHAT.PY MODULE LOADED - CHAT HISTORY FIX 🚨🚨🚨")


def compress_base64_image(base64_str: str, max_size_kb: int = 500) -> str:
    """Compress base64 image to reduce payload size for API calls."""
    try:
        if not base64_str or "base64," not in base64_str:
            return base64_str
        
        # Extract base64 data
        base64_data = base64_str.split("base64,")[1]
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        
        # Resize if too large
        max_dimensions = (1024, 1024)
        if image.size[0] > max_dimensions[0] or image.size[1] > max_dimensions[1]:
            image.thumbnail(max_dimensions, Image.Resampling.LANCZOS)
            logger.info(f"🔄 Image resized to {image.size}")
        
        # Compress with quality adjustment
        output = io.BytesIO()
        quality = 85
        while quality > 50:
            output.seek(0)
            output.truncate()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            compressed_size = len(output.getvalue()) / 1024  # KB
            
            if compressed_size <= max_size_kb:
                logger.info(f"✅ Image compressed to {compressed_size:.1f}KB (quality={quality})")
                break
            quality -= 5
        else:
            logger.warning(f"⚠️ Could not compress below {max_size_kb}KB, final size: {compressed_size:.1f}KB")
        
        # Encode back to base64
        compressed_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{compressed_base64}"
        
    except Exception as e:
        logger.error(f"❌ Failed to compress image: {e}")
        return base64_str  # Return original if compression fails


# ============================================================
# Models
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    image: Optional[str] = None


class SessionRequest(BaseModel):
    session_id: str


# ============================================================
# Auth helpers (inline)
# ============================================================

def _load_users() -> dict:
    """Load users from database (for compatibility with existing code)."""
    # This function is kept for compatibility but now uses database
    return {}

def _load_tokens() -> dict:
    """Load tokens from database (for compatibility with existing code)."""
    # This function is kept for compatibility but now uses database
    return {}


def _load_patient_profile(user_id: str) -> dict:
    """Load patient medical profile from database."""
    try:
        profile = database_service.get_user_profile(user_id)
        return profile if profile else {}
    except Exception as e:
        logger.error(f"Failed to load patient profile: {e}")
    return {}


async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
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


# ============================================================
# Routes
# ============================================================

@router.post("/send")
async def send_message(
    data: ChatRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """Send message and get complete response"""
    
    import time
    request_start = time.time()
    
    print("=== NEW CHAT REQUEST - CHAT HISTORY FIX ===")
    logger.info("🔥🔥🔥 NEW CHAT REQUEST - CHAT HISTORY FIX 🔥🔥🔥")
    logger.info(f"⏱️ Request started at {request_start}")

    if not data.message.strip() and not data.image:
        raise HTTPException(status_code=400, detail="Message or Image cannot be empty")

    try:
        # Simplified profile loading - prioritize auth profile for now
        merged_profile = {}
        if user:
            users_json = _load_users()
            user_data = users_json.get(user["username"], {})
            merged_profile = user_data.get("profile", {}).copy()
            merged_profile["username"] = user["username"]
            logger.info(f"Loaded auth profile for user {user['username']}: {list(merged_profile.keys())}")
            logger.info(f"Auth profile content: {merged_profile}")

            # Try to load patient profile if exists
            patient_profile = _load_patient_profile(user["username"])
            if patient_profile:
                merged_profile.update(patient_profile)
                logger.info(f"Also loaded patient profile: {list(patient_profile.keys())}")
                logger.info(f"Patient profile content: {patient_profile}")

        # Extract relevant medical context using the service
        medical_context = medical_context_service.extract_relevant_context(
            merged_profile, 
            current_query=data.message
        )

        # Add medical context to profile for agents
        merged_profile["medical_context"] = medical_context

        logger.info(f"Final merged profile keys: {list(merged_profile.keys())}")
        logger.info(f"Medical context has_context: {medical_context.get('has_context')}")
        logger.info(f"Medical context summary: {medical_context.get('context_summary', 'None')}")

        # Compress image to reduce payload size
        compressed_image = None
        if data.image:
            original_size = len(data.image) / 1024  # KB
            compressed_image = compress_base64_image(data.image, max_size_kb=500)
            compressed_size = len(compressed_image) / 1024  # KB
            logger.info(f"📊 Image compression: {original_size:.1f}KB → {compressed_size:.1f}KB")

        # استفاده از session_id که فرانت‌اند فرستاده
        context = AgentContext(
            session_id=data.session_id,
            user_profile=merged_profile
        )

        session_id = context.session_id

        # Load chat history for context
        print(f"📜 Loading chat history for session {session_id}")
        logger.info(f"📜 Loading chat history for session {session_id}")
        history_start = time.time()
        await context.load_chat_history()
        history_time = time.time() - history_start
        print(f"📜 Chat history loaded: {len(context.chat_history)} messages (took {history_time:.2f}s)")
        logger.info(f"📜 Chat history loaded: {len(context.chat_history)} messages (took {history_time:.2f}s)")
        print(f"📜 Chat history sample: {context.chat_history[:2] if context.chat_history else 'Empty'}")
        logger.info(f"📜 Chat history sample: {context.chat_history[:2] if context.chat_history else 'Empty'}")

        orchestrator = AgentOrchestrator(context)

        print(f"🚀 Calling orchestrator with chat_history: {len(context.chat_history)} messages")
        logger.info(f"🚀 Calling orchestrator with chat_history: {len(context.chat_history)} messages")
        orchestrator_start = time.time()
        result = await orchestrator.run(
            user_message=data.message,
            image_base64=compressed_image,
            capture_trace=True,
            user_profile=merged_profile,
            chat_history=context.chat_history
        )
        orchestrator_time = time.time() - orchestrator_start
        print(f"✅ Orchestrator completed (took {orchestrator_time:.2f}s)")
        logger.info(f"✅ Orchestrator completed (took {orchestrator_time:.2f}s)")

        final_reply = result.get("final_output", "No response generated.") if isinstance(result, dict) else str(result)
        
        # Check if this is an LLM error fallback but orchestrator succeeded
        is_llm_error = False
        if isinstance(result, dict) and result.get("error"):
            logger.warning(f"Orchestrator completed with error flag: {result.get('error')}")
            # If analysis data is available despite the error, include it in response
            if "analysis" in result and result["analysis"]:
                logger.info(f"Analysis data available despite LLM error, returning partial success")
                is_llm_error = True
                # Don't mark as error in response since analysis succeeded

        # Save message to memory store (both database and file for compatibility)
        try:
            analysis_to_save = result.get("analysis") if isinstance(result, dict) else None
            print(f"💾 Saving to memory - analysis_data: {bool(analysis_to_save)}")
            if analysis_to_save:
                print(f"💾 Analysis keys: {list(analysis_to_save.keys())}")
            
            save_start = time.time()
            
            # Save to database
            try:
                database_service.save_chat_memory(
                    session_id=session_id,
                    user_message=data.message,
                    agent_output=final_reply,
                    image_data=data.image,
                    analysis_data=analysis_to_save
                )
                print(f"💾 Saved to database")
            except Exception as db_error:
                logger.error(f"Failed to save to database: {db_error}")
                print(f"❌ Error saving to database: {db_error}")
            
            # Also save to file memory for compatibility
            await context.long_memory.save(
                session_id=session_id,
                user_message=data.message,
                agent_output=final_reply,
                image_data=data.image,
                analysis_data=analysis_to_save
            )
            
            # Save to analysis history if there's an analysis result
            if analysis_to_save and user:
                try:
                    print(f"💾🔥 Attempting to save analysis to history for user {user['username']}")
                    logger.info(f"💾🔥 Attempting to save analysis to history for user {user['username']}")
                    analysis_id = analysis_history_service.save_analysis(
                        user_id=user["username"],
                        analysis_data=analysis_to_save,
                        image_base64=data.image
                    )
                    print(f"💾✅ Saved analysis to history with ID: {analysis_id}")
                    logger.info(f"💾✅ Saved analysis to history with ID: {analysis_id}")
                except Exception as history_error:
                    logger.error(f"Failed to save to analysis history: {history_error}")
                    print(f"❌ Error saving to analysis history: {history_error}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"💾⚠️ Skipping analysis history save - analysis_to_save: {bool(analysis_to_save)}, user: {bool(user)}")
                logger.info(f"💾⚠️ Skipping analysis history save - analysis_to_save: {bool(analysis_to_save)}, user: {bool(user)}")
            
            save_time = time.time() - save_start
            print(f"💾 Memory save completed (took {save_time:.2f}s)")
            logger.info(f"💾 Memory save completed (took {save_time:.2f}s)")
        except Exception as save_error:
            logger.error(f"Failed to save message: {save_error}")
            print(f"❌ Error saving to memory: {save_error}")

        # Return structured analysis if available (for image analysis)
        response_data = {
            "reply": final_reply,
            "session_id": session_id,
            "status": "complete"
        }
        
        # Mark if this was an LLM error fallback but analysis succeeded
        if is_llm_error:
            response_data["llm_error"] = True
            response_data["analysis_succeeded"] = True

        if isinstance(result, dict) and "analysis" in result:
            analysis = result["analysis"]
            # اگر تصویر فیلتر شده، فقط اطلاعات ساده را برگردان
            if analysis.get("filtered"):
                response_data["analysis"] = {
                    "filtered": True,
                    "filter_reason": analysis.get("filter_reason", "Image detected as non-skin related"),
                    "disclaimer": analysis.get("disclaimer")
                }
            else:
                response_data["analysis"] = analysis

        total_time = time.time() - request_start
        print(f"⏱️ Total request time: {total_time:.2f}s")
        logger.info(f"⏱️ Total request time: {total_time:.2f}s")
        
        return response_data

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error in chat endpoint: {error_details}")

        return {
            "reply": "I apologize, but an error occurred. Please try again.",
            "session_id": data.session_id,
            "error": True,
            "status": "error"
        }


@router.post("/history")
async def chat_history(
    data: SessionRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """Get chat history for a session"""
    session_id = data.session_id

    # Load from database
    try:
        history = database_service.get_chat_memory(session_id)
        return {"history": history}
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
        return {"history": []}


@router.post("/clear")
async def clear_chat(
    data: SessionRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """Clear chat history for a session"""
    try:
        # Clear from database
        database_service.clear_chat_memory(data.session_id)
        
        # Also clear with AgentContext for compatibility
        context = AgentContext(session_id=data.session_id)
        await context.long_memory.clear(context.session_id)
        await context.short_memory.clear(context.session_id)

        return {"message": "Session cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear session: {e}")
        return {"message": f"Cleared (error: {str(e)})"}


@router.get("/profile-context")
async def get_profile_context(user: Optional[dict] = Depends(get_current_user)):
    """Get user profile for personalization"""
    if not user:
        return {
            "profile": None,
            "is_logged_in": False,
            "username": None
        }

    # Load profile from database
    profile = database_service.get_user_profile(user["username"]) or {}

    return {
        "profile": profile,
        "is_logged_in": True,
        "username": user["username"]
    }


@router.get("/files/{filename}")
async def get_file(filename: str):
    """Serve generated files (heatmaps, overlays, etc.)"""
    from app.config import settings
    heatmap_dir = getattr(settings, 'HEATMAP_OUTPUT_DIR', 'generated_heatmaps')

    # Construct full path
    file_path = os.path.join(heatmap_dir, filename)

    logger.info(f"File request: {filename}, full path: {file_path}, exists: {os.path.exists(file_path)}")

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)
