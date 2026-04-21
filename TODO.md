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
- [~] 实现 `scripts/build_style_profile.py`
  - 14 维风格分析 **框架已定义，但仅 4-5 个维度有实际数据**（sentence_length, paragraph_length, connector_density, punctuation, opening_ending）
  - 其余维度（rhythm_breathing, rhetoric_preference, person_usage, tense_narrative, information_density, emotional_intensity, terminology_density, citation_style, ending_style）**尚未量化填充**
  - 标点偏好已实现，分块习惯与段落配方 **未从样文自动提取**（style-memory.json 中为空数组）
  - 叙述方法 **未自动识别**
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
- [~] 生成 `references/examples.md`（3-5 段 few-shot）—— **模板已渲染，但 few-shot 内容未从样文自动提取，仍为占位文本**
- [~] 生成 `assets/style-memory.json` —— **已生成，但 `paragraph_formulas`、`narrative_moves` 为空数组**
- [x] 生成 `assets/quality-rubric.json`
- [x] 生成 `evals/evals.json`

### 4. active child 发布
- [x] 实现 `scripts/publish_child.py`
  - 将 canonical `skill/` 同步到 `.claude/skills/writer-<child-name>/`
  - 更新 `state/release-index.json`
  - 生成 git tag（如 `v1.0.0`）
- [ ] 验证 Claude Code 可通过 `/writer-<child-name>` 识别并调用

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
- [~] 实现 `scripts/sync_visible_edits.py`
  - 监听/扫描 `<child-name>_Generated_Articles/` 变动
  - 处理：删除、新增、重命名
  - manifest 丢失时退化匹配 **实际仅做了文件名拆分，未实现真正的 hash + 文首片段匹配**
  - 同步映射回 canonical repo **但未自动执行 git add + commit**

### 7. 差异分析
- [~] 实现 `scripts/diff_revision.py`
  - 对比 baseline 与用户修改稿
  - 提取 revision signals
  - 分类：L1 Cosmetic / L2 Reusable Preference / L3 Structural Rule —— **分类逻辑仅基于字符长度差与段落数变化，未进行语义分析；L1 阈值（10 字符）可能过于宽松**

### 8. 规则升级
- [~] 实现 `scripts/promote_rules.py`
  - candidate → probation → active 的升级逻辑已实现
  - 更新 `assets/style-memory.json` 中的 `confidence_buckets`
  - 生成/更新规则对象（rule_id, rule_type, evidence_count, confidence, source_articles, transferability, boundary_note）
  - 追加 `state/learning-log.jsonl`
  - **规则描述生成较机械（"用户将 'xxx...' 改为 'yyy...'"），未做语义抽象；L2 与 L3 未区分处理**

### 9. candidate 评估
- [~] 实现 `scripts/eval_candidate.py`
  - 从 stable release 派生 candidate —— **candidate 生成逻辑缺失，无脚本负责写入 `state/candidates/v*.json`**
  - 执行 old vs candidate 对比评估
  - 结构维度：文件完整性、rules 分层、supporting files 职责、eval 覆盖度 —— **已实现（基于文件存在性打分）**
  - 效果维度：风格贴合度、活人感、长文推进力、AI 味减少、作者边界控制、选题判断 —— **全为占位符，未实现自动化评估**
  - 生成 `reports/eval-summary.md`

### 10. 用户决策与发布
- [~] 在父 skill 中集成 eval 结果展示 —— **SKILL.md 中有流程描述，但非程序化集成（无自动读取 eval-summary.md 并展示的逻辑）**
- [x] 用户确认 publish 后，调用 `publish_child.py` 发布 candidate
- [x] 用户拒绝时，保留 candidate 与报告，不发布

---

## P2：完善与扩展

目标：release 管理、rollback、更完整的评估与维护。

### 11. release 管理
- [x] 完善 `state/release-index.json` 结构
- [x] 规范 release tag 命名（semver）
- [ ] 生成 release notes（`reports/change-log.md`）
- [ ] create 阶段生成 `reports/create-summary.md`

### 12. rollback
- [x] 实现 `scripts/rollback_child.py`
  - 按版本 tag 回退 canonical repo
  - 重新 publish 到 active child
  - 保留被回滚的 candidate 报告

