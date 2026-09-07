"""Session-scoped deletion, rollback, recovery, and archive path boundaries."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import subprocess
from uuid import uuid4

import numpy as np
import pytest

from src.week3.models import CameraState, FramePacket
from src.week7.store import SampleStore


def add_capture(store, session, *, retake=False):
    image = np.full((12, 16, 3), 100, dtype=np.uint8)
    packet = FramePacket("SYNTHETIC", 1, "2026-09-07T00:00:00Z", "2026-09-07T00:00:00Z",
                         CameraState.HEALTHY, image)
    return store.save_capture(session, 0, "bright_field", packet, image.copy(), [],
                              lighting_metadata={}, retake=retake)


def file_snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*.png")}


def test_delete_session_removes_records_events_and_all_retake_images_only(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("same label")['session_id']
    other = store.create_sample("same label")['session_id']
    for index in range(3):
        add_capture(store, session, retake=index > 0)
    other_capture = add_capture(store, other)
    event = store.append_event(other, "KEEP", {})
    store.append_event(session, "REMOVE", {})
    other_before = store.get_sample(other)
    other_bytes = store.image_path(other_capture['capture_id'], 'raw').read_bytes()
    result = store.delete_sample(session)
    assert result == {
        "deleted_session_id": session, "sample_id": "same label", "deleted_capture_count": 3,
        "deleted_image_count": 6, "cleanup_pending": False, "pending_image_count": 0,
    }
    assert not (tmp_path / 'images' / session).exists()
    assert not list(tmp_path.glob('.delete-*'))
    assert store.get_sample(other) == other_before
    assert store.get_sample(other)['events'] == [event]
    assert store.image_path(other_capture['capture_id'], 'raw').read_bytes() == other_bytes
    with pytest.raises(KeyError):
        store.get_sample(session)
    with sqlite3.connect(store.path) as connection:
        for table in ('samples', 'captures', 'sample_events', 'sample_deletion_cleanup'):
            assert connection.execute(f'SELECT COUNT(*) FROM {table} WHERE session_id=?', (session,)).fetchone()[0] == 0


def test_empty_and_missing_file_archives_can_be_deleted(tmp_path):
    store = SampleStore(tmp_path)
    empty = store.create_sample('empty')['session_id']
    assert store.delete_sample(empty)['deleted_image_count'] == 0
    partial = store.create_sample('missing image')['session_id']
    capture = add_capture(store, partial)
    store.image_path(capture['capture_id'], 'raw').unlink()
    assert store.delete_sample(partial)['deleted_image_count'] == 1
    missing = store.create_sample('missing archive')['session_id']
    capture = add_capture(store, missing)
    for kind in ('raw', 'annotated'):
        store.image_path(capture['capture_id'], kind).unlink()
    (tmp_path / 'images' / missing / capture['capture_id']).rmdir()
    (tmp_path / 'images' / missing).rmdir()
    assert store.delete_sample(missing)['deleted_capture_count'] == 1


def test_completed_session_can_be_deleted(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample('completed')['session_id']
    add_capture(store, session)
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE samples SET completed_at_utc=? WHERE session_id=?', ('2026-09-07', session))
    assert store.delete_sample(session)['cleanup_pending'] is False


def test_sql_failure_restores_all_files_and_rows(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample('rollback')['session_id']
    add_capture(store, session)
    add_capture(store, session, retake=True)
    store.append_event(session, 'KEEP', {})
    before = store.get_sample(session)
    files = file_snapshot(tmp_path)
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON samples "
                           "BEGIN SELECT RAISE(ABORT, 'simulated deletion failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='simulated deletion failure'):
        store.delete_sample(session)
    assert store.get_sample(session) == before
    assert file_snapshot(tmp_path) == files
    assert not list(tmp_path.glob('.delete-*'))


def test_rename_failure_keeps_rows_and_original_images(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample('locked directory')['session_id']
    add_capture(store, session)
    before = store.get_sample(session)
    files = file_snapshot(tmp_path)
    original = Path.rename

    def locked(path, target):
        if path.name == session:
            raise PermissionError('simulated locked directory')
        return original(path, target)

    monkeypatch.setattr(Path, 'rename', locked)
    with pytest.raises(PermissionError, match='locked directory'):
        store.delete_sample(session)
    assert store.get_sample(session) == before
    assert file_snapshot(tmp_path) == files


def test_sql_commit_failure_restores_the_staged_archive(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample('commit failure')['session_id']
    add_capture(store, session)
    before = store.get_sample(session)
    files = file_snapshot(tmp_path)
    original = sqlite3.connect

    class FailDeletionCommit(sqlite3.Connection):
        def commit(self):
            if self.execute('SELECT COUNT(*) FROM sample_deletion_cleanup').fetchone()[0]:
                raise sqlite3.OperationalError('simulated commit failure')
            return super().commit()

    monkeypatch.setattr(sqlite3, 'connect', lambda *args, **kwargs: original(
        *args, **kwargs, factory=FailDeletionCommit,
    ))
    with pytest.raises(sqlite3.OperationalError, match='commit failure'):
        store.delete_sample(session)
    assert store.get_sample(session) == before
    assert file_snapshot(tmp_path) == files
    assert not list(tmp_path.glob('.delete-*'))


def test_interruption_after_commit_leaves_a_durable_discoverable_cleanup_job(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample('stopped before purge')['session_id']
    add_capture(store, session)

    def process_stop(pending):
        raise SystemExit('simulated stopped process')

    monkeypatch.setattr(store, '_finish_sample_deletion', process_stop)
    with pytest.raises(SystemExit):
        store.delete_sample(session)
    restarted = SampleStore(tmp_path)
    with pytest.raises(KeyError):
        restarted.get_sample(session)
    assert restarted.list_pending_deletions()[0]['deleted_session_id'] == session
    assert restarted.delete_sample(session)['deleted_image_count'] == 2
    assert restarted.list_pending_deletions() == []


def test_partial_purge_is_explicitly_pending_and_retryable_after_restart(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample('retry cleanup')['session_id']
    add_capture(store, session)
    original = store._purge_sample_deletion

    def interrupted(directory):
        next(directory.rglob('raw.png')).unlink()
        raise PermissionError('simulated image lock')

    monkeypatch.setattr(store, '_purge_sample_deletion', interrupted)
    result = store.delete_sample(session)
    assert result['cleanup_pending'] is True
    assert result['deleted_capture_count'] == 1
    assert result['deleted_image_count'] == result['pending_image_count'] == 1
    assert 'simulated image lock' in result['cleanup_error']
    with pytest.raises(KeyError):
        store.get_sample(session)
    assert len(list(tmp_path.glob('.delete-*'))) == 1
    monkeypatch.setattr(store, '_purge_sample_deletion', original)
    final = SampleStore(tmp_path).delete_sample(session)
    assert final['cleanup_pending'] is False
    assert final['deleted_image_count'] == 2
    assert not list(tmp_path.glob('.delete-*'))


def test_pending_deletions_remain_discoverable_after_restart_without_image_reads(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample('visible after refresh')['session_id']
    add_capture(store, session)

    def locked(directory):
        raise PermissionError('simulated image lock')

    monkeypatch.setattr(store, '_purge_sample_deletion', locked)
    assert store.delete_sample(session)['cleanup_pending'] is True
    restarted = SampleStore(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(restarted, '_delete_tree_files', lambda *args: pytest.fail('unexpected image read'))
        assert restarted.list_pending_deletions() == [{
            'deleted_session_id': session, 'sample_id': 'visible after refresh',
            'deleted_capture_count': 1, 'cleanup_pending': True,
            'pending_image_count_upper_bound': 2,
        }]
    restarted.delete_sample(session)
    assert restarted.list_pending_deletions() == []


def test_interruption_before_sql_commit_is_recovered_before_retry(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample('recover move')['session_id']
    add_capture(store, session)
    archive = tmp_path / 'images' / session
    staging = tmp_path / f'.delete-{session}.{uuid4().hex}.pending'
    archive.rename(staging)
    # This represents a stopped process: SQLite rolled back but the rename did not.
    result = SampleStore(tmp_path).delete_sample(session)
    assert result['deleted_image_count'] == 2
    assert not staging.exists()


@pytest.mark.parametrize('malicious', ['../outside.png', '/outside.png', 'images/../outside.png',
                                      'images/other/raw.png'])
def test_database_path_tampering_is_rejected_without_removing_anything(tmp_path, malicious):
    store = SampleStore(tmp_path)
    session = store.create_sample('tampered path')['session_id']
    capture = add_capture(store, session)
    files = file_snapshot(tmp_path)
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE captures SET raw_image_path=? WHERE capture_id=?',
                           (malicious, capture['capture_id']))
    with pytest.raises(ValueError, match='not owned'):
        store.delete_sample(session)
    assert file_snapshot(tmp_path) == files
    with sqlite3.connect(store.path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM samples').fetchone()[0] == 1


def test_archive_referenced_by_another_session_is_rejected(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample('target')['session_id']
    other = store.create_sample('other')['session_id']
    target_capture = add_capture(store, session)
    other_capture = add_capture(store, other)
    files = file_snapshot(tmp_path)
    with sqlite3.connect(store.path) as connection:
        connection.execute('UPDATE captures SET raw_image_path=? WHERE capture_id=?',
                           (target_capture['raw_image_path'], other_capture['capture_id']))
    with pytest.raises(ValueError, match='shared'):
        store.delete_sample(session)
    assert file_snapshot(tmp_path) == files


def test_unknown_file_inside_session_is_preserved_and_blocks_deletion(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample('unexpected file')['session_id']
    saved = add_capture(store, session)
    notes = tmp_path / 'images' / session / saved['capture_id'] / 'notes.txt'
    notes.write_text('preserve me')
    with pytest.raises(ValueError, match='Unexpected file'):
        store.delete_sample(session)
    assert notes.read_text() == 'preserve me'
    assert store.get_sample(session)['captures']


@pytest.mark.parametrize('location', ['session', 'capture', 'image'])
def test_symlinks_are_rejected_without_touching_the_target(tmp_path, location):
    store = SampleStore(tmp_path / 'store')
    session = store.create_sample('linked path')['session_id']
    saved = add_capture(store, session)
    archive = store.root / 'images' / session
    target = tmp_path / 'outside'
    target.mkdir()
    marker = target / 'raw.png'
    marker.write_bytes(b'outside data')
    if location == 'session':
        link = archive
    elif location == 'capture':
        link = archive / saved['capture_id']
    else:
        link = archive / saved['capture_id'] / 'raw.png'
    parked = link.with_name(link.name + '.original')
    link.rename(parked)
    try:
        link.symlink_to(marker if location == 'image' else target, target_is_directory=location != 'image')
    except OSError as error:
        if os.name == 'nt' and location != 'image':
            # Directory junctions need no administrator privilege and exercise
            # Windows' reparse-point boundary when symlink creation is disabled.
            junction = subprocess.run(
                ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if junction.returncode != 0:
                parked.rename(link)
                pytest.skip(f'symlink and junction unavailable: {error}')
        else:
            parked.rename(link)
            pytest.skip(f'symlink unavailable: {error}')
    with pytest.raises(ValueError, match='link|Unexpected directory'):
        store.delete_sample(session)
    assert marker.read_bytes() == b'outside data'


@pytest.mark.parametrize('session', ['../images', '', 'a' * 32, uuid4().hex.upper()])
def test_invalid_session_identifiers_are_rejected(tmp_path, session):
    with pytest.raises(ValueError, match='UUID'):
        SampleStore(tmp_path).delete_sample(session)


def test_unknown_valid_session_is_not_found(tmp_path):
    with pytest.raises(KeyError):
        SampleStore(tmp_path).delete_sample(uuid4().hex)


def test_delete_of_one_session_keeps_parallel_capture_in_another(tmp_path):
    first = SampleStore(tmp_path)
    second = SampleStore(tmp_path)
    session = first.create_sample('delete')['session_id']
    other = first.create_sample('keep')['session_id']
    add_capture(first, session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(first.delete_sample, session)
        capture = pool.submit(add_capture, second, other)
        assert deletion.result()['cleanup_pending'] is False
        saved = capture.result()
    assert second.image_path(saved['capture_id'], 'raw').is_file()
    assert [sample['session_id'] for sample in first.list_samples()] == [other]
