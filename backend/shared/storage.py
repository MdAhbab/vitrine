"""Local file storage — bucketed uploads with size/MIME validation."""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .settings import settings

BUCKETS: dict[str, dict] = {
    "listings": {
        "max_bytes": 10 * 1024 * 1024,
        "mimes": {"image/jpeg", "image/png", "image/webp", "image/gif"},
        "exts": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
    },
    "chats": {
        "max_bytes": 4 * 1024 * 1024,
        "mimes": {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"},
        "exts": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"},
    },
    "avatars": {
        "max_bytes": 2 * 1024 * 1024,
        "mimes": {"image/jpeg", "image/png", "image/webp"},
        "exts": {".jpg", ".jpeg", ".png", ".webp"},
    },
    "documents": {
        "max_bytes": 10 * 1024 * 1024,
        "mimes": {
            "application/pdf", "text/plain", "text/markdown",
            "application/json", "text/x-markdown",
        },
        "exts": {".pdf", ".txt", ".md", ".markdown", ".json"},
    },
}


def ensure_buckets() -> None:
    for name in BUCKETS:
        (settings.files_root / name).mkdir(parents=True, exist_ok=True)


def _kind_for_mime(mime: str) -> str:
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    return "file"


async def save_upload(file: UploadFile, *, bucket: str, user_id: str) -> dict:
    if bucket not in BUCKETS:
        raise HTTPException(400, f"Unknown bucket: {bucket}")
    rules = BUCKETS[bucket]
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > rules["max_bytes"]:
        mb = rules["max_bytes"] // (1024 * 1024)
        raise HTTPException(400, f"File exceeds {mb} MB limit for {bucket}")

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    if ext not in rules["exts"] and mime not in rules["mimes"]:
        raise HTTPException(400, f"File type not allowed for {bucket}")

    safe_ext = ext if ext in rules["exts"] else {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "image/gif": ".gif", "application/pdf": ".pdf", "text/plain": ".txt",
    }.get(mime, ".bin")

    out_name = f"{uuid.uuid4().hex}{safe_ext}"
    dest_dir = settings.files_root / bucket / user_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / out_name
    dest.write_bytes(data)

    url = f"/files/{bucket}/{user_id}/{out_name}"
    return {
        "url": url,
        "name": filename,
        "mime": mime,
        "size": len(data),
        "kind": _kind_for_mime(mime),
        "bucket": bucket,
    }
