from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status

from app import __version__
from app.config import Settings
from app.models import HealthResponse, QARequest, QAResponse
from app.service import QAService


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.qa_service = QAService(resolved)
        yield

    application = FastAPI(
        title="史鉴 RAG API",
        description="面向历史学习的可溯源混合检索问答 API",
        version=__version__,
        lifespan=lifespan,
    )

    def service(request: Request) -> QAService:
        return request.app.state.qa_service

    @application.get(
        "/healthz",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "Database is unavailable"}},
        tags=["system"],
    )
    def health(request: Request, response: Response) -> HealthResponse:
        result = service(request).health()
        if result.status == "unhealthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result

    @application.post("/api/v1/qa", response_model=QAResponse, tags=["qa"])
    def qa(payload: QARequest, request: Request) -> QAResponse:
        try:
            return service(request).answer(payload)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return application


app = create_app()
