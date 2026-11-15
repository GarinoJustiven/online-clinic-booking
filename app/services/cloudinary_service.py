import os
import time
import hashlib
import logging
import uuid
import re
from pathlib import Path
from typing import Optional, Dict, Any, Set
import httpx
from fastapi import UploadFile, HTTPException, status
from app.config import settings

logger = logging.getLogger("caresync.cloudinary")

ALLOWED_EXTENSIONS: Set[str] = {"pdf", "jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp"
}
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB max per document

class CloudinaryService:
    def __init__(self):
        self.cloud_name = settings.CLOUDINARY_CLOUD_NAME
        self.api_key = settings.CLOUDINARY_API_KEY
        self.api_secret = settings.CLOUDINARY_API_SECRET
        self.is_configured = settings.is_cloudinary_configured

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        sorted_keys = sorted(params.keys())
        to_sign = "&".join([f"{k}={params[k]}" for k in sorted_keys if params[k] is not None])
        to_sign += self.api_secret
        return hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

    async def upload_file(
        self,
        file: UploadFile,
        folder: str = "caresync_medical_records"
    ) -> Dict[str, Any]:
        """
        Securely uploads a single medical document (PDF, JPG, PNG, WebP) to Cloudinary
        or falls back to secure local storage. Validates extension, MIME type, and size.
        """
        filename = Path(file.filename or "document").name
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
        file_ext = Path(clean_name).suffix.lstrip(".").lower()

        # Security check 1: Whitelist file extensions
        if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security Notice: File extension '.{file_ext}' is not permitted. Only PDF, JPG, PNG, and WebP medical records are allowed."
            )

        # Security check 2: Validate MIME content-type
        content_type = (file.content_type or "").lower().split(";")[0].strip()
        if content_type and content_type not in ALLOWED_MIME_TYPES and content_type != "application/octet-stream":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Security Notice: Content type '{content_type}' is not recognized as a safe medical document."
            )

        contents = await file.read()

        # Security check 3: Enforce maximum document size (10MB)
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the 10MB limit for secure medical documents."
            )
        if len(contents) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded document is empty."
            )

        if not self.is_configured:
            # Fallback to local uploads storage with full URL serving
            logger.info(f"Cloudinary running in local storage fallback mode for: {clean_name}")
            safe_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
            save_path = settings.UPLOAD_DIR / safe_name
            with open(save_path, "wb") as f:
                f.write(contents)

            local_url = f"/static/uploads/{safe_name}"
            return {
                "success": True,
                "mode": "LOCAL_STORAGE_SANDBOX",
                "secure_url": local_url,
                "public_id": f"local_{safe_name}",
                "format": file_ext,
                "bytes": len(contents),
                "original_filename": clean_name
            }

        # Cloudinary live upload
        timestamp = int(time.time())
        params_to_sign = {
            "folder": folder,
            "timestamp": timestamp
        }
        signature = self._generate_signature(params_to_sign)

        url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/auto/upload"
        
        try:
            data = {
                "api_key": self.api_key,
                "timestamp": str(timestamp),
                "folder": folder,
                "signature": signature
            }
            files = {
                "file": (filename, contents, file.content_type or "application/octet-stream")
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data, files=files)
                if response.status_code == 200:
                    resp_json = response.json()
                    return {
                        "success": True,
                        "mode": "CLOUDINARY_LIVE",
                        "secure_url": resp_json.get("secure_url"),
                        "public_id": resp_json.get("public_id"),
                        "format": resp_json.get("format", file_ext),
                        "bytes": resp_json.get("bytes", len(contents)),
                        "original_filename": filename
                    }
                else:
                    logger.error(f"Cloudinary API Error ({response.status_code}): {response.text}")
                    # Local fallback on error
                    safe_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
                    save_path = settings.UPLOAD_DIR / safe_name
                    with open(save_path, "wb") as f:
                        f.write(contents)
                    return {
                        "success": True,
                        "mode": "LOCAL_STORAGE_FALLBACK",
                        "secure_url": f"/static/uploads/{safe_name}",
                        "public_id": f"local_{safe_name}",
                        "format": file_ext,
                        "bytes": len(contents),
                        "original_filename": filename
                    }
        except Exception as e:
            logger.exception(f"Cloudinary upload failed: {e}")
            safe_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
            save_path = settings.UPLOAD_DIR / safe_name
            with open(save_path, "wb") as f:
                f.write(contents)
            return {
                "success": True,
                "mode": "LOCAL_STORAGE_FALLBACK",
                "secure_url": f"/static/uploads/{safe_name}",
                "public_id": f"local_{safe_name}",
                "format": file_ext,
                "bytes": len(contents),
                "original_filename": filename
            }

cloudinary_service = CloudinaryService()
