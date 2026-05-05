from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from opentravel.plan_validation import validate_plan


BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR / "outputs" / "eval_runs"


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    cli_args: tuple[str, ...]


SCENARIOS: dict[str, Scenario] = {
    "no_llm": Scenario(
        name="no_llm",
        description="Rule-based scaffold baseline without model calls.",
        cli_args=("--no-llm", "--no-clarify", "--no-weather"),
    ),
    "llm_skip_repair": Scenario(
        name="llm_skip_repair",
        description="Model generation baseline without refinement.",
        cli_args=("--planner-mode", "whole", "--no-clarify", "--no-weather", "--skip-repair"),
    ),
    "llm_repair": Scenario(
        name="llm_repair",
        description="Full mainline path: generation, validation, refinement.",
        cli_args=("--planner-mode", "whole", "--no-clarify", "--no-weather"),
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenTravel evaluation matrix.")
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=[],
        help="Specific input JSON names or paths. Defaults to all request JSON files in LocalAgentCLI/inputs/.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=["no_llm", "llm_skip_repair", "llm_repair"],
        choices=sorted(SCENARIOS.keys()),
        help="Scenario matrix to run.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional model override for LLM scenarios, e.g. ollama/qwen3.5:4b.",
    )
    parser.add_argument(
        "--api-base",
        default="",
        help="Optional API base override for LLM scenarios.",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Optional run label. Defaults to timestamp.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional evaluation output directory. Defaults to outputs/eval_runs/<label>/.",
    )
    args = parser.parse_args()

    input_paths = resolve_input_paths(args.inputs)
    if not input_paths:
        print("No input JSON files found for evaluation.", file=sys.stderr)
        return 1

    run_label = args.label or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (EVAL_DIR / run_label).resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    print(f"Evaluation run label: {run_label}")
    print(f"Evaluation output dir: {output_dir}")

    for scenario_name in args.scenarios:
        scenario = SCENARIOS[scenario_name]
        for input_path in input_paths:
            result = run_case(
                input_path=input_path,
                scenario=scenario,
                output_dir=output_dir,
                model_override=args.model,
                api_base_override=args.api_base,
            )
            results.append(result)
            print(
                f"[{scenario.name}] {input_path.name}: "
                f"success={result['run_success']} "
                f"before_errors={result['before_error_count']} "
                f"after_errors={result['after_error_count']}"
            )

    summary = build_summary(results, args.scenarios)
    write_outputs(
        output_dir=output_dir,
        run_label=run_label,
        input_paths=input_paths,
        scenario_names=args.scenarios,
        model_override=args.model,
        api_base_override=args.api_base,
        results=results,
        summary=summary,
    )
    print(f"Saved evaluation summary to: {output_dir / 'summary.json'}")
    print(f"Saved evaluation report to: {output_dir / 'report.md'}")
    return 0


def resolve_input_paths(raw_inputs: list[str]) -> list[Path]:
    if raw_inputs:
        paths = [_resolve_input_path(item) for item in raw_inputs]
    else:
        paths = [
            path
            for path in sorted((BASE_DIR / "inputs").glob("*.json"))
        ]
    return [path for path in paths if path.exists()]


def _resolve_input_path(raw_input: str) -> Path:
    candidate = Path(raw_input)
    if candidate.is_absolute():
        return candidate.resolve()

    direct = (BASE_DIR / candidate).resolve()
    if direct.exists():
        return direct

    nested = (BASE_DIR / "inputs" / candidate).resolve()
    if nested.exists():
        return nested

    return (Path.cwd() / candidate).resolve()


def run_case(
    *,
    input_path: Path,
    scenario: Scenario,
    output_dir: Path,
    model_override: str,
    api_base_override: str,
) -> dict[str, Any]:
    request = _load_json(input_path)
    case_dir = output_dir / "artifacts" / scenario.name / input_path.stem
    case_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "main.py",
        "--input",
        str(input_path),
        "--artifact-dir",
        str(case_dir),
        *scenario.cli_args,
    ]
    if model_override and scenario.name != "no_llm":
        command.extend(["--model", model_override])
    if api_base_override and scenario.name != "no_llm":
        command.extend(["--api-base", api_base_override])

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    runtime_sec = round(time.perf_counter() - started, 3)

    stdout_path = case_dir / "run_stdout.log"
    stderr_path = case_dir / "run_stderr.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    generated_plan = _load_json_if_exists(case_dir / "00_generated.json")
    final_plan = _load_json_if_exists(case_dir / "99_final.json") or _load_json_if_exists(
        case_dir / "plan.json"
    )

    before_validation = validate_plan(generated_plan) if generated_plan else None
    after_validation = validate_plan(final_plan) if final_plan else None

    metrics = compute_metrics(
        request=request,
        generated_plan=generated_plan,
        final_plan=final_plan,
        before_errors=(before_validation.errors if before_validation else []),
        after_errors=(after_validation.errors if after_validation else []),
        case_dir=case_dir,
        scenario=scenario,
        runtime_sec=runtime_sec,
        returncode=completed.returncode,
    )
    metrics["stdout_log"] = str(stdout_path)
    metrics["stderr_log"] = str(stderr_path)
    return metrics


