# Evaluation Framework

This document defines the first reusable evaluation harness for the current
`LocalAgentCLI` baseline.

## Goal

Build a repeatable evaluation loop that can answer:

- does the pipeline run successfully across the current sample set?
- how good is the first draft before refinement?
- how much does refinement help?
- are user `must_do` requirements actually covered?

## Script

Use [eval_runner.py](/c:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/eval_runner.py:1).

Example:

```bash
cd LocalAgentCLI
python eval_runner.py
```

Run selected scenarios:

```bash
python eval_runner.py --scenarios no_llm llm_repair
```

Run selected inputs:

```bash
python eval_runner.py --inputs sample_request.json tianjin_beijing_request.json
```

## Scenario Matrix

- `no_llm`
  scaffold baseline without model generation
- `llm_skip_repair`
  model generation baseline without refinement
- `llm_repair`
  full mainline path with refinement enabled

This gives a clean comparison between:

1. code-only baseline
2. model-only baseline
3. full pipeline result

## Metrics

### Stability

- `run_success_rate`
- `artifact_completeness_rate`
- `avg_runtime_sec`

### Validation quality

- `validation_pass_rate_before_repair`
- `validation_pass_rate_after_repair`
- `avg_error_count_before_repair`
- `avg_error_count_after_repair`
- `avg_repair_error_delta`
- `avg_repair_improvement_rate`

### Requirement satisfaction

- `must_do_coverage_rate_before`
- `must_do_coverage_rate_after`
- `must_do_full_coverage_rate_after`

### Error buckets

- `time_conflict_count_before/after`
- `transport_error_count_before/after`
- `hotel_error_count_before/after`

### Output hygiene

- `mixed_language_slot_rate`

## Output Files

Each evaluation run writes to:

```text
LocalAgentCLI/outputs/eval_runs/<timestamp>/
```

Key files:

- `summary.json`
- `cases.csv`
- `report.md`
- `artifacts/<scenario>/<input>/`

The generated `report.md` is intended to be presentation-friendly and easy to
quote in interviews.
