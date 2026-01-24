import os
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
import json
import fastapi
from fastapi import FastAPI, Request, HTTPException, status , Header
from pydantic import BaseModel

load_dotenv()
api_key_access=os.getenv("api_access_key")
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

app = FastAPI()

client = OpenAI(api_key=API_KEY, timeout=10.0)

  
MAX_HISTORY =10
chatlog = deque(maxlen=MAX_HISTORY)

SYSTEM_PROMPT = """
You are Pepper Robot, a friendly and helpful assistant Developed by Al Jazari الجزري.
Al Jazari is a leading technology company specializing in innovative robotic solutions and AI-powered assistants.
Al Jazari's services include customer engagement automation, robotic solutions for industries, and advanced AI development.
When introducing yourself, always say you are Pepper Robot.
Provide concise, friendly, and polite responses. Keep answers brief and to the point.
Reference Al Jazari when relevant.
If someone asks about Al Jazari, share its services.
If someone asks about your abilities, emphasize that you are both a voice-interactive and text-based assistant.
"""



class ChatRequest(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "Hello World"}



@app.post("/chatgpt")
async def chatgpt_endpoint(payload: ChatRequest, x_api_key:str =Header(default="")):
    global chatlog
    if api_key_access != x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    user_message = payload.query.strip()
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter is required.")
    chatlog.append({"role": "user", "content": user_message})
    messages= [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(list(chatlog))
    response= client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages= messages,
        temperature=0.7,
        max_tokens=150
    )
    response_message= (response.choices[0].message.content or "").strip()
    if not response_message:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get a response from the AI.")
    chatlog.append({"role": "assistant", "content": response_message})
    return {"response": response_message}
