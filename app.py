# app.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from datetime import datetime
import os
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
INDEX_PATH = ROOT / "index.html"

app = FastAPI(title="Bright Futures - FastAPI")

# Optional: allow CORS if you test from other origins (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENV = os.environ.get("ENV", "development").lower()
DEBUG = ENV != "production"

# Dev-only: disable caching for convenience
@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    if DEBUG:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


class DonatePayload(BaseModel):
    amount: float = Field(..., description="Donation amount in USD or INR as number")
    name: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=500)

    @validator("amount")
    def amount_must_be_positive(cls, v):
        if v is None or v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


@app.get("/", response_class=FileResponse)
async def index():
    """
    Serve the SPA index.html file from project root.
    """
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="index.html not found on server")
    return FileResponse(INDEX_PATH, media_type="text/html")


@app.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    ico = ROOT / "favicon.ico"
    if ico.exists():
        return FileResponse(ico, media_type="image/x-icon")
    raise HTTPException(status_code=404)


@app.post("/donate")
async def donate(payload: DonatePayload):
    """
    Accepts JSON payload:
      { "amount": 100, "name": "Name", "message": "Optional" }
    Returns a JSON receipt object with receipt_id and timestamp.
    """
    # Pydantic validation ensures amount > 0 etc.
    receipt_id = f"BF-{int(datetime.utcnow().timestamp())}"
    return JSONResponse(
        {
            "status": "ok",
            "receipt_id": receipt_id,
            "name": (payload.name or "Anonymous"),
            "amount": payload.amount,
            "message": (payload.message or ""),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


# SPA fallback: return index.html for other GET paths that are not static assets
@app.exception_handler(404)
async def spa_fallback(request: Request, exc):
    # If the requested path looks like a static file that exists, let 404 through
    path = request.url.path.lstrip("/")
    file_on_disk = ROOT / path
    if file_on_disk.exists():
        # real 404 for missing resource under root
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    # otherwise return SPA index
    if INDEX_PATH.exists():
        return FileResponse(INDEX_PATH, media_type="text/html")
    return JSONResponse(status_code=500, content={"detail": "index.html not found"})
