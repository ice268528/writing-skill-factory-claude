# writing-skill-factory-cli 实现需求与约束规范

> 本文档仅用于指导 Claude Code 实现 `writing-skill-factory-cli` 父 skill 与其生成的 `writer-<child-name>` 子 skill。
> 
> 本文档是实现规约，不是背景说明，不依赖任何聊天记录，不假设实现者知道本文档之外的上下文。
> 
> 实现目标：产出一套结构清晰、流程完整、支持增量学习、支持候选评估、支持发布与回滚的 Claude Code skills 系统。

---

## 1. 文档使用方式

实现者必须把本文档视为硬约束来源。

实现时必须遵守以下原则：

1. 不得假设存在本文档未写明的隐含背景。
2. 遇到实现细节空缺时，应优先保持系统可维护、可评估、可回滚，而不是追求一次性“最聪明”。
3. 如果本地参考仓库与本文档有冲突，应优先遵守本文档对目标系统的定义，再吸收参考仓库中可复用的优点。
4. 如果 Claude Code 官方 skills 机制与本文档某条设计存在冲突，应优先遵守官方机制，再在本文档范围内做最小调整。

---

## 2. 系统目标

需要实现一个 Claude Code 原生系统，包含两个层级：

- 父 skill：`writing-skill-factory-cli`
- 子 skill：`writer-<child-name>`

系统必须满足以下目标：

1. 根据用户提供的多篇文章蒸馏作者风格与写作系统。
2. 生成一个可被 Claude Code 识别和调用的子 skill。
3. 子 skill 必须是完整写作系统，而不是单段 prompt。
4. 子 skill 每次出稿时必须自动创建：
   - 内部 baseline 稿
   - 用户可编辑稿
5. 用户只修改可见稿件；父 skill 负责对比 baseline 与修改稿并抽取稳定偏好。
6. 所有学习更新必须走 candidate → eval → user decision → publish/rollback 流程。
7. 最终是否“更好”由用户判断，自动评估只提供辅助。

---

## 3. 明确非目标

以下内容不是本期实现目标：

1. 不实现跨项目云同步。
2. 不实现多用户协同编辑。
3. 不实现真正的权限隐藏或安全隔离；本系统只做工程隔离，不承诺“用户绝对看不到某目录”。
4. 不实现自动联网抓取风格样本；样本输入以本地文件为主。
5. 不实现一次生成多个长期并存、同时自动触发的 writer 子 skill 集群。默认只维护一个 active child 供日常使用。

---

## 4. 必须对齐的 Claude Code / skill-creator 约束

### 4.1 Claude Code skills 目录与发现规则

实现必须遵守 Claude Code skills 的标准目录形态：

```text
.claude/skills/<skill-name>/SKILL.md
```

要求：

1. 希望被 Claude Code 直接识别和调用的 skill，必须位于 `.claude/skills/` 下的一级子目录。
2. 不得依赖 `.claude/skills/children/<name>/SKILL.md` 这类未明确保证会被识别的二级容器目录来承载 active child。
3. active child 必须发布到 `.claude/skills/writer-<child-name>/`。
4. canonical source、state、reports 可以放在 `.claude/writing-factory/` 下，因为这些不是直接给 Claude 自动发现的 skills。

### 4.2 父 skill 的调用方式

`writing-skill-factory-cli` 属于高副作用流程型 skill。

要求：

1. 父 skill 默认设计为手动调用优先。
2. 父 skill 必须设置为不依赖模型自由自动触发。
3. 父 skill 适合使用：
   - `disable-model-invocation: true`
   - 必要的 `allowed-tools`
   - 在 create / learn / eval / rollback 场景中可使用 `context: fork`
4. 父 skill 的实现必须显式使用 Claude Code skills 支持的参数机制，而不是依赖对话上下文猜测。

### 4.3 子 skill 的内容组织

子 skill 必须遵守“`SKILL.md` 控制流程，supporting files 承载细节”的原则。

要求：

1. 不得把全部风格规则、案例、禁区、记忆都堆进一个超长 `SKILL.md`。
2. `SKILL.md` 只放：
   - 触发条件
   - 主工作流
   - supporting files 导航
   - 参数说明
3. 详细内容必须下沉到 `references/`、`assets/`、`evals/`。

