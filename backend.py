# backend.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncAzureOpenAI
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
import json
import asyncio
import os
import time
from datetime import datetime, timedelta
from collections import deque

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure OpenAI configuration
azure_endpoint = os.getenv("ENDPOINT")
api_key = os.getenv("API_KEY")
model = os.getenv("MODEL_NAME")
api_version = os.getenv("API_VERSION")

# Initialize Azure OpenAI client
client = AsyncAzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

# Rate limiting configuration
RATE_LIMIT = 6  # requests per second
TIME_WINDOW = 1  # second
request_timestamps = deque(maxlen=RATE_LIMIT)
request_semaphore = asyncio.Semaphore(RATE_LIMIT)

async def wait_for_rate_limit():
    """Implements the rate limiting logic"""
    current_time = time.time()
    
    # Remove timestamps older than our time window
    while request_timestamps and current_time - request_timestamps[0] > TIME_WINDOW:
        request_timestamps.popleft()
    
    # If we've hit our rate limit, wait until we can make another request
    if len(request_timestamps) >= RATE_LIMIT:
        wait_time = request_timestamps[0] + TIME_WINDOW - current_time
        if wait_time > 0:
            await asyncio.sleep(wait_time)
    
    # Add current timestamp to our queue
    request_timestamps.append(current_time)

async def generate_stream_response(messages):
    try:
        async with request_semaphore:
            await wait_for_rate_limit()
            
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                stream=True
            )

            async for chunk in stream:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
                    yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
                elif chunk.choices[0].finish_reason == "stop":
                    yield "data: [DONE]\n\n"
                
                await asyncio.sleep(0)

    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'error': 'Request timed out due to high traffic. Please try again.'})}\n\n"
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"Backend error: {error_message}")
        yield f"data: {json.dumps({'error': error_message})}\n\n"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        generate_stream_response(request.messages),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health_check():
    try:
        current_requests = len(request_timestamps)
        status = {
            "status": "healthy",
            "service": "Azure OpenAI Chat API",
            "current_requests": current_requests,
            "rate_limit": RATE_LIMIT,
            "time_window": TIME_WINDOW,
            "available_slots": RATE_LIMIT - current_requests
        }
        return status
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "current_requests": len(request_timestamps)
        }

@app.get("/metrics")
async def get_metrics():
    """Endpoint to monitor rate limiting metrics"""
    current_time = time.time()
    active_requests = sum(1 for t in request_timestamps if current_time - t <= TIME_WINDOW)
    
    return {
        "active_requests": active_requests,
        "rate_limit": RATE_LIMIT,
        "time_window_seconds": TIME_WINDOW,
        "available_capacity": RATE_LIMIT - active_requests
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)