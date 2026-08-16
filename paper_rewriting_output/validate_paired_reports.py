#!/usr/bin/env python3
"""Validate structural and factual parity of the paired ENG5105 Markdown reports."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EN = ROOT / "ENG5105_Proposal_Design_Report_EN.md"
ZH = ROOT / "ENG5105_Proposal_Design_Report_ZH.md"
CITE = re.compile(r"\[(\d+)\](?:\s*[–-]\s*\[(\d+)\])?")
REFERENCE_ENTRY = re.compile(
    r"^\[(\d+)\]\s+(.*?)(?=^\[\d+\]\s+|\Z)", re.MULTILINE | re.DOTALL
)


def body_and_refs(text: str) -> tuple[str, str]:
    parts = re.split(r"(?m)^# (?:References|参考文献)\s*$", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("References heading missing or duplicated")
    return parts[0], parts[1]


def expanded_citations(body: str) -> list[int]:
    result: list[int] = []
    for match in CITE.finditer(body):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        step = 1 if end >= start else -1
        result.extend(range(start, end + step, step))
    return result


def reference_entries(refs: str) -> list[tuple[int, str]]:
    """Return numbered references with whitespace-normalized entry text."""
    return [
        (int(number), " ".join(entry.split()))
        for number, entry in REFERENCE_ENTRY.findall(refs.strip())
    ]


def display_equations(text: str) -> list[str]:
    """Return whitespace-normalized LaTeX display equations in document order."""
    return [
        " ".join(equation.split())
        for equation in re.findall(r"\\\[\s*(.*?)\s*\\\]", text, re.DOTALL)
    ]


def caption_numbers(text: str, kind: str) -> list[int]:
    labels = "Table|表" if kind == "table" else "Figure|图"
    return [int(value) for value in re.findall(rf"(?m)^\*\*(?:{labels})\s*(\d+)\.", text)]


def check() -> list[str]:
    failures: list[str] = []
    en = EN.read_text(encoding="utf-8-sig")
    zh = ZH.read_text(encoding="utf-8-sig")
    en_body, en_refs = body_and_refs(en)
    zh_body, zh_refs = body_and_refs(zh)

    en_seq = expanded_citations(en_body)
    zh_seq = expanded_citations(zh_body)
    if en_seq != zh_seq:
        failures.append("Numeric citation sequence differs between English and Chinese")

    en_entries = reference_entries(en_refs)
    zh_entries = reference_entries(zh_refs)
    if not en_entries:
        failures.append("Reference list is empty")
    if en_entries != zh_entries:
        failures.append("Normalized reference entries differ between English and Chinese")

    expected_references = list(range(1, len(en_entries) + 1))
    first_citation_order = list(dict.fromkeys(en_seq))
    if first_citation_order != expected_references:
        failures.append(
            "English citations are not in contiguous first-citation order matching "
            "the reference list"
        )

    for language, entries in (("EN", en_entries), ("ZH", zh_entries)):
        numbers = [number for number, _ in entries]
        if numbers != expected_references:
            failures.append(
                f"{language} reference list is not contiguous from 1 through its final entry"
            )

    for kind, expected in (("table", list(range(1, 21))), ("figure", list(range(1, 4)))):
        en_numbers = caption_numbers(en, kind)
        zh_numbers = caption_numbers(zh, kind)
        if en_numbers != expected:
            failures.append(f"EN {kind} captions differ from {expected}")
        if zh_numbers != expected:
            failures.append(f"ZH {kind} captions differ from {expected}")

    for language, text in (("EN", en), ("ZH", zh)):
        if text.count("```mermaid") != 3 or text.count("```") != 6:
            failures.append(f"{language} Mermaid/code fence count is invalid")
        if text.count("\n\\[\n") != text.count("\n\\]\n"):
            failures.append(f"{language} display-math delimiters are unbalanced")
        sections = [int(value) for value in re.findall(r"(?m)^# (\d+)\.", text)]
        if sections != list(range(1, 13)):
            failures.append(f"{language} numbered sections are not exactly 1..12")

    en_equations = display_equations(en_body)
    zh_equations = display_equations(zh_body)
    if not en_equations:
        failures.append("No display equations found")
    if en_equations != zh_equations:
        failures.append("Display equations differ between English and Chinese")

    if re.findall(r"https?://\S+", en) != re.findall(r"https?://\S+", zh):
        failures.append("Reference URL sequences differ")
    if Counter(re.findall(r"`([A-F0-9]{64})`", en)) != Counter(
        re.findall(r"`([A-F0-9]{64})`", zh)
    ):
        failures.append("Internal evidence SHA-256 values differ")

    required = (
        "A$136.15",
        "A$141.30–A$246.30",
        "A$277.45–A$382.45",
        "10.77",
        "26.35",
        "101.32",
        "222.99",
        "654.64",
        "5689.35",
        "A75C316FBD64AFF205F48350EA37271ADEE31FF036F3040AA46EA5C350CDDC3E",
    )
    for token in required:
        en_count = en.count(token)
        zh_count = zh.count(token)
        if en_count == 0 or zh_count == 0:
            failures.append(f"Required paired token missing: {token}")
        elif en_count != zh_count:
            failures.append(f"Required paired token count differs: {token}")

    banned_en = re.compile(
        r"(?i)\b(firstly|secondly|finally|furthermore|moreover|additionally|"
        r"in conclusion|it is worth noting)\b"
    )
    for match in banned_en.finditer(en_body):
        failures.append(f"EN banned connector remains: {match.group(0)}")

    banned_zh = ("首先", "其次", "再次", "最后", "综上所述", "总而言之", "此外", "另外", "不仅如此", "值得注意的是", "需要指出的是")
    for token in banned_zh:
        if token in zh_body:
            failures.append(f"ZH banned connector remains: {token}")

    leftovers = ("Week 3", "Week 4", "Week 5", "Thursday", "Section 5.3", "360-degree", "processed frames/s")
    for token in leftovers:
        if token in zh_body:
            failures.append(f"ZH translation leftover remains: {token}")

    en_labels = Counter(re.findall(r"\b(?:LIVE_INTEGRATION_ONLY|OFFLINE_SYNTHETIC_ONLY|OFFLINE_FAULT_INJECTION_ONLY|PENDING_REAL_MATERIAL|PROPOSED_REQUIREMENT|PROPOSED_INTERFACE)\b", en_body))
    zh_labels = Counter(re.findall(r"\b(?:LIVE_INTEGRATION_ONLY|OFFLINE_SYNTHETIC_ONLY|OFFLINE_FAULT_INJECTION_ONLY|PENDING_REAL_MATERIAL|PROPOSED_REQUIREMENT|PROPOSED_INTERFACE)\b", zh_body))
    if en_labels != zh_labels:
        failures.append(f"Evidence-label counts differ: EN={dict(en_labels)}, ZH={dict(zh_labels)}")

    return failures


def main() -> int:
    failures = check()
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    en = EN.read_text(encoding="utf-8-sig")
    en_body, en_refs = body_and_refs(en)
    citation_count = len(expanded_citations(en_body))
    reference_count = len(reference_entries(en_refs))
    equation_count = len(display_equations(en_body))

    print("PASS")
    print(
        f"- paired citations: {citation_count} expanded uses; contiguous first-citation "
        f"order 1..{reference_count}"
    )
    print("- captions: Tables 1..20 and Figures 1..3 in both reports")
    print(
        f"- structures: Sections 1..12, three Mermaid diagrams, {equation_count} "
        "identical display equations and balanced math fences"
    )
    print(
        f"- parity: {reference_count} reference entries, URLs, SHA-256 values, "
        "evidence labels and critical numeric tokens"
    )
    print("- style scan: no configured medium-tier banned connectors or translation leftovers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
