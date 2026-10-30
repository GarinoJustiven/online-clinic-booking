import logging
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.orm import Session
from app.config import settings
from app.models import SmsLog

logger = logging.getLogger("caresync.semaphore")

class SemaphoreService:
    def __init__(self):
        self.api_key = settings.SEMAPHORE_API_KEY
        self.sender_name = settings.SEMAPHORE_SENDER_NAME
        self.base_url = "https://api.semaphore.co/api/v4/messages"
        self.is_configured = settings.is_semaphore_configured

    async def send_sms(
        self,
        recipient_phone: str,
        message: str,
        recipient_name: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Sends an SMS via Semaphore API v4 or records a simulated SMS in the database.
        """
        # Clean phone number (e.g., +63917... or 0917...)
        clean_phone = recipient_phone.strip() if recipient_phone else "09000000000"

        if not self.is_configured:
            logger.info(f"[SEMAPHORE SANDBOX] SMS to {clean_phone}: {message}")
            log_entry = None
            if db:
                log_entry = SmsLog(
                    recipient_phone=clean_phone,
                    recipient_name=recipient_name,
                    message=message,
                    provider="Semaphore (Sandbox Mock)",
                    status="MOCK_SIMULATED",
                    message_id=f"smph_sim_{int(hash(message) % 1000000)}"
                )
                db.add(log_entry)
                db.commit()
                db.refresh(log_entry)
            
            return {
                "success": True,
                "mode": "SANDBOX_SIMULATION",
                "status": "MOCK_SIMULATED",
                "phone": clean_phone,
                "message": message,
                "log_id": log_entry.id if log_entry else None
            }

        # Real Semaphore API Call
        payload = {
            "apikey": self.api_key,
            "number": clean_phone,
            "message": message,
        }
        if self.sender_name and self.sender_name != "CareSync":
            payload["sendername"] = self.sender_name

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.base_url, data=payload)
                if response.status_code == 200:
                    resp_data = response.json()
                    message_id = resp_data[0].get("message_id") if isinstance(resp_data, list) and resp_data else None
                    if db:
                        log_entry = SmsLog(
                            recipient_phone=clean_phone,
                            recipient_name=recipient_name,
                            message=message,
                            provider="Semaphore Live",
                            status="SENT",
                            message_id=str(message_id) if message_id else "ok"
                        )
                        db.add(log_entry)
                        db.commit()
                    return {"success": True, "mode": "SEMAPHORE_LIVE", "status": "SENT", "response": resp_data}
                else:
                    logger.error(f"Semaphore API returned {response.status_code}: {response.text}")
                    if db:
                        log_entry = SmsLog(
                            recipient_phone=clean_phone,
                            recipient_name=recipient_name,
                            message=message,
                            provider="Semaphore Live",
                            status=f"FAILED ({response.status_code})",
                            message_id=None
                        )
                        db.add(log_entry)
                        db.commit()
                    return {"success": False, "mode": "SEMAPHORE_LIVE", "status": "FAILED", "error": response.text}
        except Exception as e:
            logger.exception(f"Semaphore network exception: {e}")
            if db:
                log_entry = SmsLog(
                    recipient_phone=clean_phone,
                    recipient_name=recipient_name,
                    message=message,
                    provider="Semaphore Live",
                    status="FAILED (EXCEPTION)",
                    message_id=None
                )
                db.add(log_entry)
                db.commit()
            return {"success": False, "mode": "SEMAPHORE_LIVE", "status": "FAILED", "error": str(e)}

semaphore_service = SemaphoreService()
