from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

azure_endpoint = os.getenv("ENDPOINT")
api_key = os.getenv("API_KEY")
model = os.getenv("MODEL_NAME") 
api_version = os.getenv("API_VERSION")


# gets API Key from environment variable OPENAI_API_KEY
client = AsyncAzureOpenAI(azure_endpoint = azure_endpoint,
                          api_key=api_key,
                          api_version=api_version)

async def main() -> None:
    stream = await client.chat.completions.create(
        model=model,
        messages = [ {"role": "user", "content": "What is a mango?"} ],
        stream=True,
    )

    #async for data in stream:
    #    print(data.model_dump_json())
    #    print("test")

    async for choices in stream:
        print(choices.model_dump_json(indent=2))    
        print()

asyncio.run(main())

