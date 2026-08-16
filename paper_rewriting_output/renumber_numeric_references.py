#!/usr/bin/env python3
"""Renumber numeric citations in first-citation order across paired Markdown reports."""

from __future__ import annotations

import re
import sys
from pathlib import Path


CITATION = re.compile(r"\[(\d+)\](?:\s*[-–—]\s*\[(\d+)\])?")


def split_document(text: str) -> tuple[str, str, str]:
    match = re.search(r"(?m)^(# (?:References|参考文献))\s*$", text)
    if not match:
        raise ValueError("References heading not found")
    body = text[: match.start()].rstrip()
    heading = match.group(1)
    tail = text[match.end() :].strip()
    return body, heading, tail


def citation_order(body: str) -> list[int]:
    order: list[int] = []
    seen: set[int] = set()
    for match in CITATION.finditer(body):
        start = int(match.group(1))
        end_text = match.group(2)
        values = [start]
        if end_text is not None:
            end = int(end_text)
            step = 1 if end >= start else -1
            values = list(range(start, end + step, step))
        for value in values:
            if value not in seen:
                seen.add(value)
                order.append(value)
    return order


def parse_references(tail: str) -> dict[int, str]:
    starts = list(re.finditer(r"(?m)^\[(\d+)\]\s+", tail))
    if not starts:
        raise ValueError("No numeric reference entries found")
    entries: dict[int, str] = {}
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(tail)
        number = int(match.group(1))
        entries[number] = tail[match.end() : end].strip()
    return entries


def replace_citations(body: str, mapping: dict[int, int]) -> str:
    def repl(match: re.Match[str]) -> str:
        start = int(match.group(1))
        end_text = match.group(2)
        if end_text is None:
            return f"[{mapping[start]}]"
        end = int(end_text)
        step = 1 if end >= start else -1
        mapped = [mapping[value] for value in range(start, end + step, step)]
        if mapped == list(range(mapped[0], mapped[-1] + 1)):
            return f"[{mapped[0]}]–[{mapped[-1]}]"
        return ", ".join(f"[{value}]" for value in mapped)

    return CITATION.sub(repl, body)


def rewrite(path: Path, mapping: dict[int, int]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    body, heading, tail = split_document(text)
    references = parse_references(tail)
    if set(references) != set(mapping):
        raise ValueError(
            f"{path.name}: reference IDs differ from mapping; "
            f"missing={sorted(set(mapping) - set(references))}, "
            f"extra={sorted(set(references) - set(mapping))}"
        )
    new_body = replace_citations(body, mapping)
    ordered = sorted(references, key=lambda old: mapping[old])
    new_tail = "\n\n".join(
        f"[{mapping[old]}] {references[old]}" for old in ordered
    )
    path.write_text(f"{new_body}\n\n{heading}\n\n{new_tail}\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: renumber_numeric_references.py EN.md [ZH.md]")
    english = Path(sys.argv[1])
    en_text = english.read_text(encoding="utf-8-sig")
    en_body, _, en_tail = split_document(en_text)
    en_refs = parse_references(en_tail)
    order = citation_order(en_body)
    order.extend(number for number in sorted(en_refs) if number not in order)
    mapping = {old: new for new, old in enumerate(order, start=1)}
    if set(mapping) != set(en_refs):
        raise ValueError("Citation order and reference list do not cover the same IDs")
    for raw in sys.argv[1:]:
        rewrite(Path(raw), mapping)
    print("MAPPING=" + ",".join(f"{old}->{new}" for old, new in sorted(mapping.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
