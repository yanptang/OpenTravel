from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from opentravel.plan_validation import validate_plan


BASE_DIR = PROJECT_DIR
EVAL_ROOT = Path(__file__).resolve().parent
RUNS_DIR = EVAL_ROOT / "runs"

ERROR_BUCKETS: list[tuple[str, str]] = [
    ("must_do", "必做项覆盖错误"),
    ("time", "时间规则错误"),
    ("transport", "交通衔接错误"),
    ("hotel", "酒店收尾错误"),
    ("mixed_language", "中英混杂问题"),
    ("other", "其他错误"),
]


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    cli_args: tuple[str, ...]


SCENARIOS: dict[str, Scenario] = {
    "no_llm": Scenario(
        name="no_llm",
        description="纯规则骨架基线，不调用模型。",
        cli_args=("--no-llm", "--no-clarify", "--no-weather"),
    ),
    "llm_skip_repair": Scenario(
        name="llm_skip_repair",
        description="模型直出基线，跳过 repair。",
        cli_args=("--planner-mode", "whole", "--no-clarify", "--no-weather", "--skip-repair"),
    ),
    "llm_repair": Scenario(
        name="llm_repair",
        description="完整主链路：生成、校验、repair。",
        cli_args=("--planner-mode", "whole", "--no-clarify", "--no-weather"),
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 OpenTravel 评估矩阵。")
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=[],
        help="指定要跑的输入 JSON。默认使用 LocalAgentCLI/inputs/ 下的全部样例。",
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=["no_llm", "llm_skip_repair", "llm_repair"],
        choices=sorted(SCENARIOS.keys()),
        help="要运行的评估场景矩阵。",
    )
    parser.add_argument(
        "--model",
        default="",
        help="LLM 场景的模型覆盖，例如 ollama/qwen3.5:4b。",
    )
    parser.add_argument(
        "--api-base",
        default="",
        help="LLM 场景的 API Base 覆盖。",
    )
    parser.add_argument(
        "--label",
        default="",
        help="评估运行标签。默认使用时间戳。",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="评估输出目录。默认写入 evaluation/runs/<label>/。",
    )
    args = parser.parse_args()

    input_paths = resolve_input_paths(args.inputs)
    if not input_paths:
        print("没有找到可用于评估的输入 JSON。", file=sys.stderr)
        return 1

    run_label = args.label or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (RUNS_DIR / run_label).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    print(f"评估标签: {run_label}")
    print(f"评估输出目录: {output_dir}")

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
    shutil.rmtree(output_dir / "_tmp_artifacts", ignore_errors=True)
    print(f"已保存中文评估报告: {output_dir / 'report.md'}")
    print(f"已保存结构化结果: {output_dir / 'summary.json'}")
    return 0


def resolve_input_paths(raw_inputs: list[str]) -> list[Path]:
    if raw_inputs:
        paths = [_resolve_input_path(item) for item in raw_inputs]
    else:
        paths = sorted((BASE_DIR / "inputs").glob("*.json"))
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
    temp_case_dir = output_dir / "_tmp_artifacts" / scenario.name / input_path.stem
    final_case_dir = output_dir / "cases" / scenario.name / input_path.stem
    temp_case_dir.mkdir(parents=True, exist_ok=True)
    final_case_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "main.py",
        "--input",
        str(input_path),
        "--artifact-dir",
        str(temp_case_dir),
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

    stdout_path = final_case_dir / "run_stdout.log"
    stderr_path = final_case_dir / "run_stderr.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    generated_plan = _load_json_if_exists(temp_case_dir / "00_generated.json")
    final_plan = _load_json_if_exists(temp_case_dir / "99_final.json") or _load_json_if_exists(
        temp_case_dir / "plan.json"
    )

    before_validation = validate_plan(generated_plan) if generated_plan else None
    after_validation = validate_plan(final_plan) if final_plan else None
    before_errors = before_validation.errors if before_validation else []
    after_errors = after_validation.errors if after_validation else []

    kept_files = export_case_outputs(
        request=request,
        temp_case_dir=temp_case_dir,
        final_case_dir=final_case_dir,
        scenario=scenario,
        before_errors=before_errors,
        after_errors=after_errors,
        runtime_sec=runtime_sec,
        returncode=completed.returncode,
    )

    metrics = compute_metrics(
        request=request,
        generated_plan=generated_plan,
        final_plan=final_plan,
        before_errors=before_errors,
        after_errors=after_errors,
        case_dir=final_case_dir,
        scenario=scenario,
        runtime_sec=runtime_sec,
        returncode=completed.returncode,
    )
    metrics["stdout_log"] = str(stdout_path)
    metrics["stderr_log"] = str(stderr_path)
    metrics["final_plan_md"] = kept_files.get("plan_md", "")
    metrics["final_plan_json"] = kept_files.get("plan_json", "")
    metrics["issue_report_json"] = kept_files.get("issue_report_json", "")

    shutil.rmtree(temp_case_dir, ignore_errors=True)
    return metrics


def export_case_outputs(
    *,
    request: dict[str, Any],
    temp_case_dir: Path,
    final_case_dir: Path,
    scenario: Scenario,
    before_errors: list[str],
    after_errors: list[str],
    runtime_sec: float,
    returncode: int,
) -> dict[str, str]:
    saved: dict[str, str] = {}

    for src_name, dst_name in [
        ("plan.md", "plan.md"),
        ("plan.json", "plan.json"),
        ("99_final.md", "final_plan_snapshot.md"),
        ("99_final.json", "final_plan_snapshot.json"),
        ("request.json", "request.json"),
    ]:
        src = temp_case_dir / src_name
        dst = final_case_dir / dst_name
        if src.exists():
            shutil.copy2(src, dst)
            if dst_name == "plan.md":
                saved["plan_md"] = str(dst)
            elif dst_name == "plan.json":
                saved["plan_json"] = str(dst)

    issue_report_path = final_case_dir / "issues.json"
    issue_report = {
        "scenario": scenario.name,
        "scenario_description_zh": scenario.description,
        "request_file": request.get("_source_file", ""),
        "request_path": request.get("_request_path", ""),
        "runtime_sec": runtime_sec,
        "returncode": returncode,
        "before_error_count": len(before_errors),
        "after_error_count": len(after_errors),
        "before_error_bucket_counts": error_bucket_counts(before_errors),
        "after_error_bucket_counts": error_bucket_counts(after_errors),
        "before_errors": [{"en": error, "zh": translate_error(error)} for error in before_errors],
        "after_errors": [{"en": error, "zh": translate_error(error)} for error in after_errors],
    }
    issue_report_path.write_text(json.dumps(issue_report, ensure_ascii=False, indent=2), encoding="utf-8")
    saved["issue_report_json"] = str(issue_report_path)
    return saved


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
    before_bucket_counts = error_bucket_counts(before_errors)
    after_bucket_counts = error_bucket_counts(after_errors)

    artifact_expected = {"request.json", "plan.json", "plan.md", "issues.json", "run_stdout.log", "run_stderr.log"}
    artifact_present = {path.name for path in case_dir.iterdir() if path.is_file()}

    metrics = {
        "scenario": scenario.name,
        "scenario_description": scenario.description,
        "input_name": request.get("destination", Path(str(request.get("_request_path", ""))).stem or case_dir.name),
        "input_file": request.get("_source_file", ""),
        "request_path": str(request.get("_request_path", "")),
        "artifact_dir": str(case_dir),
        "runtime_sec": runtime_sec,
        "returncode": returncode,
        "run_success": int(returncode == 0 and final_plan is not None),
        "artifact_completeness_rate": round(len(artifact_expected & artifact_present) / len(artifact_expected), 4),
        "before_valid": int(len(before_errors) == 0) if generated_plan else 0,
        "after_valid": int(len(after_errors) == 0) if final_plan else 0,
        "before_error_count": len(before_errors),
        "after_error_count": len(after_errors),
        "repair_error_delta": len(before_errors) - len(after_errors),
        "repair_improvement_rate": _ratio(len(before_errors) - len(after_errors), len(before_errors)),
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
        "before_errors_zh": [translate_error(error) for error in before_errors],
        "after_errors_zh": [translate_error(error) for error in after_errors],
        "before_error_bucket_counts": before_bucket_counts,
        "after_error_bucket_counts": after_bucket_counts,
    }

    for bucket_key, _ in ERROR_BUCKETS:
        metrics[f"before_{bucket_key}_error_count"] = before_bucket_counts[bucket_key]
        metrics[f"after_{bucket_key}_error_count"] = after_bucket_counts[bucket_key]

    return metrics


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

    data = {
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

    for bucket_key, bucket_label in ERROR_BUCKETS:
        data[f"avg_{bucket_key}_error_count_before"] = avg(rows, f"before_{bucket_key}_error_count")
        data[f"avg_{bucket_key}_error_count_after"] = avg(rows, f"after_{bucket_key}_error_count")
        data.setdefault("error_bucket_labels", {})[bucket_key] = bucket_label

    return data


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
        "final_plan_md",
        "issue_report_json",
        "artifact_dir",
    ]
    fieldnames.extend([f"before_{bucket_key}_error_count" for bucket_key, _ in ERROR_BUCKETS])
    fieldnames.extend([f"after_{bucket_key}_error_count" for bucket_key, _ in ERROR_BUCKETS])

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
    lines = ["# OpenTravel 评估报告", ""]
    lines.append(f"- 评估标签：`{run_label}`")
    lines.append(f"- 生成时间：`{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- 输入样例数：`{len(input_paths)}`")
    lines.append(f"- 评估场景：`{', '.join(scenario_names)}`")
    if model_override:
        lines.append(f"- 模型覆盖：`{model_override}`")
    if api_base_override:
        lines.append(f"- API Base 覆盖：`{api_base_override}`")
    lines.append("")

    lines.append("## 指标说明")
    lines.append("")
    lines.append("- `Before Pass`：初稿生成后，第一次跑硬规则校验是否通过。")
    lines.append("- `After Pass`：经过 repair 后，再次跑硬规则校验是否通过。")
    lines.append("- 这里的“错误”是 `validate_plan(...)` 返回的校验错误，不是程序崩溃。")
    lines.append("- 现在会额外记录每种错误类型有多少，方便定位问题主要集中在哪一类。")
    lines.append("")

    lines.append("## 输入样例")
    lines.append("")
    for path in input_paths:
        lines.append(f"- `{path.name}`")
    lines.append("")

    lines.append("## 场景汇总")
    lines.append("")
    lines.append("| 场景 | 成功率 | 初稿通过率 | 修复后通过率 | Must-do 覆盖率 | 修复后时间错误 | 修复后交通错误 | 修复后酒店错误 | 平均耗时(秒) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for scenario_name in scenario_names:
        row = summary["scenario_summary"].get(scenario_name, {})
        lines.append(
            "| "
            f"{scenario_name} | "
            f"{fmt_pct(row.get('run_success_rate'))} | "
            f"{fmt_pct(row.get('validation_pass_rate_before_repair'))} | "
            f"{fmt_pct(row.get('validation_pass_rate_after_repair'))} | "
            f"{fmt_pct(row.get('must_do_coverage_rate_after'))} | "
            f"{fmt_num(row.get('avg_time_error_count_after'))} | "
            f"{fmt_num(row.get('avg_transport_error_count_after'))} | "
            f"{fmt_num(row.get('avg_hotel_error_count_after'))} | "
            f"{fmt_num(row.get('avg_runtime_sec'))} |"
        )
    lines.append("")

    lines.append("## 错误类型分布")
    lines.append("")
    lines.append("| 场景 | 阶段 | 必做项 | 时间 | 交通 | 酒店 | 中英混杂 | 其他 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for scenario_name in scenario_names:
        row = summary["scenario_summary"].get(scenario_name, {})
        lines.append(
            "| "
            f"{scenario_name} | 修复前 | "
            f"{fmt_num(row.get('avg_must_do_error_count_before'))} | "
            f"{fmt_num(row.get('avg_time_error_count_before'))} | "
            f"{fmt_num(row.get('avg_transport_error_count_before'))} | "
            f"{fmt_num(row.get('avg_hotel_error_count_before'))} | "
            f"{fmt_num(row.get('avg_mixed_language_error_count_before'))} | "
            f"{fmt_num(row.get('avg_other_error_count_before'))} |"
        )
        lines.append(
            "| "
            f"{scenario_name} | 修复后 | "
            f"{fmt_num(row.get('avg_must_do_error_count_after'))} | "
            f"{fmt_num(row.get('avg_time_error_count_after'))} | "
            f"{fmt_num(row.get('avg_transport_error_count_after'))} | "
            f"{fmt_num(row.get('avg_hotel_error_count_after'))} | "
            f"{fmt_num(row.get('avg_mixed_language_error_count_after'))} | "
            f"{fmt_num(row.get('avg_other_error_count_after'))} |"
        )
    lines.append("")

    lines.append("## 单条样例结果")
    lines.append("")
    lines.append("| 场景 | 输入 | 初稿错误数 | 最终错误数 | 交通 | 酒店 | 时间 | 最终攻略 | 错误明细 |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |")
    for row in results:
        plan_path = path_to_link_target(row.get("final_plan_md", ""))
        issue_path = path_to_link_target(row.get("issue_report_json", ""))
        plan_link = f"[plan.md]({plan_path})" if plan_path else "n/a"
        issue_link = f"[issues.json]({issue_path})" if issue_path else "n/a"
        lines.append(
            "| "
            f"{row['scenario']} | "
            f"{Path(row['request_path']).name or row['input_name']} | "
            f"{row['before_error_count']} | "
            f"{row['after_error_count']} | "
            f"{row['after_transport_error_count']} | "
            f"{row['after_hotel_error_count']} | "
            f"{row['after_time_error_count']} | "
            f"{plan_link} | "
            f"{issue_link} |"
        )
    lines.append("")

    lines.append("## 最终错误摘要")
    lines.append("")
    for row in results:
        lines.append(f"### {row['scenario']} / {Path(row['request_path']).name}")
        lines.append(
            f"- 错误类型统计：交通 `{row['after_transport_error_count']}`，"
            f"酒店 `{row['after_hotel_error_count']}`，"
            f"时间 `{row['after_time_error_count']}`，"
            f"必做项 `{row['after_must_do_error_count']}`，"
            f"中英混杂 `{row['after_mixed_language_error_count']}`，"
            f"其他 `{row['after_other_error_count']}`"
        )
        if not row["after_errors_zh"]:
            lines.append("- 最终校验通过，没有剩余错误。")
        else:
            for error in row["after_errors_zh"]:
                lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def classify_error(error: str) -> str:
    lower = error.lower()
    if "must-do item not covered" in lower:
        return "must_do"
    if any(marker in lower for marker in ["time format must be hh:mm", "has invalid time range", "slot overlap", "duplicate interval"]):
        return "time"
    if any(
        marker in lower
        for marker in [
            "transport needs a clear origin and destination",
            "should connect from previous overnight location",
            "should clearly connect from the previous stop",
        ]
    ):
        return "transport"
    if "should include at least one hotel slot" in lower:
        return "hotel"
    if any(marker in lower for marker in ["mixed language", "contains mixed language"]):
        return "mixed_language"
    return "other"


def error_bucket_counts(errors: list[str]) -> dict[str, int]:
    counts = {bucket_key: 0 for bucket_key, _ in ERROR_BUCKETS}
    for error in errors:
        counts[classify_error(error)] += 1
    return counts


def translate_error(error: str) -> str:
    raw = error.strip()
    lower = raw.lower()
    prefix = ""
    remainder = raw

    if raw.startswith("Day "):
        parts = raw.split(" ", 4)
        if len(parts) >= 5 and parts[2] == "slot":
            prefix = f"第{parts[1]}天，第{parts[3]}个 slot："
            remainder = parts[4]
        elif len(parts) >= 3:
            prefix = f"第{parts[1]}天："
            remainder = " ".join(parts[2:])

    mapping = [
        ("transport needs a clear origin and destination.", "交通段缺少明确的出发地和目的地。"),
        ("should connect from previous overnight location.", "这段行程没有从上一晚住宿地点自然衔接。"),
        ("should clearly connect from the previous stop.", "这段行程没有和上一个地点形成清晰衔接。"),
        ("should include at least one hotel slot.", "当天缺少至少一个酒店或住宿相关 slot。"),
        ("time format must be hh:mm", "时间格式不合法，应为 HH:MM。"),
        ("has invalid time range", "时间范围不合法，结束时间早于或等于开始时间。"),
        ("slot overlap", "slot 时间发生重叠。"),
        ("duplicate interval", "存在重复的时间区间。"),
        ("must-do item not covered", "必做项目没有被覆盖到最终行程里。"),
    ]

    translated = remainder
    for src, dst in mapping:
        if src in lower:
            translated = dst
            break

    return f"{prefix}{translated}" if prefix else translated


def path_to_link_target(path_str: str) -> str:
    if not path_str:
        return ""
    return path_str.replace("\\", "/")


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
        raise TypeError(f"{path} 必须是 JSON object。")
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
    markers = ["time format must be hh:mm", "has invalid time range", "slot overlap", "duplicate interval"]
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
