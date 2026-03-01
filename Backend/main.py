# ═══════════════════════════════════════════════════════════════════════════════════
# BACKUP: Previous implementations (commented for reference)
# ═══════════════════════════════════════════════════════════════════════════════════
# 
# 1. BgGPT + LlamaCPP (Original - Too slow, large download for Railway)
# from llama_cpp import Llama
# from huggingface_hub import hf_hub_download
# model_path = hf_hub_download(...BgGPT-Gemma...)
# llm = Llama(model_path=model_path, n_ctx=1024, n_threads=CPU_CORES, ...)
# output = llm(prompt, max_tokens=120, temperature=0.1, repeat_penalty=1.1, ...)
#
# 2. Claude Anthropic (Attempted - No free API key in Railway)
# import anthropic
# client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
# message = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=120, ...)
#
# ═══════════════════════════════════════════════════════════════════════════════════

from fastapi import FastAPI, UploadFile, File
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

# Railway-safe CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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
fact_cache = {}

# ───── API Keys ─────
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY environment variable not set")
if not SERPER_API_KEY:
    raise ValueError("❌ SERPER_API_KEY environment variable not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

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

# ───── Web Search ─────
def search_web(query: str) -> str:
    for lang in (("bg", "bg"), ("us", "en")):
        gl, hl = lang
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

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Грешка при AI анализ: {str(e)}"

# ───── API Endpoints ─────

@app.get("/")
def home():
    return {"status": "AI backend работи", "api": "Google Gemini"}

@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    detector = load_image_detector()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, detector, image)
    return {"result": result}

@app.post("/detect-text")
async def detect_text(data: TextInput):
    detector = load_text_detector()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, detector, data.text)
    return {"result": result}

@app.post("/fact-check")
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

# ───── Serve static frontend files ─────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ═══════════════════════════════════════════════════════════════════════════════════
# IMPLEMENTATION NOTES
# ═══════════════════════════════════════════════════════════════════════════════════
#
# Why Google Gemini?
# ──────────────────
# ✅ Lazy model loading (no timeout on Railway)
# ✅ Free tier with generous limits
# ✅ Fast inference (gemini-2.0-flash)
# ✅ No need for local model downloads
# ✅ Works reliably in production
#
# Environment Variables Required:
# ────────────────────────────────
# GEMINI_API_KEY - Get from https://ai.google.dev
# SERPER_API_KEY - Get from https://google-serper.dev
# ALLOWED_ORIGINS - Frontend URL(s) for CORS
#
# Railway Deployment:
# ───────────────────
# 1. Push code to Git with these files
# 2. Connect Railway to GitHub
# 3. Set environment variables in Railway dashboard
# 4. Railway will auto-deploy and run: uvicorn main:app --host 0.0.0.0 --port $PORT
#
# Troubleshooting:
# ────────────────
# Error: "GEMINI_API_KEY not set" → Add key to Railway Variables
# Error: "Connection refused" → Check CORS ALLOWED_ORIGINS setting
# Error: "Search failed" → Verify SERPER_API_KEY is valid
