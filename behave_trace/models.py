"""Domain models for behave-trace.

Pure dataclasses. No Behave imports — the model layer is fully reusable
and unit-testable in isolation.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

STATUS_RUNNING = "running"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_UNDEFINED = "undefined"
STATUS_UNTESTED = "untested"

ALL_STATUSES = (
    STATUS_RUNNING,
    STATUS_PASSED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_UNDEFINED,
    STATUS_UNTESTED,
)


def normalize_status(value: Any) -> str:
    """Normalize a Behave status to a canonical lowercase string."""
    if value is None:
        return STATUS_UNTESTED
    name = getattr(value, "name", None)
    name = str(value) if name is None else str(name)
    name = name.lower().strip()
    if name in ALL_STATUSES:
        return name
    return STATUS_UNTESTED


# ---------------------------------------------------------------------------
# Artifacts — captured per step
# ---------------------------------------------------------------------------

ARTIFACT_SCREENSHOT = "screenshot"
ARTIFACT_DOM = "dom"
ARTIFACT_LOG = "log"
ARTIFACT_EXCEPTION = "exception"
ARTIFACT_TEXT = "text"
ARTIFACT_JSON = "json"
ARTIFACT_FILE = "file"
ARTIFACT_NETWORK = "network"

# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------

LOG_INFO = "info"
LOG_WARNING = "warning"
LOG_ERROR = "error"

ALL_LOG_LEVELS = (LOG_INFO, LOG_WARNING, LOG_ERROR)

_VALID_LEVELS = frozenset(ALL_LOG_LEVELS)


def normalize_level(level: Any) -> str:
    """Normalize a log level to a canonical lowercase string.

    Accepts strings or any other type; non-string inputs are coerced
    via ``str()`` so the function never raises.
    """
    if not level:
        return LOG_INFO
    name = str(level).lower().strip()
    if name in _VALID_LEVELS:
        return name
    # Common aliases
    if name == "warn":
        return LOG_WARNING
    if name in ("err", "fatal", "critical"):
        return LOG_ERROR
    return LOG_INFO


@dataclass(slots=True)
class Artifact:
    """An artifact captured during a step execution."""

    type: str
    name: str = ""
    mime_type: str = "application/octet-stream"
    data_base64: str = ""
    text: str | None = None

    @property
    def is_image(self) -> bool:
        return self.mime_type.startswith("image/")

    @property
    def is_text(self) -> bool:
        return self.mime_type.startswith("text/") or self.mime_type in {
            "application/json",
            "application/xml",
            "text/html",
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "type": self.type,
            "name": self.name,
            "mime_type": self.mime_type,
            "data_base64": self.data_base64,
            "text": self.text,
        }


@dataclass(slots=True)
class ErrorInfo:
    """Captured error information for a failing step."""

    message: str = ""
    traceback: str = ""
    exception_type: str = ""


@dataclass(slots=True)
class DataTable:
    """A Gherkin data table."""

    headings: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Step:
    """A single Gherkin step with its execution trace."""

    keyword: str
    name: str
    status: str = STATUS_UNTESTED
    duration: float = 0.0
    location: str = ""
    text: str | None = None
    table: DataTable | None = None
    error: ErrorInfo | None = None
    artifacts: list[Artifact] = field(default_factory=list)
    logs: list[str | dict[str, Any]] = field(default_factory=list)

    @property
    def has_screenshot(self) -> bool:
        return any(a.type == ARTIFACT_SCREENSHOT for a in self.artifacts)

    @property
    def has_dom(self) -> bool:
        return any(a.type == ARTIFACT_DOM for a in self.artifacts)

    @property
    def has_network(self) -> bool:
        return any(a.type == ARTIFACT_NETWORK for a in self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "keyword": self.keyword,
            "name": self.name,
            "status": self.status,
            "duration": self.duration,
            "location": self.location,
            "text": self.text,
            "table": as_dict(self.table) if self.table else None,
            "error": as_dict(self.error) if self.error else None,
            "artifacts": [as_dict(a) for a in self.artifacts],
            "logs": self.logs,
            "has_screenshot": self.has_screenshot,
            "has_dom": self.has_dom,
            "has_network": self.has_network,
        }


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Background:
    """A Gherkin background shared by scenarios in a feature."""

    name: str = ""
    keyword: str = "Background"
    steps: list[Step] = field(default_factory=list)
    location: str = ""


@dataclass(slots=True)
class Scenario:
    """A scenario or scenario outline example."""

    name: str
    status: str = STATUS_UNTESTED
    duration: float = 0.0
    description: str = ""
    location: str = ""
    tags: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    background: Background | None = None
    feature_name: str = ""
    rule_name: str = ""
    is_outline: bool = False
    outline_name: str = ""
    examples: DataTable | None = None

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == STATUS_PASSED)

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == STATUS_FAILED)

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "name": self.name,
            "status": self.status,
            "duration": self.duration,
            "description": self.description,
            "location": self.location,
            "tags": self.tags,
            "steps": [s.to_dict() for s in self.steps],
            "background": as_dict(self.background) if self.background else None,
            "feature_name": self.feature_name,
            "rule_name": self.rule_name,
            "is_outline": self.is_outline,
            "outline_name": self.outline_name,
            "examples": as_dict(self.examples) if self.examples else None,
            "step_count": self.step_count,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
        }


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Feature:
    """A Gherkin feature."""

    name: str
    status: str = STATUS_UNTESTED
    duration: float = 0.0
    description: str = ""
    location: str = ""
    tags: list[str] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    background: Background | None = None

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "name": self.name,
            "status": self.status,
            "duration": self.duration,
            "description": self.description,
            "location": self.location,
            "tags": self.tags,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "background": as_dict(self.background) if self.background else None,
            "scenario_count": self.scenario_count,
        }


# ---------------------------------------------------------------------------
# Environment & statistics
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Environment:
    """Information about the host running the suite."""

    python_version: str = ""
    behave_version: str = ""
    behave_trace_version: str = ""
    platform: str = ""
    hostname: str = ""
    cwd: str = ""
    command: str = ""
    user: str = ""
    cpu_count: int = 0
    memory_mb: int = 0
    git_branch: str = ""
    git_commit: str = ""
    git_remote: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class TraceStats:
    """Aggregate counters and timings."""

    total_features: int = 0
    total_scenarios: int = 0
    total_steps: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    duration: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None
    total_artifacts: int = 0
    total_screenshots: int = 0
    total_logs: int = 0
    slowest_step_duration: float = 0.0
    slowest_step_name: str = ""
    avg_step_duration: float = 0.0

    @property
    def passed(self) -> int:
        return self.by_status.get(STATUS_PASSED, 0)

    @property
    def failed(self) -> int:
        return self.by_status.get(STATUS_FAILED, 0)

    @property
    def skipped(self) -> int:
        return self.by_status.get(STATUS_SKIPPED, 0)

    @property
    def pass_rate(self) -> float:
        total = self.total_scenarios
        return (self.passed / total * 100.0) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "total_features": self.total_features,
            "total_scenarios": self.total_scenarios,
            "total_steps": self.total_steps,
            "by_status": self.by_status,
            "duration": self.duration,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_artifacts": self.total_artifacts,
            "total_screenshots": self.total_screenshots,
            "total_logs": self.total_logs,
            "slowest_step_duration": self.slowest_step_duration,
            "slowest_step_name": self.slowest_step_name,
            "avg_step_duration": self.avg_step_duration,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "pass_rate": self.pass_rate,
        }


# ---------------------------------------------------------------------------
# Trace — root
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Trace:
    """Root of the trace tree — serialized to .trace file."""

    version: str = "1"
    created_at: datetime = field(default_factory=datetime.now)
    features: list[Feature] = field(default_factory=list)
    environment: Environment = field(default_factory=Environment)
    stats: TraceStats = field(default_factory=TraceStats)

    @property
    def overall_status(self) -> str:
        statuses = [f.status for f in self.features]
        if any(s == STATUS_FAILED for s in statuses):
            return STATUS_FAILED
        if any(s == STATUS_UNDEFINED for s in statuses):
            return STATUS_UNDEFINED
        if any(s == STATUS_PASSED for s in statuses):
            return STATUS_PASSED
        if statuses and all(s == STATUS_SKIPPED for s in statuses):
            return STATUS_SKIPPED
        return STATUS_UNTESTED

    def to_dict(self) -> dict[str, Any]:
        """Serialize including computed properties for the viewer frontend."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "features": [f.to_dict() for f in self.features],
            "environment": as_dict(self.environment),
            "stats": as_dict(self.stats),
            "overall_status": self.overall_status,
        }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def as_dict(obj: Any) -> Any:
    """Recursively convert dataclass instances to plain dicts.

    Uses ``to_dict()`` when available (includes computed @property fields
    needed by the viewer frontend), otherwise falls back to field-only
    serialization.
    """
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return obj.to_dict()
    if dataclasses.is_dataclass(obj):
        return {f.name: as_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, list):
        return [as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: as_dict(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj
