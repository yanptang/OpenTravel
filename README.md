<div align="center">
  <h1>OpenTravel</h1>
  <p><strong>一个面向自助旅行规划的 Agent 项目</strong></p>
  <p>把“旅行需求输入 -> 行程生成 -> 规则校验 -> 局部修改 -> 结果导出”做成一个可以持续演进的系统。</p>

  <p>
    <img src="https://img.shields.io/badge/Language-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
    <img src="https://img.shields.io/badge/Runtime-Ollama-7C3AED?style=for-the-badge" alt="Ollama" />
    <img src="https://img.shields.io/badge/Mode-CLI-0F172A?style=for-the-badge" alt="CLI" />
    <img src="https://img.shields.io/badge/Output-JSON%20%7C%20Markdown-0EA5E9?style=for-the-badge" alt="Output" />
    <img src="https://img.shields.io/badge/Planner-Daily%20Slots-22C55E?style=for-the-badge" alt="Daily Slots" />
  </p>

  <p>
    <a href="./LocalAgentCLI/README.md"><img src="https://img.shields.io/badge/Local%20CLI-使用说明-111827?style=for-the-badge" alt="Local CLI" /></a>
    <a href="./docs/next_phase_plan.md"><img src="https://img.shields.io/badge/Next%20Phase-开发计划-0F766E?style=for-the-badge" alt="Next Phase" /></a>
  </p>
</div>

---

## 2026-04-21 当前阶段说明

项目当前已经从“先把 CLI 跑通”进入到“提高攻略质量和修复闭环”的阶段。

现阶段的重点不是继续堆功能，而是把下面这条链路做稳：

`whole 生成 -> validation 诊断 -> refiner 局部重绘 -> 再 validation`

当前判断如下：

- `whole` 是当前主生成模式
- `daily` 之后仍然会继续优化，但暂时不再承担当前阶段的主质量目标
- `validation / refiner` 已经开始采用更像 `day + slot` 的局部更新思路

也就是说，当前项目已经不再只是“一次生成一个 plan”，而是开始具备一个可迭代的生成与修复闭环。

---

## 2026-04-21 当前阶段说明

项目当前已经从“先把 CLI 跑通”进入到“提高攻略质量和修复闭环”的阶段。

现阶段的重点不是继续堆功能，而是把下面这条链路做稳：

`whole 生成 -> validation 诊断 -> refiner 局部重绘 -> 再 validation`

当前判断如下：

- `whole` 是当前主生成模式
- `daily` 之后仍然会继续优化，但暂时不再承担当前阶段的主质量目标
- `validation / refiner` 已经开始采用更像 `day + slot` 的局部更新思路

也就是说，当前项目已经不再只是“一次生成一个 plan”，而是开始具备一个可迭代的生成与修复闭环。

当前仓库保留两条主线：

- `LocalAgentCLI/`：当前可运行的本地原型
- `archive/`：前置调研、旧草稿和历史原型的归档区

---

## 快速卡片

<table>
  <tr>
    <td width="25%">
      <strong>本地优先</strong><br/>
      CLI + Ollama 直连<br/>
      先把闭环跑稳
    </td>
    <td width="25%">
      <strong>结构化输出</strong><br/>
      JSON 作为中间态<br/>
      Markdown 作为最终展示
    </td>
    <td width="25%">
      <strong>时间线规划</strong><br/>
      按天按 slot 组织<br/>
      强调衔接和闭环
    </td>
    <td width="25%">
      <strong>持续演进</strong><br/>
      澄清、记忆、工具接入<br/>
      按阶段推进
    </td>
  </tr>
</table>

---

## 项目愿景

