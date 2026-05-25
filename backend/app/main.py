from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db
from app.services.ingestion import run_ingestion


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-assisted remote job verification API for hackathon demos.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def ingestion_scheduler() -> None:
    await asyncio.to_thread(run_ingestion)
    while True:
        await asyncio.sleep(settings.ingestion_interval_seconds)
        await asyncio.to_thread(run_ingestion)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    if settings.ingestion_enabled:
        app.state.ingestion_task = asyncio.create_task(ingestion_scheduler())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    task = getattr(app.state, "ingestion_task", None)
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app.include_router(router)
