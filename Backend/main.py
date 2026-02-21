from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from transformers import pipeline
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from PIL import Image
import io
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()



class FactInput(BaseModel):
    claim: str
# This MUST be the first middleware added
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes come AFTER middleware



print("Loading models...")

# ───── Image detector ─────
image_detector = pipeline(
    "image-classification",
    model="capcheck/ai-human-generated-image-detection"
)

# ───── Text detector ─────
text_detector = pipeline(
    "text-classification",
    model="fakespot-ai/roberta-base-ai-text-detection-v1"
)

# ───── Fact-check LLM ─────
model_path = hf_hub_download(
    repo_id="INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0-GGUF",
    filename="BgGPT-Gemma-2-9B-IT-v1.0.Q4_K_M.gguf"
)

llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)

SERPER_API_KEY = "3c6cba844457eff753d0c9cfd8cce7ffbf4b090e"

print("All models loaded!")

# ───── Schemas ─────
class TextInput(BaseModel):
    text: str

class FactInput(BaseModel):
    claim: str

# ───── Web search ─────
def search_web(query):
    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={"q": query, "gl": "bg", "hl": "bg", "num": 5}
        )

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

        return " | ".join(snippets)

    except Exception as e:
        return f"Search error: {e}"

# ───── Endpoints ─────

@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")

    result = image_detector(image)

    return {"result": result}


@app.post("/detect-text")
def detect_text(data: TextInput):
    result = text_detector(data.text)
    return {"result": result}


@app.post("/fact-check")
def fact_check(data: FactInput):

    context = search_web(data.claim)

    prompt = f"""
Използвай САМО информацията:

{context}

Твърдение: {data.claim}

Отговор:
Verdict: Вярно/Невярно
Увереност: X%
Обяснение:
"""

    output = llm(prompt, max_tokens=300, temperature=0.1)

    return {
        "result": output["choices"][0]["text"].strip()
    }



@app.get("/")
def home():
    return {"status": "AI backend running"}
