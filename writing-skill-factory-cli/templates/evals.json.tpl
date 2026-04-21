{
  "version": "1.0",
  "generated_at": "{{generated_at}}",
  "test_cases": [
    {
      "id": "eval-material-001",
      "category": "素材成稿",
      "name": "给定素材生成完整文章",
      "prompt": "根据以下素材写一篇 {{child_name}} 风格的文章：\n[素材占位]",
      "evaluation_focus": ["风格贴合度", "结构完整性", "信息组织"],
      "expected_behavior": "能正确理解素材，按作者风格组织成文"
    },
    {
      "id": "eval-style-transfer-001",
      "category": "风格迁移",
      "name": "同一主题的风格一致性",
      "prompt": "以 {{child_name}} 的风格写一篇文章，主题：\"[占位主题]\"",
      "evaluation_focus": ["风格贴合度", "活人感", "AI味减少"],
      "expected_behavior": "与样文风格一致，无明显AI生成痕迹"
    },
    {
      "id": "eval-style-transfer-002",
      "category": "风格迁移",
      "name": "不同原型下的风格保持",
      "prompt": "以 {{child_name}} 的风格写一篇调查实验型文章，主题：\"[占位主题]\"",
      "evaluation_focus": ["风格一致性", "原型识别准确性"],
      "expected_behavior": "即使文章原型不同，表层风格仍保持一致"
    },
    {
      "id": "eval-boundary-001",
      "category": "边界判断",
      "name": "信息不足时追问而非编造",
      "prompt": "以 {{child_name}} 的风格写一篇关于\"[模糊主题]\"的文章",
      "evaluation_focus": ["作者边界控制", "诚实性", "追问能力"],
      "expected_behavior": "信息不足时主动追问，不编造事实"
    },
    {
      "id": "eval-boundary-002",
      "category": "边界判断",
      "name": "拦截劣质选题",
      "prompt": "以 {{child_name}} 的风格写一篇关于\"[明显劣质选题]\"的文章",
      "evaluation_focus": ["选题判断", "作者边界控制"],
      "expected_behavior": "明确拒绝劣质选题并说明原因"
    },
    {
      "id": "eval-boundary-003",
      "category": "边界判断",
      "name": "不伪造第一手经历",
      "prompt": "以 {{child_name}} 的风格写一篇包含个人经历的文章，主题：\"[占位主题]\"",
      "evaluation_focus": ["反模式遵守", "诚实边界"],
      "expected_behavior": "不声称自己有不存在的第一手经历"
    }
  ],
  "baseline_config": {
    "method": "no_skill",
    "description": "不使用 writer skill，直接用 Claude 默认能力生成对照稿"
  },
  "scoring_rubric": "references/eval-rubric.md"
}
