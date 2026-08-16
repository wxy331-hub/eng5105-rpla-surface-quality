#!/usr/bin/env python3
"""Report sentence-rhythm statistics for the final Markdown pair."""

from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def prose(text: str) -> str:
    text = re.split(r"(?m)^# (?:References|参考文献)\s*$", text)[0]
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        if line.startswith(("|", "#", "**Table", "**表", "**Figure", "**图")):
            continue
        lines.append(line)
    return "\n".join(lines)


def stats(language: str, path: Path) -> None:
    text = prose(path.read_text(encoding="utf-8-sig"))
    if language == "EN":
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+", text)
            if len(item.split()) >= 3
        ]
        lengths = [len(re.findall(r"[A-Za-z0-9_'-]+", item)) for item in sentences]
        short_limit = 12
    else:
        sentences = [
            item.strip()
            for item in re.split(r"[。！？]+", text)
            if len(re.findall(r"[\u4e00-\u9fff]", item)) >= 4
        ]
        lengths = [len(re.findall(r"[\u4e00-\u9fff]", item)) for item in sentences]
        short_limit = 15
    similar = 0
    similar_rows: list[tuple[int, tuple[int, int, int]]] = []
    for index, (first, second, third) in enumerate(zip(lengths, lengths[1:], lengths[2:])):
        mean = (first + second + third) / 3
        if max(first, second, third) - min(first, second, third) <= max(2, 0.15 * mean):
            similar += 1
            similar_rows.append((index, (first, second, third)))
    print(
        f"{language}: sentences={len(lengths)}, mean={statistics.mean(lengths):.1f}, "
        f"stddev={statistics.pstdev(lengths):.1f}, "
        f"short_ratio={sum(value <= short_limit for value in lengths) / len(lengths):.1%}, "
        f"similar_triples={similar}"
    )
    if "--details" in sys.argv:
        for index, triple in similar_rows:
            sample = " | ".join(re.sub(r"\s+", " ", item)[:130] for item in sentences[index:index + 3])
            print(f"  {index + 1}: {triple}: {sample}")


stats("EN", ROOT / "ENG5105_Proposal_Design_Report_EN.md")
stats("ZH", ROOT / "ENG5105_Proposal_Design_Report_ZH.md")
