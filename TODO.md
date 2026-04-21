# writing-skill-factory-cli 实现 TODO

> 基于 `writing_skill_factory_requirements.md` 制定，按 P0 → P1 → P2 顺序推进。

---

## P0：最小闭环（MVP）

目标：能从样文生成 child skill，发布为 active skill，并完成 draft 双写。

### 1. 父 skill 骨架搭建
- [x] 创建 `.claude/skills/writing-skill-factory-cli/` 目录结构
  - `SKILL.md`
  - `references/`（architecture.md, ~~source-mapping.md, style-dimensions.md, version-policy.md~~ 最初 TODO 遗漏，实际已存在 ✅）
  - `templates/`（child-skill-skill.md.tpl, style-summary.md.tpl, usage-guide.md.tpl, manifest.json.tpl, evals.json.tpl, quality-rubric.json.tpl, article-schema.json.tpl, generation-policy.json.tpl, examples.md.tpl）
  - `scripts/`（全部 .py 文件）
- [x] 编写父 skill `SKILL.md`（触发条件、6 大指令映射、参数说明）
- [x] 编写 `references/architecture.md`（系统架构与数据流）

### 2. create-child 核心链路
- [x] 实现 `scripts/create_child.py`
  - 初始化 canonical git repo（`.claude/writing-factory/children/<child-name>/repo/`）
  - 创建目录结构（skill/, state/, reports/, workspace/）
  - 生成首版子 skill 文件（SKILL.md + references + assets + evals）
- [x] 实现 `scripts/build_style_profile.py`
  - **14 维风格分析已全部实现**（新增 D03~D14 的启发式量化）
  - 标点偏好、段落配方（`paragraph_formulas`）、叙述方法（`narrative_moves`）均从样文自动提取
  - **同步生成 `references/examples.md`**（从样文提取 few-shot 并自动生成风格要点）
  - 输出 `references/style-profile.md` + `assets/style-memory.json`
- [x] 实现 `scripts/build_cognitive_profile.py`
  - 心智模型、决策启发式、反模式、诚实边界
  - 输出 `references/editorial-rules.md` + `references/author-boundary.md` + `references/anti-patterns.md`
- [x] 实现模板渲染逻辑
  - `child-skill-skill.md.tpl` → `SKILL.md`
  - `style-summary.md.tpl` → 风格摘要
  - `manifest.json.tpl` → 首版 manifest
  - `evals.json.tpl` → 初始测试集框架

### 3. 子 skill 最小文件集
- [x] 生成 `skill/SKILL.md`（frontmatter + 触发条件 + 写作流程 + supporting files 导航）
- [x] 生成 `references/style-profile.md`
- [x] 生成 `references/editorial-rules.md`
- [x] 生成 `references/author-boundary.md`
- [x] 生成 `references/anti-patterns.md`
- [x] 生成 `references/examples.md`（3-5 段 few-shot）—— **已从样文自动提取，并自动生成风格要点**
- [x] 生成 `assets/style-memory.json` —— **已生成，`paragraph_formulas`、`narrative_moves` 均从样文自动填充**
- [x] 生成 `assets/quality-rubric.json`
- [x] 生成 `evals/evals.json`

### 4. active child 发布
- [x] 实现 `scripts/publish_child.py`
  - 将 canonical `skill/` 同步到 `.claude/skills/writer-<child-name>/`
  - 更新 `state/release-index.json`
  - 生成 git tag（如 `v1.0.0`）
- [~] 验证 Claude Code 可通过 `/writer-<child-name>` 识别并调用 —— **publish_child.py 已增加 SKILL.md 版本号自动同步，但 `/writer-test_writer` 是否可被直接调用仍需在实际 Claude Code 环境验证**

### 5. draft 双写
- [~] 实现 `scripts/generate_article.py`
  - **文件结构与 manifest 双写已实现，但 baseline/visible 正文为占位文本**（实际文章生成由 Claude Code 调用 active child skill 完成）
  - 双写 baseline → `state/baselines/<article_id>.md`
  - 双写 visible draft → `<child-name>_Generated_Articles/<article_id>__<topic>.md`
- [x] 生成 sidecar manifest（`.manifest/<article_id>.json`）
  - 字段：article_id, child_name, child_version, baseline_sha, created_at, topic, status
- [x] 实现文章对齐机制（article_id + baseline_sha + manifest）

---

## P1：学习更新与评估

目标：用户修改 visible draft 后，系统能完成 learn → candidate → eval 流程。

### 6. 可见目录同步
- [x] 实现 `scripts/sync_visible_edits.py`
  - 监听/扫描 `<child-name>_Generated_Articles/` 变动
  - 处理：删除、新增、重命名
  - manifest 丢失时退化匹配（文件名拆分）
  - 同步映射回 canonical repo
- [x] **learn_pipeline.py 已集成自动 git commit**，无需手动调用单个脚本

