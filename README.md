# OpenTravel

OpenTravel 是一个面向自助旅行规划的 Agent 项目，目标是把“旅行需求输入 -> 行程生成 -> 规则校验 -> 局部修改 -> 结果导出”这条链路做成一个可以持续演进的系统。

当前仓库保留两条主线：

- `02.LocalAgentCLI/`：当前可运行的本地原型
- `archive/`：前置调研、旧草稿和历史原型的归档区

## 项目愿景

OpenTravel 希望把旅行规划这件事做得更简单、更结构化，也更贴近个人偏好。

开源这件事的初衷主要有两点：

1. 旅行应该更容易被个性化地规划，而不是依赖零散的信息拼凑。
2. 旅行规划本身可以成为一个很好的 AI Agent 工程样例，既能展示系统设计，也能真正解决问题。

## 当前主线

当前主线已经转向本地 CLI 原型，重点是先把核心闭环做稳：

- 支持本地输入旅行需求
- 支持 slot 化行程结构
- 支持输入前校验和输出后校验
- 支持本地 Ollama 模型直连
- 支持 `daily` 分段生成模式
- 支持终端内交互修改

主线实现与说明请直接查看：

- [本地 CLI 说明](./02.LocalAgentCLI/README.md)
- [开发日志](./02.LocalAgentCLI/开发日志.md)
- [项目结构说明](./02.LocalAgentCLI/项目结构说明.md)

## 项目结构

```text
OpenTravel/
  README.md
  LICENSE
  assets/
  archive/
  02.LocalAgentCLI/
```

### `02.LocalAgentCLI/`

当前可运行版本，包含命令行入口、核心业务模块、示例输入、输出结果和完整说明文档。

### `archive/`

前置工作、旧草稿、早期原型和其他历史材料的归档区。这里保留过程，不影响主线阅读。

### `assets/`

统一存放截图、示意图和其他项目资源文件。

## 文档入口

| 文档 | 作用 |
| --- | --- |
| [02.LocalAgentCLI/README.md](./02.LocalAgentCLI/README.md) | 当前版本的运行说明 |
| [02.LocalAgentCLI/开发日志.md](./02.LocalAgentCLI/开发日志.md) | 项目推进记录 |
| [02.LocalAgentCLI/项目结构说明.md](./02.LocalAgentCLI/项目结构说明.md) | 代码结构说明 |
| [archive/](./archive/) | 前置工作与历史原型归档 |

## 快速开始

```bash
cd 02.LocalAgentCLI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --input sample_request.json --planner-mode daily
```

本地模型默认使用 Ollama 的 `qwen3.5:4b`。使用前需要先安装并启动 Ollama。

## 当前状态

当前版本已经可以在本地完成：

- 需求输入
- 生成行程
- 规则校验
- 交互编辑
- 结果导出

后续扩展方向包括：

- 偏好记忆
- 路由和距离校验
- 酒店、交通、地图等工具接入
- 更细粒度的 slot 重排
