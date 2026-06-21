"""Unit tests for ModuleStatusRegistry."""
import pytest
import time
import threading
from src.module_registry import (
    ModuleStatus, ModuleStatusRegistry, ModuleInfo,
)


class TestModuleStatus:
    def test_running_is_ok(self):
        assert ModuleStatus.RUNNING.is_ok is True

    def test_degraded_is_ok(self):
        assert ModuleStatus.DEGRADED.is_ok is True

    def test_error_is_not_ok(self):
        assert ModuleStatus.ERROR.is_ok is False

    def test_error_is_error(self):
        assert ModuleStatus.ERROR.is_error is True
        assert ModuleStatus.RUNNING.is_error is False

    def test_uninitialized_is_not_ok(self):
        assert ModuleStatus.UNINITIALIZED.is_ok is False


class TestDefaultModules:
    def test_default_has_five_modules(self):
        r = ModuleStatusRegistry()
        hc = r.health_check()
        assert set(hc.keys()) == {"audio", "asr", "translation", "overlay", "storage"}

    def test_all_default_to_uninitialized(self):
        r = ModuleStatusRegistry()
        hc = r.health_check()
        for status in hc.values():
            assert status == ModuleStatus.UNINITIALIZED

    def test_custom_modules(self):
        r = ModuleStatusRegistry(modules=["alpha", "beta"])
        assert set(r.health_check().keys()) == {"alpha", "beta"}


class TestSetGetStatus:
    def test_set_and_get(self):
        r = ModuleStatusRegistry()
        r.set_status("audio", ModuleStatus.RUNNING, "ok")
        assert r.get_status("audio") == ModuleStatus.RUNNING
        info = r.get_info("audio")
        assert info is not None
        assert info.status == ModuleStatus.RUNNING
        assert info.message == "ok"

    def test_unknown_module_returns_uninitialized(self):
        r = ModuleStatusRegistry()
        assert r.get_status("nonexistent") == ModuleStatus.UNINITIALIZED

    def test_get_info_unknown_returns_none(self):
        r = ModuleStatusRegistry()
        assert r.get_info("nonexistent") is None

    def test_register_adds_module(self):
        r = ModuleStatusRegistry(modules=["audio"])
        r.register("new_module")
        assert r.get_status("new_module") == ModuleStatus.UNINITIALIZED

    def test_set_status_auto_registers(self):
        r = ModuleStatusRegistry(modules=[])
        r.set_status("spontaneous", ModuleStatus.RUNNING)
        assert r.get_status("spontaneous") == ModuleStatus.RUNNING


