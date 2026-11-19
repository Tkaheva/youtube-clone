from fastapi import FastAPI

app = FastAPI(title="YouTude", description="YouTube clone: FastAPI + PostgreSQL + SQLAlchemy (async) + S3")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "youtude-api"}