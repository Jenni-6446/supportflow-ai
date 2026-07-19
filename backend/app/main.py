from fastapi import FastAPI

from app.routes.analysis import router as analysis_router
from app.routes.diagnosis import router as diagnosis_router
from app.routes.documentation import router as documentation_router


app = FastAPI(title="SupportFlow AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(analysis_router)
app.include_router(diagnosis_router)
app.include_router(documentation_router)
