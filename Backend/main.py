from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

# 1. Initialize the FastAPI app
app = FastAPI(title="FactCheck AI API")

# 2. Load the AI model (only happens once when server starts)
# Using a specific model name is better practice than leaving it blank
classifier = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

# 3. Define what the incoming data should look like
class FactRequest(BaseModel):
    text: str

# 4. Root endpoint (to fix that 404 error)
@app.get("/")
def home():
    return {"status": "FactCheck API is Live", "docs": "/docs"}

# 5. The actual processing endpoint
@app.post("/analyze")
def analyze_text(request: FactRequest):
    # Pass the text to the AI model
    result = classifier(request.text)
    
    # Return the AI's "thought" as JSON
    return {
        "original_text": request.text,
        "analysis": result
    }