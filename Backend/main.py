

# from fastapi import FastAPI, UploadFile, File
# from pydantic import BaseModel
# from transformers import pipeline
# from huggingface_hub import hf_hub_download
# from llama_cpp import Llama
# from PIL import Image
# import io
# import hashlib
# import asyncio
# import os
# import requests
# from concurrent.futures import ThreadPoolExecutor
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ───── Schemas ─────
# class TextInput(BaseModel):
#     text: str

# class FactInput(BaseModel):
#     claim: str

# # ───── Thread pool ─────
# CPU_CORES = os.cpu_count() or 4
# executor = ThreadPoolExecutor(max_workers=CPU_CORES)

# # ───── In-memory cache ─────
# fact_cache = {}

# # ───── API Key ─────
# SERPER_API_KEY = "3c6cba844457eff753d0c9cfd8cce7ffbf4b090e"

# print("Зареждане на моделите...")

# # ───── Image detector ─────
# image_detector = pipeline(
#     "image-classification",
#     model="capcheck/ai-human-generated-image-detection"
# )

# # ───── Text detector ─────
# text_detector = pipeline(
#     "text-classification",
#     model="xlm-roberta-large"
# )
# #fakespot-ai/roberta-base-ai-text-detection-v1
# # ───── BgGPT LLM ─────
# print("Изтегляне на модела...")
# model_path = hf_hub_download(
#     repo_id="INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0-GGUF",
#     filename="BgGPT-Gemma-2-9B-IT-v1.0.Q4_K_M.gguf"
# )

# print("Зареждане на модела...")
# llm = Llama(
#     model_path=model_path,
#     n_ctx=1024,
#     n_threads=CPU_CORES,
#     n_batch=512,
#     use_mlock=True,
#     verbose=False,
# )

# print("Всички модели са заредени!")


# # ───── Serper search with retry + fallback ─────
# def search_web(query: str) -> str:
#     # Try Bulgarian first, fall back to global if no results
#     for lang in (("bg", "bg"), ("us", "en")):
#         gl, hl = lang
#         for attempt in range(2):   # retry once on failure
#             try:
#                 response = requests.post(
#                     "https://google.serper.dev/search",
#                     headers={
#                         "X-API-KEY": SERPER_API_KEY,
#                         "Content-Type": "application/json"
#                     },
#                     json={
#                         "q": query,
#                         "gl": gl,
#                         "hl": hl,
#                         "num": 5,
#                         "lr": "lang_bg" if gl == "bg" else "lang_en"
#                     },
#                     timeout=6
#                 )

#                 if not response.ok:
#                     break   # bad status, try next region

#                 data = response.json()
#                 snippets = []

#                 # Answer box is the most accurate — prioritise it
#                 if data.get("answerBox"):
#                     box = data["answerBox"]
#                     if box.get("answer"):
#                         snippets.append(box["answer"])
#                     if box.get("snippet"):
#                         snippets.append(box["snippet"])

#                 for r in data.get("organic", [])[:4]:
#                     if r.get("snippet"):
#                         snippets.append(r["snippet"])

#                 if snippets:
#                     return " | ".join(snippets)

#             except requests.Timeout:
#                 pass   # retry
#             except Exception:
#                 break  # unexpected error, skip to next region

#     return "Няма намерена информация."


# # ───── BgGPT inference ─────
# def run_llm(claim: str) -> str:
#     search_result = search_web(claim)
#     print(f"📄 Намерено: {search_result[:200]}...")

#     context = search_result[:700]

#     prompt = f"""Провери следното твърдение като използваш само информацията по-долу.

# Информация: {context}

# Твърдение: {claim}

# Отговорът ти трябва да започва ЗАДЪЛЖИТЕЛНО с "Вярно" или "Невярно", последвано от тире и едно изречение.
# Забранено е да пишеш "Неясно", "Анализ" или каквото и да е друго в началото.
# Пример за правилен отговор: Вярно — България е държава в Европа.

# Отговор: """

#     output = llm(
#         prompt,
#         max_tokens=120,
#         temperature=0.1,
#         top_p=0.9,
#         repeat_penalty=1.1,
#         stop=["Твърдение:", "Информация:", "Неясно", "\n\n"]
#     )
#     return output["choices"][0]["text"].strip()


# # ───── Endpoints ─────

# @app.get("/")
# def home():
#     return {"status": "AI backend работи"}


# @app.post("/detect-image")
# async def detect_image(file: UploadFile = File(...)):
#     contents = await file.read()
#     image = Image.open(io.BytesIO(contents)).convert("RGB")
#     loop = asyncio.get_event_loop()
#     result = await loop.run_in_executor(executor, image_detector, image)
#     return {"result": result}


# @app.post("/detect-text")
# async def detect_text(data: TextInput):
#     loop = asyncio.get_event_loop()
#     result = await loop.run_in_executor(executor, text_detector, data.text)
#     return {"result": result}


# @app.post("/fact-check")
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




from fastapi import FastAPI, UploadFile, File
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
import anthropic

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fact-check.up.railway.app",
        "https://factcheck-noit.up.railway.app"
    ], 
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
SERPER_API_KEY = "3c6cba844457eff753d0c9cfd8cce7ffbf4b090e"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

print("Зареждане на моделите...")

# ───── Image detector ─────
image_detector = pipeline(
    "image-classification",
    model="capcheck/ai-human-generated-image-detection"
)
 
# ───── Text detector ─────
text_detector = pipeline(
    "text-classification",
    model="roberta-base-openai-detector"
)

print("Всички модели са заредени!")


# ───── Serper search with retry + fallback ─────
def search_web(query: str) -> str:
    for lang in (("bg", "bg"), ("us", "en")):
        gl, hl = lang
        for attempt in range(2):
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
                    break

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

            except requests.Timeout:
                pass
            except Exception:
                break

    return "Няма намерена информация."


# ───── Claude inference ─────
def run_llm(claim: str) -> str:
    search_result = search_web(claim)
    print(f"📄 Намерено: {search_result[:200]}...")

    context = search_result[:700]

    prompt = f"""Отговаряй САМО на български език.

Провери следното твърдение като използваш само информацията по-долу.

Информация: {context}

Твърдение: {claim}

Отговорът ти трябва да започва ЗАДЪЛЖИТЕЛНО с "Вярно" или "Невярно", последвано от тире и едно изречение. Забранено е да пишеш "Неясно", "Анализ" или каквото и да е друго в началото.
Пример за правилен отговор: Вярно — България е държава в Европа.

Отговор: """

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


# ───── Endpoints ─────

@app.get("/")
def home():
    return {"status": "AI backend работи"}


@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, image_detector, image)
    return {"result": result}


@app.post("/detect-text")
async def detect_text(data: TextInput):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, text_detector, data.text)
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
