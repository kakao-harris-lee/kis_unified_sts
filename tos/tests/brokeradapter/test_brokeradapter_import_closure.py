"""§2.2-① network-absence canary for ``tos.brokeradapter`` — closure canaries are table-driven."""

from __future__ import annotations

import ast
from pathlib import Path

from .._closure_policy import SRC_ROOT

_SRC = SRC_ROOT / "brokeradapter"

_NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "telnetlib",
        "asyncio",
        "selectors",
        "subprocess",
        "ctypes",
        "requests",
        "aiohttp",
        "httpx",
        "websocket",
        "websockets",
        "grpc",
    }
)
_CREDENTIAL_FRAGMENTS = (
    "app_key",
    "app_secret",
    "access_token",
    "api_key",
    "secret_key",
    "bearer",
)
_CLOCK_MODULES = frozenset({"time", "datetime"})
_RNG_MODULES = frozenset({"random", "secrets", "uuid"})
_DYNAMIC_CALL_NAMES = frozenset({"exec", "eval", "compile", "__import__"})
_AMBIENT_ENV_ATTRS = frozenset({"environ", "getenv"})


def _network_offenders(path: Path) -> list[str]:
    """Every network / credential / clock / RNG / escape offender in one source."""
    offenders: list[str] = []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _NETWORK_MODULES:
                    offenders.append(
                        f"{path.name}:{node.lineno} network import {alias.name}"
                    )
                if root in _CLOCK_MODULES:
                    offenders.append(
                        f"{path.name}:{node.lineno} clock import {alias.name}"
                    )
                if root in _RNG_MODULES:
                    offenders.append(
                        f"{path.name}:{node.lineno} rng import {alias.name}"
                    )
                if root == "importlib":
                    offenders.append(f"{path.name}:{node.lineno} import importlib")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in _NETWORK_MODULES:
                offenders.append(
                    f"{path.name}:{node.lineno} network from {module} import ..."
                )
            if root in _CLOCK_MODULES:
                offenders.append(
                    f"{path.name}:{node.lineno} clock from {module} import ..."
                )
            if root in _RNG_MODULES:
                offenders.append(
                    f"{path.name}:{node.lineno} rng from {module} import ..."
                )
            if root == "importlib":
                offenders.append(f"{path.name}:{node.lineno} from importlib import ...")
            if module == "os":
                for alias in node.names:
                    if alias.name in _AMBIENT_ENV_ATTRS:
                        offenders.append(
                            f"{path.name}:{node.lineno} from os import {alias.name}"
                        )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_CALL_NAMES:
                offenders.append(f"{path.name}:{node.lineno} call {func.id}()")
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                offenders.append(f"{path.name}:{node.lineno} call import_module()")
        elif isinstance(node, ast.Attribute):
            if (
                node.attr in _AMBIENT_ENV_ATTRS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                offenders.append(f"{path.name}:{node.lineno} os.{node.attr}")
        elif isinstance(node, (ast.Name, ast.arg)):
            identifier = node.id if isinstance(node, ast.Name) else node.arg
            lowered = identifier.lower()
            for fragment in _CREDENTIAL_FRAGMENTS:
                if fragment in lowered:
                    offenders.append(
                        f"{path.name}:{node.lineno} credential name {identifier}"
                    )
    return offenders


def test_the_package_contains_no_network_credential_clock_or_rng() -> None:
    """(§2.2-① / §5.1) The mechanical evidence that a real transport cannot live in ``tos/``."""
    sources = sorted(_SRC.rglob("*.py"))
    assert sources, f"no tos.brokeradapter source files found under {_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_network_offenders(path))
    assert offenders == [], (
        "tos.brokeradapter must contain no network, credential, clock, or RNG construct — its "
        f"absence is what makes design #34 §2's judgement true: {offenders}"
    )


def test_the_network_canary_detects_a_planted_violation(tmp_path: Path) -> None:
    """(both ways) Green above is evidence the canary works, not that it was neutered."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import socket\n"
        "import ssl\n"
        "import asyncio\n"
        "import requests\n"
        "from http import client\n"
        "import time\n"
        "import uuid\n"
        "import importlib\n"
        "from os import environ\n"
        "app_key = 'x'\n"
        "def f(access_token):\n"
        "    return access_token\n"
        "y = eval('1')\n",
        encoding="utf-8",
    )
    joined = " ".join(_network_offenders(planted))
    for expected in (
        "network import socket",
        "network import ssl",
        "network import asyncio",
        "network import requests",
        "network from http import",
        "clock import time",
        "rng import uuid",
        "import importlib",
        "from os import environ",
        "credential name app_key",
        "credential name access_token",
        "eval()",
    ):
        assert expected in joined, f"the network canary missed a planted {expected}"
