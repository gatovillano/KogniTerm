from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router as api_router
from .api.websocket import router as ws_router
from .api.settings import router as settings_router

app = FastAPI(title="KogniTerm Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(ws_router)

@app.get("/")
async def root():
    return {"message": "KogniTerm Server is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