### 7. 差异分析
- [x] 实现 `scripts/diff_revision.py`
  - 对比 baseline 与用户修改稿
  - 提取 revision signals
  - 分类：L1 Cosmetic / L2 Reusable Preference / L3 Structural Rule —— **已增强语义分析层**：引入 `SequenceMatcher` 相似度、段落功能识别（heading/opening/conclusion/transition/body）、纯标点/助词检测、AI 套路词识别，替代了原先仅基于字符长度与段落数的粗糙分类

### 8. 规则升级
- [x] 实现 `scripts/promote_rules.py`
  - candidate → probation → active 的升级逻辑已实现
  - 更新 `assets/style-memory.json` 中的 `confidence_buckets`
  - 生成/更新规则对象（rule_id, rule_type, evidence_count, confidence, source_articles, transferability, boundary_note）
  - 追加 `state/learning-log.jsonl`
  - **已增强语义抽象**：新增 `_abstract_rule_description()`，根据 L2/L3 区分生成结构化规则描述（如"偏好将长句拆分为短句"、"避免 AI 套路表达"、"文章开头应更直接"等），替代了原先机械的文本对比描述

### 9. candidate 评估
- [x] 实现 `scripts/eval_candidate.py`
  - 从 stable release 派生 candidate —— **generate_candidate.py 已填补此缺口**
  - 执行 old vs candidate 对比评估
  - 结构维度：文件完整性、rules 分层、supporting files 职责、eval 覆盖度 —— **已实现（基于文件存在性打分）**
  - 效果维度：
    - **style_fit、boundary_control 已实现自动化评估**（基于 style-memory 差异与规则文件完整度）
    - 其余维度（human_feel、long_form_drive、ai_taste_reduction、topic_judgment、info_sufficiency）提供**检查清单**，由人工评分
  - 生成 `reports/eval-summary.md`

### 10. 用户决策与发布
- [x] 在父 skill 中集成 eval 结果展示 —— **learn_pipeline.py 已程序化集成 eval 步骤，报告自动生成**
- [x] 用户确认 publish 后，调用 `publish_child.py` 发布 candidate
- [x] 用户拒绝时，保留 candidate 与报告，不发布

---

## P2：完善与扩展

目标：release 管理、rollback、更完整的评估与维护。

