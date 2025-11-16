# Main application file
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class WebhookData(BaseModel):
    data: dict | None = None

@app.get("/")
def home():
    return {"status": "Backend running with FastAPI!"}

@app.post("/webhook")
def receive_webhook(payload: WebhookData):
    print("Webhook received:", payload)
    return {"message": "Webhook OK"}