> 核心目标是把“我”这样一个旅行爱好者的规划方式沉淀成一个可复用的 agent。
>
> 我喜欢旅行，作为超级J人，也喜欢一份严谨，信息充足，同时具有个人风格偏好的旅行攻略。
>
> 对我而言，旅行规划是一种想象，具体的行程是把脑子里想的，眼睛看到的文字，图片，视频，别人讲述的感受，变成一个自己的体验。所以旅行对我来说是一种体验，也是一种创造性活动的结果。常常我来到一个地方以后，发现跟我自己做的攻略一模一样，我会很开心，就像是我早就认识了这个朋友，而见面以后，发现他跟我想的一模一样。
>
> 也经常有些意外的惊喜，这都是旅行的魅力所在。
>
> 我也很喜欢掌握了充分的信息以后，当意外发生，自己马上能想到解决方案。这都是前置攻略和规划给我带来的东西。
>
> 但这样的过程，需要花费大量的时间，精力和信息处理能力。而很难为外人所道。经常有朋友惊叹于我的攻略的详细，实用，可以说“完美”的规划需要我付出大量的时间精力，而每次目的地不同，我就需要重新做一次。即使流程一样，但是浏览信息的时间需要同样付出。对于一个一年至少要旅行5次以上的人来说，这个过程即快乐又痛苦。而且我也无法为每个朋友都做攻略。
>
> 因此我希望能够把“我”这样一个旅行爱好者，做成一个agent，不论是认识我的，不认识我的，都能通过这个agent，收获一份按照我的理念做出来的旅行攻略（怎么不是P人福音呢）。
>
> 如果大家仍然有探索世界的欲望，那我们就还需要旅行。
>
> 虽然我们已经可以通过图片和视频看到世界上任何一个地方的阳光，沙滩，城堡，雪山，通过数据量化空气，风，温度。但我们仍然需要站在那里，让阳光真正的照到你的身体，感受风吹在脸上的感觉，听到海浪的声音，闻到花香，吃到当地的美食，和当地人交流，感受当下。这是我认为的旅行的意义。

---

## 当前主线

当前主线为本地 CLI 原型，重点是先把核心闭环做稳：

- 支持本地输入旅行需求
- 支持 slot 化行程结构
- 支持输入前校验和输出后校验
- 支持本地 Ollama 模型直连
- 支持 `daily` 分段生成模式
- 支持终端内交互修改

主线实现与说明请直接查看：

- [本地 CLI 说明](./LocalAgentCLI/README.md)
- [项目文档](./docs/README.md)
- [开发日志](./LocalAgentCLI/开发日志.md)
- [项目结构说明](./LocalAgentCLI/项目结构说明.md)
- [下阶段开发计划](./docs/next_phase_plan.md)
- [攻略生成准则](./docs/travel_planning_principles.md)

---

## 技术卡片

| 层级 | 目前使用 | 说明 |
| --- | --- | --- |
| 运行语言 | Python | 本地原型和业务逻辑的主体 |
| 模型运行 | Ollama | 通过本地接口直连模型 |
| 生成模式 | `daily` 分段模式 | 先骨架，再逐天生成 |
| 输出结构 | JSON | 机器可校验的中间态 |
| 人类输出 | Markdown / TXT | 可直接阅读和分享 |
| 交互形态 | CLI | 先把闭环跑稳，再考虑前端 |

---

## 项目结构

```text
OpenTravel/
  README.md
  LICENSE
  docs/
  assets/
  archive/
  LocalAgentCLI/
```

### `LocalAgentCLI/`

当前可运行版本，包含命令行入口、核心业务模块、示例输入、输出结果和完整说明文档。

### `archive/`

前置工作、旧草稿、早期原型和其他历史材料的归档区。这里保留过程，不影响主线阅读。

### `assets/`

统一存放截图、示意图和其他项目资源文件。

### `docs/`

项目级文档入口，保存下一阶段开发计划、攻略生成准则等全局指导文档。

---

## 视觉流程

```mermaid
flowchart LR
  A[旅行需求输入] --> B[多轮澄清]
  B --> C[行程生成]
  C --> D[规则校验]
  D --> E[局部修改]
  E --> F[结果导出]
```

