# 学习更新与规则升级策略

## 触发条件

学习更新仅在以下条件下触发：

1. 用户已经修改 visible 目录中的文章
2. 用户显式表示"改好了"或执行 `learn` 命令

## 同步规则

| 用户操作 | 系统行为 |
|---------|---------|
| 删除 visible 稿 | 内部对应 baseline 也删除 |
| 新增 visible 稿 | 视为新学习样本（需关联 baseline） |
| 重命名 visible 稿 | 只要 `article_id` 不变，视为 rename |
| manifest 丢失 | 退化到 hash + 文首片段匹配 |

## Revision Signals 三层分类

### L1 Cosmetic（表层修饰）

- 错别字修正
- 语句通顺调整
- 局部删改
- **不进入长期记忆**

### L2 Reusable Preference（可复用偏好）

- 开头更短
- 多口语停顿
- 更少抽象判断
- 删除 AI 套话
- **进入 `candidate` 或 `probation`**

### L3 Structural Rule（结构性规则）

- 文章原型改写
- 结构重排
- 标题机制变化
- 选题判断变化
- AI / 人边界变化
- **进入核心规则集**

## 规则升级路径

```
第一次出现        第二次同类出现      多次复现或用户确认
     |                  |                  |
     v                  v                  v
candidate_rule  →  probation_rule  →  active_rule
```

## 规则对象最低结构

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

### 字段说明

| 字段 | 说明 |
|------|------|
| `rule_id` | 全局唯一标识，格式：`{type}-{brief}-{seq}` |
| `rule_type` | `cosmetic` / `reusable_preference` / `structural_rule` |
| `description` | 规则的自然语言描述 |
| `evidence_count` | 支持该规则的证据次数 |
| `confidence` | `candidate` / `probation` / `active` |
| `source_articles` | 证据来源的文章 ID 列表 |
| `transferability` | `high` / `medium` / `low` / `context_dependent` |
| `boundary_note` | 适用边界与例外情况 |

## 降级与淘汰

- **candidate** 规则若连续 3 次评估未复现，可降级为 `deprecated`
- **probation** 规则若与用户显式反馈冲突，降级为 `candidate` 或 `deprecated`
- **active** 规则原则上不主动降级，除非用户明确要求
- `deprecated` 规则保留在 `learning-log.jsonl` 中，但不再影响生成
