from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

# 1. Initialize the app
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # This allows all websites to access your API
    allow_methods=["*"],
    allow_headers=["*"],
)
# 2. Load your specific tiny model
# LABEL_0 is typically 'Fake' and LABEL_1 is 'Real' for this model
pipe = pipeline("text-classification", model="mrm8488/bert-tiny-finetuned-fake-news-detection")

class NewsArticle(BaseModel):
    text: str

@app.post("/check-news")
async def check_news(article: NewsArticle):
    # Perform the detection
    prediction = pipe(article.text)
    
    # Clean up the output for your website
    raw_label = prediction[0]['label']
    score = round(prediction[0]['score'] * 100, 2)
    
    # Map the labels to human-readable text
    # Note: If your testing shows the labels are reversed, just swap these
    verdict = "FAKE" if raw_label == "LABEL_0" else "REAL"
    
    return {
        "verdict": verdict,
        "confidence": f"{score}%",
        "raw_data": prediction
    }