"""Behave formatter entry point for behave-trace.

Register via entry point (pyproject.toml)::

    [project.entry-points."behave.formatters"]
    behave-trace = "behave_trace.formatter:TraceFormatter"

Then run::

    behave --format behave-trace -o trace.json
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Any

try:
    from behave.formatter.base import Formatter
except Exception:  # pragma: no cover - Behave optional at import time
    Formatter = object

from .collector import Collector
from .models import Artifact


class TraceFormatter(Formatter):  # type: ignore[misc]
    """Behave formatter that captures execution trace data."""

    name = "behave-trace"
    description = "Capture execution trace for behave-trace viewer"

    def __init__(self, stream_opener: Any, config: Any) -> None:
        super().__init__(stream_opener, config)
        self._collector = Collector()
        self._output_path = self._resolve_output_path(stream_opener, config)

        self._behave_feature: Any = None
        self._behave_scenario: Any = None

    # ------------------------------------------------------------------
    # Behave lifecycle
    # ------------------------------------------------------------------

    def feature(self, feature: Any) -> None:
        self._behave_feature = feature
        self._collector.on_feature(feature)

    def background(self, background: Any) -> None:
        pass

    def rule(self, rule: Any) -> None:
        self._collector.on_rule(rule)

    def scenario(self, scenario: Any) -> None:
        if self._behave_scenario is not None:
            self._collector.on_scenario_end(self._behave_scenario)
        self._behave_scenario = scenario
        self._collector.on_scenario(scenario)

    def step(self, step: Any) -> None:
        pass

    def match(self, match: Any) -> None:
        pass

    def result(self, step: Any) -> None:
        self._collector.on_step(step)

    def eof(self) -> None:
        if self._behave_scenario is not None:
            self._collector.on_scenario_end(self._behave_scenario)
            self._behave_scenario = None
        if self._behave_feature is not None:
            self._collector.on_feature_end(self._behave_feature)
            self._behave_feature = None

    def close(self) -> None:
        from .serializer import Serializer

        trace = self._collector.finalize()
        Serializer.save(trace, self._output_path)
        with contextlib.suppress(Exception):
            sys.stdout.write(
                f"\nTrace written to: {self._output_path}\n"
                f"View with: behave-trace show {self._output_path}\n"
            )

    # ------------------------------------------------------------------
    # Public attachment API (for environment.py hooks)
    # ------------------------------------------------------------------

    def attach(self, artifact: Artifact) -> None:
        self._collector.attach(artifact)

    def log(self, message: str) -> None:
        self._collector.log(message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_output_path(stream_opener: Any, config: Any) -> Path:
        candidate = getattr(stream_opener, "name", None) or getattr(stream_opener, "filename", None)
        if candidate:
            return Path(candidate)
        outputs = getattr(config, "outputs", None) or []
        for output in outputs:
            name = getattr(output, "name", None)
            if name and name not in ("<stdout>", "<stderr>"):
                return Path(name)
        return Path("trace.json")