def compute_metrics(
    *,
    request: dict[str, Any],
    generated_plan: dict[str, Any] | None,
    final_plan: dict[str, Any] | None,
    before_errors: list[str],
    after_errors: list[str],
    case_dir: Path,
    scenario: Scenario,
    runtime_sec: float,
    returncode: int,
) -> dict[str, Any]:
    must_do_total = len(request.get("must_do", [])) if isinstance(request.get("must_do"), list) else 0
    must_do_missing_after = _count_errors(after_errors, lambda err: err.startswith("Must-do item not covered"))
    must_do_missing_before = _count_errors(before_errors, lambda err: err.startswith("Must-do item not covered"))
    final_slot_count = _slot_count(final_plan)
    mixed_language_slot_count = _mixed_language_slot_count(final_plan)

    artifact_expected = {"request.json", "00_generated.json", "plan.json", "99_final.json", "plan.md", "99_final.md"}
    artifact_present = {path.name for path in case_dir.iterdir() if path.is_file()}

    return {
        "scenario": scenario.name,
        "scenario_description": scenario.description,
        "input_name": request.get("destination", Path(str(request.get("_request_path", ""))).stem or case_dir.name),
        "input_file": request.get("_source_file", ""),
        "request_path": str(request.get("_request_path", "")),
        "artifact_dir": str(case_dir),
        "runtime_sec": runtime_sec,
        "returncode": returncode,
        "run_success": int(returncode == 0 and final_plan is not None),
        "artifact_completeness_rate": round(
            len(artifact_expected & artifact_present) / len(artifact_expected), 4
        ),
        "before_valid": int(len(before_errors) == 0) if generated_plan else 0,
        "after_valid": int(len(after_errors) == 0) if final_plan else 0,
        "before_error_count": len(before_errors),
        "after_error_count": len(after_errors),
        "repair_error_delta": len(before_errors) - len(after_errors),
        "repair_improvement_rate": _ratio(
            len(before_errors) - len(after_errors),
            len(before_errors),
        ),
        "must_do_total": must_do_total,
        "must_do_missing_before": must_do_missing_before,
        "must_do_missing_after": must_do_missing_after,
        "must_do_coverage_rate_before": _ratio(must_do_total - must_do_missing_before, must_do_total),
        "must_do_coverage_rate_after": _ratio(must_do_total - must_do_missing_after, must_do_total),
        "must_do_full_coverage_after": int(must_do_total > 0 and must_do_missing_after == 0),
        "time_conflict_count_before": count_time_conflicts(before_errors),
        "time_conflict_count_after": count_time_conflicts(after_errors),
        "transport_error_count_before": count_transport_errors(before_errors),
        "transport_error_count_after": count_transport_errors(after_errors),
        "hotel_error_count_before": count_hotel_errors(before_errors),
        "hotel_error_count_after": count_hotel_errors(after_errors),
        "final_slot_count": final_slot_count,
        "mixed_language_slot_count": mixed_language_slot_count,
        "mixed_language_slot_rate": _ratio(mixed_language_slot_count, final_slot_count),
        "before_errors": before_errors,
        "after_errors": after_errors,
    }


