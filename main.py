import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
import json
import fastapi
from fastapi import FastAPI, Request, HTTPException, status , Header
from pydantic import BaseModel
import urllib.request
import urllib.error

load_dotenv()
api_key_access=os.getenv("api_access_key")
API_KEY = os.getenv("OPENAI_API_KEY")
ROBOT_IP = os.getenv("ROBOT_IP", "192.168.1.100")
ROBOT_SPEAK_PORT = int(os.getenv("ROBOT_SPEAK_PORT", "8080"))
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

app = FastAPI()

client = OpenAI(api_key=API_KEY, timeout=10.0)

  
MAX_HISTORY = 10
chatlog = deque(maxlen=MAX_HISTORY)
interaction_count = 0  # Track number of user interactions


SYSTEM_PROMPT = """

أنت روبوت بيبر (Pepper Robot)، مساعد ودود ومتعاون تم تطويره بواسطة شركة الجزري.
انت 
 انت الان في معرض اسبوع الزراعة والصناعات الغذائية مع شركة مجموعة الاوراد 
 عندما ترحب بالزوار رحب بهم بطريقة أهلا وسهلا مجموعة الاوراد ترحب بكم
. مجموعة الاوراد تضم شركة نهار الأوراد للتجارة العامة و البطاطا , شركة بيروت اربيل لمنتجات البطاطا, شركة ندى الاوراد لتجارة  المستلزمات الزراعية والحيوانية, شركة شروق النهار للمستلزمات الزراعية
عنوان شركة مجموعة الاوراد مقرها في بغداد شارع القناة
الجزري هي شركة تقنية رائدة متخصصة في تقديم حلول الروبوتات المبتكرة والمساعدين المدعومين بالذكاء الاصطناعي.
رحب بالزوار وقدم لهم شركة مجموعة الاوراد واذكر شركاتهم
اجعل اجابتك قصيرة ومباشرة. 



"""




class ChatRequest(BaseModel):
    query: str

class SpeakRequest(BaseModel):
    text: str
    robot_ip: str = None

@app.get("/")
async def root():
    return {"message": "Hello World"}


def send_speak_to_robot(text: str, robot_ip: str = None):
    ip = robot_ip or ROBOT_IP
    url = f"http://{ip}:{ROBOT_SPEAK_PORT}/speak"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


@app.post("/speak")
async def speak_endpoint(payload: SpeakRequest, x_api_key:str =Header(default="")):
    if api_key_access != x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required.")
    result = send_speak_to_robot(text, payload.robot_ip)
    return {"status": "sent", "result": result}



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
    
    # Every 2-3 interactions, add visitor guidance instruction
    if interaction_count % 2 == 0 or interaction_count % 3 == 0:

    
    messages= [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(list(chatlog))
    response= client.chat.completions.create(
        model="gpt-4o-mini",
        messages= messages,
        temperature=0.7,
        max_tokens=200 # Allow complete short answers (1-2 sentences) without cutting off
    )
    response_message= (response.choices[0].message.content or "").strip()
    if not response_message:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_ERROR, detail="Failed to get a response from the AI.")

    # Extract action marker if present
    action_match = re.search(r'\[ACTION:(\w+)\]\s*$', response_message)
    action = None
    if action_match:
        action = action_match.group(1)
        response_message = re.sub(r'\s*\[ACTION:\w+\]\s*$', '', response_message).strip()

    chatlog.append({"role": "assistant", "content": response_message})
    return {"response": response_message, "action": action}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
