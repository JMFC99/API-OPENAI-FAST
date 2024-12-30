# backend.py
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI,AzureOpenAI
import json
import asyncio
from pydantic import BaseModel
from typing import List
import os

from dotenv import load_dotenv
import os

load_dotenv()

# Initialize FastAPI app
app = FastAPI()


# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize OpenAI client
client = AzureOpenAI(
  api_key = os.getenv("API_KEY"),  
  api_version = "2024-08-01-preview",
  azure_endpoint = os.getenv("ENDPOINT")
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

async def generate_stream_response(messages):
    try:
        # Create streaming response from OpenAI
        stream = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": m.role, "content": m.content} for m in messages],
            stream=True
        )

        # Process each chunk from the stream
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                # Format the chunk as a Server-Sent Event
                yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
            await asyncio.sleep(0)  # Allow other tasks to run

        # Send completion message
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        generate_stream_response(request.messages),
        media_type="text/event-stream"
    )