from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Placeholder for actual KogniTerm logic
    return ChatResponse(response=f"Received: {request.message}. This is a stub response.")
