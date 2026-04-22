# 版本号与 Release 管理规范

## 版本号格式

采用 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/)：

```
MAJOR.MINOR.PATCH
```

### 升级规则

| 级别 | 触发条件 | 示例 |
|------|---------|------|
| MAJOR | L3 Structural Rule 变化、AI/人边界变化、文章原型机制变化 | 1.x.x → 2.0.0 |
| MINOR | L2 Reusable Preference 累积到一定程度、新增重要 eval 场景 | x.1.x → x.2.0 |
| PATCH | L1 Cosmetic 修正、bug 修复、examples 更新 | x.x.1 → x.x.2 |

## Release Tag 命名

```
v{MAJOR}.{MINOR}.{PATCH}
```

示例：`v1.0.0`, `v1.2.0`, `v2.0.0`

## Release 流程

1. **Candidate 生成**：从当前 stable release 派生 candidate
2. **评估通过**：用户确认 publish
3. **版本号确定**：根据变更内容确定新版本号
4. **打 Tag**：在 canonical repo 上打 `v{version}` tag
5. **更新索引**：追加 `state/release-index.json`
6. **发布副本**：同步到 `.claude/skills/writer-<child-name>/`
7. **生成日志**：更新 `reports/change-log.md`

## Release Index 结构

```json
{
  "releases": [
    {
      "version": "1.0.0",
      "tag": "v1.0.0",
      "date": "2026-04-19T10:32:11Z",
      "type": "create",
      "change_summary": "初始版本，基于 5 篇样文生成",
      "eval_score": null
    },
    {
      "version": "1.1.0",
      "tag": "v1.1.0",
      "date": "2026-04-21T14:20:00Z",
      "type": "learn",
      "change_summary": "用户偏好：开头更短，减少抽象判断",
      "eval_score": 4.2,
      "parent_version": "1.0.0"
    }
  ],
  "active_version": "1.1.0"
}
```

## Rollback 规则

1. 用户指定要回退到的版本号
2. 从 canonical repo 检出对应 tag
3. 重新 publish 到 active child
4. **保留被回滚版本的历史记录**，不得删除
5. 在 `learning-log.jsonl` 中记录 rollback 事件

## 变更日志规范

`reports/change-log.md` 格式：

```markdown
## v1.1.0 (2026-04-21)

### 变更类型
learn (L2 Preference 升级)

### 变更摘要
- 规则 `opening-shorter-001` 从 probation 升级为 active
- 新增规则 `less-abstract-judgment-002` (probation)
- 更新 `examples.md`：新增 2 段用户修改稿正例

### 评估结果
- 总分：4.2 / 5.0（vs v1.0.0 的 3.8）
- 风格贴合度：4.5 (+0.3)
- AI 味减少：4.0 (+0.5)

### 决策
用户于 2026-04-21 确认 publish
```
