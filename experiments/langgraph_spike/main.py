from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_AGENT_DIR = ROOT_DIR / "LocalAgentCLI"
EXPERIMENT_DIR = Path(__file__).resolve().parent

if str(LOCAL_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_AGENT_DIR))

from main import detect_language  # noqa: E402
from opentravel.input_validation import validate_request  # noqa: E402
from opentravel.models import PlannerConfig  # noqa: E402
from opentravel.plan_validation import validate_plan  # noqa: E402
from opentravel.planner import generate_plan  # noqa: E402
from opentravel.refiner import refine_plan  # noqa: E402
from opentravel.renderer import render_markdown  # noqa: E402


class GraphState(TypedDict, total=False):
    request: dict[str, Any]
    config: PlannerConfig
    artifact_dir: str
    plan: dict[str, Any] | None
    validation_errors: list[str]
    validation_valid: bool
    round_index: int
    max_rounds: int
    history: list[dict[str, Any]]
    rendered_markdown: str


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenTravel LangGraph spike")
    parser.add_argument("--input", default=r"..\..\LocalAgentCLI\inputs\sample_request.json")
    parser.add_argument("--model", default="ollama/qwen3.5:4b")
    parser.add_argument("--api-base", default="http://localhost:11434")
    parser.add_argument("--planner-mode", default="whole", choices=["daily", "whole"])
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--refine-retries", type=int, default=2)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--artifact-dir", default="")
    args = parser.parse_args()

    request_path = _resolve_input_path(args.input)
    if not request_path.exists():
        print(f"Request file not found: {request_path}")
        return 1

    request = _load_json(request_path)
    detected_language = detect_language(request)
    request["language"] = detected_language

    req_result = validate_request(request)
    if not req_result.valid:
        print("Input validation failed:")
        for err in req_result.errors:
            print(f"- {err}")
        return 1

    config = PlannerConfig(
        use_llm=(not args.no_llm),
        model=args.model,
        api_base=args.api_base,
        planner_mode=args.planner_mode,
        preferred_language=detected_language,
        max_tokens=max(128, args.max_tokens),
        request_timeout_sec=max(30, args.timeout_sec),
        refine_retries=max(0, args.refine_retries),
    )

    artifact_dir = _resolve_artifact_dir(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "request.json", request)

    app = build_graph()
    final_state = app.invoke(
        {
            "request": request,
            "config": config,
            "artifact_dir": str(artifact_dir),
            "plan": None,
            "validation_errors": [],
            "validation_valid": False,
            "round_index": 0,
            "max_rounds": config.refine_retries,
            "history": [],
            "rendered_markdown": "",
        }
    )

    print("\n--- LangGraph Summary ---\n")
    for step in final_state.get("history", []):
        if step.get("node") == "validate":
            print(
                f"round={step.get('round_index')} "
                f"valid={step.get('valid')} "
                f"errors={step.get('error_count')}"
            )

    if final_state.get("rendered_markdown"):
        print("\n--- Preview ---\n")
        _safe_console_print(final_state["rendered_markdown"])

    print(f"Saved LangGraph artifacts to: {artifact_dir}")
    return 0


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("generate", generate_node)
    graph.add_node("validate", validate_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "refine": "refine",
            "finalize": "finalize",
        },
    )
    graph.add_edge("refine", "validate")
    graph.add_edge("finalize", END)
    return graph.compile()


def generate_node(state: GraphState) -> GraphState:
    request = state["request"]
    config = state["config"]
    artifact_dir = Path(state["artifact_dir"])
    plan = generate_plan(request, config, progress=None)
    _write_json(artifact_dir / "00_generated.json", plan)
    _write_text(
        artifact_dir / "00_generated.md",
        render_markdown(plan, language=config.preferred_language),
    )
    history = list(state.get("history", []))
    history.append(
        {
            "node": "generate",
            "planner_mode": config.planner_mode,
            "use_llm": config.use_llm,
        }
    )
    return {"plan": plan, "history": history}


def validate_node(state: GraphState) -> GraphState:
    artifact_dir = Path(state["artifact_dir"])
    plan = state.get("plan")
    history = list(state.get("history", []))
    if not plan:
        history.append(
            {
                "node": "validate",
                "round_index": state.get("round_index", 0),
                "valid": False,
                "error_count": 1,
                "errors": ["Plan is missing before validation."],
            }
        )
        return {
            "validation_valid": False,
            "validation_errors": ["Plan is missing before validation."],
            "history": history,
        }

    result = validate_plan(plan)
    round_index = state.get("round_index", 0)
    if round_index > 0:
        label = f"round_{round_index:02d}_plan"
        _write_json(artifact_dir / f"{label}.json", plan)
        _write_text(
            artifact_dir / f"{label}.md",
            render_markdown(plan, language=state["config"].preferred_language),
        )
    history.append(
        {
            "node": "validate",
            "round_index": round_index,
            "valid": result.valid,
            "error_count": len(result.errors),
            "errors": list(result.errors),
        }
    )
    return {
        "validation_valid": result.valid,
        "validation_errors": list(result.errors),
        "history": history,
    }


def route_after_validate(state: GraphState) -> str:
    if state.get("validation_valid", False):
        return "finalize"
    if state.get("round_index", 0) >= state.get("max_rounds", 0):
        return "finalize"
    return "refine"


def refine_node(state: GraphState) -> GraphState:
    request = state["request"]
    config = state["config"]
    current_plan = state.get("plan")
    if not current_plan:
        return {"round_index": state.get("round_index", 0) + 1}

    next_round = state.get("round_index", 0) + 1
    repaired = refine_plan(
        request=request,
        current_plan=current_plan,
        errors=state.get("validation_errors", []),
        config=config,
    )
    history = list(state.get("history", []))
    history.append(
        {
            "node": "refine",
            "round_index": next_round,
            "changed": repaired is not None and repaired != current_plan,
            "incoming_error_count": len(state.get("validation_errors", [])),
        }
    )
    return {
        "plan": repaired or current_plan,
        "round_index": next_round,
        "history": history,
    }


def finalize_node(state: GraphState) -> GraphState:
    artifact_dir = Path(state["artifact_dir"])
    plan = state.get("plan")
    if not plan:
        return state

    rendered = render_markdown(plan, language=state["config"].preferred_language)
    _write_json(artifact_dir / "99_final.json", plan)
    _write_text(artifact_dir / "99_final.md", rendered)
    _write_json(
        artifact_dir / "graph_summary.json",
        {
            "final_valid": state.get("validation_valid", False),
            "remaining_errors": list(state.get("validation_errors", [])),
            "round_index": state.get("round_index", 0),
            "history": state.get("history", []),
        },
    )
    _write_json(artifact_dir / "plan.json", plan)
    _write_text(artifact_dir / "plan.md", rendered)
    return {"rendered_markdown": rendered}


def _resolve_input_path(raw_input: str) -> Path:
    candidate = Path(raw_input)
    if candidate.is_absolute():
        return candidate.resolve()
    return (Path.cwd() / candidate).resolve()


def _resolve_artifact_dir(raw_artifact_dir: str) -> Path:
    if raw_artifact_dir:
        return Path(raw_artifact_dir).resolve()
    return (EXPERIMENT_DIR / "outputs" / "latest").resolve()


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object.")
    return data


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _safe_console_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoded = text.encode(sys.stdout.encoding or "utf-8", errors="replace")
        sys.stdout.buffer.write(encoded + b"\n")


if __name__ == "__main__":
    raise SystemExit(main())
