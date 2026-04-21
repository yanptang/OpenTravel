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
- 支持实时阶段进度日志，显示“当前在做什么”和每个 day 的耗时

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
- `prompts/`：外置 prompt 模板目录，分为 `system/` 和 `user/` 两层，存放 planner / clarifier / refiner 的提示词。
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
如果不指定 `--artifact-dir`，默认会写到 `outputs/latest/`。

### 8. 关闭进度日志

```bash
python main.py --input tianjin_beijing_request.json --no-progress
```

如果你不想看阶段日志，可以关闭。默认会在 stderr 打印轻量进度，不影响最终 Markdown 输出。

## 输出文件

默认一次运行会生成三类文件：

- `request.json`：本次运行的输入快照
- `plan.json`：结构化行程结果
- `plan.md`：按天展示的可读攻略

如果把 `--render-format` 设为 `text`，则会输出 `plan.txt`。

当前仓库里还保留了一个更干净的快捷入口：

- `outputs/latest/`：当前最新的一版结果，也是默认输出目录
- `outputs/final/`：我认为足够稳定、值得保留的正式样例

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
- 输出目录：`outputs/final/tianjin-beijing-progress/`

运行命令：

```bash
python main.py --input tianjin_beijing_request.json --no-clarify --planner-mode daily --render-format markdown --artifact-dir outputs/final/tianjin-beijing-progress
```

## 进一步优化方向

1. 增加 per-day budget cap 检查
2. 增加地理距离和车程时长校验
3. 增加用户偏好记忆
4. 增加更细的 `slot` 重排能力
5. 如果未来接实时工具，再加入航班、酒店和地图查询

## 参数速查

下面按 5 个类别整理 CLI 参数，并列出默认值，方便你在终端里快速判断该怎么组合。

### 1. 输入输出类

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--input` | `sample_request.json` | 输入请求文件路径。 |
| `--output` | 空 | 最终 `plan.json` 输出路径。为空时写到 `artifact-dir/plan.json`。 |
| `--render-output` | 空 | 人类可读攻略输出路径。为空时按格式写到 `artifact-dir/plan.md` 或 `plan.txt`。 |
| `--artifact-dir` | 空 | 一次运行的整体产物目录，会统一保存 `request.json`、`plan.json`、`plan.md`。 |
| `--render-format` | `markdown` | 攻略输出格式，支持 `markdown` 或 `text`。 |

### 2. 模型与运行时类

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--no-llm` | `false` | 不调用模型，直接使用本地骨架生成。 |
| `--model` | `ollama/qwen3.5:4b` | 使用的模型名称。 |
| `--api-base` | `http://localhost:11434` | Ollama 接口地址。 |
| `--max-tokens` | `4096` | 模型输出上限。 |
| `--timeout-sec` | `900` | 模型请求超时时间，单位秒。 |
| `--refine-retries` | `2` | 行程校验失败后的修正重试次数。 |

### 3. 规划方式类

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--planner-mode` | `daily` | 规划模式。`daily` 是先搭骨架再逐天细化，`whole` 是一次性生成整段。 |

### 4. 交互与校验控制类

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--no-clarify` | `false` | 跳过多轮澄清，直接进入生成流程。 |
| `--no-progress` | `false` | 关闭进度提示。 |
| `--edit` | `false` | 生成后进入终端手动编辑。 |

### 5. 输出与落盘类

| 项目 | 默认值 | 含义 |
| --- | --- | --- |
| `request.json` | 自动生成 | 本次运行的输入快照。 |
| `plan.json` | 自动生成 | 结构化行程结果。 |
| `plan.md` / `plan.txt` | 自动生成 | 给人直接阅读的攻略输出。 |
| `outputs/latest/` | 默认目录 | 最新一次运行的输出目录。 |
| `outputs/final/` | 手动指定 | 比较稳定、值得保留的正式结果。 |

### 常用组合

| 组合 | 适用场景 | 说明 |
| --- | --- | --- |
| `python main.py --input sample_request.json --planner-mode daily` | 正常跑一遍本地生成 | 适合先看完整流程是否通。默认会做澄清、生成、校验和导出。 |
| `python main.py --input sample_request.json --planner-mode daily --no-clarify` | 自动化测试 / 批量验证 | 跳过澄清后更稳定，也更适合脚本化跑例子。 |
| `python main.py --input sample_request.json --planner-mode daily --edit` | 人工微调结果 | 适合生成后再手动删改 slot，看看交互编辑链路是否可用。 |
| `python main.py --input tianjin_beijing_request.json --no-llm --no-clarify --render-format markdown` | 不依赖模型时的快速验证 | 直接走本地骨架，方便检查输出格式、落盘和渲染。 |
| `python main.py --input tianjin_beijing_request.json --no-clarify --planner-mode daily --artifact-dir outputs/runs/tianjin-beijing-2day` | 固定保存一版样例 | 适合做回归样例，避免覆盖 `outputs/latest/`。 |

## 当前阶段建议

截至 2026-04-21，当前更推荐的使用方式已经有了阶段性调整：

- 生成主线优先使用 `whole`
- `daily` 仍然保留，后面还会继续做，但当前不再是首版质量优化的第一优先级
- 校验失败后，系统已经不再依赖整份重写，而是优先走“按天 / 按问题”的局部重绘修复

也就是说，当前更贴近真实使用的闭环是：

`whole 生成 -> validation 诊断 -> refiner 局部重绘 -> 再 validation`

## 自动修复机制说明

当前自动修复已经从早期的“整份 refine”调整成更聚焦的局部修复：

- `validation` 负责发现问题、定位问题、识别问题类型
- `refiner` 只重绘有问题的 `day / slot`
- 没问题的天不会送给模型，避免误改已经满意的内容

这一点对本地模型尤其重要，因为：

- 整份 plan 一起修时，小模型容易原样返回
- 局部问题单独修时，模型更容易真正动手改

## 当前推荐命令

如果你现在想跑一版更接近当前主线的完整流程，优先建议：

```bash
python main.py --input sample_request.json --planner-mode whole
```

如果你想观察校验和修复链路是否生效，可以继续配合：

```bash
python main.py --input sample_request.json --planner-mode whole --artifact-dir outputs/runs/sample-whole
```
