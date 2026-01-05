from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api.analyze import router as analyze_router


def create_app() -> FastAPI:
    app = FastAPI(title="WDSP Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"] ,
        allow_headers=["*"],
    )

    app.include_router(analyze_router)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/download/{file_name}")
    def download(file_name: str):
        # expects file_name like "<export_id>.csv"
        base = Path(settings.exports_dir)
        target = (base / file_name).resolve()
        if base.resolve() not in target.parents:
            return {"error": "invalid file"}
        if not target.exists():
            return {"error": "not found"}
        return FileResponse(path=target, media_type="text/csv", filename=file_name)

    return app


app = create_app()
