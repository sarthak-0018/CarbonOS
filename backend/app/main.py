from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.routes.domain import router as domain_router

app = FastAPI(title="CarbonOS API", version="0.1.0", description="India-first personal carbon intelligence foundation")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(domain_router)


@app.exception_handler(HTTPException)
async def http_error_handler(_request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "REQUEST_FAILED", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"], "type": item["type"]} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Request data is invalid", "details": errors}})


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness endpoint; deliberately does not connect to or mutate the database."""
    return {"status": "ok", "service": "carbonos-api"}
