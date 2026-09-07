import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_evidence_baselines.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_evidence_baselines", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_hashes_still_resolve() -> None:
    """Historical source hashes resolve to snapshots; all other anchors stay live."""
    failures = _load_verifier().check()
    assert failures == [], "\n".join(failures)


@pytest.fixture
def evidence_workspace(tmp_path):
    """Exercise real files and hashes without editing submission evidence."""
    verifier = _load_verifier()
    en_path = f"{verifier.PAPER}/{verifier.REPORT_NAMES[0]}"
    en = (ROOT / en_path).read_text(encoding="utf-8-sig")
    paths = set(verifier.reference_sources(en).values()) - verifier.BASELINE_SOURCES
    paths.update({f"{verifier.PAPER}/{name}" for name in verifier.REPORT_NAMES})
    paths.update({f"{verifier.PAPER}/final_artifact_manifest.md", verifier.BASELINE_MANIFEST, ".gitattributes"})
    paths.update({f"{verifier.BASELINE}/{source}" for source in verifier.BASELINE_SOURCES})
    for relative in paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, capture_output=True)
    failures = verifier.check(tmp_path)
    assert failures == [], "\n".join(failures)
    return verifier, tmp_path


def _mapping(verifier, root):
    path = root / verifier.BASELINE_MANIFEST
    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def test_current_source_changes_do_not_rewrite_historical_claims(evidence_workspace):
    verifier, root = evidence_workspace
    for relative in verifier.BASELINE_SOURCES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("current USB implementation\n", encoding="utf-8")
    assert verifier.check(root) == []


@pytest.mark.parametrize("also_update_mapping_hash", [False, True])
def test_corrupted_snapshot_cannot_pass_even_with_a_matching_mapping_hash(evidence_workspace, also_update_mapping_hash):
    verifier, root = evidence_workspace
    manifest_path, document = _mapping(verifier, root)
    entry = document["entries"][0]
    snapshot = root / entry["snapshot_path"]
    snapshot.write_bytes(snapshot.read_bytes() + b"\nchanged historical source\n")
    if also_update_mapping_hash:
        entry["sha256"] = verifier.sha256(snapshot)
        manifest_path.write_text(json.dumps(document), encoding="utf-8")
    failures = verifier.check(root)
    assert any("but Appendix A records" in failure for failure in failures)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "redirect", "escape", "source", "hash"])
def test_tampered_baseline_mapping_fails(evidence_workspace, mutation):
    verifier, root = evidence_workspace
    manifest_path, document = _mapping(verifier, root)
    entries = document["entries"]
    if mutation == "missing":
        entries.pop()
    elif mutation == "duplicate":
        entries[1] = dict(entries[0])
    elif mutation == "redirect":
        entries[0]["snapshot_path"] = entries[0]["source_path"]
    elif mutation == "escape":
        entries[0]["snapshot_path"] = "../outside.py"
    elif mutation == "source":
        entries[0]["source_path"] = "README.md"
    elif mutation == "hash":
        entries[0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    failures = verifier.check(root)
    assert any("baseline" in failure for failure in failures)


def test_missing_snapshot_never_falls_back_to_active_source(evidence_workspace):
    verifier, root = evidence_workspace
    _, document = _mapping(verifier, root)
    entry = document["entries"][0]
    active = root / entry["source_path"]
    active.parent.mkdir(parents=True, exist_ok=True)
    snapshot = root / entry["snapshot_path"]
    shutil.copyfile(snapshot, active)
    snapshot.unlink()
    assert any("missing or invalid" in failure for failure in verifier.check(root))


@pytest.mark.parametrize("relative", ["WEEK3_OFFLINE_IMPLEMENTATION.md", "paper_rewriting_output/ENG5105_Proposal_Design_Report_ZH.md"])
def test_unmapped_evidence_and_report_files_remain_hash_checked(evidence_workspace, relative):
    verifier, root = evidence_workspace
    target = root / relative
    target.write_bytes(target.read_bytes() + b"\nchanged evidence\n")
    assert any("hashes to" in failure for failure in verifier.check(root))


def test_later_text_attribute_override_invalidates_snapshot_protection(evidence_workspace):
    verifier, root = evidence_workspace
    attributes = root / ".gitattributes"
    with attributes.open("a", encoding="utf-8") as handle:
        handle.write(f"\n{verifier.BASELINE}/src/live_service.py text\n")
    assert any("no effective -text" in failure for failure in verifier.check(root))
