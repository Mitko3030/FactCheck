from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from transformers import pipeline
from PIL import Image
import io
import hashlib
import asyncio
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI()
api = APIRouter(prefix="/api")

# ───── CORS ─────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───── Schemas ─────
class TextInput(BaseModel):
    text: str

class FactInput(BaseModel):
    claim: str

# ───── Thread pool ─────
CPU_CORES = os.cpu_count() or 4
executor = ThreadPoolExecutor(max_workers=CPU_CORES)

# ───── In-memory cache ─────
fact_cache: dict[str, dict] = {}

# ───── API Keys ─────
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not SERPER_API_KEY:
    raise ValueError("❌ SERPER_API_KEY environment variable not set")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY environment variable not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ───── Gemini Model Picker (ListModels + best choice) ─────
_models_cache: list[str] | None = None

def list_gemini_models() -> list[str]:
    """
    Returns model IDs available for this API key, e.g.:
    ["gemini-2.0-flash", "gemini-2.0-flash-lite", ...]
    Cached in-memory after first call.
    """
    global _models_cache
    if _models_cache is not None:
        return _models_cache

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    data = r.json()

    names = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if name.startswith("models/"):
            name = name.replace("models/", "")
        if name:
            names.append(name)

    _models_cache = names
    return names

def pick_best_model() -> str | None:
    """
    Picks the best available model for your key.
    Preference order:
      1) gemini flash (fast)
      2) gemini pro (quality)
      3) any gemini model available
    """
    models = list_gemini_models()

    preferred = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-pro",
        "gemini-pro",
    ]

    for p in preferred:
        if p in models:
            return p

    for m in models:
        if "gemini" in m.lower():
            return m

    return None

# ───── Lazy model loading ─────
image_detector = None
text_detector = None

def load_image_detector():
    global image_detector
    if image_detector is None:
        print("⏳ Loading image detector...")
        image_detector = pipeline(
            "image-classification",
            model="umm-maybe/AI-image-detector"
        )
        print("✅ Image detector ready")
    return image_detector

def load_text_detector():
    global text_detector
    if text_detector is None:
        print("⏳ Loading text detector...")
        text_detector = pipeline(
            "text-classification",
            model="roberta-base-openai-detector"
        )
        print("✅ Text detector ready")
    return text_detector

# ───── Web Search (Serper) ─────
def search_web(query: str) -> str:
    for gl, hl in (("bg", "bg"), ("us", "en")):
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "gl": gl,
                    "hl": hl,
                    "num": 5,
                    "lr": "lang_bg" if gl == "bg" else "lang_en"
                },
                timeout=6
            )
            if not response.ok:
                continue

            data = response.json()
            snippets = []

            if data.get("answerBox"):
                box = data["answerBox"]
                if box.get("answer"):
                    snippets.append(box["answer"])
                if box.get("snippet"):
                    snippets.append(box["snippet"])

            for r in data.get("organic", [])[:4]:
                if r.get("snippet"):
                    snippets.append(r["snippet"])

            if snippets:
                return " | ".join(snippets)

        except Exception as e:
            print(f"Search error: {e}")
            continue

    return "Няма намерена информация."

# ───── Gemini Fact Checking ─────
def run_llm(claim: str) -> str:
    search_result = search_web(claim)
    context = search_result[:1000]

    prompt = f"""Отговаряй САМО на български език.

Провери следното твърдение като използваш предоставената информация.

Информация: {context}

Твърдение: {claim}

Инструкция: Отговорът ТРЯБВА да започва с "Вярно" или "Невярно", последвано от тире и едно кратко изречение.
Пример: Вярно — Кристиано Роналдо е португалски футболист.

Отговор: """

    model = pick_best_model()
    if not model:
        return "Грешка при AI анализ: Няма налични Gemini модели за този API ключ."

    try:
        response = gemini_client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Грешка при AI анализ: {str(e)}"

# ───── API Endpoints ─────
@api.get("/")
def home():
    return {"status": "AI backend работи", "api": "Google Gemini"}

@api.get("/models")
def models():
    # Shows which models are available + which one we pick automatically
    try:
        available = list_gemini_models()
        picked = pick_best_model()
        return {"picked": picked, "models": available}
    except Exception as e:
        return {"error": str(e)}

@api.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    detector = load_image_detector()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, detector, image)
    return {"result": result}

@api.post("/detect-text")
async def detect_text(data: TextInput):
    detector = load_text_detector()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, detector, data.text)
    return {"result": result}

@api.post("/fact-check")
async def fact_check(data: FactInput):
    cache_key = hashlib.md5(data.claim.lower().strip().encode()).hexdigest()
    if cache_key in fact_cache:
        print("✅ Cache hit")
        return fact_cache[cache_key]

    loop = asyncio.get_event_loop()
    result_text = await loop.run_in_executor(executor, run_llm, data.claim)
    response = {"result": result_text}
    fact_cache[cache_key] = response
    return response

app.include_router(api)

# ───── Serve static frontend files ─────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")