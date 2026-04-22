# 系统架构与数据流

## 整体架构

```text
+-------------------------------------------------------------+
|                      User Layer                             |
|  提供样文 / 发起 draft / 修改 visible / 决策 publish/rollback  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|              writing-skill-factory-claude (父 skill)            |
|  create | draft | learn | eval | publish | rollback | status |
+-------------------------------------------------------------+
                              |
          +-------------------+-------------------+
          |                                       |
          v                                       v
+------------------------+          +-------------------------+
| Canonical Repo (git)   |          | Active Child (skill)    |
| .claude/writing-factory|          | .claude/skills/         |
| /children/<name>/repo/ |          | writer-<child-name>/    |
+------------------------+          +-------------------------+
  | skill/      (源码)                   ^
  | state/      (学习状态)               |
  | reports/    (评估报告)               | publish / rollback
  | workspace/  (工作区)                 |
  +--------------------------------------+
                              |
                              v
+------------------------+
| Visible Output         |
| <child-name>_Generated |
| _Articles/             |
+------------------------+
```

## 数据流

### create-child 数据流

```
User 样文
    |
    v
+---------------+     +-------------------+     +-------------------+
| 样本文库盘点   | --> | build_style_      | --> | style-profile.md  |
| (去重/去异常)  |     | profile.py        |     | style-memory.json |
+---------------+     +-------------------+     +-------------------+
    |
    v
+---------------+     +-------------------+     +-------------------+
| 双层蒸馏      | --> | build_cognitive_  | --> | editorial-rules.md|
|              |     | profile.py        |     | author-boundary.md|
+---------------+     +-------------------+     | anti-patterns.md  |
                                                +-------------------+
    |
    v
+---------------+     +-------------------+     +-------------------+
| 构造 child    | --> | create_child.py   | --> | canonical repo    |
| skill        |     | (模板渲染)         |     | (skill/ + state/) |
+---------------+     +-------------------+     +-------------------+
    |
    v
+---------------+     +-------------------+     +-------------------+
| 首轮评估      | --> | eval_candidate.py | --> | eval-summary.md   |
| (baseline vs  |     | (old=无 skill)     |     | 用户决策           |
|  candidate)  |     +-------------------+     +-------------------+
+---------------+
    |
    v
+---------------+
| publish_child |
|    .py       |
+---------------+
    |
    v
.claude/skills/writer-<child-name>/
```

### draft 数据流

```
User Topic/Brief
    |
    v
+---------------+     +-------------------+     +-------------------+
| generate_     | --> | active child      | --> | baseline.md       |
| article.py   |     | (Claude skill)     |     | state/baselines/  |
+---------------+     +-------------------+     +-------------------+
    |                                               |
    |                                               v
    |                                         +-------------------+
    |                                         | manifest.json     |
    |                                         | .manifest/        |
    |                                         +-------------------+
    |
    v
+-------------------+
| visible draft.md  |
| <child>_Generated |
| _Articles/        |
+-------------------+
```

### learn 数据流

```
User 修改 visible draft
    |
    v
+---------------+     +-------------------+     +-------------------+
| sync_visible_ | --> | diff_revision.py  | --> | revision signals  |
| edits.py     |     | (baseline vs 修改) |     | (L1/L2/L3)        |
+---------------+     +-------------------+     +-------------------+
    |                                               |
    |                                               v
    |                                         +-------------------+
    |                                         | promote_rules.py  |
    |                                         | (candidate ->     |
    |                                         |  probation ->     |
    |                                         |  active)          |
    |                                         +-------------------+
    |                                               |
    v                                               v
+---------------+     +-------------------+     +-------------------+
| canonical repo | <-- | eval_candidate.py | <-- | candidate skill  |
| state/        |     | (old vs candidate) |     | (待评估版本)      |
+---------------+     +-------------------+     +-------------------+
                              |
                              v
                        +-------------------+
                        | eval-summary.md   |
                        | 用户决策           |
                        +-------------------+
                              |
                    +---------+---------+
                    |                   |
                    v                   v
              +-----------+       +-----------+
              | publish   |       | rollback  |
              +-----------+       +-----------+
```

## 核心原则

1. **canonical repo 是唯一真相源**：`.claude/skills/writer-<child-name>/` 只是已发布副本，禁止直接在 active child 目录做长期手工修改。
2. **candidate 机制**：学习更新后不得直接覆盖 active child，必须经过 candidate → eval → user decision → publish/rollback。
3. **人在回路**：即使自动评估分数更高，也不得自动 publish，必须由用户确认"更好"。
4. **双写对齐**：不得只依赖文件名对齐 baseline 与 visible draft，必须依赖 `article_id` + `baseline_sha` + manifest。
5. **子 skill 不自改**：子 skill 只负责"按当前版本的最佳规则写文章"，不负责自己修改自己、自己做 git 管理、自己决定升级。
