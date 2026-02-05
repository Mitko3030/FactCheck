from fastapi import FastAPI

app = FastAPI(title="FactCheck AI")

@app.get("/")
def read_root():
    return {"Sasho e gei!": "Welcome to FactCheck AI!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
