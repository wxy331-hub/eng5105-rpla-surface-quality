#!/usr/bin/env python3
"""Verify that every recorded SHA-256 still resolves to the file it names.

`validate_paired_reports.py` only checks that the two reports quote the same
hashes as each other. It never opens the files those hashes describe, so a stale
Appendix A entry or a stale `final_artifact_manifest.md` row passes it silently.
This script closes that gap: it recomputes each hash from disk and it confirms
that every hash-anchored path still carries its `-text` marker in
`.gitattributes`, because end-of-line normalisation would rewrite the bytes.

Run it after any change to a hash-anchored file, alongside the paired-report
validator.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
EN = PAPER / "ENG5105_Proposal_Design_Report_EN.md"
ZH = PAPER / "ENG5105_Proposal_Design_Report_ZH.md"
MANIFEST = PAPER / "final_artifact_manifest.md"
GITATTRIBUTES = ROOT / ".gitattributes"

EVIDENCE_ROW = re.compile(
    r"(?m)^\|\s*(IE\d+)\s*\|\s*\[(\d+)\]\s*\|[^|]*\|\s*`([A-F0-9]{64})`\s*\|$"
)
MANIFEST_ROW = re.compile(r"(?m)^\|\s*`([^`]+)`\s*\|\s*`([A-F0-9]{64})`\s*\|")
REFERENCE_ENTRY = re.compile(r"^\[(\d+)\]\s+(.*?)(?=^\[\d+\]\s+|\Z)", re.MULTILINE | re.DOTALL)
SOURCE_FILE = re.compile(r"source file:\s*`([^`]+)`")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def reference_sources(text: str) -> dict[int, str]:
    """Map reference number to the repository-relative path it cites."""
    _, refs = re.split(r"(?m)^# (?:References|参考文献)\s*$", text, maxsplit=1)
    sources: dict[int, str] = {}
    for number, entry in REFERENCE_ENTRY.findall(refs.strip()):
        match = SOURCE_FILE.search(entry)
        if match:
            sources[int(number)] = match.group(1)
    return sources


def check() -> list[str]:
    failures: list[str] = []
    en = EN.read_text(encoding="utf-8-sig")
    zh = ZH.read_text(encoding="utf-8-sig")
    manifest = MANIFEST.read_text(encoding="utf-8-sig")

    anchored: list[str] = []

    # 1. Appendix A: each IE row cites a reference whose entry names a file.
    sources = reference_sources(en)
    en_rows = EVIDENCE_ROW.findall(en)
    zh_rows = EVIDENCE_ROW.findall(zh)
    if not en_rows:
        failures.append("Appendix A evidence rows not found in the English report")
    if [(ie, ref) for ie, ref, _ in en_rows] != [(ie, ref) for ie, ref, _ in zh_rows]:
        failures.append("Appendix A rows differ between English and Chinese")

    for identifier, reference, recorded in en_rows:
        relative = sources.get(int(reference))
        if relative is None:
            failures.append(
                f"{identifier}: reference [{reference}] names no source file, "
                "so its hash cannot be verified"
            )
            continue
        anchored.append(relative)
        target = ROOT / relative
        if not target.is_file():
            failures.append(f"{identifier}: {relative} is missing")
            continue
        actual = sha256(target)
        if actual != recorded:
            failures.append(
                f"{identifier}: {relative} hashes to {actual} but Appendix A records {recorded}"
            )

    # 2. Manifest: one row per report.
    manifest_rows = MANIFEST_ROW.findall(manifest)
    if not manifest_rows:
        failures.append("No artifact rows found in final_artifact_manifest.md")
    for name, recorded in manifest_rows:
        target = PAPER / name
        anchored.append(str(target.relative_to(ROOT)).replace("\\", "/"))
        if not target.is_file():
            failures.append(f"manifest: {name} is missing")
            continue
        actual = sha256(target)
        if actual != recorded:
            failures.append(
                f"manifest: {name} hashes to {actual} but the manifest records {recorded}"
            )

    # 3. Every anchored path must keep its -text marker.
    if not GITATTRIBUTES.is_file():
        failures.append(".gitattributes is missing, so -text protection cannot be confirmed")
    else:
        marked = {
            line.split()[0]
            for line in GITATTRIBUTES.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "-text" in line.split()
        }
        # A pattern without a slash matches that basename at any depth; a pattern
        # with one is anchored to the directory holding .gitattributes.
        bare = {pattern for pattern in marked if "/" not in pattern}
        for relative in sorted(set(anchored)):
            if relative in marked or relative.rsplit("/", 1)[-1] in bare:
                continue
            failures.append(
                f"{relative} carries a recorded hash but has no -text marker in "
                ".gitattributes; end-of-line normalisation would invalidate it"
            )

    return failures


def main() -> int:
    failures = check()
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    en = EN.read_text(encoding="utf-8-sig")
    print("PASS")
    print(f"- Appendix A: {len(EVIDENCE_ROW.findall(en))} recorded hashes recomputed from disk")
    print(
        f"- manifest: {len(MANIFEST_ROW.findall(MANIFEST.read_text(encoding='utf-8-sig')))} "
        "report hashes recomputed from disk"
    )
    print("- .gitattributes: every hash-anchored path keeps its -text marker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
