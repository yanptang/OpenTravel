# OpenTravel 评估报告

- 评估标签：`eval_qwen35_4b_20260505_rerun`
- 生成时间：`2026-05-05T22:00:06`
- 输入样例数：`3`
- 评估场景：`no_llm, llm_skip_repair, llm_repair`
- 模型覆盖：`ollama/qwen3.5:4b`

## 指标说明

- `Before Pass`：初稿生成后，第一次跑硬规则校验是否通过。
- `After Pass`：经过 repair 后，再次跑硬规则校验是否通过。
- 这里的“错误”是 `validate_plan(...)` 返回的校验错误，不是程序崩溃。
- 现在会额外记录每种错误类型有多少，方便定位问题主要集中在哪一类。

## 输入样例

- `hengyang_changsha_request.json`
- `sample_request.json`
- `tianjin_beijing_request.json`

## 场景汇总

| 场景 | 成功率 | 初稿通过率 | 修复后通过率 | Must-do 覆盖率 | 修复后时间错误 | 修复后交通错误 | 修复后酒店错误 | 平均耗时(秒) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_llm | 100.0% | 66.7% | 66.7% | 100.0% | 0.00 | 3.00 | 0.00 | 0.35 |
| llm_skip_repair | 100.0% | 33.3% | 33.3% | 100.0% | 0.00 | 3.67 | 0.00 | 98.45 |
| llm_repair | 100.0% | 33.3% | 33.3% | 100.0% | 0.00 | 3.33 | 0.00 | 270.36 |

## 错误类型分布

| 场景 | 阶段 | 必做项 | 时间 | 交通 | 酒店 | 中英混杂 | 其他 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_llm | 修复前 | 0.00 | 0.00 | 3.00 | 0.00 | 0.00 | 0.00 |
| no_llm | 修复后 | 0.00 | 0.00 | 3.00 | 0.00 | 0.00 | 0.00 |
| llm_skip_repair | 修复前 | 0.00 | 0.00 | 3.67 | 0.00 | 0.00 | 0.00 |
| llm_skip_repair | 修复后 | 0.00 | 0.00 | 3.67 | 0.00 | 0.00 | 0.00 |
| llm_repair | 修复前 | 0.00 | 0.00 | 3.33 | 0.00 | 0.00 | 0.00 |
| llm_repair | 修复后 | 0.00 | 0.00 | 3.33 | 0.00 | 0.00 | 0.00 |

## 单条样例结果

| 场景 | 输入 | 初稿错误数 | 最终错误数 | 交通 | 酒店 | 时间 | 最终攻略 | 错误明细 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| no_llm | hengyang_changsha_request.json | 0 | 0 | 0 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/hengyang_changsha_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/hengyang_changsha_request/issues.json) |
| no_llm | sample_request.json | 9 | 9 | 9 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/sample_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/sample_request/issues.json) |
| no_llm | tianjin_beijing_request.json | 0 | 0 | 0 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/tianjin_beijing_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/no_llm/tianjin_beijing_request/issues.json) |
| llm_skip_repair | hengyang_changsha_request.json | 0 | 0 | 0 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/hengyang_changsha_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/hengyang_changsha_request/issues.json) |
| llm_skip_repair | sample_request.json | 9 | 9 | 9 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/sample_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/sample_request/issues.json) |
| llm_skip_repair | tianjin_beijing_request.json | 2 | 2 | 2 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/tianjin_beijing_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_skip_repair/tianjin_beijing_request/issues.json) |
| llm_repair | hengyang_changsha_request.json | 0 | 0 | 0 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/hengyang_changsha_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/hengyang_changsha_request/issues.json) |
| llm_repair | sample_request.json | 9 | 9 | 9 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/sample_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/sample_request/issues.json) |
| llm_repair | tianjin_beijing_request.json | 1 | 1 | 1 | 0 | 0 | [plan.md](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/tianjin_beijing_request/plan.md) | [issues.json](C:/Users/Administrator/Desktop/HPC_Projects/OpenTravel/LocalAgentCLI/evaluation/runs/eval_qwen35_4b_20260505_rerun/cases/llm_repair/tianjin_beijing_request/issues.json) |

## 最终错误摘要

### no_llm / hengyang_changsha_request.json
- 错误类型统计：交通 `0`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 最终校验通过，没有剩余错误。

### no_llm / sample_request.json
- 错误类型统计：交通 `9`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 第2天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第3天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第4天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第5天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第6天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第7天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第8天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第9天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第10天，第2个 slot：交通段缺少明确的出发地和目的地。

### no_llm / tianjin_beijing_request.json
- 错误类型统计：交通 `0`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 最终校验通过，没有剩余错误。

### llm_skip_repair / hengyang_changsha_request.json
- 错误类型统计：交通 `0`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 最终校验通过，没有剩余错误。

### llm_skip_repair / sample_request.json
- 错误类型统计：交通 `9`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 第2天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第3天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第4天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第5天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第6天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第7天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第8天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第9天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第10天，第2个 slot：交通段缺少明确的出发地和目的地。

### llm_skip_repair / tianjin_beijing_request.json
- 错误类型统计：交通 `2`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 第2天，第2个 slot：这段行程没有和上一个地点形成清晰衔接。
- 第2天，第3个 slot：这段行程没有和上一个地点形成清晰衔接。

### llm_repair / hengyang_changsha_request.json
- 错误类型统计：交通 `0`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 最终校验通过，没有剩余错误。

### llm_repair / sample_request.json
- 错误类型统计：交通 `9`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 第2天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第3天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第4天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第5天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第6天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第7天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第8天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第9天，第2个 slot：交通段缺少明确的出发地和目的地。
- 第10天，第2个 slot：交通段缺少明确的出发地和目的地。

### llm_repair / tianjin_beijing_request.json
- 错误类型统计：交通 `1`，酒店 `0`，时间 `0`，必做项 `0`，中英混杂 `0`，其他 `0`
- 第1天，第5个 slot：这段行程没有和上一个地点形成清晰衔接。