### 4.4 子 skill 的创建流程必须吸收 skill-creator 方法

父 skill 在 create-child 场景下，必须遵循以下顺序：

1. 澄清输入、输出、触发场景与边界。
2. 规划哪些信息进入 `SKILL.md`，哪些进入 `references/`、`assets/`、`scripts/`。
3. 生成 child skill 草稿。
4. 生成测试 prompts 与 `evals/evals.json`。
5. 执行 with-skill vs baseline 对比。
6. 产出结构化评估结果。
7. 由用户决定是否发布。

说明：

- 对齐 `skill-creator` 的重点不是“打成 zip 包”，而是“先建 skill，再测，再评，再迭代”。
- 由于本项目目标是 Claude Code 本地 skills，而不是 ChatGPT Web 上传包，因此发布动作应为“同步 skill 目录到 `.claude/skills/writer-<child-name>/`”，而不是生成 `skill.zip`。

---

## 5. 参考 skill 素材来源

实现时应优先读取用户本地副本原文。

### 5.1 风格蒸馏 / 风格学习

1. `wechat-style-profiler`
   - GitHub: `https://github.com/gainubi/wechat-skills/tree/main/wechat-style-profiler`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\wechat-skills\wechat-style-profiler`

2. `nuwa-skill`
   - GitHub: `https://github.com/alchaincyf/nuwa-skill`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\nuwa-skill`

3. `cangjie-skill`
   - GitHub: `https://github.com/kangarooking/cangjie-skill`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\cangjie-skill`

### 5.2 创建 skill 的 skill

4. `skill-creator`
   - GitHub: `https://github.com/anthropics/skills/tree/main/skills/skill-creator`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\claude_skills\skills\skill-creator`

### 5.3 自我进化 / 棘轮优化

5. `darwin-skill`
   - GitHub: `https://github.com/alchaincyf/darwin-skill`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\darwin-skill`

### 5.4 子 skill 质量与完整度参考

6. `khazix-writer`
   - GitHub: `https://github.com/KKKKhazix/khazix-skills/tree/main/khazix-writer`
   - 本地路径：`E:\Allproject\PyProject\StyleDistill_SKILLS\Reference projects\khazix-skills\khazix-writer`

---

## 6. 参考 skill 能力映射

本节定义参考 skill 的能力必须落到系统的哪个部分。

### 6.1 `wechat-style-profiler`

必须吸收的能力：

1. 高分辨率文风蒸馏，而不是只抽取高频词。
2. 至少覆盖以下风格要素：
   - 14 维分析框架
   - 标点偏好
   - 分块习惯
   - 段落配方
   - 叙述方法
   - 内容推进方式
3. 先做量化底盘，再做定性解释。
4. 保留 few-shot 证据，而不是只留结论。

落地要求：

- 父 skill 需要实现 `build_style_profile.py`。
- child skill 必须产出：
  - `references/style-profile.md`
  - `references/examples.md`
  - `assets/style-memory.json`

### 6.2 `nuwa-skill`

必须吸收的能力：

1. 从“像不像”升级到“怎么想 / 怎么判断 / 什么不做 / 边界在哪”。
2. 抽取以下层次：
   - 表达 DNA
   - 心智模型
   - 决策启发式
   - 反模式
   - 诚实边界
3. 规则必须具备迁移性判断，而不是仅复述原文。

落地要求：

- 父 skill 需要实现 `build_cognitive_profile.py`。
- child skill 必须产出：
  - `references/editorial-rules.md`
  - `references/author-boundary.md`
  - `references/anti-patterns.md`
- 规则对象至少要记录：
  - `rule_type`
  - `evidence_count`
  - `confidence`
  - `transferability`
  - `boundary_note`

### 6.3 `darwin-skill`

必须吸收的能力：

1. candidate 机制，而不是直接覆盖现有版本。
2. 评估、改进、测试、保留或回滚的棘轮流程。
3. 结构评估与效果评估双轨并行。
4. 人在回路，用户拥有最终裁决权。

落地要求：

- 每个 child 的 canonical source 必须是 git 仓库。
- 每次学习更新必须执行：
  1. 派生 candidate
  2. 运行评估
  3. 生成 diff 与 score delta
  4. 等待用户决策
  5. publish 或 rollback
