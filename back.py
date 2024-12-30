from openai import AsyncAzureOpenAI
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import asyncio
import os
import json
import uvicorn

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure Azure OpenAI client
azure_endpoint = os.getenv("ENDPOINT")
api_key = os.getenv("API_KEY")
model = os.getenv("MODEL_NAME")
api_version = os.getenv("API_VERSION")

client = AsyncAzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version
)

# HTML template for the chat interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Azure OpenAI Chat</title>
    <style>
        .chat-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .message-container {
            height: 400px;
            overflow-y: auto;
            border: 1px solid #ccc;
            padding: 10px;
            margin-bottom: 20px;
        }
        .input-container {
            display: flex;
            gap: 10px;
        }
        #messageInput {
            flex-grow: 1;
            padding: 10px;
        }
        button {
            padding: 10px 20px;
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .message {
            margin-bottom: 10px;
            padding: 5px;
        }
        .user-message {
            background-color: #e3f2fd;
            border-radius: 5px;
        }
        .assistant-message {
            background-color: #f5f5f5;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>Azure OpenAI Chat</h1>
        <div id="messages" class="message-container"></div>
        <div class="input-container">
            <input type="text" id="messageInput" placeholder="Type your message here...">
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const messagesDiv = document.getElementById('messages');
        const messageInput = document.getElementById('messageInput');
        let currentAssistantMessage = null;

        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            
            if (message.role === 'user') {
                // Create new user message
                const messageElement = document.createElement('div');
                messageElement.className = 'message user-message';
                messageElement.textContent = `You: ${message.content}`;
                messagesDiv.appendChild(messageElement);
            } else if (message.role === 'assistant') {
                if (message.type === 'start') {
                    // Create new assistant message container
                    currentAssistantMessage = document.createElement('div');
                    currentAssistantMessage.className = 'message assistant-message';
                    currentAssistantMessage.textContent = 'Assistant: ';
                    messagesDiv.appendChild(currentAssistantMessage);
                } else if (message.type === 'stream') {
                    // Append to existing message
                    currentAssistantMessage.textContent += message.content;
                }
            }
            
            // Scroll to bottom
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        };

        function sendMessage() {
            const message = messageInput.value;
            if (message) {
                ws.send(message);
                messageInput.value = '';
            }
        }

        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(HTML_TEMPLATE)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Receive message from client
            user_message = await websocket.receive_text()
            
            # Send user message back to display
            await websocket.send_json({
                "role": "user",
                "content": user_message
            })

            # Signal start of assistant response
            await websocket.send_json({
                "role": "assistant",
                "type": "start",
                "content": ""
            })

            # Get streaming response from Azure OpenAI
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_message}],
                stream=True
            )

            # Stream each chunk as it arrives
            async for chunk in stream:
                if len(chunk.choices)>0:
                    print(chunk.choices)
                    if chunk.choices[0].delta.content:
                        await websocket.send_json({
                            "role": "assistant",
                            "type": "stream",
                            "content": chunk.choices[0].delta.content
                        })
                
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)