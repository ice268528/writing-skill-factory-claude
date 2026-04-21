#!/usr/bin/env python3
"""
build_style_profile.py
高分辨率风格画像生成。

用法:
    python build_style_profile.py <child_name> <samples_dir> [--factory-dir <dir>]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# 14 维分析框架键名
DIMENSIONS = [
    "sentence_length", "paragraph_length", "paragraph_structure",
    "connector_density", "rhetoric_preference", "person_usage",
    "tense_narrative", "information_density", "emotional_intensity",
    "terminology_density", "citation_style", "opening_style",
    "ending_style", "rhythm_breathing"
]


def read_samples(samples_dir: str) -> List[Tuple[str, str]]:
    """读取样文，返回 (filename, content) 列表"""
    path = Path(samples_dir)
    files = []
    for ext in ("*.md", "*.txt"):
        files.extend(path.glob(ext))
    results = []
    for f in sorted(files):
        content = f.read_text(encoding="utf-8")
        # 简单清洗：移除 markdown 标记
        content = re.sub(r'[#*`\[\]!]', '', content)
        results.append((f.name, content))
    return results


def analyze_sentence_length(text: str) -> Dict:
    sentences = re.split(r'[。！？\n]', text)
    lengths = [len(s.strip()) for s in sentences if s.strip()]
    if not lengths:
        return {"avg": 0, "distribution": {}}
    avg = sum(lengths) / len(lengths)
    # 分桶
    buckets = {"short": 0, "medium": 0, "long": 0}
    for l in lengths:
        if l < 15:
            buckets["short"] += 1
        elif l < 35:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total = len(lengths)
    distribution = {k: round(v / total, 2) for k, v in buckets.items()}
    dominant = max(distribution, key=distribution.get)
    return {"avg": round(avg, 1), "distribution": distribution, "dominant": dominant}


def analyze_paragraph_length(text: str) -> Dict:
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    lengths = [len(p) for p in paragraphs]
    if not lengths:
        return {"avg": 0, "distribution": {}}
    avg = sum(lengths) / len(lengths)
    buckets = {"short": 0, "medium": 0, "long": 0}
    for l in lengths:
        if l < 80:
            buckets["short"] += 1
        elif l < 200:
            buckets["medium"] += 1
        else:
            buckets["long"] += 1
    total = len(lengths)
    distribution = {k: round(v / total, 2) for k, v in buckets.items()}
    dominant = max(distribution, key=distribution.get)
    return {"avg": round(avg, 1), "distribution": distribution, "dominant": dominant}


def analyze_punctuation(text: str) -> Dict:
    total_chars = len(text)
    if total_chars == 0:
        return {}
    marks = {
        "comma": text.count('，'),
        "period": text.count('。'),
        "semicolon": text.count('；'),
        "dash": text.count('——') + text.count('－'),
        "parentheses": text.count('（') + text.count('('),
        "quotes": text.count('"') + text.count('"') + text.count("'") + text.count("'") + text.count('「') + text.count('」'),
        "ellipsis": text.count('……') + text.count('...'),
        "exclamation": text.count('！') + text.count('!'),
        "question": text.count('？') + text.count('?'),
    }
    density = {k: round(v / total_chars * 1000, 2) for k, v in marks.items()}
    return {"counts": marks, "density_per_1k": density}


def analyze_connectors(text: str) -> Dict:
    connector_words = [
        "但是", "然而", "不过", "可是", "而", "却",
        "因为", "所以", "因此", "于是", "从而",
        "首先", "其次", "然后", "接着", "最后",
        "不仅", "而且", "并且", "同时", "另外",
        "如果", "即使", "虽然", "尽管", "无论",
        "总之", "总而言之", "换句话说", "也就是说", "换言之",
        "例如", "比如", "像", "正如"
    ]
    counts = Counter()
    for word in connector_words:
        counts[word] = len(re.findall(re.escape(word), text))
    total = sum(counts.values())
    total_chars = len(text)
    density = round(total / total_chars * 1000, 2) if total_chars else 0
    top = counts.most_common(10)
    return {"total": total, "density_per_1k": density, "top": top}


def analyze_opening_ending(samples: List[Tuple[str, str]]) -> Dict:
    openings = []
    endings = []
    for _, text in samples:
        paras = [p.strip() for p in text.split('\n\n') if p.strip()]
        if paras:
            openings.append(paras[0][:50])
            endings.append(paras[-1][-50:])
    return {"openings": openings, "endings": endings}


def extract_few_shots(samples: List[Tuple[str, str]], max_per_sample: int = 2, max_chars: int = 200) -> List[str]:
    """提取 few-shot 片段"""
    shots = []
    for _, text in samples:
        paras = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 50]
        for para in paras[:max_per_sample]:
            shot = para[:max_chars]
            if len(shot) >= 30:
                shots.append(shot)
    return shots[:5]


def build_style_profile(child_name: str, samples_dir: str, factory_dir: str) -> None:
    samples = read_samples(samples_dir)
    if not samples:
        print(f"[build_style_profile] No samples found in {samples_dir}")
        sys.exit(1)

    all_text = "\n\n".join([t for _, t in samples])

    # 分析
    sentence_analysis = analyze_sentence_length(all_text)
    paragraph_analysis = analyze_paragraph_length(all_text)
    punctuation_analysis = analyze_punctuation(all_text)
    connector_analysis = analyze_connectors(all_text)
    oe_analysis = analyze_opening_ending(samples)
    few_shots = extract_few_shots(samples)

    # 生成风格 DNA 描述
    style_dna = (
        f"该作者偏好{sentence_analysis.get('dominant', '中等')}句长，"
        f"{paragraph_analysis.get('dominant', '中等')}段落，"
        f"连接词密度为每千字 {connector_analysis['density_per_1k']} 个。"
        f"标点使用中，逗号密度 {punctuation_analysis['density_per_1k'].get('comma', 0)}，"
        f"句号密度 {punctuation_analysis['density_per_1k'].get('period', 0)}。"
    )

    # 构建 style-memory.json
    style_memory = {
        "voice_traits": [
            {"trait": "句长偏好", "value": sentence_analysis.get("dominant", "unknown"), "confidence": "active"},
            {"trait": "段长偏好", "value": paragraph_analysis.get("dominant", "unknown"), "confidence": "active"},
        ],
        "punctuation_preferences": [
            {"mark": k, "density_per_1k": v, "confidence": "active"}
            for k, v in punctuation_analysis.get("density_per_1k", {}).items()
        ],
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

    # 写入 canonical repo
    repo_dir = Path(factory_dir) / child_name / "repo"
    skill_dir = repo_dir / "skill"
    state_dir = repo_dir / "state"

    # 更新 style-profile.md
    style_profile_path = skill_dir / "references" / "style-profile.md"
    lines = [
        f"# {child_name} 风格画像",
        "",
        f"> 基于 {len(samples)} 篇样文",
        f"> 生成时间：{datetime.now(timezone.utc).isoformat()}",
        "",
        "## 核心风格 DNA",
        "",
        style_dna,
        "",
        "## 14 维量化底盘",
        "",
        "### D01 句子长度偏好",
        f"- 平均句长：{sentence_analysis['avg']} 字",
        f"- 分布：{sentence_analysis.get('distribution', {})}",
        "",
        "### D02 段落长度偏好",
        f"- 平均段长：{paragraph_analysis['avg']} 字",
        f"- 分布：{paragraph_analysis.get('distribution', {})}",
        "",
        "### D04 连接词使用密度",
        f"- 每千字连接词数：{connector_analysis['density_per_1k']}",
        f"- 高频连接词：{connector_analysis['top'][:5]}",
        "",
        "## 标点偏好",
        "",
        "| 标点 | 每千字密度 |",
        "|------|-----------|",
    ]
    for k, v in punctuation_analysis.get("density_per_1k", {}).items():
        lines.append(f"| {k} | {v} |")
    lines.extend([
        "",
        "## 风格证据（few-shot）",
        "",
    ])
    for i, shot in enumerate(few_shots, 1):
        lines.append(f"### 片段 {i}")
        lines.append(f"> {shot}")
        lines.append("")

    style_profile_path.write_text("\n".join(lines), encoding="utf-8")

    # 写入 style-memory.json
    memory_path = skill_dir / "assets" / "style-memory.json"
    memory_path.write_text(json.dumps(style_memory, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保存原始分析到 profiles
    profile_path = state_dir / "profiles" / f"style-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    profile_data = {
        "child_name": child_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(samples),
        "sentence_analysis": sentence_analysis,
        "paragraph_analysis": paragraph_analysis,
        "punctuation_analysis": punctuation_analysis,
        "connector_analysis": connector_analysis,
        "few_shots": few_shots,
    }
    profile_path.write_text(json.dumps(profile_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[build_style_profile] Style profile saved to {style_profile_path}")
    print(f"[build_style_profile] Style memory saved to {memory_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build style profile for a writer child")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("samples_dir", help="Directory containing sample articles")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()
    build_style_profile(args.child_name, args.samples_dir, args.factory_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
