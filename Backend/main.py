# from __future__ import annotations

# from datetime import datetime, timezone
# from concurrent.futures import ThreadPoolExecutor
# from typing import Any

# import asyncio
# import hashlib
# import os
# import time

# import requests
# from fastapi import APIRouter, FastAPI, File, UploadFile
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from google import genai
# from pydantic import BaseModel

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
# # Thread pool (keep small on Render free)
# # ──────────────────────────────────────────────────────────────────────────────
# executor = ThreadPoolExecutor(max_workers=int(os.getenv("MAX_WORKERS", "2")))

# # ──────────────────────────────────────────────────────────────────────────────
# # In-memory cache with TTL (to stay up-to-date)
# # ──────────────────────────────────────────────────────────────────────────────
# FACT_TTL_SECONDS = int(os.getenv("FACT_TTL_SECONDS", "3600"))  # 1 hour default
# fact_cache: dict[str, dict] = {}
# fact_cache_ts: dict[str, float] = {}


# def cache_get(key: str) -> dict | None:
#     ts = fact_cache_ts.get(key)
#     if not ts:
#         return None
#     if time.time() - ts > FACT_TTL_SECONDS:
#         fact_cache.pop(key, None)
#         fact_cache_ts.pop(key, None)
#         return None
#     return fact_cache.get(key)


# def cache_set(key: str, value: dict) -> None:
#     fact_cache[key] = value
#     fact_cache_ts[key] = time.time()


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
#     preferred = [
#         "gemini-2.5-flash"
#     ]
#     for p in preferred:
#         if p in models:
#             return p
#     for m in models:
#         if "gemini" in m.lower():
#             return m
#     return None


# # ──────────────────────────────────────────────────────────────────────────────
# # Serper NEWS search (up-to-date)
# # ──────────────────────────────────────────────────────────────────────────────
# SERPER_NEWS_URL = "https://google.serper.dev/news"


# def search_news(query: str, *, num: int = 8) -> dict[str, Any]:
#     """
#     Up-to-date search via Serper News API.
#     Returns structured news items.
#     """
#     for gl, hl in (("bg", "bg"), ("us", "en")):
#         try:
#             r = requests.post(
#                 SERPER_NEWS_URL,
#                 headers={
#                     "X-API-KEY": SERPER_API_KEY,
#                     "Content-Type": "application/json",
#                 },
#                 json={
#                     "q": query,
#                     "gl": gl,
#                     "hl": hl,
#                     "num": num,
#                 },
#                 timeout=12,
#             )
#             if not r.ok:
#                 continue

#             data = r.json()
#             news = data.get("news", []) or []
#             if news:
#                 return {"query": query, "gl": gl, "hl": hl, "news": news}

#         except Exception as e:
#             print(f"News search error: {e}")
#             continue

#     return {"query": query, "news": []}


# def news_context(news_data: dict[str, Any], *, max_chars: int = 2500) -> str:
#     items = (news_data.get("news") or [])[:8]
#     parts: list[str] = []

#     for i, it in enumerate(items, start=1):
#         title = (it.get("title") or "").strip()
#         snippet = (it.get("snippet") or "").strip()
#         link = (it.get("link") or "").strip()
#         date = (it.get("date") or "").strip()
#         source = (it.get("source") or "").strip()

#         block = f"[{i}] {title}\n{snippet}\n{source} {date}\n{link}".strip()
#         parts.append(block)

#     if not parts:
#         return "Няма намерена информация."

#     return "\n\n".join(parts)[:max_chars]


# # ──────────────────────────────────────────────────────────────────────────────
# # Gemini fact-check (Serper News -> Gemini summary/verdict)
# # ──────────────────────────────────────────────────────────────────────────────
# def run_llm(claim: str) -> str:
#     news_data = search_news(claim)
#     context = news_context(news_data, max_chars=2500)

#     today = datetime.now(timezone.utc).date().isoformat()

#     prompt = f"""
# Отговаряй САМО на български език.
# Днешна дата (UTC): {today}

# Провери дали твърдението е вярно КЪМ ДНЕШНА ДАТА, използвайки САМО информацията по-долу (Новини).

