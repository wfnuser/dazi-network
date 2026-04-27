from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.routers import health, profile, search, interest, connections


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    await db.init_db()
    yield
    await db.close_pool()


app = FastAPI(
    title="dazi-network",
    description="Matching engine backend for the dazi social platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(profile.router)
app.include_router(search.router)
app.include_router(interest.router)
app.include_router(connections.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "server_error",
            "message": "Internal server error",
        },
    )
