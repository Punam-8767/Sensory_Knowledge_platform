import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import SensoryPlatformException
from app.api.v1 import document_routes

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Core API for the Sensory Knowledge Engineering Platform",
    version="1.0.0",
    docs_url=f"{settings.API_V1_STR}/docs",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(SensoryPlatformException)
async def sensory_exception_handler(request: Request, exc: SensoryPlatformException):
    logger.warning(f"Handled SensoryPlatformException: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message}
    )

# Register API Routers
app.include_router(document_routes.router, prefix=settings.API_V1_STR)

# Health Check Routes (supports both / and /health)
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "app_name": settings.APP_NAME,
        "status": "online",
        "api_docs": f"{settings.API_V1_STR}/docs"
    }

if __name__ == "__main__":
    logger.info(f"Starting {settings.APP_NAME}...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)