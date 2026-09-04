from fastapi import FastAPI

app = FastAPI(
    title="AI SRE Incident Agent",
    version="0.1.0",
)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ai-sre-incident-agent",
    }