from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from sweagent.agent.hooks.abstract import AbstractAgentHook
from sweagent.types import AgentInfo, StepOutput, Trajectory


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActivityStreamAgentHook(AbstractAgentHook):
    """Write lightweight JSON events for each agent step.

    The resulting file can be tailed to visualize what the agent is doing
    without parsing the raw stdout stream.
    """

    def __init__(self, path: Path | str, truncate: int | None = 4000):
        self.path = Path(path)
        self.truncate = truncate
        self._lock = Lock()
        self._file = None
        self._step_index = 0
        self._attempt_index = 0

    def on_init(self, *, agent):  # type: ignore[override]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")
        self._write(
            {
                "type": "hook_initialized",
                "agent": getattr(agent, "name", "unknown"),
            }
        )

    def on_setup_attempt(self):
        self._attempt_index += 1
        self._step_index = 0
        self._write(
            {
                "type": "attempt_started",
                "attempt": self._attempt_index,
            }
        )

    def on_step_start(self):
        self._step_index += 1
        self._write(
            {
                "type": "step_started",
                "attempt": self._attempt_index,
                "step": self._step_index,
            }
        )

    def on_step_done(self, *, step: StepOutput, info: AgentInfo):
        payload: dict[str, Any] = {
            "type": "step_completed",
            "attempt": self._attempt_index,
            "step": self._step_index,
            "step_output": self._serialize_step(step),
            "info": info,
        }
        self._write(payload)

    def on_run_done(self, *, trajectory: Trajectory, info: AgentInfo):
        payload: dict[str, Any] = {
            "type": "run_completed",
            "attempt": self._attempt_index,
            "total_steps": self._step_index,
            "info": info,
        }
        self._write(payload)
        self._close()

    # Internal helpers -----------------------------------------------------

    def _serialize_step(self, step: StepOutput) -> dict[str, Any]:
        data = step.model_dump()
        for key in ("thought", "action", "output", "observation"):
            if key in data:
                data[key] = self._truncate_text(data[key])
        return data

    def _truncate_text(self, value: Any) -> Any:
        if not isinstance(value, str) or self.truncate is None:
            return value
        if len(value) <= self.truncate:
            return value
        return value[: self.truncate] + "\n... [truncated]"

    def _write(self, payload: dict[str, Any]):
        payload.setdefault("timestamp", _utc_now())
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            if self._file is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._file = self.path.open("a", encoding="utf-8")
            self._file.write(line + "\n")
            self._file.flush()

    def _close(self):
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None

    def __del__(self):  # pragma: no cover - best-effort cleanup
        self._close()
