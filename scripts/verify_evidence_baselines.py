#!/usr/bin/env python3
"""Verify historical report evidence against explicit, immutable source snapshots.

Only the three source records in BASELINE_SOURCES resolve to the dated baseline.
Their expected hashes still come from Appendix A, never from the new mapping.
Other evidence and the paired-report artifact hashes resolve as originally named.
This check does not assert that current application source equals historical code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAPER = "paper_rewriting_output"
REPORT_NAMES = ("ENG5105_Proposal_Design_Report_EN.md", "ENG5105_Proposal_Design_Report_ZH.md")
BASELINE = "data/baselines/plan_b_before_uvc_20260906"
BASELINE_MANIFEST = f"{BASELINE}/manifest.json"
BASELINE_SOURCES = frozenset({"config/live_service.json", "src/live_service.py", "src/week3/vision.py"})

# Keep the original report formats; the historical verifier itself stays intact.
EVIDENCE_ROW = re.compile(
    r"(?m)^\|\s*(IE\d+)\s*\|\s*\(ENG5105 Project Team, ((?:19|20)\d{2}[a-z]?)\)\s*"
    r"\|[^|]*\|\s*`([A-F0-9]{64})`\s*\|$"
)
MANIFEST_ROW = re.compile(r"(?m)^\|\s*`([^`]+)`\s*\|\s*`([A-F0-9]{64})`\s*\|")
REFERENCE_ENTRY = re.compile(
    r"(?m)^ENG5105 Project Team\. \(((?:19|20)\d{2}[a-z]?)\)\. (?P<rest>[^\n]+)$"
)
SOURCE_FILE = re.compile(r"source file:\s*`([^`]+)`")


def _safe_path(root: Path, relative: str, *, frozen: bool = False) -> Path:
    if not isinstance(relative, str) or not relative or any(char in relative for char in ("\\", ":", "\0")):
        raise ValueError(f"invalid workspace-relative path: {relative!r}")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative or relative == ".":
        raise ValueError(f"invalid workspace-relative path: {relative!r}")
    target = root.joinpath(*path.parts)
    resolved = target.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes workspace: {relative}")
    if frozen and resolved != target:
        raise ValueError(f"frozen baseline must not redirect through symlinks: {relative}")
    return target


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def reference_sources(text: str) -> dict[str, str]:
    sections = re.split(r"(?m)^# (?:References|参考文献)\s*$", text, maxsplit=1)
    if len(sections) != 2:
        raise ValueError("report References section not found")
    sources: dict[str, str] = {}
    for year, entry in REFERENCE_ENTRY.findall(sections[1].strip()):
        match = SOURCE_FILE.search(entry)
        if match:
            if year in sources:
                raise ValueError(f"duplicate internal source reference: {year}")
            sources[year] = match.group(1)
    return sources


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate baseline manifest key: {key}")
        result[key] = value
    return result


def _baseline_mapping(root: Path) -> dict[str, dict[str, str]]:
    path = _safe_path(root, BASELINE_MANIFEST, frozen=True)
    document = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object)
    if not isinstance(document, dict) or type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ValueError("baseline manifest requires schema_version 1")
    entries = document.get("entries")
    if not isinstance(entries, list) or len(entries) != len(BASELINE_SOURCES):
        raise ValueError("baseline mapping must contain exactly the three historical source records")
    result: dict[str, dict[str, str]] = {}
    snapshots: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"source_path", "snapshot_path", "sha256"}:
            raise ValueError("baseline entry must contain source_path, snapshot_path and sha256")
        source, snapshot, recorded = entry["source_path"], entry["snapshot_path"], entry["sha256"]
        if not isinstance(source, str) or source not in BASELINE_SOURCES:
            raise ValueError(f"baseline mapping contains an unauthorized source: {source!r}")
        if source in result:
            raise ValueError(f"duplicate baseline source mapping: {source}")
        if snapshot != f"{BASELINE}/{source}":
            raise ValueError(f"baseline snapshot mapping must preserve its source path: {source}")
        _safe_path(root, snapshot, frozen=True)
        if snapshot in snapshots:
            raise ValueError(f"duplicate baseline snapshot mapping: {snapshot}")
        if not isinstance(recorded, str) or re.fullmatch(r"[A-Fa-f0-9]{64}", recorded) is None:
            raise ValueError(f"baseline mapping has an invalid SHA-256: {source}")
        result[source] = entry
        snapshots.add(snapshot)
    if set(result) != BASELINE_SOURCES:
        raise ValueError("baseline mapping is missing a historical source record")
    return result


def _check_text_attributes(root: Path, anchored: set[str]) -> list[str]:
    failures: list[str] = []
    try:
        if not _safe_path(root, ".gitattributes").is_file():
            return [".gitattributes is missing, so -text protection cannot be confirmed"]
        # Git evaluates **, nested attribute files, and later overrides correctly.
        # Ignore global/system files so another host cannot supply missing rules.
        env = {**os.environ, "GIT_ATTR_NOSYSTEM": "1"}
        command = ["git", "-C", str(root), "-c", f"core.attributesFile={os.devnull}"]
        top = subprocess.run(command + ["rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, check=True, timeout=10, env=env)
        if Path(top.stdout.strip()).resolve() != root:
            return ["-text validation requires the specified workspace to be its Git repository root"]
        result = subprocess.run(command + ["check-attr", "-z", "--stdin", "text"],
                                input="".join(f"{path}\0" for path in sorted(anchored)),
                                capture_output=True, text=True, check=True, timeout=10, env=env)
        values = result.stdout.split("\0")
        if values[-1:] == [""]:
            values.pop()
        if len(values) != 3 * len(anchored):
            return ["git check-attr returned an incomplete -text result"]
        seen: set[str] = set()
        for index in range(0, len(values), 3):
            relative, attribute, value = values[index:index + 3]
            if relative not in anchored or relative in seen or attribute != "text":
                return ["git check-attr returned an unexpected -text result"]
            seen.add(relative)
            if value != "unset":
                failures.append(f"{relative} has no effective -text protection (text={value})")
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        failures.append(f"could not verify -text protection: {exc}")
    return failures


def check(root: Path = ROOT) -> list[str]:
    root = Path(root).resolve()
    failures: list[str] = []
    anchored: set[str] = {BASELINE_MANIFEST}
    try:
        mapping = _baseline_mapping(root)
    except (OSError, RuntimeError, ValueError) as exc:
        # Never fall back to current source when its historical mapping is invalid.
        return [f"baseline mapping: {exc}"]
    try:
        en, zh = (_safe_path(root, f"{PAPER}/{name}").read_text(encoding="utf-8-sig") for name in REPORT_NAMES)
        manifest = _safe_path(root, f"{PAPER}/final_artifact_manifest.md").read_text(encoding="utf-8-sig")
        en_sources, zh_sources = reference_sources(en), reference_sources(zh)
    except (OSError, RuntimeError, ValueError) as exc:
        return [f"report evidence: {exc}"]

    en_rows, zh_rows = EVIDENCE_ROW.findall(en), EVIDENCE_ROW.findall(zh)
    if not en_rows:
        failures.append("Appendix A evidence rows not found in the English report")
    if en_rows != zh_rows:
        failures.append("Appendix A identifiers, references or hashes differ between English and Chinese")
    if len({identifier for identifier, _, _ in en_rows}) != len(en_rows):
        failures.append("Appendix A contains duplicate evidence identifiers")
    mapped_sources: set[str] = set()
    for identifier, reference, recorded in en_rows:
        relative = en_sources.get(reference)
        if relative is None:
            failures.append(f"{identifier}: reference {reference} names no source file")
            continue
        if zh_sources.get(reference) != relative:
            failures.append(f"{identifier}: English and Chinese source paths differ")
        resolved_relative = relative
        if relative in mapping:
            mapped_sources.add(relative)
            entry = mapping[relative]
            resolved_relative = entry["snapshot_path"]
            if entry["sha256"].upper() != recorded:
                failures.append(f"{identifier}: baseline mapping hash for {relative} differs from Appendix A")
        try:
            target = _safe_path(root, resolved_relative, frozen=relative in mapping)
            anchored.add(resolved_relative)
            actual = sha256(target)
            if actual != recorded:
                failures.append(f"{identifier}: {resolved_relative} hashes to {actual} but Appendix A records {recorded}")
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append(f"{identifier}: {resolved_relative} is missing or invalid: {exc}")
    if mapped_sources != BASELINE_SOURCES:
        failures.append("Appendix A does not reference all three historical source mappings")

    manifest_rows = MANIFEST_ROW.findall(manifest)
    if sorted(name for name, _ in manifest_rows) != sorted(REPORT_NAMES):
        failures.append("artifact manifest must contain exactly the English and Chinese report rows")
    for name, recorded in manifest_rows:
        try:
            relative = f"{PAPER}/{name}"
            target = _safe_path(root, relative)
            anchored.add(relative)
            actual = sha256(target)
            if actual != recorded:
                failures.append(f"manifest: {name} hashes to {actual} but the manifest records {recorded}")
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append(f"manifest: {name} is missing or invalid: {exc}")
    failures.extend(_check_text_attributes(root, anchored))
    return failures


def main() -> int:
    failures = check()
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("PASS")
    print("- Appendix A: three historical source records checked against frozen Plan B snapshots")
    print("- Other evidence and both report hashes checked against their original files")
    print("- Historical expected hashes come from the reports; current application source is separate")
    print("- Every checked evidence file and the baseline mapping has effective -text protection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
