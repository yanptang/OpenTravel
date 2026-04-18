# OpenTravel 本地 CLI 版本

OpenTravel 本地 CLI 版本用于验证“旅行需求输入 -> 行程生成 -> 规则校验 -> 局部修改 -> 结果导出”的完整闭环。当前实现以本地可用为优先，不依赖前端页面，也不依赖实时外部 API。

## 当前能力

- 输入前校验，避免缺少关键旅行信息就进入生成流程
- 支持 `slot-based JSON` 行程结构
- 支持行程后校验，检查时间、结构和 `must-do` 覆盖情况
- 支持本地 Ollama 模型直连
- 支持 `daily` 分段生成模式，逐天生成后合并
- 支持终端内交互修改 `slot`
- 支持导出 `plan.json` 和 `plan.txt`

## 必填输入

请求文件中需要包含以下字段：

- `origin_city`
- `destination`
- `start_date`
- `end_date`
- `arrival_mode`
- `travelers`
- `transport_mode`
- `must_do`

推荐额外补充：

- `budget_level`
- `notes`
- `special_requirements`

## 目录说明

- `main.py`：命令行入口，负责读取输入、执行校验、生成计划、导出结果。
- `opentravel/`：核心业务模块，包含模型调用、验证、渲染和交互编辑。
- `sample_request.json`：示例输入文件。
- `outputs/`：默认输出目录，存放生成结果。
- `requirements.txt`：Python 依赖。

## 环境准备

```bash
cd 02.LocalAgentCLI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

本地模型运行前，需要先安装并启动 Ollama，再拉取模型：

```bash
ollama pull qwen3.5:4b
```

## 运行方式

### 1. 使用本地模型

```bash
python main.py --input sample_request.json --planner-mode daily
```

默认模型：

- `ollama/qwen3.5:4b`

### 2. 使用 mock 模式

```bash
python main.py --input sample_request.json --no-llm
```

该模式不会调用模型，而是直接使用代码中的骨架生成器产出结果，适合调试规则和结构。

### 3. 更稳的分段模式

```bash
python main.py --input sample_request.json --planner-mode daily
```

该模式先生成行程骨架，再逐天生成并合并。对小模型更友好，也更容易局部失败、局部兜底。

## 输出文件

- `outputs/plan.json`：结构化行程结果
- `outputs/plan.txt`：按天展示的可读攻略

## 交互编辑

运行时加上 `--edit` 后，可以在终端里修改结果。

支持命令：

- `help`
- `show`
- `show day <n>`
- `delete <day> <slot_id>`
- `set <day> <slot_id> <field> <value>`
- `done`

示例：

```text
set 3 2 title Drive to glacier base camp
set 3 2 time_start 08:30
delete 5 4
done
```

## 校验规则

当前代码会检查：

- 请求字段是否齐全
- 日期范围是否合法
- 每一天是否存在 `slots`
- 每一天是否以 hotel `slot` 收尾
- `slot` 时间格式是否正确
- `slot` 是否有重叠
- `must-do` 是否出现在行程里

## 本地模型说明

当前主路径直连 Ollama 原生接口，不再依赖 LiteLLM 作为主调用链路。

原因包括：

- `qwen3.5:4b` 在 LiteLLM 路径里容易出现 `content` 为空的问题
- 直接调用 Ollama 更稳定
- `daily` 模式对小模型更友好

## 进一步优化方向

1. 增加 per-day budget cap 检查
2. 增加地理距离和车程时长校验
3. 增加用户偏好记忆
4. 增加更细的 `slot` 重排能力
5. 如果未来接实时工具，再加入航班、酒店和地图查询
