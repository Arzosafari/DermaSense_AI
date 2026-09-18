# SmartHealth-LLM Backend

FastAPI backend with multi-agent architecture for skin-health assistance using PanDerm Vision Transformer.

## Architecture Overview

```text
FastAPI Application
    ↓
Agent Orchestrator
    ↓
Multi-Agent System
    ├── DeciderAgent (intent routing)
    ├── ConversationAgent (general chat)
    ├── SymptomMatcherAgent (symptom analysis)
    ├── DiseaseInfoAgent (disease knowledge)
    ├── ReasoningAgent (medical interpretation)
    └── ImageAgent (image analysis with PanDerm)
            ↓
        PanDermSkinCancerTool
            ↓
        PanDermTool (Adapter)
            ↓
        Official PanDerm Implementation
            ↓
        checkpoint-best.pth
```

## PanDerm Integration

### Model Configuration
- **Model**: PanDerm_Base_FT (Vision Transformer)
- **Classes**: 8-class ISIC 2019 + PAD-UFES classification
- **Input**: 224x224 RGB images
- **Preprocessing**: ImageNet normalization with BICUBIC resizing
- **Inference**: Single-pass evaluation with `torch.no_grad()`

### Class Mapping (Official Training Order)
```
0 = NV   = Melanocytic Nevus (Benign)
1 = MEL  = Melanoma (Malignant)
2 = BKL  = Benign Keratosis (Benign)
3 = BCC  = Basal Cell Carcinoma (Malignant)
4 = AK   = Actinic Keratosis (Malignant)
5 = VASC = Vascular Lesion (Benign)
6 = DF   = Dermatofibroma (Benign)
7 = SCC  = Squamous Cell Carcinoma (Malignant)
```

### Model Loading
```python
# Loaded once at startup in app/main.py
from app.tools.ml.panderm_skin_cancer_tool import PanDermSkinCancerTool
PanDermSkinCancerTool()  # Singleton pattern
```

## LLM Provider System

### Hybrid Architecture
```text
Agent → LLMFactory → FallbackLLM → Groq (Primary) → LM Studio (Fallback)
```

### Configuration
```python
# In app/config.py
GROQ_API_KEY: str = ""  # From environment
GROQ_MODEL_FAST: str = "llama-3.1-8b-instant"
GROQ_MODEL_REASONING: str = "llama-3.3-70b-versatile"
LM_STUDIO_HOST: str = "http://localhost:1234"
LM_STUDIO_MODEL: str = "gemma-4-E2B-it-Q4_K_M"
LLM_USE_GROQ_FIRST: bool = True
```

### Agent Model Mapping
```python
AGENT_MODEL_MAP = {
    "decider_agent": ("groq", "llama-3.1-8b-instant"),
    "reasoning_agent": ("groq", "llama-3.3-70b-versatile"),
    "image_agent": ("groq", "llama-3.3-70b-versatile"),
    # ... other agents
}
```

## User Profile System

### Profile Structure
```python
class MedicalProfile:
    # Demographics
    age: Optional[int]
    gender: Optional[str]
    skin_type: Optional[str]
    
    # Medical History
    previous_skin_conditions: Optional[List[str]]
    previous_melanoma: Optional[bool]
    previous_skin_cancer: Optional[bool]
    family_history_melanoma: Optional[bool]
    family_history_skin_cancer: Optional[bool]
    
    # Current Health
    chronic_conditions: Optional[List[str]]
    current_medications: Optional[List[str]]
    allergies: Optional[List[str]]
    
    # Lifestyle Factors
    smoking: Optional[bool]
    sun_exposure: Optional[str]
    
    # Skin Concerns
    skin_concerns: Optional[List[str]]
    previous_examinations: Optional[List[str]]
```

### API Endpoints
- `GET /api/v1/patient/profile` - Get user profile
- `POST /api/v1/patient/profile` - Save profile
- `PUT /api/v1/patient/profile` - Update profile
- `DELETE /api/v1/patient/profile` - Delete profile

### Risk Factor Computation
The system automatically computes risk factors based on profile data:
- Family history of melanoma
- Previous skin cancer diagnosis
- High sun exposure
- Fair skin type
- Smoking status
- Diabetes (if in chronic conditions)

## Medical Safety Features

### Prediction vs Diagnosis Separation
```python
# PanDerm provides prediction
prediction = {
    "predicted_class": "melanoma",
    "confidence": 0.85,
    "is_malignant": True
}

# ReasoningAgent provides interpretation
response = """
The model classified the image as melanoma with 85% confidence.
This is not a definitive diagnosis. A dermatologist should evaluate the lesion.
...
"""
```

### Safety Constraints in Prompts
- Explicit role definitions (educator, not diagnosing physician)
- Mandatory disclaimers in all responses
- Risk-based tone adjustment
- No treatment prescriptions
- Recommendation to consult professionals

