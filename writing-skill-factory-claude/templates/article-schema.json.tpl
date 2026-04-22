{
  "version": "1.0",
  "prototypes": [
    {
      "id": "phenomenon_analysis",
      "name": "现象解读",
      "description": "从具体现象切入，追溯原因与影响",
      "structure": [
        {"phase": "opening", "type": "情境或现象引入", "length_hint": "1-2段"},
        {"phase": "background", "type": "背景补充", "length_hint": "1段"},
        {"phase": "analysis", "type": "逐层分析原因", "length_hint": "3-5段"},
        {"phase": "implication", "type": "影响或趋势", "length_hint": "1-2段"},
        {"phase": "closing", "type": "开放判断或回扣", "length_hint": "1段"}
      ],
      "typical_length": "2000-4000字",
      "key_features": ["有具体切入点", "避免纯概念推演", "案例分析支撑"]
    },
    {
      "id": "investigation",
      "name": "调查实验",
      "description": "呈现过程与发现，逐步推导结论",
      "structure": [
        {"phase": "opening", "type": "问题或假设", "length_hint": "1段"},
        {"phase": "method", "type": "方法/过程", "length_hint": "1-2段"},
        {"phase": "findings", "type": "发现与数据", "length_hint": "2-4段"},
        {"phase": "analysis", "type": "分析与推导", "length_hint": "2-3段"},
        {"phase": "closing", "type": "结论与局限", "length_hint": "1段"}
      ],
      "typical_length": "3000-6000字",
      "key_features": ["过程可追溯", "数据真实", "推导严谨"]
    },
    {
      "id": "opinion_argument",
      "name": "观点论证",
      "description": "核心观点前置，分层支撑论证",
      "structure": [
        {"phase": "opening", "type": "核心观点", "length_hint": "1段"},
        {"phase": "argument_1", "type": "第一层论证", "length_hint": "1-2段"},
        {"phase": "argument_2", "type": "第二层论证", "length_hint": "1-2段"},
        {"phase": "counter", "type": "回应反对意见", "length_hint": "1段"},
        {"phase": "closing", "type": "强化观点或开放", "length_hint": "1段"}
      ],
      "typical_length": "2000-4000字",
      "key_features": ["观点明确", "论证分层", "回应反对"]
    },
    {
      "id": "experience_narrative",
      "name": "经验叙事",
      "description": "个人经历为主线，提炼普世性",
      "structure": [
        {"phase": "opening", "type": "情境引入", "length_hint": "1段"},
        {"phase": "experience", "type": "经历展开", "length_hint": "3-5段"},
        {"phase": "reflection", "type": "反思与提炼", "length_hint": "2-3段"},
        {"phase": "universal", "type": "普世性连接", "length_hint": "1段"},
        {"phase": "closing", "type": "开放收束", "length_hint": "1段"}
      ],
      "typical_length": "2000-4000字",
      "key_features": ["经历真实", "细节具体", "提炼有深度"]
    }
  ],
  "default": "phenomenon_analysis"
}
