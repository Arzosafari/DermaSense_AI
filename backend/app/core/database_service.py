"""
Database Service Layer - Provides database operations for SmartHealth.

This service layer abstracts database operations and provides a clean interface
that matches the existing file-based service patterns, allowing minimal code changes.
"""
import logging
import json
import hashlib
import secrets
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import (
    get_db, User, UserProfile, SessionToken, UserSession, 
    ScreeningHistory, ChatMemory, PDFReport
)

logger = logging.getLogger(__name__)

class DatabaseService:
    """Main database service for all persistent data operations."""
    
    def __init__(self):
        self.logger = logger
    
    # ============================================================
    # User Operations
    # ============================================================
    
    def create_user(self, username: str, password: str, profile: Optional[Dict] = None) -> Dict:
        """Create a new user with profile."""
        db = get_db()
        try:
            # Check if user exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                raise ValueError(f"Username '{username}' already exists")
            
            # Hash password
            password_hash = self._hash_password(password)
            
            # Create user
            user = User(
                username=username,
                password_hash=password_hash
            )
            db.add(user)
            db.flush()  # Get the user ID
            
            # Create profile if provided
            if profile:
                user_profile = UserProfile(
                    user_id=user.id,
                    username=username,
                    **profile
                )
                db.add(user_profile)
            
            db.commit()
            
            self.logger.info(f"Created user: {username}")
            return user.to_dict()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to create user {username}: {e}")
            raise
        finally:
            db.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                return user.to_dict()
            return None
        finally:
            db.close()
    
    def verify_user_credentials(self, username: str, password: str) -> Optional[Dict]:
        """Verify user credentials and return user data if valid."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and user.password_hash == self._hash_password(password):
                return user.to_dict()
            return None
        finally:
            db.close()
    
    def update_user_profile(self, username: str, profile_data: Dict) -> Dict:
        """Update user profile."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise ValueError(f"User '{username}' not found")
            
            # Get or create profile
            profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            if not profile:
                profile = UserProfile(user_id=user.id, username=username)
                db.add(profile)
            
            # Update profile fields
            for key, value in profile_data.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            
            profile.updated_at = datetime.utcnow()
            db.commit()
            
            self.logger.info(f"Updated profile for user: {username}")
            return profile.to_dict()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to update profile for {username}: {e}")
            raise
        finally:
            db.close()
    
    def get_user_profile(self, username: str) -> Optional[Dict]:
        """Get user profile."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return None
            
            profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            if profile:
                return profile.to_dict()
            return None
        finally:
            db.close()
    
    # ============================================================
    # Session Token Operations
    # ============================================================
    
    def create_session_token(self, username: str) -> str:
        """Create a session token for user."""
        db = get_db()
        try:
            # Delete existing tokens for this user
            db.query(SessionToken).filter(SessionToken.username == username).delete()
            
            # Create new token
            token = secrets.token_hex(32)
            session_token = SessionToken(token=token, username=username)
            db.add(session_token)
            db.commit()
            
            self.logger.info(f"Created session token for user: {username}")
            return token
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to create session token for {username}: {e}")
            raise
        finally:
            db.close()
    
    def validate_token(self, token: str) -> Optional[str]:
        """Validate token and return username."""
        db = get_db()
        try:
            session_token = db.query(SessionToken).filter(SessionToken.token == token).first()
            if session_token:
                return session_token.username
            return None
        finally:
            db.close()
    
    def delete_token(self, token: str) -> bool:
        """Delete a session token."""
        db = get_db()
        try:
            deleted = db.query(SessionToken).filter(SessionToken.token == token).delete()
            db.commit()
            return deleted > 0
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to delete token: {e}")
            return False
        finally:
            db.close()
    
    # ============================================================
    # User Session Operations (Chat Sessions)
    # ============================================================
    
    def save_user_session(self, username: str, session_data: Dict) -> Dict:
        """Save or update a user session."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise ValueError(f"User '{username}' not found")
            
            session_id = session_data.get('session_id')
            existing_session = db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.session_id == session_id
            ).first()
            
            if existing_session:
                # Update existing session
                for key, value in session_data.items():
                    if hasattr(existing_session, key):
                        setattr(existing_session, key, value)
                existing_session.updated_at = datetime.utcnow()
            else:
                # Create new session
                new_session = UserSession(
                    user_id=user.id,
                    username=username,
                    **session_data
                )
                db.add(new_session)
            
            db.commit()
            self.logger.info(f"Saved session {session_id} for user {username}")
            return session_data
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to save session for {username}: {e}")
            raise
        finally:
            db.close()
    
    def get_user_sessions(self, username: str) -> List[Dict]:
        """Get all sessions for a user."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return []
            
            sessions = db.query(UserSession).filter(
                UserSession.user_id == user.id
            ).order_by(desc(UserSession.updated_at)).all()
            
            return [session.to_dict() for session in sessions]
        finally:
            db.close()
    
    def delete_user_session(self, username: str, session_id: str) -> bool:
        """Delete a user session."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return False
            
            deleted = db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.session_id == session_id
            ).delete()
            
            db.commit()
            return deleted > 0
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            return False
        finally:
            db.close()
    
    # ============================================================
    # Screening History Operations
    # ============================================================
    
    def save_screening_history(self, username: str, analysis_data: Dict) -> str:
        """Save screening analysis to history."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise ValueError(f"User '{username}' not found")
            
            # Create screening history record
            screening = ScreeningHistory.from_dict({
                'user_id': user.id,
                'username': username,
                **analysis_data
            })
            
            db.add(screening)
            db.commit()
            
            analysis_id = analysis_data.get('analysis_id')
            self.logger.info(f"Saved screening {analysis_id} for user {username}")
            return analysis_id
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to save screening for {username}: {e}")
            raise
        finally:
            db.close()
    
    def get_screening_history(self, username: str, limit: int = 20) -> List[Dict]:
        """Get screening history for a user."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return []
            
            history = db.query(ScreeningHistory).filter(
                ScreeningHistory.user_id == user.id
            ).order_by(desc(ScreeningHistory.timestamp)).limit(limit).all()
            
            return [record.to_dict() for record in history]
        finally:
            db.close()
    
    def get_screening_by_id(self, username: str, analysis_id: str) -> Optional[Dict]:
        """Get a specific screening by ID."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"DEBUG: User not found for username: {username}")
                return None
            
            print(f"DEBUG: Found user {username} with id {user.id}, looking for analysis {analysis_id}")
            
            screening = db.query(ScreeningHistory).filter(
                ScreeningHistory.user_id == user.id,
                ScreeningHistory.analysis_id == analysis_id
            ).first()
            
            if screening:
                print(f"DEBUG: Found screening for analysis {analysis_id}")
                result = screening.to_dict()
                print(f"DEBUG: Screening data keys: {result.keys()}")
                return result
            else:
                print(f"DEBUG: Screening not found for user_id={user.id}, analysis_id={analysis_id}")
                return None
        except Exception as e:
            print(f"DEBUG: Exception in get_screening_by_id: {e}")
            return None
        finally:
            db.close()
    
    def delete_screening(self, username: str, analysis_id: str) -> bool:
        """Delete a screening from history."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return False
            
            deleted = db.query(ScreeningHistory).filter(
                ScreeningHistory.user_id == user.id,
                ScreeningHistory.analysis_id == analysis_id
            ).delete()
            
            db.commit()
            return deleted > 0
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to delete screening {analysis_id}: {e}")
            return False
        finally:
            db.close()
    
    def clear_screening_history(self, username: str) -> bool:
        """Clear all screening history for a user."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return False
            
            deleted = db.query(ScreeningHistory).filter(
                ScreeningHistory.user_id == user.id
            ).delete()
            
            db.commit()
            return deleted >= 0  # Even if 0 records, it's successful
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to clear history for {username}: {e}")
            return False
        finally:
            db.close()
    
    # ============================================================
    # Chat Memory Operations
    # ============================================================
    
    def save_chat_memory(self, session_id: str, user_message: str, agent_output: str, 
                        image_data: Optional[str] = None, analysis_data: Optional[Dict] = None):
        """Save chat memory entry."""
        db = get_db()
        try:
            memory = ChatMemory.from_dict({
                'session_id': session_id,
                'user_message': user_message,
                'agent_output': agent_output,
                'image_data': image_data,
                'analysis_data': analysis_data
            })
            
            db.add(memory)
            db.commit()
            
            self.logger.info(f"Saved chat memory for session {session_id}")
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to save chat memory for session {session_id}: {e}")
            raise
        finally:
            db.close()
    
    def get_chat_memory(self, session_id: str) -> List[Dict]:
        """Get chat memory for a session."""
        db = get_db()
        try:
            memories = db.query(ChatMemory).filter(
                ChatMemory.session_id == session_id
            ).order_by(ChatMemory.timestamp).all()
            
            return [memory.to_dict() for memory in memories]
        finally:
            db.close()
    
    def clear_chat_memory(self, session_id: str) -> bool:
        """Clear chat memory for a session."""
        db = get_db()
        try:
            deleted = db.query(ChatMemory).filter(
                ChatMemory.session_id == session_id
            ).delete()
            
            db.commit()
            return deleted >= 0
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to clear chat memory for session {session_id}: {e}")
            return False
        finally:
            db.close()
    
    # ============================================================
    # PDF Report Operations
    # ============================================================
    
    def save_pdf_report(self, analysis_id: str, username: str, report_path: str, language: str = "english") -> Dict:
        """Save PDF report record."""
        db = get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise ValueError(f"User '{username}' not found")
            
            # Check if report already exists
            existing = db.query(PDFReport).filter(PDFReport.analysis_id == analysis_id).first()
            if existing:
                # Update existing
                existing.report_path = report_path
                existing.generated_at = datetime.utcnow()
            else:
                # Create new
                report = PDFReport(
                    analysis_id=analysis_id,
                    user_id=user.id,
                    report_path=report_path
                )
                db.add(report)
            
            db.commit()
            
            self.logger.info(f"Saved PDF report for analysis {analysis_id}")
            return {"analysis_id": analysis_id, "report_path": report_path}
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Failed to save PDF report for {analysis_id}: {e}")
            raise
        finally:
            db.close()
    
    def get_pdf_report(self, analysis_id: str, language: str = "english") -> Optional[Dict]:
        """Get PDF report by analysis ID."""
        db = get_db()
        try:
            report = db.query(PDFReport).filter(PDFReport.analysis_id == analysis_id).first()
            if report:
                return report.to_dict()
            return None
        finally:
            db.close()
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _hash_password(self, password: str) -> str:
        """Hash password with SHA-256 (matching existing implementation)."""
        return hashlib.sha256(password.encode()).hexdigest()

# Global database service instance
database_service = DatabaseService()
