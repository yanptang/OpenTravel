from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from opentravel.clarifier import clarify_request
from opentravel.editor import edit_plan_interactively
from opentravel.input_validation import validate_request
from opentravel.models import PlannerConfig
from opentravel.plan_validation import validate_plan
from opentravel.planner import generate_plan
from opentravel.refiner import refine_plan
from opentravel.renderer import render_text


def main() -> int:
    # 命令行入口：负责读取需求、执行生成、校验、导出和可选编辑。
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="OpenTravel Local CLI")
    parser.add_argument("--input", default="sample_request.json")
    parser.add_argument("--output", default="")
    parser.add_argument("--render-output", default="")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--model", default="ollama/qwen3.5:4b")
    parser.add_argument("--api-base", default="http://localhost:11434")
    parser.add_argument("--planner-mode", default="daily", choices=["daily", "whole"])
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--refine-retries", type=int, default=2)
    parser.add_argument("--no-clarify", action="store_true")
    parser.add_argument("--edit", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.input)
    if not request_path.is_absolute():
        request_path = (base_dir / request_path).resolve()
    if not request_path.exists():
        print(f"Request file not found: {request_path}")
        return 1
    request = _load_json(request_path)

    config = PlannerConfig(
        use_llm=(not args.no_llm),
        model=args.model,
        api_base=args.api_base,
        planner_mode=args.planner_mode,
        max_tokens=max(128, args.max_tokens),
        request_timeout_sec=max(30, args.timeout_sec),
        refine_retries=max(0, args.refine_retries),
    )

    if not args.no_clarify:
        request = clarify_request(request, config=config)

    req_result = validate_request(request)
    if not req_result.valid:
        print("Input validation failed:")
        for err in req_result.errors:
            print(f"- {err}")
        return 1

    # 先生成整份计划，底层会根据 planner_mode 决定是 whole 还是 daily。
    plan = generate_plan(request, config)

    validation = validate_plan(plan)
    retries = 0
    # 如果真实模型输出不合格，最多尝试修正几轮。
    while (
        config.use_llm
        and (not validation.valid)
        and retries < config.refine_retries
    ):
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
        # 进入终端交互编辑模式，支持删除、修改和重看结果。
        plan = edit_plan_interactively(plan)
        validation = validate_plan(plan)
        print("Post-edit validation:", "PASS" if validation.valid else "FAIL")
        if not validation.valid:
            for err in validation.errors:
                print(f"- {err}")

    # 导出结构化 JSON，便于后续做程序化处理。
    output_path = (
        Path(args.output).resolve()
        if args.output
        else (base_dir / "outputs" / "plan.json").resolve()
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved plan JSON to: {output_path}")

    # 导出人类可读版本，方便直接查看和分享。
    render_output_path = (
        Path(args.render_output).resolve()
        if args.render_output
        else (base_dir / "outputs" / "plan.txt").resolve()
    )
    render_output_path.parent.mkdir(parents=True, exist_ok=True)
    render_output_path.write_text(render_text(plan), encoding="utf-8")
    print(f"Saved human-readable itinerary to: {render_output_path}")
    print("\n--- Preview ---\n")
    print(render_text(plan))
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object.")
    return data


if __name__ == "__main__":
    raise SystemExit(main())
