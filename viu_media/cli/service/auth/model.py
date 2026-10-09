from typing import Dict, Optional

from pydantic import BaseModel, Field

from ....libs.media_api.types import UserProfile

AUTH_VERSION = "1.0"


class AuthProfile(BaseModel):
    user_profile: UserProfile
    token: str
    refresh_token: Optional[str] = None
    # Unix timestamp after which the access token must be refreshed.
    expires_at: Optional[float] = None


class AuthModel(BaseModel):
    version: str = Field(default=AUTH_VERSION)
    profiles: Dict[str, AuthProfile] = Field(default_factory=dict)
