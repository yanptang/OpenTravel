# OpenTravel Evaluation Report

- Run label: `eval_qwen35_4b_20260505`
- Generated at: `2026-05-05T11:26:41`
- Inputs: `3`
- Scenarios: `no_llm, llm_skip_repair, llm_repair`
- Model override: `ollama/qwen3.5:4b`

## Input Set

- `hengyang_changsha_request.json`
- `sample_request.json`
- `tianjin_beijing_request.json`

## Scenario Summary

| Scenario | Success | Before Pass | After Pass | Must-do After | Time Conflicts After | Transport After | Avg Runtime (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_llm | 100.0% | 66.7% | 66.7% | 100.0% | 0.00 | 3.00 | 0.39 |
| llm_skip_repair | 100.0% | 0.0% | 0.0% | 100.0% | 0.00 | 4.67 | 108.48 |
| llm_repair | 100.0% | 0.0% | 0.0% | 100.0% | 0.00 | 3.67 | 320.53 |

## Per-Case Results

| Scenario | Input | Success | Before Errors | After Errors | Repair Delta | Must-do After | Hotel After | Mixed Language Rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_llm | hengyang_changsha_request.json | 1 | 0 | 0 | 0 | 100.0% | 0 | 0.0% |
| no_llm | sample_request.json | 1 | 9 | 9 | 0 | 100.0% | 0 | 3.4% |
| no_llm | tianjin_beijing_request.json | 1 | 0 | 0 | 0 | 100.0% | 0 | 0.0% |
| llm_skip_repair | hengyang_changsha_request.json | 1 | 4 | 4 | 0 | 100.0% | 0 | 10.0% |
| llm_skip_repair | sample_request.json | 1 | 9 | 9 | 0 | 100.0% | 0 | 3.4% |
| llm_skip_repair | tianjin_beijing_request.json | 1 | 1 | 1 | 0 | 100.0% | 0 | 0.0% |
| llm_repair | hengyang_changsha_request.json | 1 | 2 | 2 | 0 | 100.0% | 1 | 21.1% |
| llm_repair | sample_request.json | 1 | 9 | 9 | 0 | 100.0% | 0 | 3.4% |
| llm_repair | tianjin_beijing_request.json | 1 | 2 | 1 | 1 | 100.0% | 0 | 0.0% |