### 13. 评估体系深化
- [x] 完善 `references/eval-rubric.md`
- [x] 细化 `assets/quality-rubric.json` 评分标准 —— **模板已存在，但效果维度评估仍为占位**
- [ ] 增加更多自动化回归测试场景
- [x] 完善 `evals/evals.json`（素材成稿类、风格迁移类、边界判断类）—— **模板框架已存在**

### 14. examples 与 anti-patterns 维护
- [ ] 建立 examples 更新机制（从用户修改稿中提取高质量正例）—— **examples.md 当前仍为模板占位，未从样文提取**
- [ ] 建立 anti-patterns 扩充机制（从 diff 中识别高频 AI 味）—— **anti-patterns.md 为静态模板 + 简单 AI 套路列表，未从 diff 自动扩充**
- [ ] 定期（或触发式）清理过时/低置信度规则

### 15. 父 skill 完善
- [ ] 实现 `status` 指令展示当前 child 状态 —— **SKILL.md 中提到了该指令，但无对应脚本**
- [x] 完善 `references/update-policy.md`
- [x] 完善 `references/version-policy.md`
- [ ] 增加错误处理与边界 case 日志 —— **各脚本仅有基础错误处理（exit(1)），无统一日志系统**

---

## 验收检查清单

- [x] 能从 3-10 篇样文成功生成 child skill（已用 4 篇 AGI Hunt 文章测试通过）
- [x] child skill 目录结构符合需求文档第 7 节（SKILL.md + 5 references + 4 assets + evals）
- [ ] child skill 能被 Claude Code 直接识别并通过 `/writer-<child-name>` 调用（文件已发布到 `.claude/skills/`，待实际环境验证）
- [x] child skill 写稿时能自动双写 baseline 与 visible draft —— **文件结构与 manifest 双写已验证通过，但正文为占位文本**
- [~] 用户修改 visible draft 后，父 skill 能完成 learn 流程（diff + promote 链路已跑通）—— **脚本存在但无统一 pipeline 入口，需手动依次调用；sync 时未自动 git commit**
- [~] learn 流程能生成 candidate、评估报告和版本记录 —— **评估报告与版本记录已生成，但 candidate 版本本身无生成脚本（`state/candidates/` 无人写入）**
- [x] 用户能明确选择 publish 或 rollback（publish 与 rollback 脚本均测试通过）
- [x] rollback 后 active child 能恢复到之前稳定版本（v1.0.0 回滚验证通过）
- [x] child skill 输出是多文件 skill，不是单段 prompt
- [~] child skill 至少具备：选题判断、文章原型识别、AI/人类边界控制、作者态二改、最终自检 —— **child SKILL.md 中有这些能力的文本描述，但 prompts 较简略，实际执行效果未经 Claude Code 运行验证**

---

## 验证备注（2026-04-21）

基于 [验证报告](../../docs/reports/survey/writing-skill-factory-cli-todo-verification-report.md) 的审查结果，以下是 TODO 与实际实现的偏差汇总：

1. **14 维风格分析**：框架完整但仅约 1/3 维度有实际数据。建议补充其余维度的简单启发式，或调整 TODO 描述为"框架预留"。
2. **candidate 生成缺口**：eval_candidate.py 会查找 `state/candidates/v*.json`，但当前没有任何脚本负责生成并写入 candidate manifest。这是 P1 链路的关键断点。
3. **效果维度评估**：eval_candidate.py 中风格贴合度、活人感、AI 味减少等子维度全为占位符 `[待测试]`，未实现任何自动化评估（哪怕是基于样文重叠度的简单计算）。
4. **learn 流程自动化**：sync → diff → promote → eval 四个脚本存在但分散，无统一 pipeline 入口，用户需手动依次调用。
5. **正文生成**：generate_article.py 仅生成文件骨架与占位文本，实际文章由 Claude Code 调用 active child skill 完成，脚本本身不生成正文。
6. **Claude Code 识别**：child skill 文件已发布到 `.claude/skills/`，但 `/writer-test_writer` 是否可被 Claude Code 直接识别并调用，**尚未实际验证**。
7. **examples.md few-shot**：extract_few_shots 函数在 build_style_profile.py 中存在，但渲染后的 child skill examples.md 仍为模板占位内容，未反映样文实际片段。

---

## 测试数据

- 来源：`local_articles_datasets/AGI Hunt/`（4 篇公众号文章）
- 预处理：已清洗微信公众号 UI 噪音，存放于 `test_samples/`
- 状态：可用于 create-child 测试
