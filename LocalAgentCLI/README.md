# OpenTravel 本地 CLI 版本

OpenTravel 本地 CLI 版本用于验证“旅行需求输入 -> 多轮澄清 -> 行程生成 -> 规则校验 -> 局部修改 -> 结果导出”的完整闭环。当前实现以本地可用为优先，不依赖前端页面，也不依赖实时外部 API。

## 当前能力

- 输入前校验，避免缺少关键旅行信息就进入生成流程
- 支持多轮澄清，按“基础信息 -> 目的地活动 -> 通用偏好”三层推进
- 目的地活动候选会先尝试让模型生成，再作为追问选项
- 支持 `slot-based JSON` 行程结构
- 支持行程后校验，检查时间、结构和 `must-do` 覆盖情况
- 支持本地 Ollama 模型直连
- 支持 `daily` 分段生成模式，逐天生成后合并
- 支持终端内交互修改 `slot`
- 支持导出 `plan.json`
- 支持导出 Markdown 行程文档 `plan.md`
- 支持按运行批次落盘到独立目录，避免覆盖历史结果

## 语言策略

当前版本会先根据输入内容自动判断语言：

- 中文输入 -> 中文澄清、中文攻略、中文 Markdown 输出
- 英文输入 -> 英文澄清、英文攻略、英文 Markdown 输出
- 混合输入 -> 以主要语言为准

语言只影响自由文本和展示文案，结构化 JSON 协议保持不变。

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
- `opentravel/`：核心业务模块，包含澄清、模型调用、验证、渲染和交互编辑。
- `sample_request.json`：通用示例输入文件。
- `tianjin_beijing_request.json`：中文示例输入文件，用于测试两日游场景。
- `outputs/`：默认输出目录，存放生成结果。
- `requirements.txt`：Python 依赖。

## 环境准备

```bash
cd LocalAgentCLI
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

运行时如果处于交互式终端，会先进入澄清流程。澄清层按三层推进：先补齐基础信息，再基于目的地生成本地特色活动候选，最后细化预算、节奏和住宿偏好。

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

### 4. 跳过澄清

```bash
python main.py --input sample_request.json --planner-mode daily --no-clarify
```

该模式会跳过终端交互澄清，适合自动化测试或批处理场景。

### 5. 进入交互编辑

```bash
python main.py --input sample_request.json --planner-mode daily --edit
```

该模式会在生成后进入终端编辑流程，可以手动删除或修改 slot。

### 6. 导出 Markdown

```bash
python main.py --input tianjin_beijing_request.json --no-llm --no-clarify --render-format markdown
```

该模式会把结果导出为 Markdown 旅行文档，适合直接阅读或后续转成 PDF。

### 7. 指定独立输出目录

```bash
python main.py --input tianjin_beijing_request.json --no-llm --no-clarify --render-format markdown --artifact-dir outputs/runs/tianjin-beijing-2day
```

该模式会把 `request.json`、`plan.json`、`plan.md` 写入单独目录，不会覆盖历史结果。

## 输出文件

默认一次运行会生成三类文件：

- `request.json`：本次运行的输入快照
- `plan.json`：结构化行程结果
- `plan.md`：按天展示的可读攻略

如果把 `--render-format` 设为 `text`，则会输出 `plan.txt`。

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

澄清流程会优先补齐：

- 出发地、目的地、日期、人数、到达方式、交通方式、must-do
- 预算层级
- 旅行节奏
- 住宿偏好
- 每天驾驶时长上限
- 当地特色活动偏好

## 本地模型说明

当前主路径直连 Ollama 原生接口，不再依赖 LiteLLM 作为主调用链路。

原因包括：

- `qwen3.5:4b` 在 LiteLLM 路径里容易出现 `content` 为空的问题
- 直接调用 Ollama 更稳定
- `daily` 模式对小模型更友好

## 当前样例

下面这个样例用于验证中文输入、中文输出和 Markdown 文档导出：

- 输入：`tianjin_beijing_request.json`
- 输出目录：`outputs/runs/tianjin-beijing-2day-v2/`

运行命令：

```bash
python main.py --input tianjin_beijing_request.json --no-llm --no-clarify --planner-mode daily --render-format markdown --artifact-dir outputs/runs/tianjin-beijing-2day-v2
```

## 进一步优化方向

1. 增加 per-day budget cap 检查
2. 增加地理距离和车程时长校验
3. 增加用户偏好记忆
4. 增加更细的 `slot` 重排能力
5. 如果未来接实时工具，再加入航班、酒店和地图查询
