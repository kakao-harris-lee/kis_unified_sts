#!/usr/bin/env python3
"""Validate Redis TLS configuration.

ClickHouse support has been removed from the runtime stack, so this smoke
script only checks Redis TLS-related wiring.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


@dataclass
class ValidationResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_pass(self, message: str) -> None:
        self.passed.append(message)

    def add_fail(self, message: str) -> None:
        self.failed.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def test_redis_tls_disabled(result: ValidationResult) -> None:
    os.environ["REDIS_TLS_ENABLED"] = "false"
    try:
        from shared.config.tls import build_redis_tls_params

        params = build_redis_tls_params()
        if params == {}:
            result.add_pass("Redis TLS disabled params are empty")
        else:
            result.add_fail(f"Redis TLS disabled params not empty: {params}")
    except Exception as exc:
        result.add_fail(f"Redis TLS disabled check failed: {exc}")


def test_redis_tls_enabled(result: ValidationResult) -> None:
    os.environ["REDIS_TLS_ENABLED"] = "true"
    os.environ.setdefault("REDIS_TLS_CERT_REQS", "none")
    try:
        from shared.config.tls import build_redis_tls_params

        params = build_redis_tls_params()
        if params.get("ssl") is True:
            result.add_pass("Redis TLS enabled params include ssl=True")
        else:
            result.add_fail(f"Redis TLS enabled params missing ssl=True: {params}")
    except Exception as exc:
        result.add_fail(f"Redis TLS enabled check failed: {exc}")


def verify_environment(result: ValidationResult) -> None:
    if _truthy(os.environ.get("REDIS_TLS_ENABLED")):
        result.add_pass("REDIS_TLS_ENABLED is set")
    else:
        result.add_warning("REDIS_TLS_ENABLED is not enabled in current env")


def main() -> int:
    result = ValidationResult()
    test_redis_tls_disabled(result)
    test_redis_tls_enabled(result)
    verify_environment(result)

    print("Redis TLS validation")
    print(
        f"passed={len(result.passed)} failed={len(result.failed)} warnings={len(result.warnings)}"
    )
    for message in result.passed:
        print(f"PASS {message}")
    for message in result.warnings:
        print(f"WARN {message}")
    for message in result.failed:
        print(f"FAIL {message}")
    return 0 if not result.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
