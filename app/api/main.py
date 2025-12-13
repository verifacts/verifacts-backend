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

# make requests to endpoints at intervals to keep backend running
@app.on_event("startup")
async def startup_event():
    import asyncio
    import aiohttp
    async def ping():
        while True:  
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://verifacts-backend.onrender.com/health") as response:
                        if response.status == 200:
                            print("Pinged /health endpoint successfully.")
                        else:
                            print(f"Failed to ping /health endpoint: {response.status}")
            except Exception as e:
                print(f"Error pinging /health endpoint: {e}")
            await asyncio.sleep(300)  # Wait for 5 minutes before next ping
    asyncio.create_task(ping())



@app.get("/")
async def root():
    return {"message": "Welcome to the Verifacts Backend API! Check /docs for API documentation."}


@app.get("/health")
async def health_check():
    return {
        "status": "operational",
        "message": "The Verifacts Backend API is running smoothly.",
        "version": config.VERSION
    }
