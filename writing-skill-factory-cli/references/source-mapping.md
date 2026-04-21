# 参考 Skill 能力映射

## 映射总表

| 参考 Skill | 核心能力 | 落地组件 | 输出产物 |
|-----------|---------|---------|---------|
| `wechat-style-profiler` | 高分辨率文风蒸馏（14 维） | `build_style_profile.py` | `references/style-profile.md`, `assets/style-memory.json` |
| `nuwa-skill` | 认知画像、表达 DNA、反模式 | `build_cognitive_profile.py` | `references/editorial-rules.md`, `references/author-boundary.md`, `references/anti-patterns.md` |
| `darwin-skill` | candidate 机制、棘轮优化、人在回路 | `promote_rules.py`, `eval_candidate.py`, `publish_child.py`, `rollback_child.py` | `state/candidates/`, `state/releases/`, `reports/eval-summary.md` |
| `cangjie-skill` | 多阶段提取 → 结构化构造 → 测试 | `create_child.py` | 完整 runnable child skill 目录 |
| `khazix-writer` | 完整长文写作系统、AI/人边界 | child skill `SKILL.md` 设计 | 覆盖 intake → 选题 → 大纲 → 首稿 → 二改 → 自检的全流程 |

## 详细映射

### wechat-style-profiler

- **必须吸收**：
  1. 高分辨率文风蒸馏，而非只抽取高频词
  2. 14 维分析框架
  3. 标点偏好、分块习惯、段落配方、叙述方法、内容推进方式
  4. 先做量化底盘，再做定性解释
  5. 保留 few-shot 证据，而非只留结论

- **落地要求**：
  - 父 skill 实现 `build_style_profile.py`
  - child skill 必须产出 `references/style-profile.md`、`references/examples.md`、`assets/style-memory.json`

### nuwa-skill

- **必须吸收**：
  1. 从"像不像"升级到"怎么想 / 怎么判断 / 什么不做 / 边界在哪"
  2. 表达 DNA、心智模型、决策启发式、反模式、诚实边界
  3. 规则必须具备迁移性判断，而非仅复述原文

- **落地要求**：
  - 父 skill 实现 `build_cognitive_profile.py`
  - child skill 必须产出 `references/editorial-rules.md`、`references/author-boundary.md`、`references/anti-patterns.md`
  - 规则对象至少记录：`rule_type`, `evidence_count`, `confidence`, `transferability`, `boundary_note`

### darwin-skill

- **必须吸收**：
  1. candidate 机制，而非直接覆盖现有版本
  2. 评估、改进、测试、保留或回滚的棘轮流程
  3. 结构评估与效果评估双轨并行
  4. 人在回路，用户拥有最终裁决权

- **落地要求**：
  - 每个 child 的 canonical source 必须是 git 仓库
  - 每次学习更新必须执行：派生 candidate → 运行评估 → 生成 diff 与 score delta → 等待用户决策 → publish 或 rollback
  - 必须维护：`state/candidates/`, `state/releases/`, `reports/eval-summary.md`, `state/learning-log.jsonl`

### cangjie-skill

- **必须吸收**：
  1. 输出 runnable skill，而非只输出风格报告
  2. 通过多文件结构承载规则、案例、模板与验证材料
  3. 使用多阶段提取 → 筛选 → 结构化构造 → 测试流程

- **落地要求**：
  - 父 skill 的 create-child 输出必须包括：child skill 源码目录、supporting files、结构化资产、eval 文件、学习与版本日志
  - 设计哲学：`profile -> runnable writer skill -> learnable writer system`

### khazix-writer

- **必须吸收**：
  1. 子 skill 必须是完整长文写作系统
  2. 写作流程至少覆盖：素材 intake、选题诊断、文章原型识别、标题方向、证据化大纲、首稿、作者态二改、最终自检
  3. 明确 AI / 人类边界
  4. 维护显式禁区，而非把禁区散落在 prompt 中

- **落地要求**：
  - child skill 必须包含 `references/editorial-rules.md`、`references/author-boundary.md`、`references/anti-patterns.md`
  - child skill 必须能明确区分：AI 能补什么、人必须给什么