- 必须维护：
  - `state/candidates/`
  - `state/releases/`
  - `reports/eval-summary.md`
  - `state/learning-log.jsonl`

### 6.4 `cangjie-skill`

必须吸收的能力：

1. 输出 runnable skill，而不是只输出风格报告。
2. 通过多文件结构承载规则、案例、模板与验证材料。
3. 使用多阶段提取 → 筛选 → 结构化构造 → 测试流程。

落地要求：

- 父 skill 的 create-child 输出必须包括：
  - child skill 源码目录
  - supporting files
  - 结构化资产
  - eval 文件
  - 学习与版本日志
- 设计哲学必须是：
  - `profile -> runnable writer skill -> learnable writer system`

### 6.5 `khazix-writer`

必须吸收的能力：

1. 子 skill 必须是完整长文写作系统。
2. 写作流程至少覆盖：
   - 素材 intake
   - 选题诊断
   - 文章原型识别
   - 标题方向
   - 证据化大纲
   - 首稿
   - 作者态二改
   - 最终自检
3. 明确 AI / 人类边界。
4. 维护显式禁区，而不是把禁区散落在 prompt 中。

落地要求：

- child skill 必须包含：
  - `references/editorial-rules.md`
  - `references/author-boundary.md`
  - `references/anti-patterns.md`
- child skill 必须能明确区分：
  - AI 能补什么
  - 人必须给什么

---

## 7. 目录规范

```text
project-root/
├── .claude/
│   ├── skills/
│   │   ├── writing-skill-factory-cli/
│   │   │   ├── SKILL.md
│   │   │   ├── references/
│   │   │   │   ├── architecture.md
│   │   │   │   ├── source-mapping.md
│   │   │   │   ├── style-dimensions.md
│   │   │   │   ├── update-policy.md
│   │   │   │   ├── eval-rubric.md
│   │   │   │   └── version-policy.md
│   │   │   ├── templates/
│   │   │   │   ├── child-skill-skill.md.tpl
│   │   │   │   ├── style-summary.md.tpl
│   │   │   │   ├── usage-guide.md.tpl
│   │   │   │   ├── manifest.json.tpl
│   │   │   │   └── evals.json.tpl
│   │   │   └── scripts/
│   │   │       ├── create_child.py
│   │   │       ├── build_style_profile.py
│   │   │       ├── build_cognitive_profile.py
│   │   │       ├── generate_article.py
│   │   │       ├── sync_visible_edits.py
│   │   │       ├── diff_revision.py
│   │   │       ├── promote_rules.py
│   │   │       ├── eval_candidate.py
│   │   │       ├── publish_child.py
│   │   │       └── rollback_child.py
│   │   │
│   │   └── writer-<child-name>/
│   │       ├── SKILL.md
│   │       ├── references/
│   │       │   ├── style-profile.md
│   │       │   ├── editorial-rules.md
│   │       │   ├── author-boundary.md
│   │       │   ├── anti-patterns.md
│   │       │   └── examples.md
│   │       ├── assets/
│   │       │   ├── style-memory.json
│   │       │   ├── quality-rubric.json
│   │       │   ├── article-schema.json
│   │       │   └── generation-policy.json
│   │       └── evals/
│   │           └── evals.json
│   │
│   └── writing-factory/
│       └── children/
│           └── <child-name>/
│               ├── repo/
│               │   ├── skill/
│               │   │   ├── SKILL.md
│               │   │   ├── references/
│               │   │   ├── assets/
│               │   │   └── evals/
│               │   ├── state/
│               │   │   ├── profiles/
│               │   │   ├── baselines/
│               │   │   ├── revisions/
│               │   │   ├── manifests/
│               │   │   ├── candidates/
│               │   │   ├── releases/
│               │   │   ├── learning-log.jsonl
│               │   │   └── release-index.json
│               │   └── reports/
│               │       ├── create-summary.md
│               │       ├── update-summary.md
│               │       ├── change-log.md
│               │       └── eval-summary.md
│               └── workspace/
│                   └── shadow-output/
│
└── <child-name>_Generated_Articles/
    ├── 2026-04-19-001__topic-a.md
    ├── 2026-04-19-002__topic-b.md
    └── .manifest/
        ├── 2026-04-19-001.json
        └── 2026-04-19-002.json
```

