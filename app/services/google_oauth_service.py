import urllib.parse
from typing import Optional, Dict, Any
import logging
import httpx
from app.config import settings

logger = logging.getLogger("caresync.google_oauth")

class GoogleOAuthService:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.is_configured = settings.is_google_oauth_configured

    def get_authorization_url(self, redirect_uri: str, state: str = "login") -> str:
        """Generates Google OAuth 2.0 sign-in URL"""
        if not self.is_configured:
            # Sandbox mock Google Auth page
            return f"{settings.APP_URL}/auth/google/mock?state={state}"

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
            "prompt": "select_account"
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_user(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """Exchanges Google OAuth auth code for user profile"""
        if not self.is_configured or code.startswith("mock_"):
            return {
                "google_id": "google_sub_109283746",
                "email": "google.user@example.com",
                "full_name": "Google Verified Patient",
                "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop"
            }

        try:
            token_url = "https://oauth2.googleapis.com/token"
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(
                    token_url,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    }
                )
                if token_resp.status_code != 200:
                    logger.error(f"Failed to fetch Google token: {token_resp.text}")
                    return None

                tokens = token_resp.json()
                access_token = tokens.get("access_token")

                # Fetch user info
                userinfo_resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if userinfo_resp.status_code == 200:
                    profile = userinfo_resp.json()
                    return {
                        "google_id": profile.get("sub"),
                        "email": profile.get("email"),
                        "full_name": profile.get("name") or profile.get("email", "").split("@")[0],
                        "avatar_url": profile.get("picture")
                    }
                return None
        except Exception as e:
            logger.exception(f"Google OAuth exchange error: {e}")
            return None

google_oauth_service = GoogleOAuthService()
