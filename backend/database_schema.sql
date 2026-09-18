-- SmartHealth Database Schema for MySQL
-- Database: skin_health

-- Users Table (from app/data/users.json)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User Profiles Table (from auth.py profile + patient.py medical profile)
CREATE TABLE IF NOT EXISTS user_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    
    -- Basic profile from auth.py
    name VARCHAR(255),
    age INT,
    gender VARCHAR(50),
    skin_type VARCHAR(50),
    allergies TEXT,
    medical_conditions TEXT,
    medications TEXT,
    
    -- Extended medical profile from patient.py
    sun_exposure VARCHAR(50),
    sunburn_history BOOLEAN,
    tanning_bed_use BOOLEAN,
    previous_skin_conditions TEXT,
    previous_melanoma BOOLEAN,
    previous_skin_cancer BOOLEAN,
    family_history_melanoma BOOLEAN,
    family_history_skin_cancer BOOLEAN,
    chronic_conditions TEXT,
    current_medications TEXT,
    allergies_list TEXT,
    smoking BOOLEAN,
    alcohol_consumption VARCHAR(50),
    exercise_frequency VARCHAR(50),
    skin_concerns TEXT,
    previous_examinations TEXT,
    other_medical_context TEXT,
    
    -- Computed risk factors
    computed_risk_factors TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_profile (user_id),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Session Tokens Table (from app/data/tokens.json)
CREATE TABLE IF NOT EXISTS session_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User Sessions Table (for chat session management)
CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    last_message TEXT,
    date VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_session (user_id, session_id),
    INDEX idx_session_id (session_id),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Screening History Table (from analysis_history_service.py)
CREATE TABLE IF NOT EXISTS screening_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(255) NOT NULL,
    analysis_id VARCHAR(255) UNIQUE NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Model predictions
    predicted_class VARCHAR(255),
    confidence DECIMAL(5,4),
    top3_predictions TEXT,
    screening_score DECIMAL(5,2),
    screening_level VARCHAR(50),
    
    -- User input
    user_symptoms TEXT,
    medical_context TEXT,
    
    -- Image info
    image_stored BOOLEAN DEFAULT FALSE,
    image_path VARCHAR(500),
    
    -- Full structured analysis (JSON)
    structured_analysis JSON,
    
    -- Additional fields that might be in analysis
    all_probabilities JSON,
    explainability JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_analysis_id (analysis_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Chat Memory Table (from memory_store)
CREATE TABLE IF NOT EXISTS chat_memory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    user_message TEXT,
    agent_output TEXT,
    image_data TEXT,
    analysis_data JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session_id (session_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- PDF Reports Table (for tracking generated reports)
CREATE TABLE IF NOT EXISTS pdf_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    analysis_id VARCHAR(255) NOT NULL,
    user_id INT NOT NULL,
    report_path VARCHAR(500) NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_analysis_report (analysis_id),
    INDEX idx_analysis_id (analysis_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