def build_summary(results: list[dict[str, Any]], scenario_names: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_runs": len(results),
        "scenario_order": scenario_names,
        "scenario_summary": {},
    }
    for scenario_name in scenario_names:
        rows = [row for row in results if row["scenario"] == scenario_name]
        summary["scenario_summary"][scenario_name] = summarize_rows(rows)
    return summary


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "runs": len(rows),
        "run_success_rate": avg(rows, "run_success"),
        "avg_runtime_sec": avg(rows, "runtime_sec"),
        "artifact_completeness_rate": avg(rows, "artifact_completeness_rate"),
        "validation_pass_rate_before_repair": avg(rows, "before_valid"),
        "validation_pass_rate_after_repair": avg(rows, "after_valid"),
        "avg_error_count_before_repair": avg(rows, "before_error_count"),
        "avg_error_count_after_repair": avg(rows, "after_error_count"),
        "avg_repair_error_delta": avg(rows, "repair_error_delta"),
        "avg_repair_improvement_rate": avg(rows, "repair_improvement_rate"),
        "must_do_coverage_rate_before": avg(rows, "must_do_coverage_rate_before"),
        "must_do_coverage_rate_after": avg(rows, "must_do_coverage_rate_after"),
        "must_do_full_coverage_rate_after": avg(rows, "must_do_full_coverage_after"),
        "avg_time_conflict_count_before": avg(rows, "time_conflict_count_before"),
        "avg_time_conflict_count_after": avg(rows, "time_conflict_count_after"),
        "avg_transport_error_count_before": avg(rows, "transport_error_count_before"),
        "avg_transport_error_count_after": avg(rows, "transport_error_count_after"),
        "avg_hotel_error_count_before": avg(rows, "hotel_error_count_before"),
        "avg_hotel_error_count_after": avg(rows, "hotel_error_count_after"),
        "avg_mixed_language_slot_rate": avg(rows, "mixed_language_slot_rate"),
    }


