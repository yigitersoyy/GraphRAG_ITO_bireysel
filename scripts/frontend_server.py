"""Local static workspace + same-origin API proxy; no secrets are sent to the browser."""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
HOP_HEADERS = {
    "host",
    "connection",
    "content-length",
    "content-encoding",
    "transfer-encoding",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "upgrade",
}


def create_frontend(upstream: str, directory: Path = DIST) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(base_url=upstream, timeout=240, trust_env=False) as client:
            app.state.client = client
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health/ui")
    @app.get("/_stcore/health")
    def health() -> PlainTextResponse:
        return PlainTextResponse(
            "ok" if (directory / "index.html").exists() else "build missing",
            status_code=200 if (directory / "index.html").exists() else 503,
        )

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @app.api_route("/health/{path:path}", methods=["GET"])
    async def proxy(request: Request, path: str) -> Response:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 12 * 1024 * 1024:
                return JSONResponse(
                    {
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": "request body exceeds configured limit",
                        }
                    },
                    status_code=413,
                )
        try:
            result = await request.app.state.client.request(
                request.method,
                request.url.path + ("?" + request.url.query if request.url.query else ""),
                content=bytes(body),
                headers={k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS},
            )
            return Response(
                result.content,
                status_code=result.status_code,
                headers={k: v for k, v in result.headers.items() if k.lower() not in HOP_HEADERS},
            )
        except httpx.HTTPError:
            return JSONResponse(
                {
                    "error": {
                        "code": "API_UNREACHABLE",
                        "message": "API is unavailable; check the API service",
                    }
                },
                status_code=503,
            )

    app.mount("/", StaticFiles(directory=directory, html=True))
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--upstream", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    uvicorn.run(create_frontend(args.upstream), host="127.0.0.1", port=args.port, access_log=False)
