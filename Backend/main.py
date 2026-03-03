# from fastapi import FastAPI, UploadFile, File, APIRouter
# from fastapi.staticfiles import StaticFiles
# from pydantic import BaseModel
# from PIL import Image
# import io
# import hashlib
# import asyncio
# import os
# import requests
# from concurrent.futures import ThreadPoolExecutor
# from fastapi.middleware.cors import CORSMiddleware
# from google import genai

# # ──────────────────────────────────────────────────────────────────────────────
# # App setup
# # ──────────────────────────────────────────────────────────────────────────────
# app = FastAPI()
# api = APIRouter(prefix="/api")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ──────────────────────────────────────────────────────────────────────────────
# # Schemas
# # ──────────────────────────────────────────────────────────────────────────────
# class TextInput(BaseModel):
#     text: str

# class FactInput(BaseModel):
#     claim: str

# # ──────────────────────────────────────────────────────────────────────────────
# # Thread pool
# # ──────────────────────────────────────────────────────────────────────────────
# CPU_CORES = os.cpu_count() or 4
# executor = ThreadPoolExecutor(max_workers=CPU_CORES)

# # ──────────────────────────────────────────────────────────────────────────────
# # In-memory cache
# # ──────────────────────────────────────────────────────────────────────────────
# fact_cache: dict[str, dict] = {}

# # ──────────────────────────────────────────────────────────────────────────────
# # API Keys
# # ──────────────────────────────────────────────────────────────────────────────
# SERPER_API_KEY = os.getenv("SERPER_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# HF_TOKEN = os.getenv("HF_TOKEN")

# if not SERPER_API_KEY:
#     raise ValueError("❌ SERPER_API_KEY environment variable not set")
# if not GEMINI_API_KEY:
#     raise ValueError("❌ GEMINI_API_KEY environment variable not set")
# if not HF_TOKEN:
#     raise ValueError("❌ HF_TOKEN environment variable not set")

# gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# # Optional overrides (can be set as Render env vars)
# HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "umm-maybe/AI-image-detector")
# HF_TEXT_MODEL = os.getenv("HF_TEXT_MODEL", "roberta-base-openai-detector")
# HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# # ──────────────────────────────────────────────────────────────────────────────
# # Gemini model picker (ListModels + best choice)
# # ──────────────────────────────────────────────────────────────────────────────
# _models_cache: list[str] | None = None

# def list_gemini_models() -> list[str]:
#     global _models_cache
#     if _models_cache is not None:
#         return _models_cache

#     url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
#     r = requests.get(url, timeout=12)
#     r.raise_for_status()
#     data = r.json()

#     names: list[str] = []
#     for m in data.get("models", []):
#         name = m.get("name", "")
#         if name.startswith("models/"):
#             name = name.replace("models/", "")
#         if name:
#             names.append(name)

#     _models_cache = names
#     return names

# def pick_best_model() -> str | None:
#     models = list_gemini_models()

#     # Prefer newest/fast models if available for your key
#     preferred = [
#         "gemini-2.5-flash",
#         "gemini-2.0-flash",
#         "gemini-2.0-flash-lite",
#         "gemini-2.0-pro",
#         "gemini-pro",
#     ]
#     for p in preferred:
#         if p in models:
#             return p

#     # fallback: any gemini model
#     for m in models:
#         if "gemini" in m.lower():
#             return m

#     return None

# # ──────────────────────────────────────────────────────────────────────────────
# # Serper web search
# # ──────────────────────────────────────────────────────────────────────────────
# def search_web(query: str) -> str:
#     for gl, hl in (("bg", "bg"), ("us", "en")):
#         try:
#             response = requests.post(
#                 "https://google.serper.dev/search",
#                 headers={
#                     "X-API-KEY": SERPER_API_KEY,
#                     "Content-Type": "application/json"
#                 },
#                 json={
#                     "q": query,
#                     "gl": gl,
#                     "hl": hl,
#                     "num": 5,
#                     "lr": "lang_bg" if gl == "bg" else "lang_en"
#                 },
#                 timeout=6
#             )
#             if not response.ok:
#                 continue

#             data = response.json()
#             snippets: list[str] = []

#             if data.get("answerBox"):
#                 box = data["answerBox"]
#                 if box.get("answer"):
#                     snippets.append(box["answer"])
#                 if box.get("snippet"):
#                     snippets.append(box["snippet"])

#             for r in data.get("organic", [])[:4]:
#                 if r.get("snippet"):
#                     snippets.append(r["snippet"])

#             if snippets:
#                 return " | ".join(snippets)

#         except Exception as e:
#             print(f"Search error: {e}")
#             continue

#     return "Няма намерена информация."

