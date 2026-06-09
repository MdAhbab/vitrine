"""Media service — multipart uploads to bucketed local storage."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile

from backend.shared.security import Principal, current_user
from backend.shared.storage import BUCKETS, ensure_buckets, save_upload

router = APIRouter(tags=["media"])


@router.post("/media/upload")
async def upload_media(
    file: UploadFile,
    bucket: str = "listings",
    user: Principal = Depends(current_user),
) -> dict:
    if bucket not in BUCKETS:
        raise HTTPException(400, f"Unknown bucket. Use: {', '.join(BUCKETS)}")
    ensure_buckets()
    return await save_upload(file, bucket=bucket, user_id=user.id)


@router.post("/media/upload/chat")
async def upload_chat_attachment(
    file: UploadFile,
    user: Principal = Depends(current_user),
) -> dict:
    """Chat attachments: images or PDF, max 4 MB."""
    ensure_buckets()
    return await save_upload(file, bucket="chats", user_id=user.id)


app = FastAPI(title="Vitrine media")
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "media"}
