# writing-skill-factory-cli 实现 TODO

> 基于 `writing_skill_factory_requirements.md` 制定，按 P0 → P1 → P2 顺序推进。

---

## P0：最小闭环（MVP）

目标：能从样文生成 child skill，发布为 active skill，并完成 draft 双写。

### 1. 父 skill 骨架搭建
- [x] 创建 `.claude/skills/writing-skill-factory-cli/` 目录结构
  - `SKILL.md`
  - `references/`（architecture.md, source-mapping.md, style-dimensions.md, update-policy.md, eval-rubric.md, version-policy.md）
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
  - 14 维风格分析
  - 标点偏好、分块习惯、段落配方、叙述方法
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
- [x] 生成 `references/examples.md`（3-5 段 few-shot）
- [x] 生成 `assets/style-memory.json`
- [x] 生成 `assets/quality-rubric.json`
- [x] 生成 `evals/evals.json`

### 4. active child 发布
- [x] 实现 `scripts/publish_child.py`
  - 将 canonical `skill/` 同步到 `.claude/skills/writer-<child-name>/`
  - 更新 `state/release-index.json`
  - 生成 git tag（如 `v1.0.0`）
- [ ] 验证 Claude Code 可通过 `/writer-<child-name>` 识别并调用

### 5. draft 双写
- [x] 实现 `scripts/generate_article.py`
  - 调用 active child 生成文章
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
  - manifest 丢失时退化到 hash + 文首片段匹配
  - 同步映射回 canonical repo

### 7. 差异分析
- [x] 实现 `scripts/diff_revision.py`
  - 对比 baseline 与用户修改稿
  - 提取 revision signals
  - 分类：L1 Cosmetic / L2 Reusable Preference / L3 Structural Rule

### 8. 规则升级
- [x] 实现 `scripts/promote_rules.py`
  - candidate → probation → active 的升级逻辑
  - 更新 `assets/style-memory.json` 中的 `confidence_buckets`
  - 生成/更新规则对象（rule_id, rule_type, evidence_count, confidence, source_articles, transferability, boundary_note）
  - 追加 `state/learning-log.jsonl`

### 9. candidate 评估
- [x] 实现 `scripts/eval_candidate.py`
  - 从 stable release 派生 candidate
  - 执行 old vs candidate 对比评估
  - 结构维度：文件完整性、rules 分层、supporting files 职责、eval 覆盖度
  - 效果维度：风格贴合度、活人感、长文推进力、AI 味减少、作者边界控制、选题判断
  - 生成 `reports/eval-summary.md`

### 10. 用户决策与发布
- [x] 在父 skill 中集成 eval 结果展示
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
- [x] 细化 `assets/quality-rubric.json` 评分标准
- [ ] 增加更多自动化回归测试场景
- [x] 完善 `evals/evals.json`（素材成稿类、风格迁移类、边界判断类）

### 14. examples 与 anti-patterns 维护
- [ ] 建立 examples 更新机制（从用户修改稿中提取高质量正例）
- [ ] 建立 anti-patterns 扩充机制（从 diff 中识别高频 AI 味）
- [ ] 定期（或触发式）清理过时/低置信度规则

### 15. 父 skill 完善
- [ ] 实现 `status` 指令展示当前 child 状态
- [x] 完善 `references/update-policy.md`
- [x] 完善 `references/version-policy.md`
- [ ] 增加错误处理与边界 case 日志

---

## 验收检查清单

- [ ] 能从 3-10 篇样文成功生成 child skill
- [ ] child skill 目录结构符合需求文档第 7 节
- [ ] child skill 能被 Claude Code 直接识别并通过 `/writer-<child-name>` 调用
- [ ] child skill 写稿时能自动双写 baseline 与 visible draft
- [ ] 用户修改 visible draft 后，父 skill 能完成 learn 流程
- [ ] learn 流程能生成 candidate、评估报告和版本记录
- [ ] 用户能明确选择 publish 或 rollback
- [ ] rollback 后 active child 能恢复到之前稳定版本
- [x] child skill 输出是多文件 skill，不是单段 prompt
- [x] child skill 至少具备：选题判断、文章原型识别、AI/人类边界控制、作者态二改、最终自检

---

## 测试数据

- 来源：`local_articles_datasets/AGI Hunt/`（4 篇公众号文章）
- 预处理：已清洗微信公众号 UI 噪音，存放于 `test_samples/`
- 状态：可用于 create-child 测试
