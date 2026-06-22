"""Caption 规则清洗：删除脏 tag、补角色 tag、互斥规则、异常标记。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from img_tools.caption.presets import (
    load_preset,
    parse_mutual_exclude,
    parse_tag_list,
)
from img_tools.common import JobResult

_SPLIT_RE = re.compile(r"\s*,\s*")


@dataclass
class CaptionCleanOptions:
    preset: str = "default"
    recursive: bool = False
    dry_run: bool = False
    dedupe: bool | None = None
    separator: str | None = None
    trigger_word: str | None = None
    strip_tags: str | None = None
    ensure_tags: str | None = None


@dataclass
class _CleanRules:
    trigger_word: str = ""
    character_tag: str = ""
    strip_tags: set[str] = field(default_factory=set)
    ensure_tags: list[str] = field(default_factory=list)
    expected_gender: str = ""
    remove_if_missing: set[str] = field(default_factory=set)
    flag_if_present: set[str] = field(default_factory=set)
    mutual_exclude: list[tuple[str, list[str]]] = field(default_factory=list)
    dedupe: bool = True
    separator: str = ", "


def _load_rules(options: CaptionCleanOptions) -> _CleanRules:
    cfg = load_preset(options.preset)
    sep = options.separator or str(cfg.get("separator") or ", ")

    strip = parse_tag_list(
        options.strip_tags if options.strip_tags is not None else str(cfg.get("strip_tags") or ""),
    )
    ensure = parse_tag_list(
        options.ensure_tags if options.ensure_tags is not None else str(cfg.get("ensure_tags") or ""),
    )
    remove_if_missing = parse_tag_list(str(cfg.get("remove_if_missing") or ""))
    flag_if_present = parse_tag_list(str(cfg.get("flag_if_present") or ""))

    expected = str(cfg.get("expected_gender") or "").strip()
    if expected == "1girl":
        strip.extend(["1boy", "male_focus"])
    elif expected == "1boy":
        strip.extend(["1girl", "female_focus"])

    return _CleanRules(
        trigger_word=(options.trigger_word if options.trigger_word is not None else str(cfg.get("trigger_word") or "")).strip(),
        character_tag=str(cfg.get("character_tag") or "").strip(),
        strip_tags={t.lower() for t in strip},
        ensure_tags=ensure,
        expected_gender=expected,
        remove_if_missing={t.lower() for t in remove_if_missing},
        flag_if_present={t.lower() for t in flag_if_present},
        mutual_exclude=parse_mutual_exclude(str(cfg.get("mutual_exclude") or "")),
        dedupe=options.dedupe if options.dedupe is not None else bool(cfg.get("dedupe", True)),
        separator=sep,
    )


def _split_tags(content: str) -> list[str]:
    return [t.strip() for t in _SPLIT_RE.split(content.strip()) if t.strip()]


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tag)
    return out


def _dedupe_word_overlap(tags: list[str]) -> list[str]:
    """词重叠时保留更长 tag（来自 dedupe_comma_txt_tags 逻辑）。"""
    unique = _dedupe_tags(tags)
    filtered: list[str] = []
    for tag in unique:
        words = set(tag.split())
        overlaps = [b for b in filtered if words & set(b.split())]
        if overlaps:
            if any(len(b) > len(tag) for b in overlaps):
                continue
            filtered = [b for b in filtered if not (words & set(b.split()))]
            filtered.append(tag)
        else:
            filtered.append(tag)
    return filtered


def _apply_mutual_exclude(tags: list[str], rules: list[tuple[str, list[str]]]) -> list[str]:
    lower_set = {t.lower() for t in tags}
    remove: set[str] = set()
    for when, removes in rules:
        if when.lower() in lower_set:
            remove.update(r.lower() for r in removes)
    if not remove:
        return tags
    return [t for t in tags if t.lower() not in remove]


def _pin_trigger(tags: list[str], trigger: str) -> list[str]:
    if not trigger:
        return tags
    lower = [t.lower() for t in tags]
    trigger_lower = trigger.lower()
    if trigger_lower in lower:
        tags = [t for t in tags if t.lower() != trigger_lower]
    return [trigger, *tags]


def _clean_tag_list(tags: list[str], rules: _CleanRules) -> tuple[list[str], list[str]]:
    """返回 (清洗后 tags, 变更说明)。"""
    notes: list[str] = []
    original = list(tags)

    removed = [t for t in tags if t.lower() in rules.strip_tags]
    if removed:
        notes.append(f"删除: {', '.join(removed)}")
    tags = [t for t in tags if t.lower() not in rules.strip_tags]

    before = len(tags)
    tags = _apply_mutual_exclude(tags, rules.mutual_exclude)
    if len(tags) < before:
        notes.append("应用互斥规则")

    for ensure in rules.ensure_tags:
        if ensure.lower() not in {t.lower() for t in tags}:
            tags.append(ensure)
            notes.append(f"补充: {ensure}")

    if rules.dedupe:
        tags = _dedupe_word_overlap(tags)

    tags = _pin_trigger(tags, rules.trigger_word)

    if tags != original and not notes:
        notes.append("顺序/触发词调整")

    return tags, notes


def _check_anomalies(tags: list[str], rules: _CleanRules) -> list[str]:
    lower = {t.lower() for t in tags}
    flags: list[str] = []
    for tag in rules.flag_if_present:
        if tag in lower:
            flags.append(f"含异常 tag: {tag}")
    for tag in rules.remove_if_missing:
        if tag not in lower:
            flags.append(f"缺少 tag: {tag}")
    if rules.character_tag and rules.character_tag.lower() not in lower:
        flags.append(f"缺少角色 tag: {rules.character_tag}")
    return flags


def clean_single_caption(content: str, rules: _CleanRules) -> tuple[str, list[str], list[str]]:
    tags = _split_tags(content)
    cleaned, notes = _clean_tag_list(tags, rules)
    flags = _check_anomalies(cleaned, rules)
    return rules.separator.join(cleaned), notes, flags


def _glob_txt_files(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(root.rglob("*.txt"))
    return sorted(root.glob("*.txt"))


def clean_captions_in_dir(target_dir: str | Path, options: CaptionCleanOptions | None = None) -> JobResult:
    options = options or CaptionCleanOptions()
    root = Path(target_dir)
    if not root.is_dir():
        return JobResult(ok=False, message="目录不存在", errors=[str(root)])

    try:
        rules = _load_rules(options)
    except FileNotFoundError as e:
        return JobResult(ok=False, message="预设加载失败", errors=[str(e)])

    txt_files = _glob_txt_files(root, options.recursive)
    if not txt_files:
        return JobResult(ok=False, message="未找到 .txt 文件", errors=[str(root)])

    processed = 0
    skipped = 0
    flagged = 0
    details: list[str] = []
    errors: list[str] = []
    outputs: list[Path] = []

    for txt_path in txt_files:
        try:
            original = txt_path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{txt_path.name}: 读取失败 {e}")
            continue

        new_content, notes, flags = clean_single_caption(original, rules)
        rel = txt_path.relative_to(root)

        if new_content.strip() == original.strip() and not flags:
            skipped += 1
            continue

        line_parts: list[str] = [str(rel)]
        if notes:
            line_parts.append("; ".join(notes))
        if flags:
            line_parts.append("[待复核] " + "; ".join(flags))
            flagged += 1

        details.append(" · ".join(line_parts))

        if not options.dry_run and new_content.strip() != original.strip():
            try:
                txt_path.write_text(new_content, encoding="utf-8")
                outputs.append(txt_path)
                processed += 1
            except OSError as e:
                errors.append(f"{txt_path.name}: 写入失败 {e}")
        elif options.dry_run:
            if new_content.strip() != original.strip():
                processed += 1
            outputs.append(txt_path)

    mode = "预览" if options.dry_run else "完成"
    msg = f"Caption 清洗{mode}（预设: {options.preset}）"
    if flagged:
        msg += f"，{flagged} 个文件待人工复核"

    return JobResult(
        ok=len(errors) == 0,
        message=msg,
        processed=processed,
        skipped=skipped,
        errors=errors,
        details=details[:500],
        outputs=outputs,
    )


def get_tag_undesired_for_preset(preset_id: str) -> str:
    """打标阶段使用的 undesired_tags（方案 3）。"""
    try:
        cfg = load_preset(preset_id)
    except FileNotFoundError:
        return ""
    return str(cfg.get("tag_undesired") or "")


def get_trigger_for_preset(preset_id: str) -> str:
    try:
        cfg = load_preset(preset_id)
    except FileNotFoundError:
        return ""
    return str(cfg.get("trigger_word") or "")
