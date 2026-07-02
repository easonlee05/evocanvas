# ETCLOVG Mapping（ETCLOVG 映射）

> 当前成熟度层级：`L1 参考框架层`

## 1. 文档目的

本文档说明 ETCLOVG 如何映射到 EvoCanvas 当前实践型 harness 骨架。

ETCLOVG 不再作为主目录结构，但仍可作为检查视角。

## 2. 映射关系

| ETCLOVG | EvoCanvas 当前骨架 | 说明 |
| --- | --- | --- |
| E Execution | `03-runtime-tools/01 Runtime` | 执行环境、受控回合、失败恢复 |
| T Tooling | `03-runtime-tools/02 Tool Contract` | 工具接口、来源协议、工具结果入链 |
| C Context | `01-instructions-context/`、`02-memory-state/` | ETCLOVG 把上下文和记忆放在一起，EvoCanvas 拆开处理 |
| L Lifecycle | `04-orchestration-lifecycle/` | 编排和生命周期在项目内区分为两个职责 |
| O Observability | `06-observability/` | trace、回执、回放和归因 |
| V Verification | `07-verification/` | 只保留单次过程 / 输出是否过关，不再吞并 evaluation |
| G Governance | `05-safety-governance/` | 治理与安全相邻，但事实生效边界由治理负责 |

## 3. 为什么拆出 Evaluation

ETCLOVG 的 V 可以覆盖一部分验证问题，但不能完整覆盖系统长期效果评估。

EvoCanvas 必须单独回答：

- 是否降低需求失真。
- 是否提升交接物可用性。
- 是否改善产品经理的真实工作流。

因此，`08-evaluation/` 是项目主骨架中的独立分组。

## 4. 为什么拆出 Instructions

ETCLOVG 没有把 prompt / instructions 明确列为一层，但在 EvoCanvas 中，指令决定 AI 是否服从产品收敛顺序。

因此，指令必须成为显式文档对象，而不能只藏在 context 或 runtime 中。
