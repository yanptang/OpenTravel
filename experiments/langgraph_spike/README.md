# LangGraph Spike

This folder contains a minimal LangGraph orchestration version of the current
OpenTravel pipeline.

## Goal

Understand how LangGraph works without rewriting the business logic.

This spike reuses the existing modules in `LocalAgentCLI/opentravel/`:

- `planner.py`
- `plan_validation.py`
- `refiner.py`
- `renderer.py`

## Nodes

- `generate`
- `validate`
- `refine`
- `finalize`

## State

- `request`
- `config`
- `artifact_dir`
- `plan`
- `validation_errors`
- `validation_valid`
- `round_index`
- `max_rounds`
- `history`

## Run

Install dependencies from `LocalAgentCLI/requirements.txt`, then:

```bash
cd experiments/langgraph_spike
python main.py --input ..\..\LocalAgentCLI\inputs\sample_request.json
```

Run without LLM:

```bash
python main.py --input ..\..\LocalAgentCLI\inputs\sample_request.json --no-llm
```

## Outputs

Artifacts are written to:

```text
experiments/langgraph_spike/outputs/latest/
```

Typical files:

- `request.json`
- `00_generated.json`
- `round_01_plan.json`
- `99_final.json`
- `plan.md`
- `graph_summary.json`

## Notes

- This spike is intentionally small and educational.
- It is not meant to replace the production CLI yet.
- The point is to show graph-based orchestration while keeping business logic
  reused from the current codebase.

## 中文说明

这个目录放的是一个最小可运行的 LangGraph 实验版本，用来理解：

- LangGraph 怎么组织流程
- 它和当前手写 `main.py` 编排方式有什么差别
- 在不重写业务逻辑的前提下，怎么把已有流程包成 graph

### 目标

这个 spike 的目标不是替换生产主线，而是帮助理解 LangGraph 的基本使用方式。

这里尽量复用现有模块：

- `planner.py`
- `plan_validation.py`
- `refiner.py`
- `renderer.py`

也就是说，业务逻辑本身没有重写，变化的主要是“流程编排方式”。

### 节点

这个实验图里有 4 个 node：

- `generate`
- `validate`
- `refine`
- `finalize`

### 状态

图中维护的核心状态包括：

- `request`
- `config`
- `artifact_dir`
- `plan`
- `validation_errors`
- `validation_valid`
- `round_index`
- `max_rounds`
- `history`

### 如何运行

先安装 `LocalAgentCLI/requirements.txt` 里的依赖，然后执行：

```bash
cd experiments/langgraph_spike
python main.py --input ..\..\LocalAgentCLI\inputs\sample_request.json
```

如果只想先看流程，不调用模型，可以跑：

```bash
python main.py --input ..\..\LocalAgentCLI\inputs\sample_request.json --no-llm
```

### 输出位置

默认会把结果写到：

```text
experiments/langgraph_spike/outputs/latest/
```

常见输出包括：

- `request.json`
- `00_generated.json`
- `round_01_plan.json`
- `99_final.json`
- `plan.md`
- `graph_summary.json`

### 这版实验的意义

这一版主要是为了展示：

1. 如何把线性流程拆成 graph node
2. 如何在 validate 后通过条件路由决定进入 refine 还是 finalize
3. 如何在保留现有业务代码的同时，尝试 graph-based orchestration

所以它更像一个“教学版 / 理解版”实验，而不是新的正式主线。