---

## 作品展示

当前版本的输出会同时保留两种形态：

| 形态 | 用途 | 示例 |
| --- | --- | --- |
| `plan.json` | 机器可继续处理的结构化中间态 | [输出文件](./LocalAgentCLI/outputs/plan.json) |
| `plan.txt` | 给人直接阅读的行程攻略 | [输出文件](./LocalAgentCLI/outputs/plan.txt) |

<details>
<summary>展开查看一段示例输出</summary>

```text
Day 1 (2026-05-10) | Overnight: Reykjavik
  [1] 07:00-10:30 transport: Fly from Gothenburg to Iceland
  [2] 10:30-12:00 transport: Pick up rental car and drive to city
  [3] 12:00-13:00 meal: Arrival lunch
  [4] 14:00-17:00 activity: Reykjanes easy intro sightseeing
  [5] 18:30-23:00 hotel: Check in accommodation
```

</details>

---

## 路线图

| 阶段 | 目标 | 当前状态 |
| --- | --- | --- |
| Phase 1 | 本地 CLI 闭环 | 已完成 |
| Phase 2 | 多轮澄清 + 时间线 + 跨天闭环 | 进行中 |
| Phase 3 | 偏好记忆 | 待开始 |
| Phase 4 | 工具接入与外部信息增强 | 待开始 |

### 阶段说明

- Phase 1：先把最小可运行版本做出来
- Phase 2：继续强化对话式澄清、时间线组织和跨天闭环
- Phase 3：沉淀偏好记忆，让系统记住用户的旅行风格
- Phase 4：再考虑外部工具和实时信息接入

---

## 文档入口

| 文档 | 作用 |
| --- | --- |
| [LocalAgentCLI/README.md](./LocalAgentCLI/README.md) | 当前版本的运行说明 |
| [archive/CLI/README.md](./archive/CLI/README.md) | CLI 开发示例说明 |
| [LocalAgentCLI/开发日志.md](./LocalAgentCLI/开发日志.md) | 项目推进记录 |
| [LocalAgentCLI/项目结构说明.md](./LocalAgentCLI/项目结构说明.md) | 代码结构说明 |
| [archive/](./archive/) | 前置工作与历史原型归档 |

---

## 快速开始

```bash
cd LocalAgentCLI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --input sample_request.json --planner-mode daily
```

本地模型默认使用 Ollama 的 `qwen3.5:4b`。使用前需要先安装并启动 Ollama。

---

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

---

## 提交活动

<div align="center">
  <p>
    <img src="https://img.shields.io/badge/Status-Active-16A34A?style=for-the-badge" alt="Active" />
    <img src="https://img.shields.io/github/last-commit/yanptang/OpenTravel?style=for-the-badge" alt="Last Commit" />
    <img src="https://img.shields.io/github/commit-activity/m/yanptang/OpenTravel?style=for-the-badge" alt="Commit Activity" />
    <img src="https://img.shields.io/github/languages/top/yanptang/OpenTravel?style=for-the-badge" alt="Top Language" />
    <img src="https://img.shields.io/github/repo-size/yanptang/OpenTravel?style=for-the-badge" alt="Repo Size" />
  </p>
</div>

---

## 2026-04-21 当前阶段说明

项目当前已经从“先把 CLI 跑通”进入到“提高攻略质量和修复闭环”的阶段。

现阶段的重点不是继续堆功能，而是把下面这条链路做稳：

`whole 生成 -> validation 诊断 -> refiner 局部重绘 -> 再 validation`

当前判断如下：

- `whole` 是当前主生成模式
- `daily` 之后仍然会继续优化，但暂时不再承担当前阶段的主质量目标
- `validation / refiner` 已经开始采用更像 `day + slot` 的局部更新思路

也就是说，当前项目已经不再只是“一次生成一个 plan”，而是开始具备一个可迭代的生成与修复闭环。