目录语义：

1. `.claude/skills/writing-skill-factory-cli/`：父 skill 常驻目录。
2. `.claude/skills/writer-<child-name>/`：当前 active child，Claude 直接识别这里。
3. `.claude/writing-factory/children/<child-name>/repo/skill/`：该 child 的 canonical source。
4. `.claude/writing-factory/children/<child-name>/repo/state/`：学习状态、baseline、candidate、release、log。
5. `<child-name>_Generated_Articles/`：用户可见、可编辑目录。

---

## 8. 父 skill 规格

### 8.1 职责范围

父 skill 只负责以下六类动作：

1. `create-child`
2. `draft-with-child`
3. `learn-from-visible-edits`
4. `evaluate-candidate`
5. `publish-child`
6. `rollback-child`

父 skill 不负责直接长期承担写作工作。

### 8.2 前端接口

建议对外暴露以下调用形式：

```text
/writing-skill-factory create "<child-name>" "<samples-dir>"
/writing-skill-factory draft "<child-name>" "<topic-or-brief>"
/writing-skill-factory learn "<child-name>"
/writing-skill-factory eval "<child-name>"
/writing-skill-factory publish "<child-name>"
/writing-skill-factory rollback "<child-name>" "<version>"
/writing-skill-factory status "<child-name>"
```

### 8.3 脚本职责

- `create_child.py`：创建 canonical child 仓库与首版 skill 文件。
- `build_style_profile.py`：生成高分辨率风格画像。
- `build_cognitive_profile.py`：生成认知、边界与反模式画像。
- `generate_article.py`：调用 active child 写稿并执行双写。
- `sync_visible_edits.py`：同步可见目录与 baseline 的映射关系。
- `diff_revision.py`：分析 baseline 与用户修改稿差异。
- `promote_rules.py`：把 revision signals 提升为 candidate / probation / active 规则。
- `eval_candidate.py`：执行 old vs candidate 评估并生成报告。
- `publish_child.py`：把 canonical skill 发布为 active child。
- `rollback_child.py`：从 release 恢复并重新发布。

---

## 9. 子 skill 规格

### 9.1 子 skill 的唯一职责

子 skill 只负责：

> 按当前版本的最佳规则写文章。

子 skill 不负责：

1. 自己修改自己。
2. 自己做 git 管理。
3. 自己决定升级。
4. 自己维护历史版本。

### 9.2 子 skill 必须包含的文件

#### `SKILL.md`

只放：

- frontmatter
- 何时触发
- 总写作流程
- 引导 Claude 在何时读取哪些 supporting files
- 参数说明

#### `references/style-profile.md`

必须包含：

- 表层风格
- 结构习惯
- 节奏
- 标点偏好
- 分块习惯
- 段落配方
- 叙述方法
- 内容推进方式

#### `references/editorial-rules.md`

必须包含：

- 选题判断
- 文章原型识别
- 标题方向
- 大纲生成规则
- 证据与案例的取用方式
- 长文推进逻辑

#### `references/author-boundary.md`

必须包含：

- AI 可以做什么
- AI 不能替代什么
- 哪些内容必须由用户提供
- 信息不足时如何追问

#### `references/anti-patterns.md`

必须包含：

- 明确禁区
- 高频 AI 味
- 常见套路句
- 不允许伪造的作者经历
- 不允许使用的空泛收束方式

#### `references/examples.md`

必须包含：

- 3 到 5 段 few-shot 示例
- 正例 / 反例
- 代表性风格证据

#### `assets/style-memory.json`

必须包含长期记忆结构。

最低结构：

```json
{
  "voice_traits": [],
  "punctuation_preferences": [],
  "paragraph_formulas": [],
  "narrative_moves": [],
  "editorial_heuristics": [],
  "author_boundary_rules": [],
  "anti_patterns": [],
  "confidence_buckets": {
    "candidate": [],
    "probation": [],
    "active": []
  }
}
```

#### `assets/quality-rubric.json`

必须包含评估维度与分数定义。

#### `evals/evals.json`

必须包含 create 阶段生成的测试集和回归测试集。

---

