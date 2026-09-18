# backend/app/memory/long_term_file_memory.py - MySQL Database Version
import json
import os
from typing import List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LongTermFileMemory:
    def __init__(self, base_dir="memory_store"):
        # 🆕 مسیر مطلق بر اساس محل این فایل
        # این فایل در backend/app/memory/ هست، پس دوتا می‌ریم بالا تا به backend برسیم
        current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/app/memory
        app_dir = os.path.dirname(current_dir)  # backend/app
        backend_dir = os.path.dirname(app_dir)  # backend
        
        self.base_dir = os.path.join(backend_dir, base_dir)
        logger.info(f"LongTermFileMemory base_dir: {self.base_dir}")
        os.makedirs(self.base_dir, exist_ok=True)

    def _filepath(self, session_id):
        return os.path.join(self.base_dir, f"{session_id}.json")

    async def save(self, session_id, user_message, agent_output, image_data=None, analysis_data=None):
        # Save to database (primary storage)
        try:
            from app.core.database_service import database_service
            database_service.save_chat_memory(
                session_id=session_id,
                user_message=user_message,
                agent_output=agent_output,
                image_data=image_data,
                analysis_data=analysis_data
            )
            logger.info(f"✅ Saved to database for session {session_id}")
        except Exception as db_error:
            logger.error(f"❌ Failed to save to database: {db_error}")
        
        # Also save to file for compatibility and backup
        filepath = self._filepath(session_id)
        logger.info(f"💾 Saving to file: {filepath}")

        # Load existing memory
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []

        # Append new entry with optional image and analysis data
        entry = {
            "user_message": user_message,
            "agent_output": agent_output,
            "timestamp": datetime.now().isoformat()
        }
        
        if image_data:
            entry["image_data"] = image_data
            logger.info(f"💾 Saving image data for session {session_id}")
            
        if analysis_data:
            entry["analysis_data"] = analysis_data
            logger.info(f"💾 Saving analysis data for session {session_id}")
        
        data.append(entry)

        # Save back to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved {len(data)} items to {filepath}")

    async def get(self, session_id) -> List[dict]:
        # Try to load from database first
        try:
            from app.core.database_service import database_service
            db_memory = database_service.get_chat_memory(session_id)
            if db_memory:
                logger.info(f"📜 Loaded {len(db_memory)} items from database for session {session_id}")
                return db_memory
        except Exception as db_error:
            logger.error(f"❌ Failed to load from database: {db_error}")
        
        # Fallback to file storage
        filepath = self._filepath(session_id)
        logger.info(f"📜 Reading from file: {filepath}")
        logger.info(f"📜 File exists: {os.path.exists(filepath)}")

        if not os.path.exists(filepath):
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"📜 Read {len(data)} items from {filepath}")
            return data

    async def clear(self, session_id):
        # Clear from database
        try:
            from app.core.database_service import database_service
            database_service.clear_chat_memory(session_id)
            logger.info(f"🗑️ Cleared from database for session {session_id}")
        except Exception as db_error:
            logger.error(f"❌ Failed to clear from database: {db_error}")
        
        # Also clear file
        filepath = self._filepath(session_id)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"🗑️ Deleted: {filepath}")
