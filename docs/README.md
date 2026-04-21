# 项目文档

这里放的是指导整个 OpenTravel 项目的核心文档，不属于前置调研，也不属于某个局部原型的说明。

## 文档索引

- [下一阶段开发计划](./next_phase_plan.md)
- [攻略生成准则](./travel_planning_principles.md)
- [模型与算力策略](./model_and_compute_strategy.md)
- [项目运行流程](./项目运行流程.md)
- [项目结构说明](./项目结构说明.md)

## 阅读顺序

如果我现在要继续开发，优先看：

1. `next_phase_plan.md`
2. `travel_planning_principles.md`
3. `model_and_compute_strategy.md`
4. `项目运行流程.md`
5. `项目结构说明.md`
6. `LocalAgentCLI/README.md`
7. `LocalAgentCLI/开发日志.md`
## LocalAgentCLI prompt 模板目录

如果你要修改模型提示词，优先看：

- `LocalAgentCLI/prompts/system/`
- `LocalAgentCLI/prompts/user/`

## 2026-04-21 推荐阅读补充

如果你现在接手项目，除了上面的文档顺序，还建议补看这两类内容：

- `docs/issue_solutions.md`
  - 记录最近这轮“refine 为什么不起效、后来为什么局部重绘开始生效”的方法总结
- `docs/开发日志.md`
  - 记录当前阶段为何转向 `whole` 主线，以及 `validation/refiner` 如何改成按天 / 按问题局部修复

当前项目的最新理解可以先记住一句话：

> 生成主线先以 `whole` 为主，修复链路已经切到“validation 诊断 + refiner 局部重绘”的闭环，`daily` 后续继续优化，但暂时不承担当前阶段的主质量目标。