## 10. create-child 工作流

### Phase 0：识别 create 场景

触发条件：

- 用户提供 3 到 10 篇样文
- 目标是生成新的 child skill
- 当前不是对已有 child 做学习更新

### Phase 1：澄清

父 skill 至少要确认：

1. child 名称
2. 样文是否属于统一作者 / 统一风格目标
3. 输出是否面向公众号长文
4. 是否允许自动触发
5. 用户想保留哪些固定风格
6. 哪些现象只是当前样本偶然特征
7. 是否存在明确禁区
8. 是否存在必须保留的作者态

### Phase 2：样本文库盘点

必须执行：

1. 建立样本清单
2. 识别文件格式
3. 去重
4. 剔除异常文本
5. 判断样本是否风格混杂
6. 统计字数、篇幅与时间跨度

### Phase 3：双层蒸馏

#### 3.1 风格蒸馏

输出至少包括：

- 14 维分析
- 标点偏好
- 分块习惯
- 段落配方
- 叙述方法
- 内容推进方式
- 风格 DNA
- few-shot 片段

#### 3.2 认知蒸馏

输出至少包括：

- 心智模型
- 决策启发式
- 反模式
- 价值判断倾向
- 诚实边界
- 作者 / AI 边界

### Phase 4：构造 child skill

create-child 必须产出一个 runnable child skill，而不是只产出报告。

最低输出：

- `skill/SKILL.md`
- `skill/references/style-profile.md`
- `skill/references/editorial-rules.md`
- `skill/references/author-boundary.md`
- `skill/references/anti-patterns.md`
- `skill/references/examples.md`
- `skill/assets/style-memory.json`
- `skill/assets/quality-rubric.json`
- `skill/evals/evals.json`

### Phase 5：生成测试 prompts

至少覆盖三类：

1. 素材成稿类
2. 风格迁移类
3. 边界判断类

### Phase 6：首轮评估

至少支持：

- baseline = 无 skill
- candidate = 当前 child skill

评估项至少包括：

- 风格贴合度
- 结构推进
- 活人感
- AI 味减少程度
- 作者边界控制
- 是否胡编第一手经历
- 是否能拦截劣质选题

### Phase 7：用户决策

create 阶段结束前，父 skill 必须输出：

- `style-summary`
- child skill 目录
- eval 输出
- 差异说明
- 推荐下一步：publish 或 revise

### Phase 8：发布

只有用户明确认可后，才允许把 canonical child 发布为 active child：

```text
.claude/skills/writer-<child-name>/
```

---

## 11. draft 工作流

### 11.1 双写要求

每次 active child 产出文章时，必须同时写两份：

1. 内部 baseline
   - 保存到 canonical repo 的 `state/baselines/`
   - 可选同步到 `workspace/shadow-output/`
2. 用户可编辑稿
   - 保存到项目根目录 `<child-name>_Generated_Articles/`

### 11.2 对齐依据

对齐不得只依赖文件名。

必须依赖：

- `article_id`
- `baseline_sha`
- manifest
- 必要时追加 hash + 文首片段兜底

### 11.3 visible 文章元数据

每篇 visible 稿必须带 sidecar manifest 或 frontmatter。

最低字段：

```yaml
article_id: 2026-04-19-001
child_name: writer-example
child_version: v1.2.0
baseline_sha: 8f3a9d...
created_at: 2026-04-19T10:32:11Z
topic: example-topic
status: drafted
```

---

## 12. learn 工作流

### 12.1 用户交互前提

学习更新触发条件：

- 用户已经修改 visible 目录中的文章
- 用户显式表示“改好了”或执行 learn 命令

### 12.2 同步规则

- 用户删除 visible 稿：内部对应稿也删除。
- 用户新增 visible 稿：视为新学习样本。
- 用户重命名 visible 稿：只要 `article_id` 不变，就视为 rename。
- manifest 丢失时：退化到 hash + 文首片段匹配。

### 12.3 revision signals 三层分类

#### L1 Cosmetic

- 错别字
- 顺句
- 局部删改
- 不进入长期记忆

#### L2 Reusable Preference

- 开头更短
- 多口语停顿
- 更少抽象判断
- 删除 AI 套话
- 进入 `candidate` 或 `probation`

