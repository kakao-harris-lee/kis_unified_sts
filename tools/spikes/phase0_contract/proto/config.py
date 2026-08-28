"""의존성 없는 최소 설정 파서.

`key: value` 한 줄 형식만 지원한다.  파싱·검증 실패는 **중단**이지 기본값이
아니다(공통 규칙).  값은 정수로 해석 가능하면 정수, 아니면 문자열이다.
"""

from __future__ import annotations

from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

REQUIRED_KEYS = (
    "owner_track_range_max_width",
    "phase_min",
    "phase_max",
    "anchor_classification_checkable",
    "anchor_classification_partial",
    "anchor_classification_nmc",
    "anchor_closable_no_ids",
    "anchor_enforcement_key_count",
    "anchor_evidence_level_distribution",
    "anchor_level_kinds",
    "declared_limit_ids",
    "limit_vocabulary_waivers",
    "anchor_limit_text_digest",
    "anchor_limit_emitted_digest",
    "anchor_case_prose_digest",
    "anchor_runner_source_digest",
    # v2.6 (심판 F1/F3) — 부재하면 `load_config` 가 중단한다 (fail-closed).
    "anchor_source_bytes_digest",
    "anchor_forbidden_artifacts_digest",
    "declared_self_checks",
    "declared_required_metrics",
    # v2.7 (심판 #3/#7) — 부재하면 `load_config` 가 중단한다 (fail-closed).
    "anchor_prehook_runner",
    "anchor_prehook_audit_guard",
    "anchor_policy_values",
    # v2.8 (심판 v2.7 #3/#4/#5 + 운영자 처분 B) — 전부 fail-closed 필수 키다.
    "anchor_prehook_executable",
    "anchor_probe_records",
    "policy_value_exclusions",
    "deferred_owner_tracks",
    # v2.9 (심판 v2.8 #5) — 운영자 처분에서 파생한 **필수** 이연.  부재하면
    # `load_config` 가 중단한다 (fail-closed).  `deferred_owner_tracks` 만으로는
    # 미끼 이연(다른 선언 id 하나)으로 대체돼도 `SELF-3` 이 green 이었다.
    "required_deferrals",
)


class ConfigError(RuntimeError):
    """설정 파싱·검증 실패.  기본값으로 접지 않는다."""


def _parse_scalar(raw: str) -> int | str:
    """정수로 읽히면 정수, 아니면 문자열."""
    text = raw.strip()
    if not text:
        raise ConfigError("빈 값은 허용하지 않는다")
    try:
        return int(text)
    except ValueError:
        return text


def load_config(path: Path | None = None) -> dict[str, int | str]:
    """설정 파일을 읽어 dict 로 돌려준다.

    필수 키가 없거나 문법이 어긋나면 `ConfigError` 로 중단한다.
    """
    target = path or CONFIG_PATH
    if not target.exists():
        raise ConfigError(f"설정 파일 부재: {target}")

    parsed: dict[str, int | str] = {}
    for lineno, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        if ":" not in stripped:
            raise ConfigError(f"{target}:{lineno} `key: value` 형식이 아니다: {line!r}")
        key, raw = stripped.split(":", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f"{target}:{lineno} 키가 비었다")
        if key in parsed:
            raise ConfigError(f"{target}:{lineno} 키 중복: {key}")
        parsed[key] = _parse_scalar(raw)

    missing = [key for key in REQUIRED_KEYS if key not in parsed]
    if missing:
        raise ConfigError(f"필수 키 누락: {missing}")
    return parsed


def cfg_int(cfg: dict[str, int | str], key: str) -> int:
    """정수 임계값을 꺼낸다.  타입이 다르면 중단한다."""
    value = cfg.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"정수 임계값이 아니다: {key}={value!r}")
    return value


def cfg_list(cfg: dict[str, int | str], key: str) -> tuple[str, ...]:
    """콤마 구분 리스트를 꺼낸다."""
    value = cfg.get(key)
    if value is None:
        raise ConfigError(f"키 부재: {key}")
    return tuple(part.strip() for part in str(value).split(",") if part.strip())


def cfg_pairs(cfg: dict[str, int | str], key: str) -> dict[str, str]:
    """`a=1,b=2` 형태의 콤마 구분 쌍 목록을 꺼낸다.

    `=` 가 없거나 키가 중복되면 **중단**한다 — 조용히 버리지 않는다.
    """
    pairs: dict[str, str] = {}
    for item in cfg_list(cfg, key):
        if "=" not in item:
            raise ConfigError(f"{key}: `이름=값` 형식이 아니다: {item!r}")
        name, raw = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ConfigError(f"{key}: 이름이 비었다: {item!r}")
        if name in pairs:
            raise ConfigError(f"{key}: 이름 중복: {name}")
        pairs[name] = raw.strip()
    if not pairs:
        raise ConfigError(f"{key}: 빈 쌍 목록")
    return pairs
