from openai import AsyncAzureOpenAI
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
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

# Initialize FastAPI app

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

        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            const messageElement = document.createElement('div');
            messageElement.textContent = `${message.role}: ${message.content}`;
            messagesDiv.appendChild(messageElement);
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

            # Get response from Azure OpenAI
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": user_message}],
                stream=True
            )

            # Stream the response
            full_response = ""
            async for chunk in stream:
                print(chunk)
                if len(chunk.choices)>0:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
            
            # Send complete response
            await websocket.send_json({
                "role": "assistant",
                "content": full_response
            })
            
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run("back:app", host="0.0.0.0", port=8000, reload=True)