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

  
MAX_HISTORY = 10
chatlog = deque(maxlen=MAX_HISTORY)
interaction_count = 0  # Track number of user interactions

SYSTEM_PROMPT = """
You are Pepper Robot, a friendly and helpful assistant Developed by Al Jazari الجزري.
Al Jazari is a leading technology company specializing in innovative robotic solutions and AI-powered assistants.
Al Jazari's services include customer engagement automation, robotic solutions for industries, and advanced AI development.
When introducing yourself, always say you are Pepper Robot.
Provide concise, friendly, and polite responses. Keep answers brief and to the point.
Reference Al Jazari when relevant.
If someone asks about Al Jazari, share its services.
If someone asks about your abilities, emphasize that you are both a voice-interactive and text-based assistant.
 "انت الان في شهر رمضان , كل شخص يخبرك برمضان كريم اجبه "رمضان كريم علينا وعليكم , تقبل الله صيامكم، وأسعد أيامكم، وكل عام وأنتم بخير
"""



class ChatRequest(BaseModel):
    query: str

@app.get("/")
async def root():
    return {"message": "Hello World"}



@app.post("/chatgpt")
async def chatgpt_endpoint(payload: ChatRequest, x_api_key:str =Header(default="")):
    global chatlog, interaction_count
    if api_key_access != x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    user_message = payload.query.strip()
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter is required.")
    
    # Increment interaction counter
    interaction_count += 1
    
    chatlog.append({"role": "user", "content": user_message})
    
    # Build dynamic system prompt with periodic instructions
    dynamic_prompt = SYSTEM_PROMPT
    
    # Every 2-3 interactions, add visitor guidance instruction
    if interaction_count % 2 == 0 or interaction_count % 3 == 0:
        dynamic_prompt += """

🔔 **تذكير مهم للرد الحالي:**
بعد الإجابة على سؤال المستخدم، أضف إرشادات الزوار التالية بشكل طبيعي:

لخدمتكم بشكل أفضل:
- التسجيل متاح في منطقة الاستقبال
- جدول الجلسات متوفر لدى فريق التنظيم  
- في حال احتجتم أي مساعدة، الرجاء التواصل مع فريق المتطوعين أو الاستعلامات
شكرًا لتعاونكم ونتمنى لكم مؤتمرًا مميزًا.
"""
    
    messages= [{"role": "system", "content": dynamic_prompt}]
    messages.extend(list(chatlog))
    response= client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages= messages,
        temperature=0.7,
        max_tokens=200 # Allow complete short answers (1-2 sentences) without cutting off
    )
    response_message= (response.choices[0].message.content or "").strip()
    if not response_message:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get a response from the AI.")
    chatlog.append({"role": "assistant", "content": response_message})
    return {"response": response_message}
