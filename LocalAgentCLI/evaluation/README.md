# Evaluation

This folder keeps all evaluation-related content for `LocalAgentCLI` in one place:

- runner script
- evaluation docs
- saved run outputs
- presentation-ready result summaries
- per-case final itineraries and issue traces

## Layout

```text
LocalAgentCLI/evaluation/
├─ eval_runner.py
├─ README.md
├─ results/
│  └─ evaluation_results_qwen35_4b_20260505.md
└─ runs/
   └─ <run_label>/
      ├─ cases.csv
      ├─ report.md
      ├─ summary.json
      └─ cases/
         └─ <scenario>/<input>/
            ├─ plan.md
            ├─ plan.json
            ├─ request.json
            ├─ issues.json
            ├─ run_stdout.log
            └─ run_stderr.log
```

## Goal

Build a repeatable evaluation loop that can answer:

- does the pipeline run successfully across the current sample set?
- how good is the first draft before refinement?
- how much does refinement help?
- are user `must_do` requirements actually covered?

## Script

Use [eval_runner.py](/c:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/eval_runner.py:1).

Example:

```bash
cd LocalAgentCLI
python evaluation/eval_runner.py
```

Run selected scenarios:

```bash
python evaluation/eval_runner.py --scenarios no_llm llm_repair
```

Run selected inputs:

```bash
python evaluation/eval_runner.py --inputs sample_request.json tianjin_beijing_request.json
```

## Scenario Matrix

- `no_llm`: scaffold baseline without model generation
- `llm_skip_repair`: model generation baseline without refinement
- `llm_repair`: full mainline path with refinement enabled

This gives a clean comparison between:

1. code-only baseline
2. model-only baseline
3. full pipeline result

## Metrics

### Stability

- `run_success_rate`
- `artifact_completeness_rate`
- `avg_runtime_sec`

### Validation Quality

- `validation_pass_rate_before_repair`
- `validation_pass_rate_after_repair`
- `avg_error_count_before_repair`
- `avg_error_count_after_repair`
- `avg_repair_error_delta`
- `avg_repair_improvement_rate`

### Requirement Satisfaction

- `must_do_coverage_rate_before`
- `must_do_coverage_rate_after`
- `must_do_full_coverage_rate_after`

### Error Buckets

- `time_conflict_count_before/after`
- `transport_error_count_before/after`
- `hotel_error_count_before/after`
- `must_do_error_count_before/after`
- `mixed_language_error_count_before/after`
- `other_error_count_before/after`

### Output Hygiene

- `mixed_language_slot_rate`

## Output Files

Each evaluation run writes to:

```text
LocalAgentCLI/evaluation/runs/<run_label>/
```

Key files:

- `summary.json`
- `cases.csv`
- `report.md`
- `cases/<scenario>/<input>/plan.md`
- `cases/<scenario>/<input>/issues.json`

`summary.json` 和 `report.md` 现在会同时给出“错误总数”和“错误类型分布”。
`issues.json` 会保留单条 case 的 before/after 错误列表，以及每种类型分别有多少。

## What Counts As An Error

The evaluation "errors" are validation errors returned by `validate_plan(...)`,
not Python exceptions.

Typical examples:

- transport slots without a clear origin or destination
- slots that do not clearly connect from the previous stop
- missing hotel or overnight closure on a day
- invalid or overlapping time ranges
- mixed Chinese and English output in the same slot

The generated `report.md` is now Chinese-first and easier to read directly,
while each case folder keeps the final generated itinerary plus the before/after
issue list so you can trace exactly what changed.
