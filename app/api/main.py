from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import router as v1_router
from app.core.config import config

app = FastAPI(
    title=config.PROJECT_NAME,
    version=config.VERSION,
    openapi_url=f"{config.API_PREFIX}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Verifacts Backend API!"}

@app.get("/health")
async def health_check():
    return {
        "status": "operational",
        "message": "The Verifacts Backend API is running smoothly.",
        "version": config.VERSION
        }
    

    