# # ──────────────────────────────────────────────────────────────────────────────
# # Gemini fact-check
# # ──────────────────────────────────────────────────────────────────────────────
# def run_llm(claim: str) -> str:
#     search_result = search_web(claim)
#     context = search_result[:1000]

#     prompt = f"""Отговаряй САМО на български език.

# Провери следното твърдение като използваш предоставената информация.

# Информация: {context}

# Твърдение: {claim}

# Инструкция: Отговорът ТРЯБВА да започва с "Вярно" или "Невярно", последвано от тире и едно кратко изречение.
# Пример: Вярно — Кристиано Роналдо е португалски футболист.

# Отговор: """

#     model = pick_best_model()
#     if not model:
#         return "Грешка при AI анализ: Няма налични Gemini модели за този API ключ."

#     try:
#         response = gemini_client.models.generate_content(
#             model=model,
#             contents=prompt
#         )
#         return response.text.strip()
#     except Exception as e:
#         return f"Грешка при AI анализ: {str(e)}"

# # ──────────────────────────────────────────────────────────────────────────────
# # Hugging Face Inference API (remote) for image/text detection
# # ──────────────────────────────────────────────────────────────────────────────
# def hf_image_classify(image_bytes: bytes):
#     url = f"https://api-inference.huggingface.co/models/{HF_IMAGE_MODEL}"
#     r = requests.post(url, headers=HF_HEADERS, data=image_bytes, timeout=60)
#     if r.status_code == 503:
#         return [{"label": "LOADING", "score": 0.0}]
#     r.raise_for_status()
#     return r.json()

# def hf_text_classify(text: str):
#     url = f"https://api-inference.huggingface.co/models/{HF_TEXT_MODEL}"
#     r = requests.post(url, headers=HF_HEADERS, json={"inputs": text}, timeout=60)
#     if r.status_code == 503:
#         return [{"label": "LOADING", "score": 0.0}]
#     r.raise_for_status()
#     return r.json()

# # ──────────────────────────────────────────────────────────────────────────────
# # API endpoints
# # ──────────────────────────────────────────────────────────────────────────────
# @api.get("/")
# def home():
#     return {"status": "AI backend работи", "api": "Google Gemini + HF Inference"}

# @api.get("/models")
# def models():
#     try:
#         available = list_gemini_models()
#         picked = pick_best_model()
#         return {"picked": picked, "models": available}
#     except Exception as e:
#         return {"error": str(e)}

# @api.post("/detect-image")
# async def detect_image(file: UploadFile = File(...)):
#     contents = await file.read()

#     # (Optional) validate it's an image
#     try:
#         Image.open(io.BytesIO(contents)).verify()
#     except Exception:
#         return {"result": [{"label": "INVALID_IMAGE", "score": 0.0}]}

#     loop = asyncio.get_event_loop()
#     result = await loop.run_in_executor(executor, hf_image_classify, contents)
#     return {"result": result}

# @api.post("/detect-text")
# async def detect_text(data: TextInput):
#     loop = asyncio.get_event_loop()
#     result = await loop.run_in_executor(executor, hf_text_classify, data.text)
#     return {"result": result}

# @api.post("/fact-check")
# async def fact_check(data: FactInput):
#     cache_key = hashlib.md5(data.claim.lower().strip().encode()).hexdigest()
#     if cache_key in fact_cache:
#         print("✅ Cache hit")
#         return fact_cache[cache_key]

#     loop = asyncio.get_event_loop()
#     result_text = await loop.run_in_executor(executor, run_llm, data.claim)
#     response = {"result": result_text}
#     fact_cache[cache_key] = response
#     return response

# app.include_router(api)

# # ──────────────────────────────────────────────────────────────────────────────
# # Serve static frontend files
# # ──────────────────────────────────────────────────────────────────────────────
# frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
# if os.path.exists(frontend_path):
#     app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


from fastapi import FastAPI, UploadFile, File, APIRouter
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import hashlib
import asyncio
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from fastapi.middleware.cors import CORSMiddleware
from google import genai

# ──────────────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI()
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────
class TextInput(BaseModel):
    text: str

class FactInput(BaseModel):
    claim: str

# ──────────────────────────────────────────────────────────────────────────────
# Thread pool (keep small on Render free)
# ──────────────────────────────────────────────────────────────────────────────
executor = ThreadPoolExecutor(max_workers=2)

# ──────────────────────────────────────────────────────────────────────────────
# In-memory cache
# ──────────────────────────────────────────────────────────────────────────────
fact_cache: dict[str, dict] = {}

# ──────────────────────────────────────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────────────────────────────────────
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

if not SERPER_API_KEY:
    raise ValueError("❌ SERPER_API_KEY environment variable not set")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY environment variable not set")
