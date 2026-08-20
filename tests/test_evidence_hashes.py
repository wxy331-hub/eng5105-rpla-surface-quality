import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "paper_rewriting_output" / "verify_manifest_hashes.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_manifest_hashes", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recorded_hashes_still_resolve() -> None:
    """Editing a hash-anchored file without updating its recorded SHA-256 fails here.

    Appendix A and `final_artifact_manifest.md` quote a hash for each evidence
    record, including `src/live_service.py`, `src/week3/vision.py` and
    `config/live_service.json`. The paired-report validator only compares the two
    reports against each other, so it cannot see a hash that has gone stale
    against the file it names. This test recomputes every one of them from disk
    and checks that each anchored path keeps its `-text` marker.
    """
    failures = _load_verifier().check()
    assert failures == [], "\n".join(failures)
