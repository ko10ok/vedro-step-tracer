"""Маскирование чувствительных данных в значениях перед выводом."""

__all__ = ("mask_secrets",)


def mask_secrets(value: str) -> str:
    """Маскирует пароль в строках вида scheme://user:password@host."""
    if "://" in value and "@" in value:
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(value)
            if parsed.password:
                replaced = parsed._replace(
                    netloc=(f"{parsed.username}:***@{parsed.hostname}" +
                            (f":{parsed.port}" if parsed.port else ""))
                )
                return urlunparse(replaced)
        except Exception:
            pass
    return value
