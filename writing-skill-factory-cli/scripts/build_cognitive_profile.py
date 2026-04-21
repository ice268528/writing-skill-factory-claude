#!/usr/bin/env python3
"""
build_cognitive_profile.py
认知、边界与反模式画像生成。

用法:
    python build_cognitive_profile.py <child_name> <samples_dir> [--factory-dir <dir>]
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


def read_samples(samples_dir: str) -> List[Tuple[str, str]]:
    path = Path(samples_dir)
    files = []
    for ext in ("*.md", "*.txt"):
        files.extend(path.glob(ext))
    results = []
    for f in sorted(files):
        content = f.read_text(encoding="utf-8")
        content = re.sub(r'[#*`\[\]!]', '', content)
        results.append((f.name, content))
    return results


def extract_structural_patterns(texts: List[str]) -> Dict:
    """提取结构模式：文章如何分段、推进"""
    patterns = {
        "段落数分布": [],
        "开头模式": Counter(),
        "结尾模式": Counter(),
    }
    for text in texts:
        paras = [p.strip() for p in text.split('\n\n') if p.strip()]
        patterns["段落数分布"].append(len(paras))
        if paras:
            first = paras[0]
            if any(w in first for w in ["为什么", "怎么", "什么", "吗", "呢"]):
                patterns["开头模式"]["提问切入"] += 1
            elif any(w in first for w in ["最近", "那天", "有一次", "记得"]):
                patterns["开头模式"]["情境切入"] += 1
            elif any(w in first for w in ["数据", "报告", "显示", "统计"]):
                patterns["开头模式"]["数据切入"] += 1
            else:
                patterns["开头模式"]["观点切入"] += 1

            last = paras[-1]
            if any(w in last for w in ["总之", "总结", "归根结底", "说到底"]):
                patterns["结尾模式"]["收束总结"] += 1
            elif any(w in last for w in ["你", "我们", "不妨", "试试"]):
                patterns["结尾模式"]["行动号召"] += 1
            elif any(w in last for w in ["？", "?"]):
                patterns["结尾模式"]["反问"] += 1
            else:
                patterns["结尾模式"]["开放式"] += 1
    return patterns


def infer_mindset(texts: List[str]) -> List[Dict]:
    """推断心智模型"""
    all_text = "\n".join(texts)
    heuristics = []

    # 简单启发式推断
    if "我觉得" in all_text or "我认为" in all_text or "在我看来" in all_text:
        heuristics.append({
            "type": "mindset",
            "description": "倾向于明确表达个人观点或立场",
            "evidence_count": len(texts),
            "confidence": "active",
            "transferability": "high",
            "boundary_note": "适用于评论型、观点型文章"
        })

    if "但是" in all_text or "然而" in all_text or "不过" in all_text:
        heuristics.append({
            "type": "mindset",
            "description": "习惯在论述中呈现对立面或转折",
            "evidence_count": len(texts),
            "confidence": "active",
            "transferability": "high",
            "boundary_note": "适用于分析型、思辨型文章"
        })

    if "比如" in all_text or "例如" in all_text or "像" in all_text:
        heuristics.append({
            "type": "heuristic",
            "description": "善用具体案例支撑抽象观点",
            "evidence_count": len(texts),
            "confidence": "active",
            "transferability": "high",
            "boundary_note": "通用"
        })

    if "?>" in all_text or "不一定" in all_text or "可能" in all_text or "也许" in all_text:
        heuristics.append({
            "type": "mindset",
            "description": "表达中保留不确定性，避免绝对化判断",
            "evidence_count": len(texts),
            "confidence": "active",
            "transferability": "medium",
            "boundary_note": "适用于探讨型、非结论性主题"
        })

    return heuristics


def infer_anti_patterns(texts: List[str]) -> List[Dict]:
    """推断反模式（AI 容易犯的、作者不会犯的错误）"""
    anti_patterns = []

    # 常见 AI 套路句检测（在样文中不应出现，若出现则说明不是禁区，否则设为禁区）
    ai_cliches = [
        "在当今社会",
        "随着科技的发展",
        "这是一个值得深思的问题",
        "不仅如此",
        "总而言之",
        "综上所述",
    ]

    all_text = "\n".join(texts)
    for cliche in ai_cliches:
        if cliche not in all_text:
            anti_patterns.append({
                "type": "anti_pattern",
                "description": f"避免使用'{cliche}'等套路化表达",
                "evidence_count": 0,  # 未出现即为禁区
                "confidence": "active",
                "transferability": "high",
                "boundary_note": "通用禁区"
            })

    # 伪造经历
    anti_patterns.append({
        "type": "anti_pattern",
        "description": "禁止伪造作者的第一手经历、情绪或结论",
        "evidence_count": 0,
        "confidence": "active",
        "transferability": "high",
        "boundary_note": "绝对禁区"
    })

    # 空泛收束
    anti_patterns.append({
        "type": "anti_pattern",
        "description": "避免使用空泛的总结式收束，如'让我们一起...'、'相信未来...'",
        "evidence_count": 0,
        "confidence": "active",
        "transferability": "high",
        "boundary_note": "通用禁区"
    })

    return anti_patterns


def infer_boundary(texts: List[str]) -> Dict:
    """推断 AI / 人边界"""
    all_text = "\n".join(texts)

    # 检测是否有个人经历
    has_personal_exp = any(w in all_text for w in ["我", "我的", "我曾经", "我记得"])

    boundary = {
        "ai_can": [
            "根据素材组织文章结构",
            "模仿作者的表层风格（句长、节奏、标点）",
            "提供选题判断与大纲建议",
            "进行语言润色与节奏调整",
            "识别并删除 AI 套路句",
        ],
        "ai_cannot": [
            "替代作者做出价值判断",
            "声称拥有作者的第一手经历",
            "在信息不足时编造事实",
            "替作者决定\"什么值得写\"（只能建议，最终由人裁决）",
        ],
        "human_must_provide": [
            "核心观点或立场",
            "第一手经历与感受（如文章需要）",
            "关键事实与数据来源",
            "选题的最终确认",
        ],
        "when_unclear": "明确告知用户信息不足，列出需要补充的材料，而不是强行生成。"
    }

    if has_personal_exp:
        boundary["ai_cannot"].append("虚构作者的个人经历或情感体验")
        boundary["human_must_provide"].append("真实的个人经历或情感素材")

    return boundary


def build_cognitive_profile(child_name: str, samples_dir: str, factory_dir: str) -> None:
    samples = read_samples(samples_dir)
    if not samples:
        print(f"[build_cognitive_profile] No samples found in {samples_dir}")
        sys.exit(1)

    texts = [t for _, t in samples]

    structural = extract_structural_patterns(texts)
    heuristics = infer_mindset(texts)
    anti_patterns = infer_anti_patterns(texts)
    boundary = infer_boundary(texts)

    repo_dir = Path(factory_dir) / child_name / "repo"
    skill_dir = repo_dir / "skill"

    # 生成 editorial-rules.md
    editorial_path = skill_dir / "references" / "editorial-rules.md"
    editorial_lines = [
        f"# {child_name} 编辑规则",
        "",
        "## 选题判断",
        "",
        "- 优先选择有具体情境或案例支撑的主题",
        "- 避免纯概念推演、缺乏实证的观点",
        "- 若用户选题过于空泛，建议缩小范围或提供素材",
        "",
        "## 文章原型识别",
        "",
        "根据开头与结构模式，识别文章原型：",
        "",
        "| 原型 | 特征 | 适用场景 |",
        "|------|------|---------|",
        "| 现象解读 | 从具体现象切入，追溯原因 | 社会热点、行业观察 |",
        "| 调查实验 | 呈现过程与发现，逐步推导 | 方法论、产品复盘 |",
        "| 观点论证 | 核心观点前置，分层支撑 | 评论、立场表达 |",
        "| 经验叙事 | 个人经历为主线，提炼普世性 | 成长、职场、创作 |",
        "",
        "## 标题方向",
        "",
        "- 避免标题党与过度承诺",
        "- 优先具体信息而非抽象概括",
        "- 可适当使用问号或对比结构",
        "",
        "## 大纲生成规则",
        "",
        "- 每段必须有核心论点",
        "- 论点之后必须有支撑（案例、数据、引用、对比）",
        "- 段与段之间有过渡，避免跳跃",
        "",
        "## 证据与案例取用",
        "",
        "- 优先使用用户提供的素材",
        "- 若需补充案例，明确标注来源或说明是\"常见现象\"",
        "- 禁止编造数据或引用",
        "",
        "## 长文推进逻辑",
        "",
        "- 开头：建立情境或提出问题，避免直接给结论",
        "- 中段：逐层展开，每推进一层增加信息密度",
        "- 结尾：回扣开头或留下开放判断，避免空泛总结",
    ]
    editorial_path.write_text("\n".join(editorial_lines), encoding="utf-8")

    # 生成 author-boundary.md
    boundary_path = skill_dir / "references" / "author-boundary.md"
    boundary_lines = [
        f"# {child_name} 作者边界",
        "",
        "## AI 可以做什么",
        "",
    ]
    for item in boundary["ai_can"]:
        boundary_lines.append(f"- {item}")
    boundary_lines.extend([
        "",
        "## AI 不能替代什么",
        "",
    ])
    for item in boundary["ai_cannot"]:
        boundary_lines.append(f"- {item}")
    boundary_lines.extend([
        "",
        "## 哪些内容必须由用户提供",
        "",
    ])
    for item in boundary["human_must_provide"]:
        boundary_lines.append(f"- {item}")
    boundary_lines.extend([
        "",
        "## 信息不足时如何追问",
        "",
        boundary["when_unclear"],
    ])
    boundary_path.write_text("\n".join(boundary_lines), encoding="utf-8")

    # 生成 anti-patterns.md
    anti_path = skill_dir / "references" / "anti-patterns.md"
    anti_lines = [
        f"# {child_name} 禁区与反模式",
        "",
        "## 明确禁区",
        "",
    ]
    for p in anti_patterns:
        anti_lines.append(f"### {p['description']}")
        anti_lines.append(f"- 置信度：{p['confidence']}")
        anti_lines.append(f"- 迁移性：{p['transferability']}")
        anti_lines.append(f"- 边界：{p['boundary_note']}")
        anti_lines.append("")
    anti_lines.extend([
        "## 高频 AI 味",
        "",
        "以下表达在样文中未出现，视为 AI 套路，需避免：",
        "",
    ])
    ai_cliches = [
        "在当今社会",
        "随着科技的发展",
        "这是一个值得深思的问题",
        "不仅如此",
        "总而言之",
        "综上所述",
        "让我们一起",
        "相信未来",
        "毫无疑问",
        "不可否认的是",
    ]
    for cliche in ai_cliches:
        anti_lines.append(f"- {cliche}")
    anti_lines.extend([
        "",
        "## 常见套路句",
        "",
        "- \"...的背后，是...\"（过度归因）",
        "- \"这不得不让人思考...\"（强行升华）",
        "- \"从某种程度上说...\"（模糊表态）",
        "- \"无论是A还是B...\"（虚假全面）",
        "",
        "## 不允许伪造的作者经历",
        "",
        "- 禁止声称\"我曾经...\"、\"我记得...\"等第一人称经历",
        "- 禁止表达\"我感到...\"、\"我愤怒...\"等第一人称情绪",
        "- 若文章需要个人视角，使用\"假设\"、\"如果是我\"等明确虚构标记",
        "",
        "## 不允许使用的空泛收束方式",
        "",
        "- \"让我们一起期待...\"",
        "- \"未来可期...\"",
        "- \"这，就是...\"（伪金句）",
        "- 以口号或号召代替判断",
    ])
    anti_path.write_text("\n".join(anti_lines), encoding="utf-8")

    # 更新 style-memory.json 中的规则
    memory_path = skill_dir / "assets" / "style-memory.json"
    if memory_path.exists():
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
    else:
        memory = {
            "voice_traits": [],
            "punctuation_preferences": [],
            "paragraph_formulas": [],
            "narrative_moves": [],
            "editorial_heuristics": [],
            "author_boundary_rules": [],
            "anti_patterns": [],
            "confidence_buckets": {"candidate": [], "probation": [], "active": []}
        }

    memory["editorial_heuristics"] = heuristics
    memory["author_boundary_rules"] = [
        {"rule": item, "confidence": "active"} for item in boundary["ai_can"]
    ] + [
        {"rule": item, "confidence": "active", "type": "prohibition"} for item in boundary["ai_cannot"]
    ]
    memory["anti_patterns"] = anti_patterns
    memory["confidence_buckets"]["active"] = heuristics + anti_patterns

    memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[build_cognitive_profile] Editorial rules saved to {editorial_path}")
    print(f"[build_cognitive_profile] Author boundary saved to {boundary_path}")
    print(f"[build_cognitive_profile] Anti-patterns saved to {anti_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build cognitive profile for a writer child")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("samples_dir", help="Directory containing sample articles")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()
    build_cognitive_profile(args.child_name, args.samples_dir, args.factory_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
