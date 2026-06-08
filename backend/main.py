import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import routers
from routes import health, webhook, shipments, trucks, conversations
from utils.delay_checker import start_delay_checker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-seed mock data on startup if mock mode is active
    from services import supabase_service
    if supabase_service.is_mock_active():
        logger.info("Supabase is in MOCK mode. Seeding initial control room state...")
        try:
            import seed_demo
            seed_demo.run_seed()
        except Exception as e:
            logger.error(f"Failed to auto-seed mock data: {e}")

    # Start background delay checker
    loop = asyncio.get_event_loop()
    delay_task = loop.create_task(start_delay_checker())
    logger.info("Delay checker background task spawned.")
    yield
    # Cleanup background task
    delay_task.cancel()
    logger.info("Delay checker background task stopped.")

app = FastAPI(
    title="LoadSetu API",
    description="Agentic freight coordination API for India's MSME trucking layer",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(shipments.router)
app.include_router(trucks.router)
app.include_router(conversations.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the LoadSetu API",
        "docs_url": "/docs",
        "health_check": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    # Read port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
