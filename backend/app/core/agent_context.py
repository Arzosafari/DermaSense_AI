# backend/app/core/agent_context.py
import uuid
import logging
from app.memory.long_term_file_memory import LongTermFileMemory
from app.memory.memory import ShortTermMemory

logger = logging.getLogger(__name__)


class AgentContext:
    def __init__(self, session_id: str = None, user_profile: dict = None):
        # 🆕 فقط وقتی session_id نداشته باشیم UUID جدید بساز
        self.session_id = session_id if session_id else str(uuid.uuid4())
        self.user_profile = user_profile or {}
        self.debug = False
        self.tools = {}
        
        # Initialize memory systems
        self.short_memory = ShortTermMemory()
        self.long_memory = LongTermFileMemory()
        self.chat_history = []  # Store loaded chat history
        
        logger.debug(
            "AgentContext initialized | session_id=%s | has_profile=%s",
            self.session_id,
            bool(self.user_profile)
        )
    
    async def load_chat_history(self):
        """Load chat history from long memory for context"""
        try:
            history = await self.long_memory.get(self.session_id)
            self.chat_history = history
            logger.info(f"Loaded {len(history)} messages from chat history for session {self.session_id}")
            return history
        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
            self.chat_history = []
            return []