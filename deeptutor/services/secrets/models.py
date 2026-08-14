from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SecretMigrationStatus:
    backend: str
    plaintext_count: int
    reference_count: int
    configured_count: int

    @property
    def migration_required(self) -> bool:
        return self.plaintext_count > 0

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "migration_required": self.migration_required}


__all__ = ["SecretMigrationStatus"]
