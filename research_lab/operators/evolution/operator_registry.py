"""Versioned operator registry for operator evolution."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class OperatorVersion:
    """A specific version of an operator within a family."""
    family: str
    version: str
    callable_ref: Callable[..., Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: float = 0.0
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "version": self.version,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
            "is_active": self.is_active,
        }


class VersionedOperatorRegistry:
    """Registry that tracks operator families and their versioned variants."""

    def __init__(self) -> None:
        # family → version → OperatorVersion
        self._registry: dict[str, dict[str, OperatorVersion]] = {}
        # family → active version string
        self._active: dict[str, str] = {}

    def register(
        self,
        operator_family: str,
        version: str,
        callable_ref: Callable[..., Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OperatorVersion:
        """Register an operator version. First version auto-becomes active."""
        entry = OperatorVersion(
            family=operator_family,
            version=version,
            callable_ref=callable_ref,
            metadata=metadata or {},
            registered_at=time.time(),
        )
        family_versions = self._registry.setdefault(operator_family, {})
        family_versions[version] = entry

        # Auto-activate first version
        if operator_family not in self._active:
            self._active[operator_family] = version
            entry.is_active = True

        return entry

    def get(
        self,
        operator_family: str,
        version: str | None = None,
    ) -> OperatorVersion | None:
        """Get a specific version, or active version if version is None."""
        family_versions = self._registry.get(operator_family, {})
        if version is not None:
            return family_versions.get(version)
        # Return active
        active_ver = self._active.get(operator_family)
        if active_ver:
            return family_versions.get(active_ver)
        return None

    def list_versions(self, operator_family: str) -> list[OperatorVersion]:
        """List all registered versions for a family, ordered by registration time."""
        versions = list(self._registry.get(operator_family, {}).values())
        return sorted(versions, key=lambda v: v.registered_at)

    def list_families(self) -> list[str]:
        """List all registered operator families."""
        return sorted(self._registry.keys())

    def active_version(self, operator_family: str) -> str | None:
        """Get the active version string for a family."""
        return self._active.get(operator_family)

    def set_active(self, operator_family: str, version: str) -> OperatorVersion:
        """Promote a version to active. Raises KeyError if version not registered."""
        family_versions = self._registry.get(operator_family, {})
        if version not in family_versions:
            raise KeyError(f"Version {version} not registered for {operator_family}")

        # Deactivate current
        old_ver = self._active.get(operator_family)
        if old_ver and old_ver in family_versions:
            family_versions[old_ver].is_active = False

        # Activate new
        self._active[operator_family] = version
        entry = family_versions[version]
        entry.is_active = True
        return entry
