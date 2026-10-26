"""Media storage abstraction supporting local filesystem and future object stores."""

import os
import re
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)

ALLOWED_MEDIA_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10MB limit


class MediaStorage(ABC):
    """Abstract interface for storing and retrieving media assets."""

    @abstractmethod
    def save_media(self, content: bytes, mime_type: str) -> str:
        """Save media binary and return a safe unique identifier."""

    @abstractmethod
    def get_media(self, media_unique_id: str) -> tuple[bytes, str] | None:
        """Retrieve media content bytes and mime type by unique ID, or None if missing."""

    @abstractmethod
    def delete_media(self, media_unique_id: str) -> bool:
        """Delete media asset by unique ID."""

    @abstractmethod
    def cleanup_orphans(self, active_unique_ids: set[str], max_age_hours: int = 24) -> int:
        """Remove unreferenced media assets older than max_age_hours."""


class LocalMediaStorage(MediaStorage):
    """Local filesystem persistent media storage implementation."""

    def __init__(self, storage_dir: str | None = None) -> None:
        settings = get_settings()
        self.storage_dir = os.path.abspath(storage_dir or settings.media_storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)

    @staticmethod
    def _sanitize_uid(media_unique_id: str) -> str:
        """Sanitize unique ID to prevent path traversal."""
        return re.sub(r"[^a-zA-Z0-9_-]", "", media_unique_id)

    def _resolve_candidate_path(self, safe_uid: str, ext: str) -> str | None:
        """Resolve and verify path is strictly within storage_dir."""
        dest_path = os.path.abspath(os.path.join(self.storage_dir, f"{safe_uid}{ext}"))
        if not dest_path.startswith(self.storage_dir):
            return None
        return dest_path

    def save_media(self, content: bytes, mime_type: str) -> str:
        """Save media content with validation and return unique identifier."""
        if not content:
            raise ValueError("Media content cannot be empty.")
        if len(content) > MAX_IMAGE_BYTES:
            max_mb = MAX_IMAGE_BYTES // (1024 * 1024)
            raise ValueError(f"Media exceeds maximum allowed size of {max_mb}MB.")

        # Exact magic-byte verification
        is_valid_magic = False
        ext = ".jpg"
        if mime_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"):
            is_valid_magic = True
            ext = ".jpg"
        elif mime_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
            is_valid_magic = True
            ext = ".png"
        elif (
            mime_type == "image/webp"
            and content.startswith(b"RIFF")
            and len(content) > 12
            and content[8:12] == b"WEBP"
        ):
            is_valid_magic = True
            ext = ".webp"

        if not is_valid_magic:
            raise ValueError(
                "File content does not match expected image magic bytes for declared MIME type."
            )

        safe_uid = f"admin_media_{uuid.uuid4().hex}"
        dest_path = self._resolve_candidate_path(safe_uid, ext)
        if not dest_path:
            raise ValueError("Invalid destination path traversal detected.")

        with open(dest_path, "wb") as f:
            f.write(content)

        logger.info("Saved media %s (%s) to %s", safe_uid, mime_type, dest_path)
        return safe_uid

    def get_media(self, media_unique_id: str) -> tuple[bytes, str] | None:
        """Retrieve media content bytes and mime type by unique ID."""
        safe_uid = self._sanitize_uid(media_unique_id)
        if not safe_uid:
            return None

        for ext, mime in ((".jpg", "image/jpeg"), (".png", "image/png"), (".webp", "image/webp")):
            candidate = self._resolve_candidate_path(safe_uid, ext)
            if candidate and os.path.exists(candidate):
                try:
                    with open(candidate, "rb") as f:
                        data = f.read()
                    return data, mime
                except OSError as e:
                    logger.warning("Failed to read media file %s: %s", candidate, e)
                    return None

        return None

    def delete_media(self, media_unique_id: str) -> bool:
        """Delete media asset by unique ID."""
        safe_uid = self._sanitize_uid(media_unique_id)
        if not safe_uid:
            return False

        deleted = False
        for ext in (".jpg", ".png", ".webp"):
            candidate = self._resolve_candidate_path(safe_uid, ext)
            if candidate and os.path.exists(candidate):
                try:
                    os.remove(candidate)
                    deleted = True
                except OSError as e:
                    logger.warning("Failed to delete media file %s: %s", candidate, e)

        return deleted

    def cleanup_orphans(self, active_unique_ids: set[str], max_age_hours: int = 24) -> int:
        """Remove unreferenced media assets older than max_age_hours."""
        if not os.path.exists(self.storage_dir):
            return 0

        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        cleaned_count = 0

        for fname in os.listdir(self.storage_dir):
            if not fname.startswith("admin_media_"):
                continue

            file_path = os.path.join(self.storage_dir, fname)
            if not os.path.isfile(file_path):
                continue

            # Check if file matches an active unique id
            uid_stem, _ = os.path.splitext(fname)
            if uid_stem in active_unique_ids:
                continue

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC)
                if mtime < cutoff:
                    os.remove(file_path)
                    cleaned_count += 1
            except OSError as e:
                logger.warning("Failed to clean up orphan media file %s: %s", file_path, e)

        logger.info("Cleaned up %d orphan media files from %s", cleaned_count, self.storage_dir)
        return cleaned_count


def get_media_storage() -> MediaStorage:
    """Return default configured media storage service instance."""
    return LocalMediaStorage()
