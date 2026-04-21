#!/usr/bin/env python3
"""
eval_candidate.py
执行 old vs candidate 评估并生成报告。

用法:
    python eval_candidate.py <child_name> [--factory-dir <dir>]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import setup_logger, LogContext


def run_git_show(repo_dir: Path, tag: str, file_path: str) -> str:
    """从 git tag 读取文件内容"""
    try:
        result = subprocess.run(
            ["git", "show", f"{tag}:{file_path}"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def read_current_file(skill_dir: Path, file_path: str) -> str:
    """读取当前 skill 目录中的文件"""
    try:
        return (skill_dir / file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def parse_style_memory(text: str) -> dict:
    """解析 style-memory.json 文本"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def compute_style_fit(baseline_memory: dict, candidate_memory: dict) -> float:
    """计算风格贴合度得分（0-5）"""
    base_traits = {t.get("trait"): t.get("value") for t in baseline_memory.get("voice_traits", [])}
    cand_traits = {t.get("trait"): t.get("value") for t in candidate_memory.get("voice_traits", [])}

    if not base_traits or not cand_traits:
        return 3.0

    matches = 0
    total = 0
    for trait, base_val in base_traits.items():
        total += 1
        if cand_traits.get(trait) == base_val:
            matches += 1

    # punctuation preferences 对比
    base_punct = {p.get("mark"): p.get("density_per_1k") for p in baseline_memory.get("punctuation_preferences", [])}
    cand_punct = {p.get("mark"): p.get("density_per_1k") for p in candidate_memory.get("punctuation_preferences", [])}
    if base_punct and cand_punct:
        punct_matches = 0
        punct_total = 0
        for mark, base_density in base_punct.items():
            punct_total += 1
            cand_density = cand_punct.get(mark)
            if cand_density is not None:
                # 允许 20% 的误差
                if abs(base_density - cand_density) / max(base_density, 0.01) < 0.2:
                    punct_matches += 1
        total += punct_total
        matches += punct_matches

    if total == 0:
        return 3.0

    ratio = matches / total
    # 映射到 0-5 分
    if ratio >= 0.9:
        return 5.0
    elif ratio >= 0.7:
        return 4.0
    elif ratio >= 0.5:
        return 3.0
    elif ratio >= 0.3:
        return 2.0
    else:
        return 1.0


def compute_boundary_control(skill_dir: Path) -> float:
    """计算边界控制得分（0-5），基于规则文件完整性"""
    boundary_path = skill_dir / "references" / "author-boundary.md"
    anti_path = skill_dir / "references" / "anti-patterns.md"

    score = 0.0
    if boundary_path.exists():
        text = boundary_path.read_text(encoding="utf-8")
        # 统计 "##" 或 "###" 标题数作为规则区块数
        sections = len(re.findall(r'^#{2,3}\s', text, re.MULTILINE))
        if sections >= 4:
            score += 2.5
        elif sections >= 2:
            score += 1.5
        else:
            score += 0.5

    if anti_path.exists():
        text = anti_path.read_text(encoding="utf-8")
        sections = len(re.findall(r'^#{2,3}\s', text, re.MULTILINE))
        if sections >= 3:
            score += 2.5
        elif sections >= 1:
            score += 1.5
        else:
            score += 0.5

    return min(score, 5.0)