## API Endpoints

### Core Endpoints
- `GET /` - Backend status
- `GET /health/status` - Health check
- `GET /health/ping` - Ping endpoint
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe

### Chat Endpoints
- `POST /api/v1/chat/send` - Send message with optional image
- `POST /api/v1/chat/history` - Get conversation history
- `POST /api/v1/chat/clear` - Clear conversation

### Authentication Endpoints
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/check` - Check authentication status
- `GET /api/v1/auth/profile` - Get user profile
- `PUT /api/v1/auth/profile` - Update user profile

## Performance Optimization

### Model Loading Strategy
- **Single Instance**: PanDerm loaded once at startup
- **Eval Mode**: `model.eval()` for inference
- **No Gradient**: `torch.no_grad()` for memory efficiency
- **Device Management**: CUDA with CPU fallback
- **Checkpoint Caching**: Avoid repeated disk I/O

### LLM Strategy
- **Connection Pooling**: Reuse HTTP connections
- **Timeout Management**: Configurable timeouts for API calls
- **Fallback System**: Automatic fallback to local model
- **Error Handling**: Graceful degradation on failures

## Security Measures

### Authentication
- Token-based authentication
- SHA-256 password hashing
- Session token management
- User-specific profile isolation

### Data Protection
- `.env` files gitignored
- API keys never committed
- No sensitive data in logs
- Input validation on all endpoints
- Profile data access control

### File System Security
- Arbitrary path prevention
- Image validation
- File size limits
- Type checking

## Error Handling

### Graceful Degradation
- Groq API failure → LM Studio fallback
- Model loading failure → Disabled feature warning
- Image processing failure → User-friendly error
- Profile access failure → Authentication error

### Logging Strategy
- Operational information logged
- API keys never logged
- Patient data anonymized in logs
- Error details server-side only

## Testing

### Lightweight Tests
```bash
pytest tests/backend/test_lightweight.py -v
```

Tests cover:
- Class mapping verification
- Malignancy detection logic
- Profile system functionality
- LLM factory operation
- Security configurations
- API endpoint availability
- Medical safety constraints

### Test Categories
- **ClassMapping**: ISIC class order and malignancy
- **ProfileSystem**: Profile creation and risk computation
- **LLMFactory**: Provider selection and fallback
- **PanDermConfig**: Configuration validation (no model loading)
- **Security**: Gitignore and access control
- **MedicalSafety**: Safety constraint verification

## Dependencies

### Core Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `python-multipart` - File upload support

### ML Dependencies
- `torch` - PyTorch
- `torchvision` - Vision transforms
- `timm` - Vision Transformer models
- `open_clip_torch` - CLIP models
- `transformers` - Hugging Face models

### LLM Dependencies
- `langchain` - LLM framework
- `httpx` - Async HTTP client
- `openai` - OpenAI-compatible API client

### Utilities
- `pandas` - Data processing
- `numpy` - Numerical operations
- `faiss-cpu` - Vector similarity search
- `sentence-transformers` - Embeddings

## Environment Setup

### Required Environment Variables
```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL_FAST=llama-3.1-8b-instant
GROQ_MODEL_REASONING=llama-3.3-70b-versatile
LM_STUDIO_HOST=http://localhost:1234
LM_STUDIO_MODEL=gemma-4-E2B-it-Q4_K_M
```

### Optional Variables
```bash
SERPER_API_KEY=your_serper_api_key  # For web search
OLLAMA_HOST=http://localhost:11434  # Alternative LLM
```

## Medical Limitations

### System Scope
- **Educational Purpose Only**: Not a medical diagnosis system
- **Screening Tool**: AI-assisted screening, not definitive diagnosis
- **Professional Consultation**: Always recommend dermatologist evaluation
- **No Treatment**: Never prescribe medications or treatments

### Prediction Limitations
- **Image Quality**: Dependent on input image quality
- **Training Data**: Limited to ISIC 2019 + PAD-UFES classes
- **Confidence Levels**: Model confidence may not reflect clinical certainty
- **Context Limitation**: Cannot replace physical examination

### Safety Disclaimers
All medical responses include:
- Explicit educational purpose statement
- Recommendation for professional evaluation
- Confidence level disclosure
- Uncertainty acknowledgment
- No definitive diagnostic language

## Contribution to Bachelor Project

This implementation demonstrates:
1. Multi-agent architecture for health assistance
2. Integration of pretrained Vision Transformer for medical imaging
3. Personalized responses using user profiles
4. Hybrid LLM architecture with fallback systems
5. Combination of image analysis, symptoms, and context
6. Separation of ML prediction and medical reasoning
7. Safety-aware medical response generation