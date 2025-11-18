from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Team Emotional Intelligence Backend",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Backend running", "message": "Hello from FastAPI"}

@app.post("/analyze")
def analyze_message(data: dict):
    """
    Placeholder until real AI logic is added in Phase 2.
    """
    return {
        "sentiment": "neutral",
        "emotion": "none",
        "stress_score": 0,
        "category": "general",
        "suggested_reply": "Thank you for your message.",
    }
