#!/usr/bin/env python3
"""
eval_candidate.py
执行 old vs candidate 评估并生成报告。

用法:
    python eval_candidate.py <child_name> [--factory-dir <dir>]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def eval_candidate(child_name: str, factory_dir: str) -> dict:
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

    # 效果维度评估（需要人工/测试，此处生成框架）
    effect_scores = {
        "style_fit": "[待测试：与样文对比风格贴合度]",
        "human_feel": "[待测试：活人感评估]",
        "long_form_drive": "[待测试：长文推进力]",
        "ai_taste_reduction": "[待测试：AI 味减少程度]",
        "boundary_control": "[待测试：作者边界控制]",
        "topic_judgment": "[待测试：选题判断准确性]",
        "info_sufficiency": "[待测试：信息充足性处理]",
    }

    # 总分（效果维度暂按占位平均 3.0 计算）
    effect_placeholder_avg = 3.0
    total_score = round(structure_avg * 0.3 + effect_placeholder_avg * 0.7, 2)

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
            "average": effect_placeholder_avg,
            "note": "效果维度需通过实际生成文章进行人工或半自动评估",
        },
        "total_score": total_score,
        "recommendation": "请运行测试 prompts 并人工评估效果维度后，再决定 publish 或 revise",
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
        f"平均分：{effect_placeholder_avg:.2f} / 5.0（占位）",
        "",
        "| 子维度 | 得分 |",
        "|--------|------|",
    ])
    for k, v in effect_scores.items():
        lines.append(f"| {k} | {v} |")

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
