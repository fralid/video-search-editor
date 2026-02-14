from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {"status": "ok", "service": "Video Search & Editor (Standalone)"}


@router.get("/api/health")
def health():
    return {"status": "ok"}
