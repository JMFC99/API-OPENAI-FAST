from openai import AsyncAzureOpenAI
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import os
import json
import uvicorn
from datetime import datetime

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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Azure OpenAI Chat</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    <style>
        .message-container {
            height: calc(100vh - 220px);
        }
        .file-preview {
            opacity: 1;
            transition: opacity 0.3s;
        }
        .file-preview:hover .remove-button {
            opacity: 1;
        }
        .remove-button {
            opacity: 0;
            transition: opacity 0.3s;
        }
    </style>
</head>
<body class="h-screen flex flex-col bg-white">
    <!-- Header -->
    <div class="bg-white border-b p-4">
        <div class="flex items-center space-x-2">
            <div class="border p-2 rounded-lg">
                <span class="font-bold text-xl">AZURE</span>
                <span class="font-bold text-gray-500 text-xl">CHAT</span>
            </div>
        </div>
    </div>

    <!-- Chat Messages -->
    <div id="messages" class="flex-1 overflow-y-auto p-4 message-container"></div>

    <!-- File Previews -->
    <div id="filePreviewsContainer" class="border-t p-4 hidden">
        <div id="filePreviews" class="flex gap-4 overflow-x-auto pb-2"></div>
    </div>

    <!-- Input Area -->
    <div class="border-t p-4">
        <div class="flex gap-2">
            <input type="file" id="fileInput" multiple accept="image/*,.pdf,.doc,.docx,.txt" class="hidden">
            <button onclick="document.getElementById('fileInput').click()" 
                    class="p-2 hover:bg-gray-100 rounded-md transition-colors">
                📎
            </button>
            <button onclick="togglePromptsModal()" 
                    class="p-2 hover:bg-gray-100 rounded-md transition-colors">
                ✨
            </button>
            <input type="text" id="messageInput" 
                   class="flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                   placeholder="Type a message...">
            <button onclick="sendMessage()" 
                    class="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors">
                Send
            </button>
        </div>
    </div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const messagesDiv = document.getElementById('messages');
        const messageInput = document.getElementById('messageInput');
        const fileInput = document.getElementById('fileInput');
        const filePreviewsContainer = document.getElementById('filePreviewsContainer');
        const filePreviews = document.getElementById('filePreviews');
        let uploadedFiles = [];
        let currentAssistantMessage = null;

        function getTimeString() {
            return new Date().toLocaleTimeString();
        }

        function createMessageElement(message, sender) {
            const wrapper = document.createElement('div');
            wrapper.className = `mb-4 flex ${sender === 'user' ? 'justify-end' : 'justify-start'}`;
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `max-w-[70%] ${sender === 'user' ? 'bg-blue-100' : 'bg-gray-100'} rounded-lg p-3`;
            
            if (typeof message === 'string') {
                messageDiv.textContent = message;
            } else {
                messageDiv.appendChild(message);
            }

            // Add timestamp
            const timestamp = document.createElement('div');
            timestamp.className = 'text-xs text-gray-500 mt-1';
            timestamp.textContent = getTimeString();
            messageDiv.appendChild(timestamp);

            wrapper.appendChild(messageDiv);
            return wrapper;
        }

        function handleFileUpload(event) {
            const files = Array.from(event.target.files);
            if (files.length === 0) return;

            uploadedFiles = files;
            updateFilePreviews();
        }

        function updateFilePreviews() {
            filePreviews.innerHTML = '';
            if (uploadedFiles.length === 0) {
                filePreviewsContainer.classList.add('hidden');
                return;
            }

            filePreviewsContainer.classList.remove('hidden');
            uploadedFiles.forEach((file, index) => {
                const preview = document.createElement('div');
                preview.className = 'file-preview relative group';
                preview.innerHTML = `
                    <div class="relative w-32 h-32 border rounded-lg overflow-hidden bg-gray-50">
                        ${file.type.startsWith('image/') 
                            ? `<img src="${URL.createObjectURL(file)}" class="w-full h-full object-cover">` 
                            : `<div class="flex flex-col items-center justify-center h-full p-2">
                                <span class="text-4xl mb-2">📄</span>
                                <span class="text-xs text-gray-500 text-center truncate w-full">${file.name}</span>
                               </div>`
                        }
                        <button onclick="removeFile(${index})" 
                                class="remove-button absolute top-1 right-1 p-1 bg-white rounded-full shadow">
                            ❌
                        </button>
                    </div>
                    <div class="mt-1 text-xs text-gray-500">
                        <p class="truncate max-w-[128px]">${file.name}</p>
                        <p>${(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                `;
                filePreviews.appendChild(preview);
            });
        }

        function removeFile(index) {
            uploadedFiles.splice(index, 1);
            updateFilePreviews();
        }

        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            
            if (message.role === 'user') {
                const messageElement = createMessageElement(message.content, 'user');
                messagesDiv.appendChild(messageElement);
            } else if (message.role === 'assistant') {
                if (message.type === 'start') {
                    currentAssistantMessage = document.createElement('div');
                    const wrapper = createMessageElement(currentAssistantMessage, 'assistant');
                    messagesDiv.appendChild(wrapper);
                } else if (message.type === 'stream') {
                    currentAssistantMessage.textContent += message.content;
                }
            }
            
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        };

        function sendMessage() {
            const message = messageInput.value;
            if (!message.trim() && uploadedFiles.length === 0) return;

            ws.send(JSON.stringify({
                text: message,
                files: uploadedFiles.map(f => ({ name: f.name, size: f.size, type: f.type }))
            }));

            messageInput.value = '';
            uploadedFiles = [];
            updateFilePreviews();
        }

        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        fileInput.addEventListener('change', handleFileUpload);
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
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Send user message back to display
            await websocket.send_json({
                "role": "user",
                "content": message_data["text"]
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
                messages=[{"role": "user", "content": message_data["text"]}],
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