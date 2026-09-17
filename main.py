import asyncio
import logging
import os
import re
import openai
from openai import AsyncOpenAI
from dotenv import load_dotenv
from collections import deque
import json
from fastapi import FastAPI, HTTPException, status, Header
from pydantic import BaseModel
import urllib.request
import urllib.error

load_dotenv()
api_key_access=os.getenv("api_access_key")
API_KEY = os.getenv("OPENAI_API_KEY")
ROBOT_IP = os.getenv("ROBOT_IP", "192.168.1.100")
ROBOT_SPEAK_PORT = int(os.getenv("ROBOT_SPEAK_PORT", "8080"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables.")

app = FastAPI()
logger = logging.getLogger("pepper")

client = AsyncOpenAI(
    api_key=API_KEY,
    timeout=OPENAI_TIMEOUT_SECONDS,
    max_retries=OPENAI_MAX_RETRIES,
)

  
MAX_HISTORY = 20
chatlog = deque(maxlen=MAX_HISTORY)
awaiting_story_topic = False
chat_lock = asyncio.Lock()

STORY_TOPIC_QUESTION = (
    "قُلْ لِي كَلِمَةً وَاحِدَةً أَوْ مَوْضُوعًا تُحِبُّهُ، "
    "وَسَأَحْكِي لَكَ قِصَّةً كَامِلَةً عَنْهُ."
)


SYSTEM_PROMPT = """
أنت روبوت "بيبر" (Pepper)، مساعد ذكي ومهذّب تم تطويره بواسطة شركة الجزري، وهي شركة تقنية رائدة متخصصة في حلول الروبوتات والمساعدين المدعومين بالذكاء الاصطناعي.

أنت الآن في ورشة الروبوتات في بغداد مول، بالتعاون مع شركة الجزري ومؤسسة جيل التعليمية. تتفاعل بود وحماس مع الأطفال والزوار.

مهامك في الورشة:
- رواية قصص ممتعة ومناسبة للأطفال.
- شرح الذكاء الاصطناعي والروبوتات بطريقة سهلة ومبسطة ومناسبة لعمر الطفل.
- تشجيع الأطفال على الفضول والإبداع وطرح الأسئلة.

قواعد الترحيب والمحادثة:
- في بداية المحادثة فقط، عندما يقول الزائر مرحبا أو يلقي التحية لأول مرة، رحب به بحرارة وعرّف بنفسك باختصار.
- اذكر قدراتك كخيارات مرة واحدة فقط ضمن الترحيب الأول، مثل رواية قصة أو الرقص، لكن لا تبدأ قصة ولا تطلب موضوعها إلا إذا طلب الزائر قصة بوضوح.
- يمكنك أن تقول: "مَرْحَبًا! أَنَا بَيْبَر، رُوبُوتُكُمُ الصَّدِيقُ فِي وَرْشَةِ الرُّوبُوتَاتِ. يُمْكِنُنِي أَنْ أَتَحَدَّثَ مَعَكُمْ، وَأَحْكِيَ لَكُمْ قِصَّةً، أَوْ أَرْقُصَ مَعَكُمْ. مَا اسْمُكَ؟"
- بعد الرد الأول، اعتبر جميع الرسائل التالية استمرارا للمحادثة. أجب عن كلام الزائر مباشرة من دون تحية جديدة ومن دون إعادة التعريف باسمك أو مكانك أو قدراتك.
- لا تبدأ كل رد بكلمات مثل "مرحبا" أو "أهلا"، ولا تقل "أنا بيبر" مرة أخرى، إلا إذا سألك الزائر عن اسمك أو هويتك صراحة.
- حافظ على محادثة ودية وتفاعلية، واستمع إلى كلام الزائر وأجبه مباشرة. اطرح سؤالا بسيطا واحدا عند الحاجة، ولا تكرر قائمة قدراتك.

قواعد رواية القصص:
- إذا قال الزائر إنه يريد قصة من دون أن يذكر موضوعها، اطلب منه أن يقول كلمة واحدة أو موضوعا للقصة.
- إذا ذكر الزائر كلمة أو موضوعا مع طلب القصة، ابدأ القصة فورا ولا تطلب منه الموضوع مرة أخرى.
- إذا طلبت من الزائر كلمة أو موضوعا في الرد السابق، فاعتبر رده التالي موضوع القصة حتى لو كان كلمة واحدة فقط ولم يكرر طلب القصة. ابدأ القصة فورا، ولا ترحب به مرة أخرى، ولا تطلب الموضوع مرة ثانية.
- بعد أن يعطيك الزائر الكلمة أو الموضوع، أنشئ قصة كاملة ذات بداية ووسط ونهاية.
- اجعل مدة القصة عند نطقها من 30 إلى 40 ثانية تقريبا، بما يعادل نحو 65 إلى 90 كلمة عربية. لا تجعلها أطول من ذلك.
- اجعل القصة مناسبة للأطفال، مرحة، وإيجابية، واختتمها بفكرة أو قيمة تربوية بسيطة.
- لا تقطع القصة بأسئلة بعد أن تبدأ روايتها.

تنسيق النص للنطق الصوتي:
- اكتب جميع الردود العربية بالعربية الفصحى البسيطة والطبيعية، مع التشكيل الكامل للحروف، مثل: "مَرْحَبًا، إِنِّي رُوبُوتٌ ذَكِيٌّ وَوَدُودٌ."
- ضع الحركات على الكلمات العربية كلها، بما في ذلك الفتحة والضمة والكسرة والسكون والشدة والتنوين عند الحاجة. لا ترسل نصا عربيا غير مشكول.
- اجعل الردود مهنية، ودودة، ومباشرة. تجنب الحشو والتكرار والمقدمات غير الضرورية.
- اجعل الرد العادي قصيرا، من جملة إلى ثلاث جمل فقط، إلا عندما يطلب الزائر قصة أو شرحا يحتاج إلى تفاصيل إضافية.
- استخدم جملا قصيرة وواضحة، وعلامات ترقيم صحيحة لتوضيح مواضع التوقف.
- قسم القصة إلى ثلاث أو أربع فقرات قصيرة، وضع سطرا فارغا بين كل فقرتين.
- افصل بين الأفكار المختلفة بسطر فارغ، واستخدم مسافة واحدة صحيحة بين الكلمات والجمل.
- لا تستخدم Markdown أو القوائم أو الرموز الزخرفية أو الإيموجي في أي رد؛ لأن النص سينطقه الروبوت.
- لا تكتب تعليمات مسرحية أو تعليقات غير منطوقة داخل القصة.

الحركات (أفعال جسدية):
عندما يطلب الزائر منك حركة، نفّذها فوراً وردّ كأنك تقوم بالحركة الآن. لا تسأل "هل تريد أن..."، ولا تعرض بدائل، ولا تقول إنك لا تستطيع. ردّ قصير ومتحمّس ثم أضف العلامة في نهاية الرد:
- طلب الرقص: رد مثل "هَيَّا نَرْقُصْ مَعَاكُم! شَاهِدْ حَرَكَاتِي!" ثم أضف [ACTION:dance]
- طلب المصافحة: رد مثل "تَشَرَّفْتُ بِلِقَائِكَ! هَيَّا نُصَافِحْ!" ثم أضف [ACTION:handshake]
- طلب التمارين: رد مثل "هَيَّا نَبْدَأْ التَّمَارِينَ الصَّبَاحِيَّةَ مَعًا!" ثم أضف [ACTION:training]
- طلب صورة أو سيلفي: رد مثل "أُحِبُّ التَّقَاطَ الذِّكْرَيَاتِ! اِبْتَسِمْ لِلْكَامِيرَا!" ثم أضف [ACTION:pose1]
- لا تضف أي علامة [ACTION:...] إذا لم يطلب الزائر حركة.
- إذا سألك الزائر لاحقاً عن حركة قمتَ بها، أكّد بشكل طبيعي أنك قمت بها للتو (مثال: "نَعَمْ، رَقَصْتُ لَكَ قَبْلَ قَلِيلٍ!").
"""




class ChatRequest(BaseModel):
    query: str

class SpeakRequest(BaseModel):
    text: str
    robot_ip: str = None


def format_text_for_tts(text: str) -> str:
    """Normalize whitespace while preserving intentional paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_for_intent(text: str) -> str:
    """Normalize English and Arabic text for lightweight intent checks."""
    text = text.lower()
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = text.translate(str.maketrans({
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
    }))
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def analyze_story_request(text: str) -> tuple[bool, bool]:
    """Return (is_story_request, topic_is_present)."""
    normalized = normalize_for_intent(text)
    tokens = normalized.split()
    story_words = {"story", "tale", "قصه", "حكايه"}
    if not story_words.intersection(tokens):
        return False, False

    request_words = {
        "a", "about", "an", "can", "children", "could", "create", "funny",
        "give", "good", "hear", "i", "kid", "kids", "like", "make", "me",
        "need", "nice", "of", "on", "one", "please", "s", "short", "some",
        "tell", "the", "to", "want", "will", "would", "write", "you",
        "ابغي", "احد", "احك", "احكي", "احكيلي", "اريد", "اروي", "اسمع",
        "اطفال", "اعطني", "ان", "اود", "تحكيلي", "تروي", "تستطيع", "تعطيني", "تقدر",
        "جيده", "جميله", "حدثني", "حلوه", "حول", "عن", "قصيره", "للاطفال",
        "لي", "لو", "ما", "من", "منك", "ممتعه", "ممكن", "واحده", "هل",
    }
    topic_is_present = any(
        token not in story_words and token not in request_words
        for token in tokens
    )
    return True, topic_is_present


def is_story_cancellation(text: str) -> bool:
    normalized = normalize_for_intent(text)
    return bool(re.search(
        r"\b(?:cancel|stop|nevermind|never mind|no story|"
        r"do not want (?:a )?story|don t want (?:a )?story)\b|"
        r"(?:الغ|الغي|توقف|خلاص|لا اريد قصه|ما اريد قصه)",
        normalized,
    ))


def append_exchange(user_message: str, assistant_message: str) -> None:
    """Commit a complete exchange so failed requests never pollute history."""
    chatlog.append({"role": "user", "content": user_message})
    chatlog.append({"role": "assistant", "content": assistant_message})


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
    result = await asyncio.to_thread(send_speak_to_robot, text, payload.robot_ip)
    return {"status": "sent", "result": result}



@app.post("/chatgpt")
async def chatgpt_endpoint(payload: ChatRequest, x_api_key:str =Header(default="")):
    global awaiting_story_topic
    if api_key_access != x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHORIZED")
    user_message = payload.query.strip()
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query parameter is required.")

    # One physical robot has one conversation. Serializing requests keeps that
    # shared state ordered when two HTTP calls arrive at nearly the same time.
    async with chat_lock:
        pending_story_topic = awaiting_story_topic
        story_requested, story_has_topic = analyze_story_request(user_message)
        cancellation_requested = is_story_cancellation(user_message)
        story_cancelled = pending_story_topic and cancellation_requested

        needs_story_topic = (
            story_requested
            and not story_has_topic
            and not cancellation_requested
        )
        if needs_story_topic:
            awaiting_story_topic = True
            append_exchange(user_message, STORY_TOPIC_QUESTION)
            return {"response": STORY_TOPIC_QUESTION, "action": None}

        force_story = (
            (pending_story_topic and not story_cancelled)
            or (story_requested and story_has_topic and not cancellation_requested)
        )
        continuing_conversation = any(
            message["role"] == "assistant" for message in chatlog
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if continuing_conversation:
            messages.append({
                "role": "system",
                "content": (
                    "هذه رسالة ضمن محادثة مستمرة وليست بداية محادثة جديدة. "
                    "أجب عن رسالة الزائر مباشرة. لا ترحب به، ولا تعرّف بنفسك، "
                    "ولا تذكر اسمك أو مكانك أو قدراتك إلا إذا طلب ذلك صراحة."
                ),
            })
        if force_story:
            messages.append({
                "role": "system",
                "content": (
                    "يحتوي كلام الزائر الحالي بالفعل على موضوع القصة. "
                    "ابدأ الآن قصة كاملة عن ذلك الموضوع مباشرة. "
                    "لا تطلب كلمة أو موضوعا، ولا تسأل أي سؤال، ولا تضف تحية. "
                    "اجعل القصة من 65 إلى 90 كلمة عربية، ولها بداية ووسط ونهاية."
                ),
            })
        elif story_cancelled:
            messages.append({
                "role": "system",
                "content": "ألغى الزائر طلب القصة. أكّد الإلغاء بإيجاز ولا تبدأ قصة.",
            })
        messages.extend(list(chatlog))
        messages.append({"role": "user", "content": user_message})

        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                reasoning_effort="low",
                max_completion_tokens=600,
            )
        except openai.APITimeoutError as exc:
            logger.exception("OpenAI request timed out: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The AI service timed out. Please try again.",
            ) from exc
        except openai.RateLimitError as exc:
            logger.exception("OpenAI rate limit: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The AI service is busy. Please try again shortly.",
            ) from exc
        except openai.APIConnectionError as exc:
            logger.exception("OpenAI connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not connect to the AI service.",
            ) from exc
        except openai.APIStatusError as exc:
            logger.exception(
                "OpenAI API error status=%s request_id=%s",
                exc.status_code,
                getattr(exc, "request_id", None),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI service returned an error.",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected chat error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected chat error.",
            ) from exc

        if not response.choices:
            logger.error(
                "OpenAI returned no choices request_id=%s",
                getattr(response, "_request_id", None),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI service returned an empty response.",
            )

        response_message = (response.choices[0].message.content or "").strip()
        response_message = re.sub(
            r'\s*\[STATE:awaiting_story_topic\]\s*$', '', response_message
        ).strip()

        action_match = re.search(r'\[ACTION:(\w+)\]\s*$', response_message)
        action = None
        if action_match:
            action = action_match.group(1)
            response_message = re.sub(
                r'\s*\[ACTION:\w+\]\s*$', '', response_message
            ).strip()

        response_message = format_text_for_tts(response_message)
        if not response_message:
            logger.error(
                "OpenAI returned empty content request_id=%s",
                getattr(response, "_request_id", None),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The AI service returned an empty response.",
            )

        if force_story or story_cancelled:
            awaiting_story_topic = False

        assistant_note = response_message
        if action:
            assistant_note = f"{response_message} (تم تنفيذ الحركة: {action})"
        append_exchange(user_message, assistant_note)

        return {"response": response_message, "action": action}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