if not HF_TOKEN:
    raise ValueError("❌ HF_TOKEN environment variable not set")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Optional overrides (can be set as Render env vars)
HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "umm-maybe/AI-image-detector")
HF_TEXT_MODEL = os.getenv("HF_TEXT_MODEL", "roberta-base-openai-detector")
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# ──────────────────────────────────────────────────────────────────────────────
# Gemini model picker (ListModels + best choice)
# ──────────────────────────────────────────────────────────────────────────────
_models_cache: list[str] | None = None

def list_gemini_models() -> list[str]:
    global _models_cache
    if _models_cache is not None:
        return _models_cache

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    data = r.json()

    names: list[str] = []
    for m in data.get("models", []):
        name = m.get("name", "")
        if name.startswith("models/"):
            name = name.replace("models/", "")
        if name:
            names.append(name)

    _models_cache = names
    return names

def pick_best_model() -> str | None:
    models = list_gemini_models()
    preferred = [
        "gemini-2.5-flash",
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

# ──────────────────────────────────────────────────────────────────────────────
# Serper web search
# ──────────────────────────────────────────────────────────────────────────────
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
                timeout=8
            )
            if not response.ok:
                continue

            data = response.json()
            snippets: list[str] = []

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

# ──────────────────────────────────────────────────────────────────────────────
# Gemini fact-check
# ──────────────────────────────────────────────────────────────────────────────
def run_llm(claim: str) -> str:
    context = search_web(claim)[:1000]

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

# ──────────────────────────────────────────────────────────────────────────────
# HF Inference API helpers (DO NOT crash the server)
# ──────────────────────────────────────────────────────────────────────────────
def normalize_hf_model(s: str) -> str:
    s = (s or "").strip()
    # if someone pasted a full URL
    if s.startswith("http://") or s.startswith("https://"):
        # keep only path after /models/
        if "/models/" in s:
            s = s.split("/models/", 1)[1]
        else:
            # fallback: keep last two path parts
            s = s.rstrip("/").split("/")[-2:]
            s = "/".join(s)
    # remove leading "models/"
    if s.startswith("models/"):
        s = s[len("models/"):]
    return s

HF_IMAGE_MODEL = normalize_hf_model(os.getenv("HF_IMAGE_MODEL", "umm-maybe/AI-image-detector"))
HF_TEXT_MODEL  = normalize_hf_model(os.getenv("HF_TEXT_MODEL", "roberta-base-openai-detector"))

HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Accept": "application/json",
}

def hf_image_classify(image_bytes: bytes):
    model = HF_IMAGE_MODEL
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    r = requests.post(url, headers=HF_HEADERS, data=image_bytes, timeout=60)

    if r.status_code == 503:
        return [{"label": "LOADING", "score": 0.0}]

    if not r.ok:
        # return readable error instead of crashing
        return [{"label": f"HF_ERROR_{r.status_code}", "score": 0.0, "detail": r.text[:500]}]

    return r.json()

def hf_text_classify(text: str):
    model = HF_TEXT_MODEL
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    r = requests.post(url, headers=HF_HEADERS, json={"inputs": text}, timeout=60)

    if r.status_code == 503:
        return [{"label": "LOADING", "score": 0.0}]

    if not r.ok:
        return [{"label": f"HF_ERROR_{r.status_code}", "score": 0.0, "detail": r.text[:500]}]

    return r.json()

# ──────────────────────────────────────────────────────────────────────────────
# API endpoints
# ──────────────────────────────────────────────────────────────────────────────
@api.get("/")
def home():
    return {"status": "AI backend работи", "api": "Google Gemini + HF Inference"}

@api.get("/models")
def models():
    try:
        available = list_gemini_models()
        picked = pick_best_model()
        return {"picked": picked, "models": available}
    except Exception as e:
        return {"error": str(e)}

@api.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    # Read bytes only (no PIL verify to avoid extra memory + crashes)
    contents = await file.read()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, hf_image_classify, contents)
    return {"result": result}

@api.post("/detect-text")
async def detect_text(data: TextInput):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, hf_text_classify, data.text)
    return {"result": result}

@api.post("/fact-check")
async def fact_check(data: FactInput):
    cache_key = hashlib.md5(data.claim.lower().strip().encode()).hexdigest()
    if cache_key in fact_cache:
        return fact_cache[cache_key]

    loop = asyncio.get_event_loop()
    result_text = await loop.run_in_executor(executor, run_llm, data.claim)
    response = {"result": result_text}
    fact_cache[cache_key] = response
    return response

app.include_router(api)

# ──────────────────────────────────────────────────────────────────────────────
# Serve static frontend
# ──────────────────────────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")