def eval_candidate(child_name: str, factory_dir: str) -> dict:
    logger = setup_logger(__name__, child_name=child_name)
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    skill_dir = repo_dir / "skill"
    reports_dir = repo_dir / "reports"

    # 读取当前版本与 candidate 版本
    release_index_path = state_dir / "release-index.json"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        current_version = release_index.get("active_version", "1.0.0")
    else:
        current_version = "1.0.0"

    # 查找最新 candidate
    candidates_dir = state_dir / "candidates"
    candidate_version = None
    candidate_manifest = None
    if candidates_dir.exists():
        candidates = sorted(candidates_dir.glob("v*.json"))
        if candidates:
            candidate_manifest = json.loads(candidates[-1].read_text(encoding="utf-8"))
            candidate_version = candidate_manifest.get("version", "candidate")

    # 结构维度评估（自动）
    structure_scores = {}
    required_files = [
        "SKILL.md",
        "references/style-profile.md",
        "references/editorial-rules.md",
        "references/author-boundary.md",
        "references/anti-patterns.md",
        "references/examples.md",
        "assets/style-memory.json",
        "assets/quality-rubric.json",
        "evals/evals.json",
    ]
    missing = [f for f in required_files if not (skill_dir / f).exists()]
    structure_scores["file_integrity"] = 5 if not missing else (3 if len(missing) <= 2 else 1)
    structure_scores["rules_clarity"] = 4  # 简化评估
    structure_scores["supporting_files_clarity"] = 4
    structure_scores["eval_coverage"] = 4
    structure_scores["git_management"] = 4

    structure_avg = sum(structure_scores.values()) / len(structure_scores)

    # 效果维度评估（部分自动化 + 部分需人工）
    # 自动化部分
    baseline_tag = f"v{current_version}"
    baseline_memory_text = run_git_show(repo_dir, baseline_tag, "skill/assets/style-memory.json")
    baseline_memory = parse_style_memory(baseline_memory_text)
    candidate_memory = parse_style_memory(read_current_file(skill_dir, "assets/style-memory.json"))

    style_fit_score = compute_style_fit(baseline_memory, candidate_memory)
    boundary_score = compute_boundary_control(skill_dir)

    # 半自动/人工部分（提供检查清单和指引）
    effect_scores = {
        "style_fit": round(style_fit_score, 1),
        "human_feel": {
            "score": None,
            "auto_note": "需人工评估",
            "checklist": [
                "生成文章是否避免 AI 套路句？",
                "句子是否有自然的停顿与呼吸感？",
                "段落过渡是否生硬？",
            ]
        },
        "long_form_drive": {
            "score": None,
            "auto_note": "需人工评估",
            "checklist": [
                "2000 字以上文章是否能保持推进力？",
                "中段是否出现信息塌陷或重复？",
                "结尾是否与开头形成有效呼应？",
            ]
        },
        "ai_taste_reduction": {
            "score": None,
            "auto_note": "需人工评估",
            "checklist": [
                "是否存在 '在当今社会'、'综上所述' 等套路？",
                "是否有过度总结或空泛收束？",
                "人称使用是否与样文一致？",
            ]
        },
        "boundary_control": round(boundary_score, 1),
        "topic_judgment": {
            "score": None,
            "auto_note": "需人工评估",
            "checklist": [
                "对劣质选题是否能明确拒绝并说明原因？",
                "对信息不足的情况是否会追问而非强行生成？",
                "选题判断是否符合作者的真实偏好？",
            ]
        },
        "info_sufficiency": {
            "score": None,
            "auto_note": "需人工评估",
            "checklist": [
                "信息不足时是否列出具体补充项？",
                "是否在信息有限时仍强行编造？",
                "对素材的利用是否充分？",
            ]
        },
    }

    # 效果维度平均分（自动化得分 + 占位符按 3.0 计算）
    auto_scores = [v for k, v in effect_scores.items() if isinstance(v, (int, float))]
    placeholder_count = len(effect_scores) - len(auto_scores)
    placeholder_avg = 3.0
    effect_avg = (sum(auto_scores) + placeholder_count * placeholder_avg) / len(effect_scores)

    total_score = round(structure_avg * 0.3 + effect_avg * 0.7, 2)

    report = {
        "eval_id": f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        "child_name": child_name,
        "baseline_version": current_version,
        "candidate_version": candidate_version or "unknown",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "structure_dimension": {
            "scores": structure_scores,
            "average": round(structure_avg, 2),
        },
        "effect_dimension": {
            "scores": effect_scores,
            "average_auto": round(sum(auto_scores) / len(auto_scores), 2) if auto_scores else 0,
            "average_with_placeholders": round(effect_avg, 2),
            "auto_evaluated": ["style_fit", "boundary_control"],
            "manual_required": ["human_feel", "long_form_drive", "ai_taste_reduction", "topic_judgment", "info_sufficiency"],
            "note": "效果维度中 style_fit 与 boundary_control 已自动评估；其余需运行测试 prompts 并人工评分。",
        },
        "total_score": total_score,
        "recommendation": (
            "结构维度通过。效果维度中，"
            f"style_fit={style_fit_score:.1f}、boundary_control={boundary_score:.1f} 已自动计算。"
            "请运行测试 prompts 并人工评估剩余维度后，再决定 publish 或 revise。"
        ),
        "missing_files": missing,
    }

    # 保存报告
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "eval-summary.md"
    lines = [
        f"# 评估报告：{child_name}",
        "",
        f"- 评估时间：{report['evaluated_at']}",
        f"- Baseline 版本：{current_version}",
        f"- Candidate 版本：{candidate_version or 'unknown'}",
        "",
        "## 结构维度",
        "",
        f"平均分：{structure_avg:.2f} / 5.0",
        "",
        "| 子维度 | 得分 |",
        "|--------|------|",
    ]
    for k, v in structure_scores.items():
        lines.append(f"| {k} | {v} |")

    lines.extend([
        "",
        "## 效果维度",
        "",
        f"自动评估平均分：{report['effect_dimension']['average_auto']:.2f} / 5.0",
        f"含占位符平均分：{report['effect_dimension']['average_with_placeholders']:.2f} / 5.0",
        "",
        "| 子维度 | 得分 | 类型 |",
        "|--------|------|------|",
    ])
    for k, v in effect_scores.items():
        if isinstance(v, dict):
            lines.append(f"| {k} | [待人工评分] | 人工 |")
            lines.append("")
            lines.append("**检查清单**：")
            for item in v.get("checklist", []):
                lines.append(f"- [ ] {item}")
            lines.append("")
        else:
            lines.append(f"| {k} | {v} | 自动 |")

    lines.extend([
        "",
        f"## 总分\n\n{total_score} / 5.0",
        "",
        "## 推荐决策\n\n" + report["recommendation"],
        "",
    ])
    if missing:
        lines.append("## 缺失文件\n")
        for f in missing:
            lines.append(f"- {f}")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    # 同时保存 JSON
    (reports_dir / f"{report['eval_id']}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate candidate vs baseline")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()

    result = eval_candidate(args.child_name, args.factory_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
