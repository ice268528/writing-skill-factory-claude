# writer-{{child_name}} 使用指南

## 快速开始

```text
/writer-{{child_name}} "文章主题或 brief"
```

## 可用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `topic` | 文章主题（必填） | `"为什么年轻人不爱换手机了"` |
| `article_type` | 指定文章原型 | `"现象解读"` |
| `word_count` | 目标字数 | `3000` |
| `evidence_files` | 素材文件路径 | `["data/report.pdf", "notes.md"]` |

## 文章原型

{{article_prototypes}}

## 常见用法

### 根据话题生成

```text
/writer-{{child_name}} "分析当前 AI 写作工具对内容行业的影响"
```

### 根据素材生成

```text
/writer-{{child_name}} topic="复盘这次产品上线" evidence_files=["launch-notes.md"]
```

### 指定类型与字数

```text
/writer-{{child_name}} topic="..." article_type="调查实验" word_count=5000
```

## 修改与反馈

1. 文章生成后，在 `{{child_name}}_Generated_Articles/` 中修改
2. 修改完成后，运行：
   ```text
   /writing-skill-factory learn "{{child_name}}"
   ```
3. 系统会分析你的修改，生成 candidate 版本供评估

## 边界说明

{{boundary_notes}}
