# OpenTravel Evaluation Results

- Date: `2026-05-05`
- Model: `ollama/qwen3.5:4b`
- Inputs: `3`
- Scenarios: `no_llm`, `llm_skip_repair`, `llm_repair`
- Raw artifacts: [report.md](/c:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505/report.md:1), [summary.json](/c:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505/summary.json:1)

## Test Set

- `sample_request.json`: `Gothenburg -> Iceland`, 10-day self-drive trip
- `tianjin_beijing_request.json`: `天津 -> 北京`, 2-day public transit trip
- `hengyang_changsha_request.json`: `衡阳 -> 长沙`, 3-day public transit trip

## Commands

Main evaluation:

```bash
cd LocalAgentCLI
python evaluation/eval_runner.py --model ollama/qwen3.5:4b --label eval_qwen35_4b_20260505
```

LangGraph smoke check:

```bash
cd experiments/langgraph_spike
python main.py --input ..\..\LocalAgentCLI\inputs\sample_request.json --no-llm --artifact-dir ..\..\LocalAgentCLI\outputs\langgraph_spike\smoke_no_llm
```

## Scenario Summary

| Scenario | Success | Before Pass | After Pass | Must-do After | Time Conflicts After | Transport After | Avg Runtime (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_llm` | 100.0% | 66.7% | 66.7% | 100.0% | 0.00 | 3.00 | 0.39 |
| `llm_skip_repair` | 100.0% | 0.0% | 0.0% | 100.0% | 0.00 | 4.67 | 108.48 |
| `llm_repair` | 100.0% | 0.0% | 0.0% | 100.0% | 0.00 | 3.67 | 320.53 |

## What This Means

- The pipeline is stable: all `9/9` runs finished successfully and produced artifacts.
- `must_do` coverage is strong on this small test set: all scenarios reached `100%`.
- The current weak point is not must-do or time conflicts, but route continuity and structure repair.
- `repair` helped a little on the small-city cases, but it did not fix the hardest sample end to end.
- The Iceland sample remained the hardest case and still carried `9` transport or continuity errors after repair.

## Per-Case Takeaways

- `天津 -> 北京` was the cleanest route. `no_llm` already passed, and `llm_repair` reduced errors from `2` to `1`.
- `衡阳 -> 长沙` was generally workable, but `llm_repair` traded one transport issue for one hotel-closing issue.
- `Gothenburg -> Iceland` exposed the current planner and refiner ceiling. It consistently kept `9` errors across all three scenarios.

## Interview-Ready Summary

You can describe this run as:

> I built a repeatable evaluation harness around three fixed travel requests and ran a 3x3 matrix with `qwen3.5:4b`: a pure-rule baseline, LLM generation without repair, and the full pipeline with repair. All nine runs completed successfully, must-do coverage stayed at 100%, and the main remaining failure mode was transport continuity on the hardest long-range itinerary. That gave me a concrete baseline before changing prompts, repair logic, RAG, or orchestration.