class TestIsReady:
    def test_running_is_ready(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        assert r.is_ready("audio") is True

    def test_degraded_is_ready(self):
        r = ModuleStatusRegistry()
        r.mark_degraded("translation", "no API key")
        assert r.is_ready("translation") is True

    def test_uninitialized_not_ready(self):
        r = ModuleStatusRegistry()
        assert r.is_ready("audio") is False

    def test_error_not_ready(self):
        r = ModuleStatusRegistry()
        r.mark_error("audio", "device missing")
        assert r.is_ready("audio") is False


class TestHealthCheck:
    def test_all_running(self):
        r = ModuleStatusRegistry()
        for m in ("audio", "asr", "translation", "overlay", "storage"):
            r.mark_running(m)
        assert r.all_ready() is True

    def test_one_degraded_still_all_ready(self):
        r = ModuleStatusRegistry()
        for m in ("audio", "asr", "translation", "overlay", "storage"):
            r.mark_running(m)
        r.mark_degraded("translation")
        assert r.all_ready() is True

    def test_one_error_not_all_ready(self):
        r = ModuleStatusRegistry()
        for m in ("audio", "asr", "translation", "overlay", "storage"):
            r.mark_running(m)
        r.mark_error("storage")
        assert r.all_ready() is False

    def test_has_errors(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_error("asr")
        assert r.has_errors() is True

    def test_no_errors(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_degraded("translation")
        assert r.has_errors() is False

    def test_new_registry_all_uninitialized_not_ready(self):
        """All modules UNINITIALIZED → all_ready() must be False."""
        r = ModuleStatusRegistry()
        assert r.all_ready() is False

    def test_some_running_others_uninitialized_not_ready(self):
        """Only audio/asr running, others UNINITIALIZED → all_ready() False."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        # translation, overlay, storage are still UNINITIALIZED
        assert r.all_ready() is False

    def test_all_five_running_is_ready(self):
        """All 5 default modules RUNNING → all_ready() True."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        r.mark_running("translation")
        r.mark_running("overlay")
        r.mark_running("storage")
        assert r.all_ready() is True

    def test_translation_degraded_others_running_is_ready(self):
        """translation DEGRADED, others RUNNING → all_ready() True."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        r.mark_degraded("translation")
        r.mark_running("overlay")
        r.mark_running("storage")
        assert r.all_ready() is True

    def test_one_module_error_not_ready(self):
        """asr ERROR → all_ready() False."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_error("asr", "model crash")
        r.mark_running("translation")
        r.mark_running("overlay")
        r.mark_running("storage")
        assert r.all_ready() is False

    def test_one_module_stopped_not_ready(self):
        """overlay STOPPED → all_ready() False."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        r.mark_running("translation")
        r.set_status("overlay", ModuleStatus.STOPPED)
        r.mark_running("storage")
        assert r.all_ready() is False

    def test_one_module_starting_not_ready(self):
        """storage still STARTING → all_ready() False."""
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        r.mark_running("translation")
        r.mark_running("overlay")
        r.set_status("storage", ModuleStatus.STARTING)
        assert r.all_ready() is False

    def test_empty_registry_not_ready(self):
        """Empty registry (no modules) → all_ready() False."""
        r = ModuleStatusRegistry(modules=[])
        assert r.all_ready() is False


class TestWaitForReady:
    def test_immediately_ready(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        assert r.wait_for_ready(["audio", "asr"], timeout=1.0) is True

    def test_times_out(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        # asr stays UNINITIALIZED
        assert r.wait_for_ready(["audio", "asr"], timeout=0.5) is False

    def test_becomes_ready_after_delay(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        # asr becomes ready after a short delay
        def _later():
            time.sleep(0.2)
            r.mark_running("asr")
        t = threading.Thread(target=_later, daemon=True)
        t.start()
        assert r.wait_for_ready(["audio", "asr"], timeout=2.0) is True


class TestThreadSafety:
    def test_concurrent_writes(self):
        r = ModuleStatusRegistry()
        errors = []

        def writer(start_idx: int):
            for i in range(start_idx, start_idx + 50):
                try:
                    r.set_status(f"m{i}", ModuleStatus.RUNNING)
                except Exception as e:
                    errors.append(str(e))

        threads = [
            threading.Thread(target=writer, args=(i,), daemon=True)
            for i in range(0, 200, 50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert r.get_status("m0") == ModuleStatus.RUNNING
        assert r.get_status("m199") == ModuleStatus.RUNNING

    def test_concurrent_reads_during_writes(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        done = threading.Event()

        def reader():
            while not done.is_set():
                r.health_check()
                r.all_ready()
                r.has_errors()

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        for i in range(100):
            r.set_status(f"mod{i}", ModuleStatus.RUNNING)

        done.set()
        t.join(timeout=2)
        # No crash = pass


class TestModuleFailureDoesNotAffectSession:
    """Simulation: module DEGRADED / ERROR should not change session state."""
    def test_degraded_translation_everything_else_running(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_running("asr")
        r.mark_degraded("translation", "API key missing")
        r.mark_running("overlay")
        r.mark_running("storage")

        # Session should still be healthy from the registry perspective
        assert r.is_ready("audio") is True
        assert r.is_ready("asr") is True
        assert r.is_ready("translation") is True  # DEGRADED is still OK
        assert r.is_ready("overlay") is True
        assert r.is_ready("storage") is True
        assert r.all_ready() is True
        assert r.has_errors() is False

    def test_asr_error_but_other_modules_running(self):
        r = ModuleStatusRegistry()
        r.mark_running("audio")
        r.mark_error("asr", "model load failed")
        r.mark_running("translation")
        r.mark_running("overlay")
        r.mark_running("storage")

        assert r.is_ready("asr") is False
        assert r.has_errors() is True
        assert r.all_ready() is False
        # audio / translation / overlay / storage are still running
        assert r.is_ready("audio") is True
        assert r.is_ready("overlay") is True
