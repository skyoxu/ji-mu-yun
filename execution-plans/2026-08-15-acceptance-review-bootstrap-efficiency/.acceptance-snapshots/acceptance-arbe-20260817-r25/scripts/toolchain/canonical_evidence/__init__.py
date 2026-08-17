"""Repository-neutral canonical evidence primitive (AD-4, AD-5)."""

from .core import canonical_bytes, domain_hash, normalize_repository_path, parse_json_strict, validate_content_identity

__all__ = ["canonical_bytes", "domain_hash", "normalize_repository_path", "parse_json_strict", "validate_content_identity"]
