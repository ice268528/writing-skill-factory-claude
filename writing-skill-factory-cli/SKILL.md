---
name: writing-skill-factory-cli
description: >
  父级 skill 工厂 CLI。负责根据样文蒸馏作者风格、创建 writer-<child-name> 子 skill、
  管理 draft 双写、从用户修改中学习、评估 candidate、发布与回滚。
disable-model-invocation: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# writing-skill-factory-cli

> 根据用户提供的多篇文章蒸馏作者风格与写作系统，生成可被 Claude Code 识别和调用的 `writer-<child-name>` 子 skill。

## 职责范围

本 skill 只负责以下六类动作：

1. `create-child` — 从样文创建新的 writer 子 skill
2. `draft-with-child` — 调用 active child 生成文章（双写 baseline + visible）
3. `learn-from-visible-edits` — 对比用户修改，抽取稳定偏好
4. `evaluate-candidate` — 评估 candidate 版本 vs stable release
5. `publish-child` — 将 candidate 发布为 active child
6. `rollback-child` — 回滚到指定稳定版本

本 skill **不直接承担长期写作工作**。

## 调用方式

```text
/writing-skill-factory create   "<child-name>" "<samples-dir>"
/writing-skill-factory draft    "<child-name>" "<topic-or-brief>"
/writing-skill-factory learn    "<child-name>"
/writing-skill-factory eval     "<child-name>"
/writing-skill-factory publish  "<child-name>"
/writing-skill-factory rollback "<child-name>" "<version>"
/writing-skill-factory status   "<child-name>"
```

## 工作流总览

### create-child

Phase 0: 识别 create 场景（用户提供 3-10 篇样文）
Phase 1: 澄清（确认名称、风格统一性、输出形式、禁区等）
Phase 2: 样本文库盘点（去重、去异常、统计）
Phase 3: 双层蒸馏（风格蒸馏 + 认知蒸馏）
Phase 4: 构造 child skill（SKILL.md + references + assets + evals）
Phase 5: 生成测试 prompts（素材成稿 / 风格迁移 / 边界判断）
Phase 6: 首轮评估（baseline vs candidate）
Phase 7: 用户决策（publish 或 revise）
Phase 8: 发布到 `.claude/skills/writer-<child-name>/`

> 详细流程见 `references/architecture.md`

### draft-with-child

1. **验证 active child**
   - 确认 `.claude/skills/writer-<child-name>/SKILL.md` 存在且 frontmatter 中的 `name` 为 `writer-<child-name>`
   - 确认 canonical repo 存在：`.claude/writing-factory/children/<child-name>/repo/`

2. **准备文件结构与元数据**
   - 运行 Bash：`python scripts/generate_article.py <child_name> "<topic>" --factory-dir .claude/writing-factory/children --project-root .`
   - 解析脚本输出的 JSON manifest，获取 `article_id`、`baseline_path`、`visible_path`、`manifest_path`
   - 脚本已自动创建 frontmatter + 占位骨架，并生成 sidecar manifest

3. **加载 child skill 写作系统**
   - Read `.claude/skills/writer-<child-name>/SKILL.md`
   - Read `.claude/skills/writer-<child-name>/references/style-profile.md`
   - Read `.claude/skills/writer-<child-name>/references/editorial-rules.md`
   - Read `.claude/skills/writer-<child-name>/references/anti-patterns.md`
   - Read `.claude/skills/writer-<child-name>/references/author-boundary.md`
   - Read `.claude/skills/writer-<child-name>/references/examples.md`
   - Read `.claude/skills/writer-<child-name>/assets/style-memory.json`

4. **生成完整文章**
   - 按照 child skill 的 Phase 1-6 写作流程生成文章正文
   - 遵守所有 references 中的风格、规则、边界与反模式约束
   - 文章必须是完整成品，不得输出占位符或模板文本

5. **双写**
   - **baseline**：用 Write 工具覆盖 `baseline_path` 指向的文件。保留原有 frontmatter，将正文替换为步骤 4 生成的完整文章。
   - **visible draft**：用 Write 工具覆盖 `visible_path` 指向的文件。保留原有 frontmatter，将正文替换为与 baseline 相同的内容。
   - 双写后重新计算 sha256，更新 manifest 中的 `baseline_sha` 和 `current_sha`

6. **完成 manifest 与报告**
   - 更新 sidecar manifest 的 `status` 为 `generated`
   - 更新 canonical repo 中 `state/manifests/<article_id>.json`
   - 向用户报告：visible draft 的完整路径，并提示用户可在此文件上直接编辑，完成后运行 `/writing-skill-factory learn <child-name>`

### learn-from-visible-edits

统一入口：`scripts/learn_pipeline.py`

1. 扫描 visible 目录变动（增删改）
2. 同步映射回 canonical repo（含自动 git commit）
3. diff baseline vs 用户修改稿
4. 分类 revision signals（L1 Cosmetic / L2 Reusable Preference / L3 Structural Rule）
5. 规则升级（candidate → probation → active）
6. 生成 candidate 版本（`scripts/generate_candidate.py`）
7. 触发 evaluate-candidate

支持 `--dry-run` 预览、`--article-id` 指定单篇文章、`--skip-eval` 跳过评估。

### evaluate-candidate

1. 结构维度评估（文件完整性、rules 分层、eval 覆盖度）
2. 效果维度评估（风格贴合度、活人感、AI 味减少、边界控制）
3. 生成 `reports/eval-summary.md`
4. 等待用户裁决（**不得自动 publish**）

### publish-child

1. 将 canonical candidate 同步到 `.claude/skills/writer-<child-name>/`
2. 打 release tag
3. 更新 `state/release-index.json`

### rollback-child

1. 检出指定 release tag
2. 重新 publish 到 active child
3. 保留失败 candidate 的报告

### status

1. 运行 `scripts/show_status.py <child-name>`
2. 展示当前 child 的六大状态板块：
   - **Release**：最新版本、发布次数
   - **Candidates**：候选数量、最新候选版本
   - **Rules**：active / probation / candidate 规则统计
   - **Learning**：pipeline 运行次数、promote 事件数
   - **Articles**：样文、baseline、revision 数量
   - **Evals**：评估报告数量与最新报告
3. 支持 `--json` 输出原始 JSON（供其他脚本消费）

## 目录映射

| 路径 | 语义 |
|------|------|
| `.claude/skills/writing-skill-factory-cli/` | 父 skill 常驻目录 |
| `.claude/skills/writer-<child-name>/` | 当前 active child（Claude 直接识别） |
| `.claude/writing-factory/children/<child-name>/repo/` | child 的 canonical git 仓库 |
| `.claude/writing-factory/children/<child-name>/repo/skill/` | child skill 源码 |
| `.claude/writing-factory/children/<child-name>/repo/state/` | 学习状态、baseline、candidate、release、log |
| `.claude/writing-factory/children/<child-name>/repo/reports/` | 评估报告与变更日志 |
| `<child-name>_Generated_Articles/` | 用户可见、可编辑目录 |

## Supporting Files

- `references/architecture.md` — 系统架构与数据流
- `references/source-mapping.md` — 参考 skill 能力映射表
- `references/style-dimensions.md` — 14 维风格分析框架定义
- `references/update-policy.md` — 学习更新与规则升级策略
- `references/eval-rubric.md` — 评估维度与评分标准
- `references/version-policy.md` — 版本号与 release 管理规范

## Scripts

- `scripts/create_child.py` — 创建 canonical child 仓库与首版 skill
- `scripts/build_style_profile.py` — 高分辨率风格画像生成
- `scripts/build_cognitive_profile.py` — 认知、边界与反模式画像生成
- `scripts/generate_article.py` — 调用 active child 写稿并执行双写
- `scripts/sync_visible_edits.py` — 同步可见目录与 baseline 映射
- `scripts/diff_revision.py` — 分析 baseline 与用户修改稿差异
- `scripts/promote_rules.py` — revision signals 提升为 candidate/probation/active 规则
- `scripts/eval_candidate.py` — old vs candidate 评估并生成报告
- `scripts/generate_candidate.py` — 从 canonical repo 生成 candidate 版本（填补 P1 链路断点）
- `scripts/learn_pipeline.py` — **统一 learn 流程入口**（sync → diff → promote → candidate → eval）
- `scripts/publish_child.py` — canonical skill → active child 发布
- `scripts/rollback_child.py` — 从 release 恢复并重新发布
- `scripts/show_status.py` — 展示 child 当前状态（release、rules、learning、evals 等）
