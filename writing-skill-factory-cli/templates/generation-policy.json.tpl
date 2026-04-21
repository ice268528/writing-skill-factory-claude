{
  "version": "1.0",
  "child_name": "{{child_name}}",
  "policies": {
    "output_format": "markdown",
    "frontmatter_required": true,
    "frontmatter_fields": [
      "article_id",
      "child_name",
      "child_version",
      "baseline_sha",
      "created_at",
      "topic",
      "status"
    ],
    "dual_write": {
      "enabled": true,
      "baseline_path": "state/baselines/",
      "visible_path": "{{child_name}}_Generated_Articles/",
      "manifest_path": ".manifest/"
    },
    "quality_check": {
      "enabled": true,
      "checkpoints": [
        "选题判断",
        "原型识别",
        "大纲生成",
        "首稿生成",
        "作者态二改",
        "最终自检"
      ]
    },
    "boundary_enforcement": {
      "enabled": true,
      "rules": [
        "禁止伪造第一手经历",
        "禁止在信息不足时编造事实",
        "必须明确标注假设与推断",
        "必须追问而非猜测关键信息"
      ]
    },
    "style_enforcement": {
      "enabled": true,
      "sources": [
        "references/style-profile.md",
        "assets/style-memory.json"
      ]
    }
  },
  "limits": {
    "max_word_count": 8000,
    "min_word_count": 500,
    "default_word_count": 3000
  }
}