#### L3 Structural Rule

- 文章原型改写
- 结构重排
- 标题机制变化
- 选题判断变化
- AI / 人边界变化
- 进入核心规则集

### 12.4 规则升级

- 第一次出现：`candidate_rule`
- 第二次同类出现：`probation_rule`
- 多次复现或用户明确确认：`active_rule`

### 12.5 规则对象最低结构

```json
{
  "rule_id": "opening-shorter-001",
  "rule_type": "reusable_preference",
  "description": "开头第一段偏短，避免解释型铺垫，优先用具体情境切入",
  "evidence_count": 3,
  "confidence": "probation",
  "source_articles": ["2026-04-19-001", "2026-04-20-002"],
  "transferability": "high",
  "boundary_note": "仅适用于调查实验型与现象解读型"
}
```

---

## 13. evaluate / publish / rollback 工作流

### 13.1 candidate 机制

学习更新后不得直接覆盖 active child。

必须执行：

1. 从当前 stable release 派生 candidate
2. 写入新规则
3. 运行评估
4. 生成 report
5. 等待用户决策
6. publish 或 rollback

### 13.2 评估维度

至少分两类：

#### 结构维度

- 文件结构完整性
- rules 分层清晰度
- supporting files 职责明确性
- eval 覆盖度

#### 效果维度

- 风格贴合度
- 活人感
- 长文推进力
- AI 味减少程度
- 作者边界控制
- 选题判断准确性

### 13.3 用户裁决优先

即使自动评估分数更高，也不得自动 publish。

必须由用户确认“更好”后才 publish。

### 13.4 rollback

rollback 必须由 canonical repo 负责：

1. 回到指定 stable release tag
2. 重新 publish 到 active child
3. 保留失败 candidate 的报告，不得静默丢弃

---

## 14. Git 版本模型

每个 child 必须拥有自己的 canonical git 仓库：

```text
.claude/writing-factory/children/<child-name>/repo/
```

必须纳入版本控制的内容：

- `skill/`
- `state/learning-log.jsonl`
- `state/candidates/*`
- `state/releases/*`
- `reports/*.md`

发布规则：

1. canonical repo 是唯一真相源。
2. `.claude/skills/writer-<child-name>/` 只是已发布副本。
3. 禁止直接在 active child 目录上做长期手工修改并把它当成 canonical source。

---

## 15. 验收标准

实现完成后，至少应满足以下验收条件：

1. 能从 3 到 10 篇样文成功生成一个 child skill。
2. child skill 目录结构符合本文档第 7 节。
3. child skill 能被 Claude Code 直接识别并通过 `/writer-<child-name>` 调用。
4. child skill 写稿时能自动双写 baseline 与 visible draft。
5. 用户修改 visible draft 后，父 skill 能完成 learn 流程。
6. learn 流程能生成 candidate、评估报告和版本记录。
7. 用户能明确选择 publish 或 rollback。
8. rollback 后 active child 能恢复到之前稳定版本。
9. child skill 的输出不是单段 prompt，而是完整多文件 skill。
10. child skill 至少具备：
    - 选题判断
    - 文章原型识别
    - AI / 人类边界控制
    - 作者态二改
    - 最终自检

---

## 16. 禁止事项

以下实现方式禁止采用：

1. 只输出风格报告，不生成 runnable child skill。
2. 把所有规则塞进一个超长 `SKILL.md`。
3. 直接把用户一次性的修改当成永久核心规则，不经过 candidate / eval / user decision。
4. 直接覆盖 active child，不保留 candidate 与 release。
5. 只靠文件名对齐 baseline 与 visible draft。
6. 让子 skill 自己改自己。
7. 把 active child 当成 canonical source。
8. 把风格学习退化成高频词或句式模仿。
9. 伪造作者第一手经历、情绪或结论。
10. 在信息不足时强行生成需要第一手事实支撑的内容。

---

## 17. 实现优先级

建议按以下顺序实现：

### P0

- 目录搭建
- create-child 最小闭环
- active child 发布
- draft 双写

### P1

- visible edits 同步
- revision diff
- rule promotion
- candidate 评估

### P2

- release 管理
- rollback
- 更细的评估 rubric
- 更完整的 examples 与 anti-patterns 维护

