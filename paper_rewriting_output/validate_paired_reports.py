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
# APA 7th: a citation is a parenthetical whose every semicolon-separated chunk
# is "Author, Year" with optional extra years. Both bracket forms appear because
# the Chinese report uses full-width parentheses.
PARENTHETICAL = re.compile(r"[(（]([^()（）]+)[)）]")
YEAR = re.compile(r"^(?:19|20)\d{2}[a-z]?$")
REFERENCE_ENTRY = re.compile(r"(?m)^(?P<author>[^\n]+?)\. \((?P<year>(?:19|20)\d{2}[a-z]?)\)\. (?P<rest>[^\n]+)$")


def body_and_refs(text: str) -> tuple[str, str]:
    parts = re.split(r"(?m)^# (?:References|参考文献)\s*$", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("References heading missing or duplicated")
    return parts[0], parts[1]


def citation_keys(body: str) -> list[tuple[str, str]]:
    """Return every (label, year) an in-text citation names, in document order."""
    keys: list[tuple[str, str]] = []
    for match in PARENTHETICAL.finditer(body):
        chunks = [chunk.strip() for chunk in match.group(1).split(";")]
        parsed: list[tuple[str, str]] = []
        for chunk in chunks:
            parts = [part.strip() for part in chunk.split(",")]
            if len(parts) < 2 or not all(YEAR.match(part) for part in parts[1:]):
                parsed = []
                break
            parsed.extend((parts[0], year) for year in parts[1:])
        keys.extend(parsed)
    return keys


def first_surname(label: str) -> str:
    """The surname an entry must start with for a label to resolve to it."""
    return label.replace(" et al.", "").split(" & ")[0].strip()


def reference_entries(refs: str) -> list[tuple[str, str, str]]:
    """Return (author, year, normalized full entry) for each reference."""
    return [
        (match.group("author").strip(), match.group("year"),
         " ".join(match.group(0).split()))
        for match in REFERENCE_ENTRY.finditer(refs.strip())
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

    en_seq = citation_keys(en_body)
    zh_seq = citation_keys(zh_body)
    if en_seq != zh_seq:
        failures.append("Citation sequence differs between English and Chinese")

    en_entries = reference_entries(en_refs)
    zh_entries = reference_entries(zh_refs)
    if not en_entries:
        failures.append("Reference list is empty")
    if [entry[2] for entry in en_entries] != [entry[2] for entry in zh_entries]:
        failures.append("Normalized reference entries differ between English and Chinese")

    sort_keys = [(author.lower(), year) for author, year, _ in en_entries]
    if sort_keys != sorted(sort_keys):
        failures.append("Reference list is not in alphabetical order")

    cited = set(en_seq)
    for label, year in sorted(cited):
        surname = first_surname(label)
        if not any(author.startswith(surname) and entry_year == year
                   for author, entry_year, _ in en_entries):
            failures.append(f"Citation has no matching reference entry: {label}, {year}")

    for author, year, _ in en_entries:
        if not any(entry_year == year and author.startswith(first_surname(label))
                   for label, entry_year in cited):
            failures.append(f"Reference entry is never cited: {author}, {year}")

    for kind, expected in (("table", list(range(1, 21))), ("figure", list(range(1, 5)))):
        en_numbers = caption_numbers(en, kind)
        zh_numbers = caption_numbers(zh, kind)
        if en_numbers != expected:
            failures.append(f"EN {kind} captions differ from {expected}")
        if zh_numbers != expected:
            failures.append(f"ZH {kind} captions differ from {expected}")

    for language, text in (("EN", en), ("ZH", zh)):
        if text.count("```mermaid") != 4 or text.count("```") != 8:
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
        "A$142.00",
        "A$18.00",
        "A$342.00–537.00",
        "A$360.00–555.00",
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

    # Plan A is the selected concept but its hardware is not ordered; neither
    # language may imply otherwise, and no interim figure may be relabelled.
    for language, text in (("EN", en), ("ZH", zh)):
        if "on order" in text or "已下单" in text:
            failures.append(f"{language} states the hardware is on order, which is not the case")

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
    citation_count = len(citation_keys(en_body))
    reference_count = len(reference_entries(en_refs))
    equation_count = len(display_equations(en_body))

    print("PASS")
    print(
        f"- paired citations: {citation_count} APA author-date uses resolving to "
        f"{reference_count} alphabetised entries"
    )
    print("- captions: Tables 1..20 and Figures 1..4 in both reports")
    print(
        f"- structures: Sections 1..12, four Mermaid diagrams, {equation_count} "
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
