from fastapi import APIRouter
from pydantic import BaseModel
import subprocess
import asyncio
import os
from typing import List, Optional

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    output: str
    error: str = ""
    exitCode: int = 0

class FileItem(BaseModel):
    name: str
    path: str
    isDirectory: bool
    size: Optional[int] = None

class DirectoryRequest(BaseModel):
    path: str = "."

class DirectoryResponse(BaseModel):
    items: List[FileItem]
    currentPath: str

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Placeholder for actual KogniTerm logic
    return ChatResponse(response=f"Received: {request.message}. This is a stub response.")

@router.post("/execute", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
    """Execute a shell command and return the output."""
    try:
        # Run command in a subprocess
        process = await asyncio.create_subprocess_shell(
            request.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        
        stdout, stderr = await process.communicate()
        
        return CommandResponse(
            output=stdout.decode('utf-8') if stdout else "",
            error=stderr.decode('utf-8') if stderr else "",
            exitCode=process.returncode or 0
        )
    except Exception as e:
        return CommandResponse(
            output="",
            error=str(e),
            exitCode=1
        )

@router.post("/files/list", response_model=DirectoryResponse)
async def list_directory(request: DirectoryRequest):
    """List contents of a directory."""
    try:
        path = os.path.abspath(request.path)
        items = []
        
        for entry in os.scandir(path):
            # Skip hidden files
            if entry.name.startswith('.'):
                continue
                
            item = FileItem(
                name=entry.name,
                path=entry.path,
                isDirectory=entry.is_dir(),
                size=entry.stat().st_size if entry.is_file() else None
            )
            items.append(item)
        
        # Sort: directories first, then files
        items.sort(key=lambda x: (not x.isDirectory, x.name.lower()))
        
        return DirectoryResponse(
            items=items,
            currentPath=path
        )
    except Exception as e:
        return DirectoryResponse(
            items=[],
            currentPath=request.path
        )


