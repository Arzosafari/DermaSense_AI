# SmartHealth-LLM

SmartHealth-LLM is an AI-based skin-health assistant using a multi-agent architecture with PanDerm Vision Transformer for skin lesion classification.

## Key Features

- **Multi-Agent Architecture**: Specialized agents for conversation, symptom matching, disease information, reasoning, and image analysis
- **PanDerm Integration**: Fine-tuned Vision Transformer for 8-class skin lesion classification (ISIC 2019 + PAD-UFES)
- **Hybrid LLM System**: Groq API with local Gemma/LM Studio fallback
- **User Profile System**: Personalized responses based on medical history and risk factors
- **Medical Safety**: Clear separation between AI prediction and medical interpretation
- **Bilingual Support**: English and Persian (Farsi) language support

## Architecture

```text
User Request
    ↓
Agent Orchestrator
    ↓
Multi-Agent System
    ├── DeciderAgent (routing)
    ├── ConversationAgent (general chat)
    ├── SymptomMatcherAgent (symptom analysis)
    ├── DiseaseInfoAgent (disease knowledge)
    ├── ReasoningAgent (medical interpretation)
    └── ImageAgent (skin lesion analysis)
            ↓
        PanDermSkinCancerTool
            ↓
        PanDermTool
            ↓
        Official PanDerm Vision Transformer
            ↓
        8-Class Prediction
```

## Repository Structure

```text
backend/               FastAPI app, agents, tools, prompts, models
├── app/
│   ├── agents/        Multi-agent system
│   ├── api/v1/        REST API endpoints
│   ├── llm/           LLM adapters and factory
│   ├── tools/         ML tools (PanDerm, NER, etc.)
│   ├── utils/         Utilities (ISIC classes, malignancy scoring)
│   └── models/panderm/ PanDerm configuration and labels
frontend/              React client with authentication and profile management
external/PanDerm/      Official PanDerm repository (git submodule)
scripts/               Bootstrap and evaluation scripts
tests/                 Pytest suites (lightweight tests without model loading)
```

## Environment Configuration

Copy and edit backend env file:

```bash
cp backend/.env.example backend/.env
```

Required environment variables:
- `GROQ_API_KEY` - Groq API key for primary LLM (get from https://console.groq.com/)
- `GROQ_MODEL_FAST` - Fast model for quick responses (default: llama-3.1-8b-instant)
- `GROQ_MODEL_REASONING` - Reasoning model for complex tasks (default: llama-3.3-70b-versatile)
- `LM_STUDIO_HOST` - Local LM Studio host (default: http://localhost:1234)
- `LM_STUDIO_MODEL` - Local Gemma model (default: gemma-4-E2B-it-Q4_K_M)

Optional variables:
- `SERPER_API_KEY` - Optional web search for disease information
- `OLLAMA_HOST` - Alternative local LLM provider

## PanDerm Model Setup

The system uses the official PanDerm Vision Transformer for skin lesion classification. The model checkpoint should be placed at:

```
backend/app/models/panderm/checkpoints/checkpoint-best.pth
```

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

## Run Locally

### Backend

```bash
cd backend
python -m venv venv_clean
source venv_clean/bin/activate  # On Windows: venv_clean\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend URL: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm start
```

Frontend URL: `http://localhost:3000`

## Authentication & User Profiles

The system includes user authentication and profile management:

### Authentication
- Register: `POST /api/v1/auth/register`
- Login: `POST /api/v1/auth/login`
- Logout: `POST /api/v1/auth/logout`
- Check: `GET /api/v1/auth/check`

### Profile Management
- Get Profile: `GET /api/v1/patient/profile`
- Save Profile: `POST /api/v1/patient/profile`
- Update Profile: `PUT /api/v1/patient/profile`
- Delete Profile: `DELETE /api/v1/patient/profile`

Profile fields include:
- Demographics (age, gender, skin type)
- Medical history (previous conditions, medications, allergies)
- Risk factors (family history, sun exposure, smoking)
- Skin concerns and previous examinations

## Backend API

### Core
- `GET /` -> backend status message
- `GET /health/status` -> `{"status":"ok"}`
- `GET /health/ping`
- `GET /health/live`
- `GET /health/ready`

### Chat
- `POST /api/v1/chat/send` - Send message with optional image
- `POST /api/v1/chat/history` - Get conversation history
- `POST /api/v1/chat/clear` - Clear conversation

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/profile` - Get user profile
- `PUT /api/v1/auth/profile` - Update user profile

### Patient Profile
- `GET /api/v1/patient/profile` - Get medical profile
- `POST /api/v1/patient/profile` - Save medical profile
- `PUT /api/v1/patient/profile` - Update medical profile
- `DELETE /api/v1/patient/profile` - Delete medical profile

## Tests

Lightweight tests (no model loading):

```bash
cd backend
pytest tests/backend/test_lightweight.py -v
```

These tests verify:
- Class mapping and malignancy detection
- Profile system and risk factor computation
- LLM factory and provider selection
- PanDerm configuration (without loading model)
- Security configurations
- API endpoint configuration
- Medical safety constraints

## Medical Safety

The system is designed for educational purposes only and includes multiple safety measures:

1. **Clear Disclaimers**: All medical responses include explicit disclaimers
2. **Prediction vs Diagnosis**: Clear distinction between AI prediction and medical diagnosis
3. **Professional Recommendations**: Always recommend consultation with dermatologists
4. **No Treatment Prescriptions**: System never prescribes medications or treatments
5. **Uncertainty Handling**: Acknowledges limitations and confidence levels
6. **Risk-Based Communication**: Tone and urgency adjusted based on risk assessment

## LLM Provider Architecture

The system uses a hybrid LLM approach:

```text
Agent
  ↓
LLM Factory
  ↓
FallbackLLM
  ├── GroqAdapter (Primary)
  └── LMStudioAdapter (Fallback)
```

### Groq (Primary)
- Fast inference with low latency
- Supports various model sizes
- Requires API key configuration
- Automatic fallback on failure

### LM Studio (Fallback)
- Local Gemma model
- No API costs
- Requires LM Studio running locally
- Activated automatically when Groq fails

## Multi-Agent System

### DeciderAgent
Routes user requests to appropriate agents based on intent analysis.

### ConversationAgent
Handles general conversation, greetings, and non-medical chat.

### SymptomMatcherAgent
Extracts and analyzes skin-related symptoms from user descriptions.

### DiseaseInfoAgent
Provides educational information about specific skin conditions.

### ReasoningAgent
Generates personalized medical explanations combining:
- PanDerm predictions
- User profile context
- Symptom information
- Medical knowledge base

### ImageAgent
Processes skin lesion images using PanDerm and provides screening results.

## Performance Considerations

- **Model Loading**: PanDerm model is loaded once at startup
- **Inference Optimization**: Uses `eval()` mode and `torch.no_grad()`
- **Memory Management**: Avoids repeated checkpoint loading
- **Fallback System**: Graceful degradation when services unavailable

## Security

- `.env` files are gitignored
- API keys never committed to repository
- User authentication required for profile access
- Profile data isolated per user
- Input validation on all endpoints
- No sensitive data in logs

## Dependencies

Key backend dependencies:
- `fastapi` - Web framework
- `torch` - PyTorch for ML models
- `timm` - Vision Transformer models
- `open_clip_torch` - CLIP models
- `langchain` - LLM integration
- `httpx` - Async HTTP client
- `transformers` - Hugging Face models

## License

MIT