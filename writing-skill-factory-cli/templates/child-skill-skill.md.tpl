---
name: writer-{{child_name}}
description: >
  {{child_name}} 的个人写作系统。根据当前最佳规则生成文章，
  自动双写 baseline 与 visible draft，不自我修改。
---

# writer-{{child_name}}

> {{child_name}} 的写作系统，基于 {{sample_count}} 篇样文蒸馏而成。
> 当前版本：{{version}}

## 何时触发

用户要求以 {{child_name}} 的风格写作、生成文章、或处理与 {{child_name}} 写作相关的内容时。

## 写作流程

### Phase 1: 素材 Intake

1. 读取用户提供的 topic / brief / 素材
2. 检查信息充足性
3. 信息不足时，按 `references/author-boundary.md` 追问

### Phase 2: 选题诊断

1. 判断选题是否值得写
2. 识别文章原型（见 `references/editorial-rules.md`）
3. 若选题劣质，明确拒绝并说明原因

### Phase 3: 大纲生成

1. 根据文章原型选择结构模板
2. 生成证据化大纲（每段有核心论点 + 支撑材料）
3. 标题方向建议

### Phase 4: 首稿生成

1. 按 `references/style-profile.md` 控制表层风格
2. 按 `references/editorial-rules.md` 控制内容逻辑
3. 避免 `references/anti-patterns.md` 中的禁区
4. 遵守 `references/author-boundary.md` 中的 AI/人边界

### Phase 5: 作者态二改

1. 以作者视角审视全文
2. 检查节奏、呼吸感、信息密度
3. 优化过渡与收束

### Phase 6: 最终自检

1. 是否有 AI 套路句？
2. 是否伪造了作者经历？
3. 信息密度是否均匀？
4. 开头与结尾是否到位？

## 双写要求

每篇文章生成后，必须同时输出：

1. **内部 baseline**（通过父 skill 写入 `state/baselines/`）
2. **用户可编辑稿**（通过父 skill 写入 `{{child_name}}_Generated_Articles/`）

## Supporting Files 导航

| 文件 | 用途 |
|------|------|
| `references/style-profile.md` | 表层风格、节奏、标点、段落配方 |
| `references/editorial-rules.md` | 选题、原型、大纲、证据、推进逻辑 |
| `references/author-boundary.md` | AI 能做什么、人必须给什么 |
| `references/anti-patterns.md` | 禁区、AI 味、套路句 |
| `references/examples.md` | few-shot 正例与反例 |
| `assets/style-memory.json` | 长期记忆与规则置信度 |
| `assets/quality-rubric.json` | 质量评估维度 |
| `assets/article-schema.json` | 文章结构模板 |
| `assets/generation-policy.json` | 生成策略与参数 |

## 参数

- `topic`: 文章主题或 brief
- `article_type`: 文章原型（可选，默认自动识别）
- `word_count`: 目标字数（可选）
- `evidence_files`: 素材文件路径列表（可选）
