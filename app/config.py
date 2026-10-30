import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "CareSync PH")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "caresync-super-secret-jwt-session-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # App URL (used for redirects and webhook callbacks)
    APP_URL: str = os.getenv("APP_URL", "http://127.0.0.1:8000").rstrip("/")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'clinic.db'}")

    # API 1: PayMongo (Sandbox / Live)
    PAYMONGO_SECRET_KEY: str = os.getenv("PAYMONGO_SECRET_KEY", "").strip()
    PAYMONGO_PUBLIC_KEY: str = os.getenv("PAYMONGO_PUBLIC_KEY", "").strip()
    PAYMONGO_BASE_URL: str = os.getenv("PAYMONGO_BASE_URL", "https://api.paymongo.com/v1").rstrip("/")

    # API 2: Semaphore SMS
    SEMAPHORE_API_KEY: str = os.getenv("SEMAPHORE_API_KEY", "").strip()
    SEMAPHORE_SENDER_NAME: str = os.getenv("SEMAPHORE_SENDER_NAME", "CareSync").strip()

    # API 3: Google Calendar API
    GOOGLE_CALENDAR_API_KEY: str = os.getenv("GOOGLE_CALENDAR_API_KEY", "").strip()

    # API 4: Google OAuth 2.0
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    # API 5: Cloudinary (Medical Document & ID Storage)
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "").strip()
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "").strip()

    # Uploads directory fallback (located inside app/static/uploads)
    UPLOAD_DIR: Path = Path(__file__).resolve().parent / "static" / "uploads"

    @property
    def is_paymongo_configured(self) -> bool:
        return bool(self.PAYMONGO_SECRET_KEY and not self.PAYMONGO_SECRET_KEY.startswith("your_"))

    @property
    def is_semaphore_configured(self) -> bool:
        return bool(self.SEMAPHORE_API_KEY and not self.SEMAPHORE_API_KEY.startswith("your_"))

    @property
    def is_google_calendar_configured(self) -> bool:
        return bool(self.GOOGLE_CALENDAR_API_KEY and not self.GOOGLE_CALENDAR_API_KEY.startswith("your_"))

    @property
    def is_google_oauth_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and not self.GOOGLE_CLIENT_ID.startswith("your_"))

    @property
    def is_cloudinary_configured(self) -> bool:
        return bool(
            self.CLOUDINARY_CLOUD_NAME and 
            self.CLOUDINARY_API_KEY and 
            self.CLOUDINARY_API_SECRET and
            not self.CLOUDINARY_CLOUD_NAME.startswith("your_")
        )

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
