import json
from pathlib import Path

import pytest

from scripts.openmontage_chat.orchestrator import LocalOrchestrator, parse_decision
from scripts.openmontage_chat.project_store import ProjectStore


class FakeTool:
    name = "fixture_writer"
    capability = "video_post"
    provider = "local"
    capabilities = ["write_fixture"]
    input_schema = {"type": "object", "required": ["output_path"], "properties": {"output_path": {"type": "string"}}}
    side_effects = ["writes output"]
    resource_profile = type("Resource", (), {"network_required": False})()

    def get_status(self):
        return type("Status", (), {"value": "available"})()

    def get_info(self):
        return {"name": self.name, "capability": self.capability, "provider": self.provider, "capabilities": self.capabilities, "input_schema": self.input_schema, "side_effects": self.side_effects}


class FakeRegistry:
    def __init__(self):
        self.tools = {"fixture_writer": FakeTool()}

    def get_available(self):
        return list(self.tools.values())

    def get(self, name):
        return self.tools.get(name)


class FakeAdapter:
    def __init__(self):
        self.registry = FakeRegistry()
        self.calls = []

    def run(self, name, params):
        self.calls.append((name, params))
        path = Path(params["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        return {"ok": True, "data": {"output": str(path)}, "artifacts": [str(path)], "cost_usd": 0}


def _decision(**changes):
    value = {
        "intent": "source_edit", "confidence": 0.8, "known_brief": {},
        "questions": [], "enhancements": [], "ready_to_plan": False,
        "response": "Уточню задачу", "plan": None,
    }
    value.update(changes)
    return value


def _pipeline(root: Path):
    path = root / "pipeline_defs" / "documentary-montage.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: documentary-montage\n", encoding="utf-8")


def _staged_pipeline(root: Path):
    path = root / "pipeline_defs" / "fixture-pipeline.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""name: fixture-pipeline
stages:
  - name: compose
    skill: pipelines/fixture/compose-director
    produces: [render_report]
    tools_available: [fixture_writer]
    human_approval_default: false
""", encoding="utf-8")


def _ordered_pipeline(root: Path):
    path = root / "pipeline_defs" / "ordered.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("""name: ordered
stages:
  - name: idea
    skill: pipelines/fixture/idea-director
    produces: [brief]
    tools_available: []
    human_approval_default: true
  - name: compose
    skill: pipelines/fixture/compose-director
    produces: [render_report]
    tools_available: [fixture_writer]
    human_approval_default: false
""", encoding="utf-8")


def test_decision_parser_bounds_questions_and_improvements():
    value = _decision(
        questions=[{"question_id": str(i), "text": "Q", "choices": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]} for i in range(5)],
        enhancements=[{"enhancement_id": str(i), "label": "E", "benefit": "B", "cost": "C"} for i in range(5)],
    )

    parsed = parse_decision(json.dumps(value, ensure_ascii=False))

    assert len(parsed["questions"]) == 3
    assert len(parsed["enhancements"]) == 3


def test_decision_parser_keeps_only_concise_answerable_questions():
    value = _decision(questions=[
        {"question_id": "platform", "text": "Куда готовим видео?", "choices": [
            {"value": "shorts", "label": "Shorts", "recommended": False},
            {"value": "youtube", "label": "YouTube", "recommended": True},
            {"value": "other", "label": "Другое", "recommended": False},
            {"value": "extra", "label": "Лишнее", "recommended": False},
        ]},
        {"question_id": "broken", "text": "Без вариантов", "choices": []},
    ])

    parsed = parse_decision(json.dumps(value, ensure_ascii=False))

    assert len(parsed["questions"]) == 1
    assert [choice["value"] for choice in parsed["questions"][0]["choices"]] == ["youtube", "shorts", "other"]


def test_capability_envelope_contains_only_available_non_network_tools(tmp_path: Path):
    adapter = FakeAdapter()
    remote = FakeTool()
    remote.name = "cloud_generator"
    remote.resource_profile = type("Resource", (), {"network_required": True})()
    adapter.registry.tools[remote.name] = remote
    orchestrator = LocalOrchestrator(tmp_path, store=ProjectStore(tmp_path), adapter=adapter, model_chat=lambda payload: {})

    envelope = orchestrator.capability_envelope()

    assert [tool["name"] for tool in envelope] == ["fixture_writer"]


def test_submit_persists_concise_questions_without_executing(tmp_path: Path):
    store = ProjectStore(tmp_path)
    state = store.create("Brief")
    adapter = FakeAdapter()
    response = _decision(questions=[{
        "question_id": "platform", "text": "Куда готовим видео?",
        "choices": [{"value": "youtube", "label": "YouTube 16:9", "recommended": True}, {"value": "shorts", "label": "Shorts 9:16"}],
        "blocking": True,
    }])
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter, model_chat=lambda payload: {"message": {"content": json.dumps(response, ensure_ascii=False)}})

    result = orchestrator.submit(state["project_id"], "Смонтируй", "confirm")

    assert result["status"] == "needs_brief"
    assert result["brief"]["questions"][0]["question_id"] == "platform"
    assert adapter.calls == []


def test_confirm_mode_saves_valid_plan_without_running_it(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Plan")
    adapter = FakeAdapter()
    output = str(Path(state["project_root"]) / "renders" / "v001" / "result.txt")
    response = _decision(
        ready_to_plan=True, response="План готов",
        plan={"pipeline": "documentary-montage", "summary": "Создать результат", "steps": [{"tool": "fixture_writer", "params": {"output_path": output}, "label": "Монтаж"}]},
    )
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter, model_chat=lambda payload: {"message": {"content": json.dumps(response, ensure_ascii=False)}})

    result = orchestrator.submit(state["project_id"], "Делай", "confirm")

    assert result["status"] == "awaiting_approval"
    assert result["plan"]["steps"][0]["tool"] == "fixture_writer"
    assert adapter.calls == []


def test_approve_executes_and_marks_ready_only_after_verification(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Run")
    adapter = FakeAdapter()
    output = str(Path(state["project_root"]) / "renders" / "v001" / "result.txt")
    store.save_plan(state["project_id"], {"pipeline": "documentary-montage", "summary": "Write", "steps": [{"tool": "fixture_writer", "params": {"output_path": output}, "label": "Write"}]})
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter, model_chat=lambda payload: {})

    result = orchestrator.approve_plan(state["project_id"])

    assert result["status"] == "ready"
    assert result["verified_artifact"]["path"] == output
    assert adapter.calls[0][0] == "fixture_writer"


def test_approve_creates_project_output_directories_before_tool_runs(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Output dirs")
    adapter = FakeAdapter()
    output = Path(state["project_root"]) / "renders" / "v001" / "nested" / "result.txt"
    store.save_plan(state["project_id"], {"pipeline": "documentary-montage", "steps": [{"tool": "fixture_writer", "params": {"output_path": str(output)}}]})
    observed = []
    original_run = adapter.run
    adapter.run = lambda name, params: observed.append(Path(params["output_path"]).parent.is_dir()) or original_run(name, params)

    LocalOrchestrator(tmp_path, store=store, adapter=adapter).approve_plan(state["project_id"])

    assert observed == [True]


def test_plan_rejects_unknown_tool_and_outside_output(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Blocked")
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=FakeAdapter(), model_chat=lambda payload: {})

    with pytest.raises(ValueError, match="unavailable"):
        orchestrator.validate_plan(state["project_id"], {"pipeline": "documentary-montage", "steps": [{"tool": "missing", "params": {}}]})
    with pytest.raises(ValueError, match="outside"):
        orchestrator.validate_plan(state["project_id"], {"pipeline": "documentary-montage", "steps": [{"tool": "fixture_writer", "params": {"output_path": str(tmp_path / "escape.txt")}}]})


def test_plan_rejects_params_that_do_not_match_tool_schema(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Schema")
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=FakeAdapter(), model_chat=lambda payload: {})

    with pytest.raises(ValueError, match="invalid parameters"):
        orchestrator.validate_plan(state["project_id"], {
            "pipeline": "documentary-montage", "steps": [{"tool": "fixture_writer", "params": {}}],
        })


def test_plan_rejects_undeclared_source_paths(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Sources")
    tool = FakeTool()
    tool.input_schema = {"type": "object", "required": ["input_path", "output_path"], "properties": {"input_path": {"type": "string"}, "output_path": {"type": "string"}}}
    adapter = FakeAdapter()
    adapter.registry.tools["fixture_writer"] = tool
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter)

    with pytest.raises(ValueError, match="undeclared source"):
        orchestrator.validate_plan(state["project_id"], {"pipeline": "documentary-montage", "steps": [{
            "tool": "fixture_writer", "params": {
                "input_path": str(tmp_path / "secret.mp4"),
                "output_path": str(Path(state["project_root"]) / "renders" / "out.txt"),
            },
        }]})


def test_read_only_mode_never_saves_or_executes_a_plan(tmp_path: Path):
    _pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Read only")
    adapter = FakeAdapter()
    output = str(Path(state["project_root"]) / "renders" / "v001" / "result.txt")
    response = _decision(
        ready_to_plan=True, response="Могу подготовить план",
        plan={"pipeline": "documentary-montage", "summary": "Write", "steps": [{"tool": "fixture_writer", "params": {"output_path": output}}]},
    )
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter, model_chat=lambda payload: {"message": {"content": json.dumps(response)}})

    result = orchestrator.submit(state["project_id"], "Проверь", "read_only")

    assert result["status"] == "ready_to_plan"
    assert result["plan"] is None
    assert adapter.calls == []


def test_plan_is_bound_to_manifest_stage_tools_and_expected_outputs(tmp_path: Path):
    _staged_pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Manifest")
    output = str(Path(state["project_root"]) / "renders" / "final.txt")
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=FakeAdapter())

    plan = orchestrator.validate_plan(state["project_id"], {
        "pipeline": "fixture-pipeline", "stage": "compose",
        "steps": [{"tool": "fixture_writer", "params": {"output_path": output}}],
        "expected_artifacts": [{"key": "final", "path": output, "required": True}],
    })
    assert plan["stage_contract"]["skill"] == "pipelines/fixture/compose-director"
    assert plan["stage_contract"]["produces"] == ["render_report"]

    with pytest.raises(ValueError, match="стадии"):
        orchestrator.validate_plan(state["project_id"], {
            "pipeline": "fixture-pipeline", "stage": "missing",
            "steps": [{"tool": "fixture_writer", "params": {"output_path": output}}],
        })


def test_approval_requires_active_plan_id_and_every_expected_artifact(tmp_path: Path):
    _staged_pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("All outputs")
    adapter = FakeAdapter()
    output = str(Path(state["project_root"]) / "renders" / "final.txt")
    missing = str(Path(state["project_root"]) / "artifacts" / "report.json")
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=adapter)
    validated = orchestrator.validate_plan(state["project_id"], {
        "pipeline": "fixture-pipeline", "stage": "compose",
        "steps": [{"tool": "fixture_writer", "params": {"output_path": output}}],
        "expected_artifacts": [
            {"key": "final", "path": output, "required": True},
            {"key": "report", "path": missing, "required": True},
        ],
    })
    saved = store.save_plan(state["project_id"], validated, mode="confirm")

    with pytest.raises(ValueError, match="устарел"):
        orchestrator.approve_plan(state["project_id"], "wrong", "confirm")
    result = orchestrator.approve_plan(state["project_id"], saved["plan_id"], "confirm")
    assert result["status"] == "needs_attention"
    assert result["artifacts_state"]["verified"][0]["path"] == output


def test_plan_cannot_skip_incomplete_manifest_stages(tmp_path: Path):
    _ordered_pipeline(tmp_path)
    store = ProjectStore(tmp_path)
    state = store.create("Order")
    output = str(Path(state["project_root"]) / "renders" / "final.txt")
    orchestrator = LocalOrchestrator(tmp_path, store=store, adapter=FakeAdapter())

    with pytest.raises(ValueError, match="следующая стадия.*idea"):
        orchestrator.validate_plan(state["project_id"], {
            "pipeline": "ordered", "stage": "compose",
            "steps": [{"tool": "fixture_writer", "params": {"output_path": output}}],
        })