def write_outputs(
    *,
    output_dir: Path,
    run_label: str,
    input_paths: list[Path],
    scenario_names: list[str],
    model_override: str,
    api_base_override: str,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    summary_path = output_dir / "summary.json"
    csv_path = output_dir / "cases.csv"
    report_path = output_dir / "report.md"

    summary_path.write_text(
        json.dumps(
            {
                "run_label": run_label,
                "inputs": [str(path) for path in input_paths],
                "scenario_names": scenario_names,
                "model_override": model_override,
                "api_base_override": api_base_override,
                "summary": summary,
                "cases": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fieldnames = [
        "scenario",
        "input_name",
        "request_path",
        "run_success",
        "runtime_sec",
        "before_valid",
        "after_valid",
        "before_error_count",
        "after_error_count",
        "repair_error_delta",
        "repair_improvement_rate",
        "must_do_total",
        "must_do_coverage_rate_before",
        "must_do_coverage_rate_after",
        "must_do_full_coverage_after",
        "time_conflict_count_before",
        "time_conflict_count_after",
        "transport_error_count_before",
        "transport_error_count_after",
        "hotel_error_count_before",
        "hotel_error_count_after",
        "mixed_language_slot_rate",
        "artifact_dir",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    report_path.write_text(
        render_report(
            run_label=run_label,
            input_paths=input_paths,
            scenario_names=scenario_names,
            model_override=model_override,
            api_base_override=api_base_override,
            results=results,
            summary=summary,
        ),
        encoding="utf-8",
    )


def render_report(
    *,
    run_label: str,
    input_paths: list[Path],
    scenario_names: list[str],
    model_override: str,
    api_base_override: str,
    results: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    lines = ["# OpenTravel Evaluation Report", ""]
    lines.append(f"- Run label: `{run_label}`")
    lines.append(f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Inputs: `{len(input_paths)}`")
    lines.append(f"- Scenarios: `{', '.join(scenario_names)}`")
    if model_override:
        lines.append(f"- Model override: `{model_override}`")
    if api_base_override:
        lines.append(f"- API base override: `{api_base_override}`")
    lines.append("")

    lines.append("## Input Set")
    lines.append("")
    for path in input_paths:
        lines.append(f"- `{path.name}`")
    lines.append("")

    lines.append("## Scenario Summary")
    lines.append("")
    lines.append("| Scenario | Success | Before Pass | After Pass | Must-do After | Time Conflicts After | Transport After | Avg Runtime (s) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for scenario_name in scenario_names:
        row = summary["scenario_summary"].get(scenario_name, {})
        lines.append(
            "| "
            f"{scenario_name} | "
            f"{fmt_pct(row.get('run_success_rate'))} | "
            f"{fmt_pct(row.get('validation_pass_rate_before_repair'))} | "
            f"{fmt_pct(row.get('validation_pass_rate_after_repair'))} | "
            f"{fmt_pct(row.get('must_do_coverage_rate_after'))} | "
            f"{fmt_num(row.get('avg_time_conflict_count_after'))} | "
            f"{fmt_num(row.get('avg_transport_error_count_after'))} | "
            f"{fmt_num(row.get('avg_runtime_sec'))} |"
        )
    lines.append("")

    lines.append("## Per-Case Results")
    lines.append("")
    lines.append("| Scenario | Input | Success | Before Errors | After Errors | Repair Delta | Must-do After | Hotel After | Mixed Language Rate |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in results:
        lines.append(
            "| "
            f"{row['scenario']} | "
            f"{Path(row['request_path']).name or row['input_name']} | "
            f"{row['run_success']} | "
            f"{row['before_error_count']} | "
            f"{row['after_error_count']} | "
            f"{row['repair_error_delta']} | "
            f"{fmt_pct(row['must_do_coverage_rate_after'])} | "
            f"{row['hotel_error_count_after']} | "
            f"{fmt_pct(row['mixed_language_slot_rate'])} |"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def avg(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row.get(key, 0) or 0) for row in rows) / len(rows), 4)


def fmt_pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def fmt_num(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object.")
    data["_request_path"] = str(path.resolve())
    data["_source_file"] = path.name
    return data


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return raw if isinstance(raw, dict) else None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _count_errors(errors: list[str], predicate: Any) -> int:
    return sum(1 for error in errors if predicate(error))


def count_time_conflicts(errors: list[str]) -> int:
    markers = [
        "time format must be hh:mm",
        "has invalid time range",
        "slot overlap",
        "duplicate interval",
    ]
    return sum(1 for error in errors if any(marker in error.lower() for marker in markers))


def count_transport_errors(errors: list[str]) -> int:
    markers = [
        "transport needs a clear origin and destination",
        "should connect from previous overnight location",
        "should clearly connect from the previous stop",
    ]
    return sum(1 for error in errors if any(marker in error.lower() for marker in markers))


def count_hotel_errors(errors: list[str]) -> int:
    return sum(1 for error in errors if "should include at least one hotel slot" in error.lower())


def _slot_count(plan: dict[str, Any] | None) -> int:
    if not plan:
        return 0
    total = 0
    for day in plan.get("days", []):
        if isinstance(day, dict) and isinstance(day.get("slots"), list):
            total += len(day["slots"])
    return total


def _mixed_language_slot_count(plan: dict[str, Any] | None) -> int:
    if not plan:
        return 0
    count = 0
    for day in plan.get("days", []):
        if not isinstance(day, dict):
            continue
        for slot in day.get("slots", []):
            if not isinstance(slot, dict):
                continue
            text = " ".join(
                [
                    str(slot.get("title", "")),
                    str(slot.get("location", "")),
                    str(slot.get("details", "")),
                    str(slot.get("rationale", "")),
                ]
            )
            has_zh = any("\u4e00" <= ch <= "\u9fff" for ch in text)
            has_en = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in text)
            if has_zh and has_en:
                count += 1
    return count


if __name__ == "__main__":
    raise SystemExit(main())
