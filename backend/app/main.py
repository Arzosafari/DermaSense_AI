# app/main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, patient  # 🆕 اضافه کردن patient

from app.core.log_level_middleware import PerRouteLogLevelMiddleware
from app.api.v1 import chat, health, debug, metrics
from app.core.app_logging import setup_logging

logger = logging.getLogger(__name__)

# تنظیم لاگینگ قبل از هر چیز
setup_logging()

# ایجاد اپلیکیشن FastAPI
app = FastAPI(
    title="SmartHealth API",
    version="0.1.0",
    description="SmartHealth Multi-Agent LLM Backend with Image Analysis"
)

# ============================================================
# CORS Middleware
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ============================================================
# Custom Middleware
# ============================================================
app.add_middleware(PerRouteLogLevelMiddleware)

# ============================================================
# Startup Event - Pre-load all models
# ============================================================
@app.on_event("startup")
async def startup_event():
    """Pre-load all models and databases at startup to avoid loading during requests"""
    logger.info("=" * 70)
    logger.info("🚀 SMARTHEALTH API STARTING UP...")
    logger.info("=" * 70)
    
    # ----- 0. Initialize MySQL Database -----
    try:
        logger.info("📦 [0/6] Initializing MySQL Database...")
        from app.core.database import init_database
        success = init_database()
        if success:
            logger.info("   ✅ MySQL database connection established")
        else:
            logger.warning("   ⚠️ Failed to connect to MySQL database - file-based storage will be used as fallback")
    except Exception as e:
        logger.error(f"   ❌ Failed to initialize MySQL database: {e}")
        import traceback
        traceback.print_exc()
        logger.warning("   ⚠️ Continuing without MySQL - file-based storage will be used")
    
    # ----- 1. Pre-load Embedding Model -----
    try:
        logger.info("📦 [1/6] Loading Embedding Model...")
        from app.utils.embeddings import EmbeddingSingleton
        embedding = EmbeddingSingleton.get_instance()
        test_embedding = embedding.embed_query("test")
        logger.info(f"   ✅ Embedding model loaded successfully (dim={len(test_embedding)})")
    except Exception as e:
        logger.error(f"   ❌ Failed to load Embedding model: {e}")
        logger.warning("   ⚠️ Vector search features may not work")

    # ----- 2. Pre-load NER Model -----
    try:
        logger.info("📦 [2/6] Loading Biomedical NER Model...")
        from app.tools.medical.biomedical_ner_tool import _get_or_create_ner_pipeline
        _get_or_create_ner_pipeline()
        logger.info("   ✅ Biomedical NER model loaded successfully")
    except Exception as e:
        logger.error(f"   ❌ Failed to load NER model: {e}")
        logger.warning("   ⚠️ Symptom extraction may not work")

    # ----- 3. Pre-load Disease Database -----
    try:
        logger.info("📦 [3/6] Loading Disease Database...")
        from app.tools.medical.disease_info_tool import DiseaseInfoRetrieverTool
        DiseaseInfoRetrieverTool()
        logger.info("   ✅ Disease database loaded successfully")
    except Exception as e:
        logger.error(f"   ❌ Failed to load Disease database: {e}")
        logger.warning("   ⚠️ Disease information lookup may not work")

    # ----- 4. Pre-load Symptom FAISS Database -----
    try:
        logger.info("📦 [4/6] Loading Symptom Vector Database...")
        from app.tools.medical.symptom_matcher_tool import SymptomDiseaseMatcherTool
        SymptomDiseaseMatcherTool()
        logger.info("   ✅ Symptom vector database loaded successfully")
    except Exception as e:
        logger.error(f"   ❌ Failed to load Symptom database: {e}")
        logger.warning("   ⚠️ Symptom matching may not work")

    # ----- 5. Pre-load PanDerm Model (Optional - heavy) -----
    try:
        logger.info("📦 [5/6] Loading PanDerm Skin Cancer Model...")
        from app.tools.ml.panderm_skin_cancer_tool import PanDermSkinCancerTool
        PanDermSkinCancerTool()
        logger.info("   ✅ PanDerm model loaded successfully")
    except Exception as e:
        logger.error(f"   ❌ Failed to load PanDerm model: {e}")
        logger.warning("   ⚠️ Image analysis feature may not work")
        logger.warning("   💡 To enable image analysis, ensure 'checkpoint-best.pth' is in the correct path")

    # ----- Final Status -----
    logger.info("=" * 70)
    logger.info("🎉 ALL MODELS LOADED - API IS READY!")
    logger.info("=" * 70)
    logger.info(f"   📡 LM Studio: Check if running on port 1234")
    logger.info(f"   🖥️  API Base URL: http://localhost:8000")
    logger.info(f"   📚 API Docs: http://localhost:8000/docs")
    logger.info(f"   🔍 API Health: http://localhost:8000/health")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("=" * 50)
    logger.info("🛑 SmartHealth API shutting down...")
    logger.info("=" * 50)

# ============================================================
# Routes
# ============================================================

# Home route
@app.get("/")
async def home():
    return {
        "message": "SmartHealth Backend Running",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }

# API Routes
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(debug.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(patient.router)  # 🆕 ثبت patient router


# ============================================================
# Error Handlers
# ============================================================

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred",
            "path": str(request.url.path)
        }
    )

# ============================================================
# Run script (for direct execution)
# ============================================================
if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting SmartHealth API server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        timeout_keep_alive=120,
    )