### 11. release 管理
- [x] 完善 `state/release-index.json` 结构
- [x] 规范 release tag 命名（semver）
- [x] `generate_candidate.py` 自动生成 candidate manifest 并更新 release-index —— **已实现，支持版本碰撞自动避让**
- [x] 生成 release notes（`reports/change-log.md`）—— **已集成到 create_child.py、generate_candidate.py、publish_child.py、rollback_child.py`，自动追加变更记录**
- [x] create 阶段生成 `reports/create-summary.md` —— **create_child.py 已集成**

### 12. rollback
- [x] 实现 `scripts/rollback_child.py`
  - 按版本 tag 回退 canonical repo
  - 重新 publish 到 active child
  - 保留被回滚的 candidate 报告

### 13. 评估体系深化
- [x] 完善 `references/eval-rubric.md`
- [x] 细化 `assets/quality-rubric.json` 评分标准 —— **效果维度已实现部分自动化（style_fit、boundary_control）**
- [ ] 增加更多自动化回归测试场景
- [x] 完善 `evals/evals.json`（素材成稿类、风格迁移类、边界判断类）—— **模板框架已存在**

### 14. examples 与 anti-patterns 维护
- [x] 建立 examples 更新机制 —— **build_style_profile.py 已从样文自动提取 few-shot 并生成 examples.md**
- [x] 建立 anti-patterns 扩充机制（从 diff 中识别高频 AI 味）—— **promote_rules.py 已集成 `_update_anti_patterns_from_revision()`，自动从 revision 中提取用户删除的 AI 套路词并追加到 anti-patterns.md，避免重复添加**
- [ ] 定期（或触发式）清理过时/低置信度规则

### 15. 父 skill 完善
- [x] **实现 `scripts/learn_pipeline.py` 作为统一入口** —— 覆盖 sync → diff → promote → candidate → eval 全链路
- [x] 实现 `status` 指令展示当前 child 状态 —— **新建 `scripts/show_status.py`，展示 release、candidate、rules、learning、articles、evals 六大板块**
- [x] 完善 `references/update-policy.md`
- [x] 完善 `references/version-policy.md`
- [ ] 增加错误处理与边界 case 日志 —— **各脚本仅有基础错误处理（exit(1)），无统一日志系统**

---

## 验收检查清单

- [x] 能从 3-10 篇样文成功生成 child skill（已用 4 篇 AGI Hunt 文章测试通过）
- [x] child skill 目录结构符合需求文档第 7 节（SKILL.md + 5 references + 4 assets + evals）
- [x] child skill 能被 Claude Code 直接识别并通过 `/writer-<child-name>` 调用（`/writer-test_writer` 已实际验证，SKILL.md 完整加载）
- [x] child skill 写稿时能自动双写 baseline 与 visible draft —— **文件结构与 manifest 双写已验证通过，但正文为占位文本**
- [x] 用户修改 visible draft 后，父 skill 能完成 learn 流程 —— **learn_pipeline.py 已统一入口，sync → diff → promote 全链路跑通，含自动 git commit**
- [x] learn 流程能生成 candidate、评估报告和版本记录 —— **generate_candidate.py 填补缺口，candidate manifest 已自动生成并写入 `state/candidates/`**
- [x] 用户能明确选择 publish 或 rollback（publish 与 rollback 脚本均测试通过）
- [x] rollback 后 active child 能恢复到之前稳定版本（v1.0.0 回滚验证通过）
- [x] child skill 输出是多文件 skill，不是单段 prompt
- [x] child skill 至少具备：选题判断、文章原型识别、AI/人类边界控制、作者态二改、最终自检 —— **SKILL.md 中有完整流程描述，references 文件已由 build 脚本自动填充，实际效果待更多样文验证**

---

## 验证备注（2026-04-21）

基于 [验证报告](../../docs/reports/survey/writing-skill-factory-cli-todo-verification-report.md) 的审查结果，以下是 TODO 与实际实现的偏差汇总：

### 已修复（本次推进）

1. **14 维风格分析**：`build_style_profile.py` 已补全全部 14 维度的启发式量化（D01~D14），并在 test_writer（4 篇 AGI Hunt 样文）上验证通过。同时自动提取 `paragraph_formulas`、`narrative_moves`，同步生成 `examples.md`。
2. **candidate 生成缺口**：新建 `scripts/generate_candidate.py`，填补 P1 链路关键断点。支持自动版本递增、碰撞避让、git commit/tag、release-index 更新。
3. **效果维度评估**：`eval_candidate.py` 已实现 `style_fit`（基于 style-memory 差异）和 `boundary_control`（基于规则文件完整度）的自动化评分；其余维度从纯占位符升级为**带检查清单的人工评估指引**。
4. **learn 流程自动化**：新建 `scripts/learn_pipeline.py` 作为统一入口，串联 sync → diff → promote → generate_candidate → eval 五步，支持 `--dry-run`、指定 article-id、自动 git commit。
5. **examples.md few-shot**：`build_style_profile.py` 已自动从样文提取 few-shot 片段并重写 `examples.md`，替代了原先模板占位内容。

### 本次推进（2026-04-21 后续）

6. **diff 语义分析**：`diff_revision.py` 已重写 `classify_change()`，新增：
   - `SequenceMatcher` 相似度计算（L1 阈值提升至 0.92）
   - 纯标点/空格/助词变化检测（精确识别 cosmetic 修改）
   - 段落功能识别（heading/opening/conclusion/transition/thesis/body）
   - 开头/结尾重写、标题变更、大幅删改等 L3 场景识别
7. **promote 语义抽象**：`promote_rules.py` 新增 `_abstract_rule_description()`，根据 L2/L3 区分处理：
   - L2：识别长句拆分/合并、连接词偏好、具体化/抽象化、AI 套路词替换等模式
   - L3：识别开头/结尾重写、标题调整、段落功能转变等结构性规则
8. **create-summary & change-log**：`create_child.py`、`generate_candidate.py`、`publish_child.py`、`rollback_child.py` 均已集成变更日志自动追加。
9. **status 脚本**：新建 `scripts/show_status.py`，支持 `--json` 输出和人类可读表格，展示 release、candidate、rules、learning、articles、evals 状态。
10. **publish 版本同步**：`publish_child.py` 发布时自动更新 `SKILL.md` 中的版本号声明，避免 active skill 与 release-index 版本不一致。

### 仍待验证/完善

11. **正文生成**：`generate_article.py` 仍仅生成文件骨架与占位文本，实际文章由 Claude Code 调用 active child skill 完成，脚本本身不生成正文。（设计如此，未变更）
12. **Claude Code 识别**：`/writer-test_writer` 已验证可在 Claude Code 中直接识别并调用，SKILL.md 内容完整加载。（验证时间：2026-04-21）
13. **anti-patterns 自动扩充**：`promote_rules.py` 已集成 `_update_anti_patterns_from_revision()`，从 revision diff 中自动提取用户删除的 AI 套路词并追加到 `anti-patterns.md`，避免重复。但尚未建立从 diff 中识别"高频 AI 味句型"（而非单纯词汇）的机制。（P2 可深化）
14. **统一日志系统**：各脚本仅有基础错误处理（exit(1)），无统一日志系统与结构化日志输出。（P2 需求）

---

## 测试数据

- 来源：`local_articles_datasets/AGI Hunt/`（4 篇公众号文章）
- 预处理：已清洗微信公众号 UI 噪音，存放于 `test_samples/`
- 状态：可用于 create-child 测试
