import os
import time
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from fastapi import UploadFile
from app.config import settings

logger = logging.getLogger("caresync.cloudinary")

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
        Uploads a file (PDF, JPG, PNG, etc.) to Cloudinary or falls back to local storage.
        """
        contents = await file.read()
        filename = file.filename or "uploaded_document"
        file_ext = Path(filename).suffix.lstrip(".").lower() or "bin"

        if not self.is_configured:
            # Fallback to local uploads storage with full URL serving
            logger.info(f"Cloudinary running in local storage fallback mode for: {filename}")
            safe_name = f"{uuid.uuid4().hex[:12]}_{filename.replace(' ', '_')}"
            save_path = settings.UPLOAD_DIR / safe_name
            with open(save_path, "wb") as f:
                f.write(contents)

            local_url = f"{settings.APP_URL}/static/uploads/{safe_name}"
            return {
                "success": True,
                "mode": "LOCAL_STORAGE_SANDBOX",
                "secure_url": local_url,
                "public_id": f"local_{safe_name}",
                "format": file_ext,
                "bytes": len(contents),
                "original_filename": filename
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
                    safe_name = f"{uuid.uuid4().hex[:12]}_{filename.replace(' ', '_')}"
                    save_path = settings.UPLOAD_DIR / safe_name
                    with open(save_path, "wb") as f:
                        f.write(contents)
                    return {
                        "success": True,
                        "mode": "LOCAL_STORAGE_FALLBACK",
                        "secure_url": f"{settings.APP_URL}/static/uploads/{safe_name}",
                        "public_id": f"local_{safe_name}",
                        "format": file_ext,
                        "bytes": len(contents),
                        "original_filename": filename
                    }
        except Exception as e:
            logger.exception(f"Cloudinary upload failed: {e}")
            safe_name = f"{uuid.uuid4().hex[:12]}_{filename.replace(' ', '_')}"
            save_path = settings.UPLOAD_DIR / safe_name
            with open(save_path, "wb") as f:
                f.write(contents)
            return {
                "success": True,
                "mode": "LOCAL_STORAGE_FALLBACK",
                "secure_url": f"{settings.APP_URL}/static/uploads/{safe_name}",
                "public_id": f"local_{safe_name}",
                "format": file_ext,
                "bytes": len(contents),
                "original_filename": filename
            }

cloudinary_service = CloudinaryService()
