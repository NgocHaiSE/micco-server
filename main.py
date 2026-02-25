from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import auth, documents, dashboard, chat

# ─── Create tables ───────────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ─── App ─────────────────────────────────────────────────────
app = FastAPI(
    title="Micco AI API",
    description="Enterprise Document Management API with AI Assistant",
    version="1.0.0",
)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ───────────────────────────────────────
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(chat.router)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "app": "Micco AI API", "version": "1.0.0"}
