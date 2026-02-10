import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config.file_watcher import FileWatcher


@pytest.fixture
def watcher():
    """FileWatcher 인스턴스를 생성하고, 테스트 후 정리한다."""
    fw = FileWatcher(poll_interval=0.05)
    yield fw
    fw.stop()


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """임시 파일을 생성한다."""
    f = tmp_path / "config.txt"
    f.write_text("initial content")
    return f


class TestInit:
    def test_default_poll_interval(self):
        """기본 poll_interval 은 1.0 이다."""
        fw = FileWatcher()
        assert fw.poll_interval == 1.0

    def test_custom_poll_interval(self, watcher: FileWatcher):
        """사용자 지정 poll_interval 이 올바르게 설정된다."""
        assert watcher.poll_interval == 0.05

    def test_initially_not_running(self, watcher: FileWatcher):
        """초기 상태에서 _running 은 False 이다."""
        assert watcher._running is False

    def test_initially_no_watched_files(self, watcher: FileWatcher):
        """초기 상태에서 감시 파일이 없다."""
        assert watcher._watched_files == {}

    def test_initially_no_callbacks(self, watcher: FileWatcher):
        """초기 상태에서 콜백이 없다."""
        assert watcher._callbacks == {}

    def test_initially_no_thread(self, watcher: FileWatcher):
        """초기 상태에서 스레드가 None 이다."""
        assert watcher._thread is None


class TestWatch:
    def test_registers_file_hash(self, watcher: FileWatcher, sample_file: Path):
        """watch 호출 시 파일 해시가 등록된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        resolved = sample_file.resolve()
        assert resolved in watcher._watched_files
        assert watcher._watched_files[resolved] != ""

    def test_registers_callback(self, watcher: FileWatcher, sample_file: Path):
        """watch 호출 시 콜백이 등록된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        resolved = sample_file.resolve()
        assert watcher._callbacks[resolved] is callback

    def test_auto_starts_watcher(self, watcher: FileWatcher, sample_file: Path):
        """watch 호출 시 자동으로 watcher 스레드가 시작된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        assert watcher._running is True
        assert watcher._thread is not None
        assert watcher._thread.is_alive()

    def test_nonexistent_file_registers_empty_hash(self, watcher: FileWatcher, tmp_path: Path):
        """존재하지 않는 파일을 watch 하면 빈 해시가 등록된다."""
        missing = tmp_path / "nonexistent.txt"
        callback = MagicMock()
        watcher.watch(str(missing), callback)

        resolved = missing.resolve()
        assert watcher._watched_files[resolved] == ""


class TestUnwatch:
    def test_removes_file_and_callback(self, watcher: FileWatcher, sample_file: Path):
        """unwatch 호출 시 파일과 콜백이 제거된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)
        watcher.unwatch(str(sample_file))

        resolved = sample_file.resolve()
        assert resolved not in watcher._watched_files
        assert resolved not in watcher._callbacks

    def test_unwatch_nonexistent_file_no_error(self, watcher: FileWatcher, tmp_path: Path):
        """등록되지 않은 파일을 unwatch 해도 에러가 발생하지 않는다."""
        watcher.unwatch(str(tmp_path / "unknown.txt"))


class TestStartStop:
    def test_start_creates_daemon_thread(self, watcher: FileWatcher):
        """start 호출 시 데몬 스레드가 생성된다."""
        watcher.start()

        assert watcher._running is True
        assert watcher._thread.daemon is True

    def test_start_is_idempotent(self, watcher: FileWatcher):
        """start 를 여러 번 호출해도 스레드가 하나만 생성된다."""
        watcher.start()
        thread = watcher._thread
        watcher.start()

        assert watcher._thread is thread

    def test_stop_clears_thread(self, watcher: FileWatcher):
        """stop 호출 시 스레드가 정리된다."""
        watcher.start()
        watcher.stop()

        assert watcher._running is False
        assert watcher._thread is None

    def test_stop_without_start_no_error(self, watcher: FileWatcher):
        """start 없이 stop 을 호출해도 에러가 발생하지 않는다."""
        watcher.stop()


class TestFileChangeDetection:
    def test_callback_triggered_on_file_change(self, watcher: FileWatcher, sample_file: Path):
        """파일이 변경되면 콜백이 호출된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        sample_file.write_text("changed content")
        time.sleep(0.2)

        callback.assert_called_once_with(sample_file.resolve())

    def test_callback_not_triggered_without_change(self, watcher: FileWatcher, sample_file: Path):
        """파일이 변경되지 않으면 콜백이 호출되지 않는다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        time.sleep(0.2)

        callback.assert_not_called()

    def test_hash_updated_after_change(self, watcher: FileWatcher, sample_file: Path):
        """파일 변경 후 해시가 갱신된다."""
        callback = MagicMock()
        watcher.watch(str(sample_file), callback)

        resolved = sample_file.resolve()
        old_hash = watcher._watched_files[resolved]

        sample_file.write_text("new content")
        time.sleep(0.2)

        assert watcher._watched_files[resolved] != old_hash

    def test_callback_error_does_not_crash_watcher(self, watcher: FileWatcher, sample_file: Path):
        """콜백에서 예외가 발생해도 watcher 가 중단되지 않는다."""
        callback = MagicMock(side_effect=RuntimeError("callback error"))
        watcher.watch(str(sample_file), callback)

        sample_file.write_text("trigger change")
        time.sleep(0.2)

        assert watcher._running is True
        assert watcher._thread.is_alive()


class TestGetFileHash:
    def test_returns_md5_hex_digest(self, sample_file: Path):
        """파일 해시가 MD5 hex digest 형식이다."""
        result = FileWatcher._get_file_hash(sample_file)

        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_content_same_hash(self, tmp_path: Path):
        """같은 내용의 파일은 같은 해시를 반환한다."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same")
        f2.write_text("same")

        assert FileWatcher._get_file_hash(f1) == FileWatcher._get_file_hash(f2)

    def test_different_content_different_hash(self, tmp_path: Path):
        """다른 내용의 파일은 다른 해시를 반환한다."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content1")
        f2.write_text("content2")

        assert FileWatcher._get_file_hash(f1) != FileWatcher._get_file_hash(f2)

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        """존재하지 않는 파일은 빈 문자열을 반환한다."""
        result = FileWatcher._get_file_hash(tmp_path / "missing.txt")

        assert result == ""
