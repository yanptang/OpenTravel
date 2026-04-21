"""OpenTravel Local CLI 主入口。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from opentravel.clarifier import clarify_request
from opentravel.editor import edit_plan_interactively
from opentravel.input_validation import validate_request
from opentravel.models import PlannerConfig
from opentravel.progress import ProgressReporter
from opentravel.plan_validation import validate_plan
from opentravel.planner import generate_plan
from opentravel.refiner import refine_plan
from opentravel.renderer import render_markdown, render_text


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="OpenTravel Local CLI")
    parser.add_argument("--input", default="sample_request.json")
    parser.add_argument("--output", default="")
    parser.add_argument("--render-output", default="")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--model", default="ollama/qwen3.5:4b")
    parser.add_argument("--api-base", default="http://localhost:11434")
    parser.add_argument("--planner-mode", default="daily", choices=["daily", "whole"])
    parser.add_argument("--render-format", default="markdown", choices=["markdown", "text"])
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--refine-retries", type=int, default=2)
    parser.add_argument("--no-clarify", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--edit", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.input)
    if not request_path.is_absolute():
        request_path = (base_dir / request_path).resolve()
    if not request_path.exists():
        print(f"Request file not found: {request_path}")
        return 1

    request = _load_json(request_path)
    detected_language = detect_language(request)
    request["language"] = detected_language
    progress = ProgressReporter(enabled=(not args.no_progress), language=detected_language)
    progress.stage("已读取需求文件，开始初始化", percent=1)

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

    if not args.no_clarify:
        progress.stage("进入多轮澄清", percent=2)
        request = clarify_request(request, config=config, progress=progress)
        detected_language = detect_language(request)
        request["language"] = detected_language
        config.preferred_language = detected_language
        progress.language = detected_language

    progress.stage("校验输入需求", percent=3)
    req_result = validate_request(request)
    if not req_result.valid:
        print("Input validation failed:")
        for err in req_result.errors:
            print(f"- {err}")
        return 1

    artifact_dir = _resolve_artifact_dir(base_dir, args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    progress.stage("保存输入快照", percent=4)
    request_snapshot = artifact_dir / "request.json"
    request_snapshot.write_text(
        json.dumps(request, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved request snapshot to: {request_snapshot}")

    progress.stage("开始生成行程", percent=5)
    plan = generate_plan(request, config, progress=progress)
    progress.stage("开始校验行程", percent=75)
    validation = validate_plan(plan)
    retries = 0

    while config.use_llm and (not validation.valid) and retries < config.refine_retries:
        print(f"Plan validation failed. Trying refine pass {retries + 1}...")
        refined = refine_plan(request, plan, validation.errors, config)
        if refined is None:
            break
        plan = refined
        validation = validate_plan(plan)
        retries += 1

    if not validation.valid:
        print("Final plan still has validation issues:")
        for err in validation.errors:
            print(f"- {err}")
    else:
        print("Plan validation passed.")

    if args.edit:
        progress.stage("进入手动编辑", percent=85)
        plan = edit_plan_interactively(plan)
        validation = validate_plan(plan)
        print("Post-edit validation:", "PASS" if validation.valid else "FAIL")
        if not validation.valid:
            for err in validation.errors:
                print(f"- {err}")

    output_path = (
        Path(args.output).resolve()
        if args.output
        else (artifact_dir / "plan.json").resolve()
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved plan JSON to: {output_path}")

    progress.stage("渲染 Markdown 攻略", percent=95)
    render_output_path = (
        Path(args.render_output).resolve()
        if args.render_output
        else (
            artifact_dir / ("plan.md" if args.render_format == "markdown" else "plan.txt")
        ).resolve()
    )
    render_output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_text = render_plan(plan, language=config.preferred_language, fmt=args.render_format)
    render_output_path.write_text(rendered_text, encoding="utf-8")
    print(f"Saved human-readable itinerary to: {render_output_path}")
    print("\n--- Preview ---\n")
    print(rendered_text)
    progress.stage("完成", percent=100)
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object.")
    return data


def _resolve_artifact_dir(base_dir: Path, artifact_dir: str) -> Path:
    if artifact_dir:
        return Path(artifact_dir).resolve()
    return (base_dir / "outputs" / "latest").resolve()


def detect_language(request: dict[str, Any]) -> str:
    values = _collect_string_values(request)
    text = "\n".join(values)
    zh_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if zh_count > 0 and zh_count >= latin_count:
        return "zh"
    if zh_count == 0 and latin_count > 0:
        return "en"
    if latin_count > zh_count * 2 and latin_count > 30:
        return "en"
    return "zh"


def _collect_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        collected: list[str] = []
        for item in value.values():
            collected.extend(_collect_string_values(item))
        return collected
    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            collected.extend(_collect_string_values(item))
        return collected
    return []


def render_plan(plan: dict[str, Any], language: str, fmt: str) -> str:
    if fmt == "markdown":
        return render_markdown(plan, language=language)
    return render_text(plan, language=language)


if __name__ == "__main__":
    raise SystemExit(main())
