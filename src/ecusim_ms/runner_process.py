"""Manage the CLI runner as a separate process."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from ecusim_ms.stop_flag import request_stop


class RunnerProcess:
    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self._stop_path: Optional[Path] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._on_stdout: Optional[Callable[[str], None]] = None
        self._on_stderr: Optional[Callable[[str], None]] = None

    def set_log_callbacks(
        self,
        on_stdout_line: Optional[Callable[[str], None]],
        on_stderr_line: Optional[Callable[[str], None]],
    ) -> None:
        self._on_stdout = on_stdout_line
        self._on_stderr = on_stderr_line

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _start_reader(self, stream, callback: Optional[Callable[[str], None]]) -> threading.Thread:
        def _loop():
            if stream is None or callback is None:
                return
            try:
                for line in stream:
                    if not line:
                        break
                    try:
                        callback(line.rstrip("\n"))
                    except Exception:
                        pass
            except Exception:
                pass

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        return t

    def start(
        self,
        control_path: Path | str,
        telemetry_path: Path | str,
        stop_path: Path | str,
        extra_args: Optional[Iterable[str]] = None,
    ) -> None:
        if self.is_running():
            return
        self._stop_path = Path(stop_path)
        args: List[str] = [
            sys.executable,
            "-m",
            "ecusim_ms.cli_runner",
            "--control",
            str(control_path),
            "--telemetry",
            str(telemetry_path),
            "--stop-file",
            str(stop_path),
        ]
        if extra_args:
            args.extend(extra_args)
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._stdout_thread = self._start_reader(self.proc.stdout, self._on_stdout)
        self._stderr_thread = self._start_reader(self.proc.stderr, self._on_stderr)

        # Early exit detection
        time.sleep(0.2)
        if self.proc.poll() is not None:
            try:
                stdout_tail = (self.proc.stdout.read() or "").strip() if self.proc.stdout else ""
            except Exception:
                stdout_tail = ""
            try:
                stderr_tail = (self.proc.stderr.read() or "").strip() if self.proc.stderr else ""
            except Exception:
                stderr_tail = ""
            msg = "Runner exited early."
            if stderr_tail:
                msg += f" stderr: {stderr_tail}"
            elif stdout_tail:
                msg += f" stdout: {stdout_tail}"
            raise RuntimeError(msg)

    def stop(self, grace_s: float = 3.0) -> None:
        if not self.is_running():
            self.proc = None
            return

        try:
            if self._stop_path:
                request_stop(self._stop_path)
        except Exception:
            pass

        waited = 0.0
        while self.is_running() and waited < grace_s:
            time.sleep(0.1)
            waited += 0.1

        if self.is_running():
            try:
                self.proc.terminate()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=1.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self._cleanup_threads()
        self.proc = None
        self._stop_path = None
        self._stdout_thread = None
        self._stderr_thread = None

    def force_kill(self) -> None:
        """Immediately terminate the runner process (no grace)."""
        if not self.is_running():
            self.proc = None
            self._kill_by_cmdline()
            return
        try:
            if self._stop_path:
                request_stop(self._stop_path)
        except Exception:
            pass
        pid = self.proc.pid if self.proc else None
        try:
            self.proc.terminate()
        except Exception:
            pass
        time.sleep(0.1)
        if self.is_running():
            try:
                self.proc.kill()
            except Exception:
                pass
        # Windows fallback: force kill process tree
        if self.is_running() and pid:
            try:
                import subprocess

                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        self._kill_by_cmdline()
        self._cleanup_threads()
        self.proc = None
        self._stop_path = None
        self._stdout_thread = None
        self._stderr_thread = None

    def _cleanup_threads(self) -> None:
        try:
            if self._stdout_thread:
                self._stdout_thread.join(timeout=1.0)
        except Exception:
            pass

    def _kill_by_cmdline(self) -> None:
        """Best-effort kill of any lingering cli_runner processes (Windows only)."""
        try:
            import os
            import subprocess

            if os.name != "nt":
                return
            cmd = (
                "$p = Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -match 'ecusim_ms\\.cli_runner' }; "
                "foreach ($x in $p) { taskkill /F /T /PID $x.ProcessId | Out-Null }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        try:
            if self._stderr_thread:
                self._stderr_thread.join(timeout=1.0)
        except Exception:
            pass

    def restart(
        self,
        control_path: Path | str,
        telemetry_path: Path | str,
        stop_path: Path | str,
        extra_args: Optional[Iterable[str]] = None,
    ) -> None:
        self.stop()
        self.start(control_path, telemetry_path, stop_path, extra_args=extra_args)
