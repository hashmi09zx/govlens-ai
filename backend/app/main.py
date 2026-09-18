import os
import sys
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env
load_dotenv()

from app.db.session import init_db
from app.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Security Fail Fast Check
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        logger.error(
            "CRITICAL SECURITY FAILURE: GROQ_API_KEY environment variable is missing, empty, or unconfigured. "
            "Application startup halted. Please provide a valid GROQ_API_KEY in backend/.env."
        )
        sys.exit(1)

    logger.info("Initializing database tables...")
    init_db()
    logger.info("Database initialized successfully.")
    yield


app = FastAPI(
    title="GovLens AI API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [orig.strip() for orig in origins_str.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "govlens-ai-backend"}
