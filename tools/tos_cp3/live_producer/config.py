"""Every tunable of ③, read from one YAML file. Nothing below is hardcoded.

CLAUDE.md's non-negotiable rule: thresholds, schedules and feature gates belong
in YAML, not in branches. δ (1.8 s) and G (10 s) are **operator-confirmed,
2026-10-14**; the PR-1 run (evidence
``docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md``
§1.4) only proposed them and explicitly refused to let them be written into
code ("PR-2 가 이 값을 config 로 받아야 하며, 이 문서는 코드에 박는 것을 승인하지
않는다"). Confirmation does not change where they live: the YAML carries both
values with their evidence basis, and nothing here defaults them.

An UNKNOWN key is refused rather than ignored. A silently-ignored key is how a
typo in ``missing_no_successor_timeout_s`` becomes "G is whatever the default
was" with nothing saying so.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class LiveProducerRefused(RuntimeError):
    """The producer refused to start, or refused to write. Never routed around."""


#: Keys the YAML must carry, with the Python type each is read as. There is no
#: default for any of them: a default here is a value nobody reviewed.
_REQUIRED: tuple[tuple[str, type], ...] = (
    ("env_file", str),
    ("token_cache_dir", str),
    ("strategy_yaml", str),
    ("calendar_yaml", str),
    ("execution_yaml", str),
    ("calendar_session_id", str),
    ("calendar_session_phase", str),
    ("first_poll_delay_s", float),
    ("missing_no_successor_timeout_s", float),
    ("repoll_pace_s", float),
    ("request_timeout_s", float),
    ("attempts", int),
    ("retry_pause_s", float),
    ("pace_s", float),
    ("max_pages", int),
    ("min_bars_per_day", int),
    ("max_seed_calendar_days", int),
    ("max_consecutive_produce_errors", int),
)


@dataclass(frozen=True)
class LiveProducerConfig:
    """The resolved configuration, plus the digest of the file it came from."""

    path: Path
    sha256: str
    env_file: Path
    token_cache_dir: Path
    strategy_yaml: Path
    calendar_yaml: Path
    execution_yaml: Path
    calendar_session_id: str
    calendar_session_phase: str
    #: δ — the first poll happens at ``bar boundary + first_poll_delay_s``.
    first_poll_delay_s: float
    #: G — re-poll until ``boundary + G`` before calling the minute late.
    missing_no_successor_timeout_s: float
    repoll_pace_s: float
    request_timeout_s: float
    attempts: int
    retry_pause_s: float
    pace_s: float
    max_pages: int
    min_bars_per_day: int
    max_seed_calendar_days: int
    max_consecutive_produce_errors: int
    #: The two parser env values the producer PINS (plan §3.3 L9). Bar size and
    #: the drop rule must not change quietly with the environment.
    parser_env: tuple[tuple[str, str], ...]

    @property
    def transport(self) -> dict[str, Any]:
        """The ``cfg`` mapping :class:`tools.tos_cp3.quote_client.Quotes` reads."""
        return {
            "attempts": self.attempts,
            "pace_s": self.pace_s,
            "retry_pause_s": self.retry_pause_s,
            "request_timeout_s": self.request_timeout_s,
            "max_pages": self.max_pages,
            "hour_cls_code": dict(self.parser_env)["KIS_FUTURES_HOUR_CLS_CODE"],
        }


def _resolve(repo_root: Path, value: str) -> Path:
    """Repo-relative paths resolve against the checkout; absolute ones stand."""
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else repo_root / candidate


def load_config(path: Path, *, repo_root: Path) -> LiveProducerConfig:
    """Read and validate the producer's YAML, or refuse."""
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise LiveProducerRefused(f"{path}: not a YAML mapping")

    known = {name for name, _ in _REQUIRED} | {"parser_env"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise LiveProducerRefused(
            f"{path}: unknown key(s) {unknown}. An ignored key is a setting the "
            "operator believes is in effect and is not"
        )
    missing = sorted(name for name, _ in _REQUIRED if name not in data)
    if missing:
        raise LiveProducerRefused(f"{path}: missing key(s) {missing}")

    values: dict[str, Any] = {}
    for name, kind in _REQUIRED:
        try:
            values[name] = kind(data[name])
        except (TypeError, ValueError) as exc:
            raise LiveProducerRefused(
                f"{path}: {name}={data[name]!r} is not a {kind.__name__}"
            ) from exc

    parser_env = data.get("parser_env")
    if not isinstance(parser_env, dict) or not parser_env:
        raise LiveProducerRefused(f"{path}: parser_env must be a non-empty mapping")
    pins = tuple(sorted((str(k), str(v)) for k, v in parser_env.items()))
    for required_pin in ("KIS_FUTURES_HOUR_CLS_CODE", "KIS_MINUTE_BAR_MIN_VOLUME"):
        if required_pin not in dict(pins):
            raise LiveProducerRefused(
                f"{path}: parser_env must pin {required_pin} — plan §3.3 L9 "
                "makes bar size and the volume drop rule config, not ambient env"
            )

    if values["missing_no_successor_timeout_s"] <= values["first_poll_delay_s"]:
        raise LiveProducerRefused(
            f"{path}: G={values['missing_no_successor_timeout_s']} must exceed "
            f"δ={values['first_poll_delay_s']}; otherwise the re-poll window is "
            "empty and δ becomes a single blocking wait, which the PR-1 evidence "
            "§1.4 explicitly refuses (δ 를 단독 대기 시간으로 쓰면 안 된다)"
        )
    if values["missing_no_successor_timeout_s"] >= 60:
        raise LiveProducerRefused(
            f"{path}: G={values['missing_no_successor_timeout_s']} would overlap "
            "the next minute boundary (evidence §1.4 upper constraint)"
        )
    if values["max_consecutive_produce_errors"] < 1:
        raise LiveProducerRefused(
            f"{path}: max_consecutive_produce_errors must be >= 1 (plan §3.5)"
        )

    return LiveProducerConfig(
        path=path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        env_file=_resolve(repo_root, values.pop("env_file")),
        token_cache_dir=_resolve(repo_root, values.pop("token_cache_dir")),
        strategy_yaml=_resolve(repo_root, values.pop("strategy_yaml")),
        calendar_yaml=_resolve(repo_root, values.pop("calendar_yaml")),
        execution_yaml=_resolve(repo_root, values.pop("execution_yaml")),
        parser_env=pins,
        **values,
    )


def assert_env_pins(
    config: LiveProducerConfig, environ: MutableMapping[str, str]
) -> None:
    """Refuse to start when the environment contradicts a pin, then apply it.

    An already-set, DIFFERENT value is the failure this guards: a shell with
    ``KIS_MINUTE_BAR_MIN_VOLUME=0`` would make ``parse_ohlcv`` keep the
    zero-volume rows the pinned run drops, so the producer's frame and B1a's
    would silently disagree bar for bar. Unset is fine — the pin is then simply
    applied (the same rule PR-1's probe used).
    """
    for key, expected in config.parser_env:
        actual = environ.get(key)
        if actual is not None and actual != expected:
            raise LiveProducerRefused(
                f"parser env pin mismatch: {key}={actual!r} in the environment, "
                f"{expected!r} in {config.path}"
            )
        environ[key] = expected


def read_query_credentials(
    config: LiveProducerConfig,
    *,
    reader: Any,
    environ: MutableMapping[str, str],
) -> tuple[str, ...]:
    """Pull ONLY the two futures query secrets from the explicitly named file.

    Plan §3.4: nothing else from ``.env.real`` crosses into this process, and
    the runner/runtime environments never receive these two at all (PR-3 pins
    that). ``reader`` is
    :func:`shared.config.dotenv_guard.read_explicit_dotenv`, which refuses a
    relative path and does nothing at all in hermetic mode.
    """
    keys = ("KIS_FUTURES_APP_KEY", "KIS_FUTURES_APP_SECRET")
    values: Mapping[str, str] = reader(config.env_file, keys=keys)
    for key in keys:
        value = values.get(key)
        if not value:
            raise LiveProducerRefused(
                f"{config.env_file} does not supply {key}; the producer reads no "
                "other credential source"
            )
        environ[key] = value
    return keys
