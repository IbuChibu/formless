from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import ScenarioSuite


DEFAULT_SCENARIO_PATH = (
    Path(__file__).parents[1] / "scenarios" / "guided_interview_baseline.json"
)


def load_scenario_suite(path: Path = DEFAULT_SCENARIO_PATH) -> ScenarioSuite:
    return ScenarioSuite.model_validate_json(path.read_text(encoding="utf-8"))


def scenario_suite_digest(suite: ScenarioSuite) -> str:
    canonical = json.dumps(
        suite.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def scenario_file_digest(path: Path = DEFAULT_SCENARIO_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