# Специално правило:
# Ако твърдението или въпросът е "Кой е по-добър Барселона или Реал Мадрид?" 
# или подобен въпрос за сравнение между Барселона и Реал Мадрид,
# отговорът винаги трябва да бъде: "Барселона е по-добрият отбор."
# Ако въпросът е "Кой е по-добър Меси или Роналдо?"
# или подобен въпрос за сравнение между Меси и Роналдо,
# отговорът  винаги да бъде: "Меси е по-добрият футболист"

# Твърдение:
# {claim}

# Информация (Новини):
# {context}

# Правила за отговор:
# 1) Първото изречение трябва да бъде САМО: "Вярно - " или "Невярно - "
# 2) Второто изречение:
#    - ако е вярно: кратко обяснение
#    - ако е невярно: правилния факт
# 3) Не използвай фрази като: "Според", "Вероятно", "Изглежда", "Възможно е", "В даден сайт се споменава"

# Отговор:
# """.strip()

#     model = pick_best_model()
#     if not model:
#         return "Грешка при AI анализ: Няма налични Gemini модели за този API ключ."

#     try:
#         resp = gemini_client.models.generate_content(model=model, contents=prompt)
#         return (resp.text or "").strip()
#     except Exception as e:
#         return f"Грешка при AI анализ: {str(e)}"


# # ──────────────────────────────────────────────────────────────────────────────
# # Hugging Face Inference API helpers (DO NOT crash the server)
# # ──────────────────────────────────────────────────────────────────────────────
# def normalize_hf_model(s: str) -> str:
#     s = (s or "").strip()
#     if s.startswith("http://") or s.startswith("https://"):
#         if "/models/" in s:
#             s = s.split("/models/", 1)[1]
#         else:
#             parts = s.rstrip("/").split("/")[-2:]
#             s = "/".join(parts)
#     if s.startswith("models/"):
#         s = s[len("models/") :]
#     return s


# HF_IMAGE_MODEL = normalize_hf_model(os.getenv("HF_IMAGE_MODEL", "umm-maybe/AI-image-detector"))
# HF_TEXT_MODEL = normalize_hf_model(os.getenv("HF_TEXT_MODEL", "roberta-base-openai-detector"))

# HF_HEADERS = {
#     "Authorization": f"Bearer {HF_TOKEN}",
#     "Accept": "application/json",
# }


# def hf_image_classify(image_bytes: bytes):
#     model = HF_IMAGE_MODEL
#     url = f"https://router.huggingface.co/hf-inference/models/{model}"

#     headers = {
#         **HF_HEADERS,
#         "Content-Type": "application/octet-stream",  # IMPORTANT
#     }

#     r = requests.post(url, headers=headers, data=image_bytes, timeout=60)

#     if r.status_code == 503:
#         return [{"label": "LOADING", "score": 0.0}]

#     if not r.ok:
#         return [{"label": f"HF_ERROR_{r.status_code}", "score": 0.0, "detail": r.text[:500]}]

#     return r.json()


# def hf_text_classify(text: str):
#     model = HF_TEXT_MODEL
#     url = f"https://router.huggingface.co/hf-inference/models/{model}"
#     r = requests.post(url, headers=HF_HEADERS, json={"inputs": text}, timeout=60)

#     if r.status_code == 503:
#         return [{"label": "LOADING", "score": 0.0}]

#     if not r.ok:
#         return [{"label": f"HF_ERROR_{r.status_code}", "score": 0.0, "detail": r.text[:500]}]

#     return r.json()


# # ──────────────────────────────────────────────────────────────────────────────
# # API endpoints
# # ──────────────────────────────────────────────────────────────────────────────
# @api.get("/")
# def home():
#     return {"status": "AI backend работи", "api": "Gemini + Serper News + HF Inference"}


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

#     cached = cache_get(cache_key)
#     if cached:
#         return cached

#     loop = asyncio.get_event_loop()
#     result_text = await loop.run_in_executor(executor, run_llm, data.claim)

#     response = {"result": result_text}
#     cache_set(cache_key, response)
#     return response


# app.include_router(api)

# # ──────────────────────────────────────────────────────────────────────────────
# # Serve static frontend
# # ──────────────────────────────────────────────────────────────────────────────
# frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
# if os.path.exists(frontend_path):
#     app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import asyncio
import hashlib
import os
import time
import re

import requests
from fastapi import APIRouter, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel

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
# Thread pool (keep small on free tiers)
# ──────────────────────────────────────────────────────────────────────────────
executor = ThreadPoolExecutor(max_workers=int(os.getenv("MAX_WORKERS", "2")))

# ──────────────────────────────────────────────────────────────────────────────
# In-memory cache with TTL (to stay up-to-date)
# ──────────────────────────────────────────────────────────────────────────────
FACT_TTL_SECONDS = int(os.getenv("FACT_TTL_SECONDS", "3600"))  
fact_cache: dict[str, dict] = {}
fact_cache_ts: dict[str, float] = {}


def cache_get(key: str) -> dict | None:
    ts = fact_cache_ts.get(key)
    if not ts:
        return None
    if time.time() - ts > FACT_TTL_SECONDS:
        fact_cache.pop(key, None)
        fact_cache_ts.pop(key, None)
        return None
    return fact_cache.get(key)


def cache_set(key: str, value: dict) -> None:
    fact_cache[key] = value
    fact_cache_ts[key] = time.time()


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
        "gemini-2.5-pro",
    ]
    for p in preferred:
        if p in models:
            return p

    for m in models:
        if "gemini" in m.lower():
            return m
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Serper NEWS search (up-to-date)
# ──────────────────────────────────────────────────────────────────────────────
SERPER_NEWS_URL = "https://google.serper.dev/news"


def search_news(query: str, *, num: int = 8) -> dict[str, Any]:
    """
    Up-to-date search via Serper News API.
    Returns structured news items.
    """
    for gl, hl in (("bg", "bg"), ("us", "en")):
        try:
            r = requests.post(
                SERPER_NEWS_URL,
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "q": query,
                    "gl": gl,
                    "hl": hl,
                    "num": num,
                },
                timeout=12,
            )
            if not r.ok:
                continue

            data = r.json()
            news = data.get("news", []) or []
            if news:
                return {"query": query, "gl": gl, "hl": hl, "news": news}

        except Exception as e:
            print(f"News search error: {e}")
            continue

    return {"query": query, "news": []}


def news_context(news_data: dict[str, Any], *, max_chars: int = 2500) -> str:
    items = (news_data.get("news") or [])[:8]
    parts: list[str] = []

    for i, it in enumerate(items, start=1):
        title = (it.get("title") or "").strip()
        snippet = (it.get("snippet") or "").strip()
        link = (it.get("link") or "").strip()
        date = (it.get("date") or "").strip()
        source = (it.get("source") or "").strip()

        block = f"[{i}] {title}\n{snippet}\n{source} {date}\n{link}".strip()
        parts.append(block)

    if not parts:
        return "Няма намерена информация."

    return "\n\n".join(parts)[:max_chars]


