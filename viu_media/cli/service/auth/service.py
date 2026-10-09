import json
import logging
from typing import Optional

from ....core.constants import APP_DATA_DIR
from ....core.utils.file import AtomicWriter, FileLock
from ....libs.media_api.types import UserProfile
from .model import AuthModel, AuthProfile

logger = logging.getLogger(__name__)

AUTH_FILE = APP_DATA_DIR / "auth.json"


class AuthService:
    def __init__(self, media_api: str):
        self.path = AUTH_FILE
        self.media_api = media_api
        _lock_file = APP_DATA_DIR / "auth.lock"
        self._lock = FileLock(_lock_file)

    def get_auth(self) -> Optional[AuthProfile]:
        auth = self._load_auth()
        return auth.profiles.get(self.media_api)

    def save_user_profile(
        self,
        profile: UserProfile,
        token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[float] = None,
    ) -> None:
        auth = self._load_auth()
        auth.profiles[self.media_api] = AuthProfile(
            user_profile=profile,
            token=token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        self._save_auth(auth)

    def clear_user_profile(self) -> None:
        """Removes this service's saved credentials, keeping other profiles."""
        if not self.path.exists():
            return
        auth = self._load_auth()
        if auth.profiles.pop(self.media_api, None) is not None:
            self._save_auth(auth)
            logger.info(f"Cleared {self.media_api} credentials.")

    def _load_auth(self) -> AuthModel:
        if not self.path.exists():
            self._auth = AuthModel()
            self._save_auth(self._auth)
            return self._auth

        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            self._auth = AuthModel.model_validate(data)
            return self._auth

    def _save_auth(self, auth: AuthModel):
        with self._lock:
            with AtomicWriter(self.path) as f:
                json.dump(auth.model_dump(), f, indent=2)
            logger.info(f"Successfully saved user credentials to {self.path}")
