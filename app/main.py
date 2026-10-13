from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import pool, run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Smart Desk Assistant API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