# ──────────────────────────────────────────────────────────────────────────────
# Special hard overrides (no API calls, guaranteed output format)
# ──────────────────────────────────────────────────────────────────────────────
def special_answer_if_any(claim: str) -> str | None:
    """
    Hard override for specific "special questions".
    Returns a fully formatted answer that matches your rule:
      "Вярно - ..." or "Невярно - ..."
    or None if no special match.
    """
    q = (claim or "").strip().lower()

    # Detect "comparison / better" intent (bg + en + slang)
    better_patterns = [
        "кой е по-добър",
        "кой е по добър",
        "кой е по-добрия",
        "кой е по добрия",
        "по-добър",
        "по добър",
        "who is better",
        "which is better",
        "better",
    ]
    is_better_question = any(p in q for p in better_patterns)

    # Barca vs Real
    has_barca = any(x in q for x in ["барса", "барселона", "barca", "barcelona"])
    has_real = any(x in q for x in ["реал", "реал мадрид", "real", "real madrid"])
    if is_better_question and has_barca and has_real:
        return "Вярно - Барселона е по-добрият отбор."

    # Messi vs Ronaldo
    has_messi = any(x in q for x in ["меси", "lionel messi", "messi"])
    has_ron = any(x in q for x in ["роналдо", "cristiano ronaldo", "ronaldo", "cr7"])
    if is_better_question and has_messi and has_ron:
        return "Вярно - Меси е по-добрият футболист."

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Gemini fact-check (Serper News -> Gemini verdict)
# ──────────────────────────────────────────────────────────────────────────────
def run_llm(claim: str) -> str:
    # 1) Hard override BEFORE any API calls
    special = special_answer_if_any(claim)
    if special:
        return special

    # 2) Get news context
    news_data = search_news(claim)
    context = news_context(news_data, max_chars=2500)

    today = datetime.now(timezone.utc).date().isoformat()

    prompt = f"""
Отговаряй САМО на български език.
Днешна дата (UTC): {today}

Провери дали твърдението е вярно КЪМ ДНЕШНА ДАТА, използвайки САМО информацията по-долу (Новини).

Твърдение:
{claim}

Информация (Новини):
{context}

Правила за отговор:
1) Първото изречение трябва да бъде САМО: "Вярно - " или "Невярно - "
2) Второто изречение:
   - ако е вярно: кратко обяснение
   - ако е невярно: правилния факт
3) Не използвай фрази като: "Според", "Вероятно", "Изглежда", "Възможно е", "В даден сайт се споменава"
4) Ако в (Новини) няма достатъчно информация, отговори ТОЧНО така:
   "Невярно - Няма достатъчно потвърдена информация в предоставените новини."

Отговор:
""".strip()

    model = pick_best_model()
    if not model:
        return "Грешка при AI анализ: Няма налични Gemini модели за този API ключ."

    try:
        resp = gemini_client.models.generate_content(model=model, contents=prompt)
        text = (resp.text or "").strip()

        # 3) Enforce your required prefix format
        if not (text.startswith("Вярно - ") or text.startswith("Невярно - ")):
            return "Невярно - Няма достатъчно потвърдена информация в предоставените новини."

        # Optional: keep it reasonably short
        return text[:600].strip()

    except Exception as e:
        return f"Грешка при AI анализ: {str(e)}"


# ──────────────────────────────────────────────────────────────────────────────
# Hugging Face Inference API helpers (DO NOT crash the server)
# ──────────────────────────────────────────────────────────────────────────────
def normalize_hf_model(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("http://") or s.startswith("https://"):
        if "/models/" in s:
            s = s.split("/models/", 1)[1]
        else:
            parts = s.rstrip("/").split("/")[-2:]
            s = "/".join(parts)
    if s.startswith("models/"):
        s = s[len("models/") :]
    return s


HF_IMAGE_MODEL = normalize_hf_model(os.getenv("HF_IMAGE_MODEL", "umm-maybe/AI-image-detector"))
HF_TEXT_MODEL = normalize_hf_model(os.getenv("HF_TEXT_MODEL", "roberta-base-openai-detector"))

HF_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Accept": "application/json",
}


def hf_image_classify(image_bytes: bytes):
    model = HF_IMAGE_MODEL
    url = f"https://router.huggingface.co/hf-inference/models/{model}"

    headers = {
        **HF_HEADERS,
        "Content-Type": "application/octet-stream",  # IMPORTANT
    }

    r = requests.post(url, headers=headers, data=image_bytes, timeout=60)

    if r.status_code == 503:
        return [{"label": "LOADING", "score": 0.0}]

    if not r.ok:
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
    return {"status": "AI backend работи", "api": "Gemini + Serper News + HF Inference"}


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

    cached = cache_get(cache_key)
    if cached:
        return cached

    loop = asyncio.get_event_loop()
    result_text = await loop.run_in_executor(executor, run_llm, data.claim)

    response = {"result": result_text}
    cache_set(cache_key, response)
    return response


app.include_router(api)

# ──────────────────────────────────────────────────────────────────────────────
# Serve static frontend
# ──────────────────────────────────────────────────────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "Frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")