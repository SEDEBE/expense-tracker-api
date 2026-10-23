from django.conf import settings
from google.auth.transport import requests
from google.oauth2 import id_token

# Reused between calls: it caches Google's public keys instead of downloading them every time.
_transport = requests.Request()


def google_token_verify(credential: str) -> dict:
    """Check a Google ID token (signature, expiry, audience) and return its claims.

    Raises ValueError if the token is not valid for this app.
    """
    claims = id_token.verify_oauth2_token(credential, _transport, settings.GOOGLE_CLIENT_ID)
    if not claims.get("email_verified"):
        raise ValueError("Google has not verified this email address")
    return claims
