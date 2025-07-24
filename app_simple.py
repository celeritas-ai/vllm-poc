#!/usr/bin/env python3
"""
vLLM Server PoC - Simplified Demo Version
A simple FastAPI server that demonstrates the API structure without vLLM dependencies.
"""

import os
import time
import asyncio
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9


class ChatResponse(BaseModel):
    id: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class HealthResponse(BaseModel):
    status: str
    model: str
    gpu_memory_used: Optional[str] = None


app = FastAPI(
    title="vLLM PoC Server (Demo)",
    description="A proof of concept server demonstrating vLLM API structure",
    version="1.0.0-demo"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock model name
model_name = os.getenv("MODEL_NAME", "demo-model")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        model=model_name,
        gpu_memory_used="Demo mode - no GPU"
    )


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint (demo implementation)."""
    
    # Simulate processing time
    await asyncio.sleep(0.1)
    
    # Get the last user message
    user_message = ""
    for message in reversed(request.messages):
        if message.role == "user":
            user_message = message.content
            break
    
    # Generate a simple demo response
    demo_responses = [
        f"Hello! You said: '{user_message}'. This is a demo response from the vLLM PoC server.",
        f"I received your message: '{user_message}'. In a real deployment, this would be processed by vLLM.",
        f"Demo mode: Your input was '{user_message}'. The actual vLLM would generate a more sophisticated response.",
    ]
    
    import random
    generated_text = random.choice(demo_responses)
    
    # Create request ID
    request_id = f"demo-{int(time.time())}"
    
    return ChatResponse(
        id=request_id,
        choices=[{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": generated_text
            },
            "finish_reason": "stop"
        }],
        usage={
            "prompt_tokens": len(user_message.split()) if user_message else 0,
            "completion_tokens": len(generated_text.split()),
            "total_tokens": len(user_message.split()) + len(generated_text.split()) if user_message else len(generated_text.split())
        }
    )


@app.get("/models")
async def list_models():
    """List available models."""
    return {
        "object": "list",
        "data": [{
            "id": model_name,
            "object": "model", 
            "created": 1677610602,
            "owned_by": "vllm-poc-demo"
        }]
    }


@app.get("/")
async def root():
    """Root endpoint with information about the demo."""
    return {
        "message": "vLLM PoC Server Demo",
        "version": "1.0.0-demo",
        "endpoints": {
            "health": "/health",
            "chat": "/v1/chat/completions", 
            "models": "/models",
            "docs": "/docs"
        },
        "note": "This is a demo version. The real implementation uses vLLM for GPU-accelerated inference."
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting vLLM PoC Demo Server on {host}:{port}")
    print(f"📡 API Documentation: http://{host}:{port}/docs")
    print(f"🔍 Health Check: http://{host}:{port}/health")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )