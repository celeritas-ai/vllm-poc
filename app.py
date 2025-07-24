#!/usr/bin/env python3
"""
vLLM Server PoC
A simple FastAPI server that serves a language model using vLLM.
"""

import os
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import configuration
from config import get_config

# Import vLLM components with error handling for different platforms
try:
    from vllm import SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    VLLM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  vLLM not available: {e}")
    print("🔄 Falling back to demo mode")
    VLLM_AVAILABLE = False
    # Mock classes for demo mode
    class SamplingParams:
        def __init__(self, **kwargs):
            self.params = kwargs
    
    class AsyncEngineArgs:
        def __init__(self, **kwargs):
            self.args = kwargs
    
    class AsyncLLMEngine:
        @classmethod
        def from_engine_args(cls, args):
            return cls()
        
        async def generate(self, prompt, sampling_params, request_id):
            # Mock generator for demo
            class MockOutput:
                def __init__(self):
                    self.request_id = request_id
                    self.outputs = [type('obj', (object,), {'text': 'Demo response: This is a mock response since vLLM is not available.'})()]
            yield MockOutput()


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


# Global variables
llm_engine: Optional[AsyncLLMEngine] = None
config_manager = get_config()
model_name = config_manager.env_vars["MODEL_NAME"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the LLM engine."""
    global llm_engine
    
    # Print platform information
    print("🖥️  Platform Configuration:")
    config_manager.print_platform_info()
    
    if VLLM_AVAILABLE:
        try:
            # Get platform-specific vLLM arguments
            vllm_args = config_manager.get_vllm_args()
            print(f"🚀 Initializing vLLM with args: {vllm_args}")
            
            # Initialize the engine with platform-specific settings
            engine_args = AsyncEngineArgs(**vllm_args)
            llm_engine = AsyncLLMEngine.from_engine_args(engine_args)
            print("✅ vLLM engine initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize vLLM engine: {e}")
            print("🔄 Continuing in demo mode")
            llm_engine = AsyncLLMEngine()  # Use mock implementation
    else:
        print("🔄 Running in demo mode (vLLM not available)")
        llm_engine = AsyncLLMEngine()  # Use mock implementation
    
    yield
    
    # Cleanup
    if llm_engine:
        llm_engine = None


app = FastAPI(
    title="vLLM PoC Server",
    description=f"A proof of concept server for vLLM inference (Platform: {config_manager.config.name})",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if llm_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Get platform-specific GPU info
    gpu_info = "N/A"
    if config_manager.config.supports_cuda:
        gpu_info = "CUDA enabled"
    elif config_manager.config.supports_mps:
        gpu_info = "MPS (Apple Silicon) enabled"
    else:
        gpu_info = "CPU only"
    
    status = "healthy" if VLLM_AVAILABLE else "demo_mode"
    
    return HealthResponse(
        status=status,
        model=model_name,
        gpu_memory_used=gpu_info
    )


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint."""
    if llm_engine is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Convert messages to prompt format
    prompt = ""
    for message in request.messages:
        if message.role == "user":
            prompt += f"User: {message.content}\n"
        elif message.role == "assistant":
            prompt += f"Assistant: {message.content}\n"
    
    prompt += "Assistant:"
    
    # Set up sampling parameters
    sampling_params = SamplingParams(
        temperature=request.temperature or 0.7,
        top_p=request.top_p or 0.9,
        max_tokens=request.max_tokens or 512,
    )
    
    # Generate response
    try:
        results = llm_engine.generate(prompt, sampling_params, request_id="chat")
        final_output = None
        async for request_output in results:
            final_output = request_output
        
        if final_output is None:
            raise HTTPException(status_code=500, detail="No output generated")
        
        generated_text = final_output.outputs[0].text
        
        return ChatResponse(
            id="chat-" + final_output.request_id,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": generated_text.strip()
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(generated_text.split()),
                "total_tokens": len(prompt.split()) + len(generated_text.split())
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/models")
async def list_models():
    """List available models."""
    return {
        "object": "list",
        "data": [{
            "id": model_name,
            "object": "model",
            "created": 1677610602,
            "owned_by": "vllm-poc"
        }]
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )