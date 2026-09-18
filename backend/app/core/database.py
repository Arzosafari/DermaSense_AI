"""
Database Module - MySQL connection and ORM models for SmartHealth.

This module provides the database layer for MySQL integration using SQLAlchemy ORM.
It handles connections, models, and provides a clean interface for database operations.
"""
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DECIMAL, TIMESTAMP, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool
from datetime import datetime
import json

from app.config import settings

logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()

# Database URL construction
def get_database_url():
    """Construct MySQL database URL from settings."""
    return f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?charset=utf8mb4"

# Create engine with connection pooling
engine = None
SessionLocal = None

def init_database():
    """Initialize database connection and create tables if they don't exist."""
    global engine, SessionLocal
    
    try:
        database_url = get_database_url()
        logger.info(f"Connecting to MySQL database: {settings.DB_NAME} at {settings.DB_HOST}:{settings.DB_PORT}")
        
        # Create engine with connection pooling
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=3600,    # Recycle connections after 1 hour
            echo=settings.DEBUG   # Log SQL queries in debug mode
        )
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database connection established and tables verified")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def get_db():
    """Get database session for dependency injection."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

def is_database_initialized():
    """Check if database has been successfully initialized."""
    return SessionLocal is not None

# ============================================================
# ORM Models
# ============================================================

class User(Base):
    """Users table - corresponds to app/data/users.json"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    screening_history = relationship("ScreeningHistory", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class UserProfile(Base):
    """User profiles table - combines auth.py profile and patient.py medical profile"""
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    username = Column(String(255), nullable=False, index=True)
    
    # Basic profile from auth.py
    name = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    skin_type = Column(String(50), nullable=True)
    allergies = Column(Text, nullable=True)
    medical_conditions = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    
    # Extended medical profile from patient.py
    sun_exposure = Column(String(50), nullable=True)
    sunburn_history = Column(Boolean, nullable=True)
    tanning_bed_use = Column(Boolean, nullable=True)
    previous_skin_conditions = Column(Text, nullable=True)
    previous_melanoma = Column(Boolean, nullable=True)
    previous_skin_cancer = Column(Boolean, nullable=True)
    family_history_melanoma = Column(Boolean, nullable=True)
    family_history_skin_cancer = Column(Boolean, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    current_medications = Column(Text, nullable=True)
    allergies_list = Column(Text, nullable=True)
    smoking = Column(Boolean, nullable=True)
    alcohol_consumption = Column(String(50), nullable=True)
    exercise_frequency = Column(String(50), nullable=True)
    skin_concerns = Column(Text, nullable=True)
    previous_examinations = Column(Text, nullable=True)
    other_medical_context = Column(Text, nullable=True)
    
    # Computed risk factors (stored as JSON string)
    computed_risk_factors = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="profile")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', name='unique_user_profile'),
    )
    
    def to_dict(self):
        """Convert to dictionary, handling JSON fields."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "skin_type": self.skin_type,
            "allergies": self.allergies,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "sun_exposure": self.sun_exposure,
            "sunburn_history": self.sunburn_history,
            "tanning_bed_use": self.tanning_bed_use,
            "previous_skin_conditions": self.previous_skin_conditions,
            "previous_melanoma": self.previous_melanoma,
            "previous_skin_cancer": self.previous_skin_cancer,
            "family_history_melanoma": self.family_history_melanoma,
            "family_history_skin_cancer": self.family_history_skin_cancer,
            "chronic_conditions": self.chronic_conditions,
            "current_medications": self.current_medications,
            "allergies_list": self.allergies_list,
            "smoking": self.smoking,
            "alcohol_consumption": self.alcohol_consumption,
            "exercise_frequency": self.exercise_frequency,
            "skin_concerns": self.skin_concerns,
            "previous_examinations": self.previous_examinations,
            "other_medical_context": self.other_medical_context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Parse computed risk factors if stored as JSON
        if self.computed_risk_factors:
            try:
                result["computed_risk_factors"] = json.loads(self.computed_risk_factors)
            except:
                result["computed_risk_factors"] = self.computed_risk_factors
        
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create UserProfile from dictionary."""
        # Handle computed_risk_factors conversion
        if 'computed_risk_factors' in data and isinstance(data['computed_risk_factors'], list):
            data = data.copy()
            data['computed_risk_factors'] = json.dumps(data['computed_risk_factors'])
        
        return cls(**data)

class SessionToken(Base):
    """Session tokens table - corresponds to app/data/tokens.json"""
    __tablename__ = "session_tokens"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), ForeignKey('users.username', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }

class UserSession(Base):
    """User sessions table for chat session management"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    username = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    last_message = Column(Text, nullable=True)
    date = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'session_id', name='unique_user_session'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "session_id": self.session_id,
            "title": self.title,
            "last_message": self.last_message,
            "date": self.date,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class ScreeningHistory(Base):
    """Screening history table - corresponds to analysis_history_service.py"""
    __tablename__ = "screening_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    username = Column(String(255), nullable=False, index=True)
    analysis_id = Column(String(255), unique=True, nullable=False, index=True)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    
    # Model predictions
    predicted_class = Column(String(255), nullable=True)
    confidence = Column(DECIMAL(5, 4), nullable=True)
    top3_predictions = Column(Text, nullable=True)  # JSON string
    screening_score = Column(DECIMAL(5, 2), nullable=True)
    screening_level = Column(String(50), nullable=True)
    
    # User input
    user_symptoms = Column(Text, nullable=True)
    medical_context = Column(Text, nullable=True)
    
    # Image info
    image_stored = Column(Boolean, default=False)
    image_path = Column(String(500), nullable=True)
    
    # Full structured analysis (JSON)
    structured_analysis = Column(Text, nullable=True)  # JSON string
    
    # Additional fields
    all_probabilities = Column(Text, nullable=True)  # JSON string
    explainability = Column(Text, nullable=True)  # JSON string
    
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="screening_history")
    
    def to_dict(self):
        """Convert to dictionary, parsing JSON fields."""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "predicted_class": self.predicted_class,
            "confidence": float(self.confidence) if self.confidence else None,
            "screening_score": float(self.screening_score) if self.screening_score else None,
            "screening_level": self.screening_level,
            "user_symptoms": self.user_symptoms,
            "medical_context": self.medical_context,
            "image_stored": self.image_stored,
            "image_path": self.image_path,
            "structured_analysis": self.structured_analysis,
            "all_probabilities": self.all_probabilities,
            "explainability": self.explainability,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        # Parse JSON fields
        if self.top3_predictions:
            try:
                result["top3_predictions"] = json.loads(self.top3_predictions)
            except:
                result["top3_predictions"] = self.top3_predictions
        
        if self.structured_analysis:
            try:
                result["structured_analysis"] = json.loads(self.structured_analysis)
            except:
                result["structured_analysis"] = self.structured_analysis
        
        if self.all_probabilities:
            try:
                result["all_probabilities"] = json.loads(self.all_probabilities)
            except:
                result["all_probabilities"] = self.all_probabilities
        
        if self.explainability:
            try:
                result["explainability"] = json.loads(self.explainability)
            except:
                result["explainability"] = self.explainability
        
        if self.medical_context:
            try:
                result["medical_context"] = json.loads(self.medical_context)
            except:
                result["medical_context"] = self.medical_context
        
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create ScreeningHistory from dictionary, handling JSON fields."""
        data = data.copy()
        
        # Convert JSON fields to strings
        for field in ['top3_predictions', 'structured_analysis', 'all_probabilities', 'explainability', 'medical_context']:
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field])
        
        return cls(**data)

class ChatMemory(Base):
    """Chat memory table - corresponds to memory_store"""
    __tablename__ = "chat_memory"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), nullable=False, index=True)
    user_message = Column(Text, nullable=True)
    agent_output = Column(Text, nullable=True)
    image_data = Column(Text, nullable=True)
    analysis_data = Column(Text, nullable=True)  # JSON string
    timestamp = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        """Convert to dictionary, parsing JSON fields."""
        result = {
            "id": self.id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "agent_output": self.agent_output,
            "image_data": self.image_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
        
        if self.analysis_data:
            try:
                result["analysis_data"] = json.loads(self.analysis_data)
            except:
                result["analysis_data"] = self.analysis_data
        
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create ChatMemory from dictionary, handling JSON fields."""
        data = data.copy()
        
        # Convert analysis_data to JSON string if it's a dict/list
        if 'analysis_data' in data and isinstance(data['analysis_data'], (dict, list)):
            data['analysis_data'] = json.dumps(data['analysis_data'])
        
        return cls(**data)

class PDFReport(Base):
    """PDF reports table for tracking generated reports"""
    __tablename__ = "pdf_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    report_path = Column(String(500), nullable=False)
    generated_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "user_id": self.user_id,
            "report_path": self.report_path,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "language": "english"  # Default to english for compatibility
        }
