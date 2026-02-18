"""""
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Download model (only runs once, then uses cache)
print("Downloading model...")
model_path = hf_hub_download(
    repo_id="INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0-GGUF",
    filename="BgGPT-Gemma-2-9B-IT-v1.0.Q4_K_M.gguf"
)

# Load model
print("Loading model...")
llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)

# Check facts
def check_fact(claim):
    prompt = f"Вярно ли е следното: {claim}\nОтговор (Вярно/Невярно с % увереност):"
    output = llm(prompt, max_tokens=50, temperature=0.3)
    return output['choices'][0]['text'].strip()

# Test
print(check_fact("Небето е синьо."))
"""
# from llama_cpp import Llama
# import requests

# def search_web(query):
#     # Use DuckDuckGo (free, no API key)
#     url = f"https://api.duckduckgo.com/?q={query}&format=json&lang=bg"
#     response = requests.get(url)
#     data = response.json()
#     return data.get("AbstractText", "")

# def check_fact(claim):
#     # First search the web
#     search_result = search_web(claim)
    
#     # Then pass to BgGPT
#     prompt = f"""Провери дали следното твърдение е вярно.
    
# Информация от интернет: {search_result}
# Твърдение: {claim}

# Отговор (Вярно/Невярно с % увереност):"""
    
#     output = llm(prompt, max_tokens=100, temperature=0.3)
#     return output['choices'][0]['text'].strip()











# from huggingface_hub import hf_hub_download
# from llama_cpp import Llama
# from duckduckgo_search import DDGS

# # ── 1. Install this first in terminal ────────────────────────────────────
# # pip install duckduckgo-search

# # ── 2. Download model (only once, then cached) ───────────────────────────
# print("Downloading model...")
# model_path = hf_hub_download(
#     repo_id="INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0-GGUF",
#     filename="BgGPT-Gemma-2-9B-IT-v1.0.Q4_K_M.gguf"
# )

# # ── 3. Load model ─────────────────────────────────────────────────────────
# print("Loading model...")
# llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)
# print("Model ready!\n")

# # ── 4. DuckDuckGo real search ─────────────────────────────────────────────
# def search_web(query):
#     try:
#         with DDGS() as ddgs:
#             results = list(ddgs.text(query, region="bg-bg", max_results=5))
#             if results:
#                 # Combine top 5 results into one context
#                 combined = " | ".join([r["body"] for r in results])
#                 return combined
#             return "Няма намерена информация."
#     except Exception as e:
#         return f"Грешка при търсене: {str(e)}"

# # ── 5. Fact check ─────────────────────────────────────────────────────────
# def check_fact(claim):
#     print(f"🔍 Searching: {claim}")
#     search_result = search_web(claim)
#     print(f"📄 Found: {search_result[:200]}...\n")  # Show first 200 chars

#     prompt = f"""Ти си система за проверка на факти. Използвай САМО информацията от интернет по-долу, за да прецениш дали твърдението е вярно.

# Информация от интернет: {search_result}

# Твърдение: {claim}

# Отговори в следния формат:
# Verdict: Вярно/Невярно/Неясно
# Увереност: X%
# Обяснение: (обясни защо, базирано на намерената информация)

# Отговор:"""

#     output = llm(prompt, max_tokens=300, temperature=0.3)
#     return output['choices'][0]['text'].strip()

# # ── 6. Run ────────────────────────────────────────────────────────────────
# while True:
#     print("=" * 50)
#     claim = input("Въведи твърдение (или 'exit' за изход): ")
    
#     if claim.lower() == "exit":
#         print("Довиждане!")
#         break

#     result = check_fact(claim)
#     print(f"\n✅ Резултат:\n{result}\n")



from huggingface_hub import hf_hub_download
from llama_cpp import Llama
import requests

SERPER_API_KEY = "3c6cba844457eff753d0c9cfd8cce7ffbf4b090e"  # paste your key here

# ── 1. Download model ─────────────────────────────────────────────────────
print("Downloading model...")
model_path = hf_hub_download(
    repo_id="INSAIT-Institute/BgGPT-Gemma-2-9B-IT-v1.0-GGUF",
    filename="BgGPT-Gemma-2-9B-IT-v1.0.Q4_K_M.gguf"
)

# ── 2. Load model ─────────────────────────────────────────────────────────
print("Loading model...")
llm = Llama(model_path=model_path, n_ctx=2048, n_threads=4, verbose=False)
print("Model ready!\n")

# ── 3. Google Search via Serper ───────────────────────────────────────────
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

        results = []

        # Get answer box if available (most accurate)
        if data.get("answerBox"):
            box = data["answerBox"]
            if box.get("answer"):
                results.append(f"Директен отговор: {box['answer']}")
            if box.get("snippet"):
                results.append(f"Обобщение: {box['snippet']}")

        # Get top organic results
        for r in data.get("organic", [])[:4]:
            if r.get("snippet"):
                results.append(r["snippet"])

        return " | ".join(results) if results else "Няма намерена информация."

    except Exception as e:
        return f"Грешка при търсене: {str(e)}"

# ── 4. Fact check ─────────────────────────────────────────────────────────
def check_fact(claim):
    print(f"🔍 Търся: {claim}")
    search_result = search_web(claim)
    print(f"📄 Намерено: {search_result[:300]}...\n")

    prompt = f"""Ти си строга система за проверка на факти. Използвай САМО информацията от интернет.

Правила:
- Ако информацията потвърждава твърдението -> Вярно
- Ако информацията противоречи на твърдението -> Невярно
- "Неясно" е ЗАБРАНЕНО
- Увереността трябва да е между 70% и 100%

Информация от интернет: {search_result}

Твърдение: {claim}

Отговори ТОЧНО така:
Verdict: Вярно/Невярно
Увереност: X%
Обяснение: (1-2 изречения)

Отговор:"""

    output = llm(prompt, max_tokens=300, temperature=0.1)
    return output['choices'][0]['text'].strip()

# ── 5. Run ────────────────────────────────────────────────────────────────
while True:
    print("=" * 50)
    claim = input("Въведи твърдение (или 'exit' за изход): ")

    if claim.lower() == "exit":
        print("Довиждане!")
        break

    result = check_fact(claim)
    print(f"\n✅ Резултат:\n{result}\n")