"""규칙 파일을 읽어 엔진이 쓸 평면 목록으로 펼친다.

사람은 문서 유형 단위로 규칙을 쓰고, 엔진은 평면 목록을 본다. 유형 묶음을 평면으로 펼치는
것은 항상 되지만 그 반대는 안 되므로(같은 관할을 쓰는 규칙들이 같은 템플릿을 가리킨다는
보장이 없다) 평면이 정본이고 유형 묶음은 표기법이다.

템플릿을 열어 기대값을 뽑는 일도 여기서 한다. 덕분에 `engine.py` 와 규칙 모듈은 템플릿이라는
것이 있는 줄 모른다.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from checker import rules as rule_registry
from checker.model import ConfigError, DocType, Rule


def _as_list(value, where: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{where}: 목록이어야 하는데 {type(value).__name__} 이다")
    return value


def _read_one(path: Path) -> list[DocType]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name}: YAML 을 읽을 수 없다 — {exc}") from exc
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise ConfigError(f"{path.name}: 최상위가 사전이어야 한다")

    # 한 파일에 유형 하나를 담을 수도, '유형들' 아래 여럿을 담을 수도 있다.
    # 어느 쪽으로 쓸지는 규칙을 쓰는 사람이 정하고, 엔진은 강제하지 않는다.
    blocks = raw.get("유형들") or raw.get("types")
    if blocks is None:
        blocks = {raw.get("유형") or raw.get("type") or path.stem: raw}
    if not isinstance(blocks, dict):
        raise ConfigError(f"{path.name}: '유형들' 아래는 사전이어야 한다")

    out = []
    for name, body in blocks.items():
        if not isinstance(body, dict):
            raise ConfigError(f"{path.name}: 유형 '{name}' 아래는 사전이어야 한다")
        out.append(_build(name, body, path))
    return out


def _build(name: str, body: dict, source: Path) -> DocType:
    where = f"{source.name}: 유형 '{name}'"
    jurisdiction = body.get("관할") or body.get("jurisdiction")
    template = body.get("템플릿") or body.get("template")
    if not jurisdiction:
        raise ConfigError(f"{where}: '관할' 이 없다")
    if not template:
        raise ConfigError(f"{where}: '템플릿' 이 없다")

    template_path = (source.parent / str(template)).resolve()
    if not template_path.is_file():
        raise ConfigError(f"{where}: 템플릿을 찾을 수 없다 — {template}")

    built = []
    for i, entry in enumerate(_as_list(body.get("규칙") or body.get("rules"), where)):
        if not isinstance(entry, dict):
            raise ConfigError(f"{where}: {i + 1}번째 규칙이 사전이 아니다")
        kind = entry.get("종류") or entry.get("kind")
        if not kind:
            raise ConfigError(f"{where}: {i + 1}번째 규칙에 '종류' 가 없다")

        rule_registry.get(kind)  # 모르는 종류면 여기서 걸린다
        params = {k: v for k, v in entry.items() if k not in ("종류", "kind")}

        # 템플릿에서 기대값을 뽑아 params 에 박아 둔다.
        prep = rule_registry.get_prepare(kind)
        if prep is not None:
            try:
                params = prep(params, template_path)
            except ConfigError:
                raise
            except Exception as exc:
                raise ConfigError(f"{where}: {kind} 규칙의 기대값을 템플릿에서 뽑지 못했다 — {exc}") from exc

        built.append(Rule(kind=kind, doc_type=name, template=str(template), params=params))

    return DocType(
        name=str(name),
        jurisdiction=str(jurisdiction),
        template=str(template),
        rules=tuple(built),
        source=str(source),
    )


def load(target: Path) -> list[DocType]:
    """규칙 파일 하나 또는 폴더 하나를 읽는다.

    폴더면 안의 `*.yaml` 과 `*.yml` 을 모두 읽어 합친다. 한 파일에 몰아 쓰든 유형마다
    쪼개든 같은 결과가 나오므로, 이 선택은 코드가 아니라 규칙을 쓰는 사람의 몫이다.
    """
    if target.is_dir():
        files = sorted(p for p in target.iterdir() if p.suffix.lower() in (".yaml", ".yml"))
        if not files:
            raise ConfigError(f"{target} 안에 규칙 파일(*.yaml)이 없다")
    elif target.is_file():
        files = [target]
    else:
        raise ConfigError(f"규칙을 찾을 수 없다 — {target}")

    types: list[DocType] = []
    for f in files:
        types.extend(_read_one(f))

    _check_conflicts(types)
    return types


def _check_conflicts(types: list[DocType]) -> None:
    """값싸게 판정되는 충돌만 로드 시점에 잡는다.

    임의의 두 glob 이 공통 경로를 가질 수 있는지 정적으로 따지는 일반 해석은 하지 않는다.
    정규 언어 교집합에 해당하는 작업이라 비용이 크고, 이론상 겹치지만 실제로는 만나지 않는
    쌍에 거짓 경보를 낸다. 여기서 놓친 겹침은 실제 파일이 두 유형에 걸릴 때 엔진이 잡는다.
    """
    seen_names: dict[str, str] = {}
    seen_globs: dict[str, str] = {}
    for t in types:
        if t.name in seen_names:
            raise ConfigError(
                f"유형 이름 '{t.name}' 이 두 번 나온다 — {seen_names[t.name]}, {t.source}"
            )
        seen_names[t.name] = t.source

        if t.jurisdiction in seen_globs:
            raise ConfigError(
                f"관할 '{t.jurisdiction}' 을 두 유형이 함께 쓴다 — "
                f"{seen_globs[t.jurisdiction]}, {t.source}"
            )
        seen_globs[t.jurisdiction] = f"{t.source} (유형 {t.name})"

    # 한 관할이 다른 관할의 리터럴 접두사인 경우도 값싸게 잡힌다.
    for a in types:
        for b in types:
            if a is b:
                continue
            pa, pb = a.jurisdiction, b.jurisdiction
            head_a = pa.split("*", 1)[0].rstrip("/")
            if head_a and pb.startswith(head_a + "/") and "*" not in head_a:
                if pa.rstrip("*/") == head_a and pa.endswith("**"):
                    raise ConfigError(
                        f"관할이 서로를 덮는다 — 유형 '{a.name}' 의 '{pa}' 가 "
                        f"유형 '{b.name}' 의 '{pb}' 를 포함한다"
                    )
