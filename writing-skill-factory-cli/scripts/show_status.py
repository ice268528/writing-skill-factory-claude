#!/usr/bin/env python3
"""
show_status.py
展示指定 child skill 的当前状态：版本、规则、学习记录、候选版本等。

用法:
    python show_status.py <child_name> [--factory-dir <dir>]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from factory_logging import LogContext, setup_logger

logger = setup_logger("show_status")


def _parse_semver(version_str: str) -> tuple[int, ...]:
    """将版本号字符串解析为可比较的整数元组。"""
    if not version_str:
        return (0, 0, 0)
    cleaned = version_str.strip().lstrip("vV")
    parts = cleaned.split(".")
    nums = []
    for p in parts:
        m = re.match(r'(\d+)', p)
        nums.append(int(m.group(1)) if m else 0)
    # 补齐到至少 3 位
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def show_status(child_name: str, factory_dir: str) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    skill_dir = repo_dir / "skill"

    status = {
        "child_name": child_name,
        "canonical_repo": str(repo_dir),
        "sections": {},
    }

    # --------------------------------------------------------------
    # 1. Release 索引
    # --------------------------------------------------------------
    release_index_path = state_dir / "release-index.json"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        releases = release_index.get("releases", [])
        latest = max(releases, key=lambda r: _parse_semver(r.get("version", ""))) if releases else None
        status["sections"]["release"] = {
            "latest_version": latest.get("version") if latest else None,
            "latest_tag": latest.get("tag") if latest else None,
            "release_count": len(releases),
            "releases": [{"version": r.get("version"), "tag": r.get("tag"), "created_at": r.get("created_at")} for r in releases],
        }
    else:
        status["sections"]["release"] = {"latest_version": None, "release_count": 0}

    # --------------------------------------------------------------
    # 2. 候选版本 (candidates)
    # --------------------------------------------------------------
    candidates_dir = state_dir / "candidates"
    if candidates_dir.exists():
        candidate_files = sorted(candidates_dir.glob("*.json"), key=lambda p: _parse_semver(p.stem))
    else:
        candidate_files = []
    status["sections"]["candidates"] = {
        "count": len(candidate_files),
        "latest": None,
    }
    if candidate_files:
        latest_candidate = json.loads(candidate_files[-1].read_text(encoding="utf-8"))
        status["sections"]["candidates"]["latest"] = {
            "version": latest_candidate.get("version"),
            "parent_version": latest_candidate.get("parent_version"),
            "created_at": latest_candidate.get("created_at"),
        }

    # --------------------------------------------------------------
    # 3. 学习记录统计
    # --------------------------------------------------------------
    learning_log_path = state_dir / "learning-log.jsonl"
    log_entries = []
    if learning_log_path.exists():
        with learning_log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    log_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    promote_count = sum(1 for e in log_entries if e.get("event") == "promote_rules")
    pipeline_count = sum(1 for e in log_entries if e.get("event") == "learn_pipeline")
    status["sections"]["learning"] = {
        "total_log_entries": len(log_entries),
        "learn_pipeline_runs": pipeline_count,
        "promote_events": promote_count,
    }

    # --------------------------------------------------------------
    # 4. 规则统计 (style-memory.json)
    # --------------------------------------------------------------
    memory_path = skill_dir / "assets" / "style-memory.json"
    if memory_path.exists():
        memory = json.loads(memory_path.read_text(encoding="utf-8"))
        buckets = memory.get("confidence_buckets", {})
        status["sections"]["rules"] = {
            "candidate": len(buckets.get("candidate", [])),
            "probation": len(buckets.get("probation", [])),
            "active": len(buckets.get("active", [])),
            "total": sum(len(buckets.get(k, [])) for k in ("candidate", "probation", "active")),
        }
    else:
        status["sections"]["rules"] = {"candidate": 0, "probation": 0, "active": 0, "total": 0}

    # --------------------------------------------------------------
    # 5. 样文与文章统计
    # --------------------------------------------------------------
    workspace_dir = repo_dir / "workspace"
    sample_count = len(list(workspace_dir.glob("*.md"))) if workspace_dir.exists() else 0

    baselines_dir = state_dir / "baselines"
    baseline_count = len(list(baselines_dir.glob("*.md"))) if baselines_dir.exists() else 0

    revisions_dir = state_dir / "revisions"
    revision_count = len(list(revisions_dir.glob("*.json"))) if revisions_dir.exists() else 0

    status["sections"]["articles"] = {
        "samples": sample_count,
        "baselines": baseline_count,
        "revisions": revision_count,
    }

    # --------------------------------------------------------------
    # 6. 评估报告
    # --------------------------------------------------------------
    reports_dir = repo_dir / "reports"
    eval_reports = sorted(reports_dir.glob("eval-*.md")) if reports_dir.exists() else []
    status["sections"]["evals"] = {
        "eval_report_count": len(eval_reports),
        "latest_eval": str(eval_reports[-1].name) if eval_reports else None,
    }

    return status


def print_status(status: dict) -> None:
    """以人类可读的格式打印状态"""
    name = status["child_name"]
    sections = status["sections"]

    print(f"\n{'=' * 60}")
    print(f"  Child Skill 状态: {name}")
    print(f"{'=' * 60}")

    rel = sections.get("release", {})
    print(f"\n[Release]")
    print(f"   最新版本: {rel.get('latest_version') or 'N/A'} ({rel.get('latest_tag') or 'N/A'})")
    print(f"   发布次数: {rel.get('release_count', 0)}")

    cand = sections.get("candidates", {})
    print(f"\n[Candidates]")
    print(f"   候选数量: {cand.get('count', 0)}")
    if cand.get("latest"):
        print(f"   最新候选: v{cand['latest']['version']} (基于 {cand['latest']['parent_version']})")

    rules = sections.get("rules", {})
    print(f"\n[Rules]")
    print(f"   Active:    {rules.get('active', 0)}")
    print(f"   Probation: {rules.get('probation', 0)}")
    print(f"   Candidate: {rules.get('candidate', 0)}")
    print(f"   总计:      {rules.get('total', 0)}")

    learning = sections.get("learning", {})
    print(f"\n[Learning]")
    print(f"   Pipeline 运行: {learning.get('learn_pipeline_runs', 0)} 次")
    print(f"   Promote 事件:  {learning.get('promote_events', 0)} 次")

    art = sections.get("articles", {})
    print(f"\n[Articles]")
    print(f"   样文数量:  {art.get('samples', 0)}")
    print(f"   Baselines: {art.get('baselines', 0)}")
    print(f"   Revisions: {art.get('revisions', 0)}")

    ev = sections.get("evals", {})
    print(f"\n[Evals]")
    print(f"   评估报告: {ev.get('eval_report_count', 0)}")
    if ev.get("latest_eval"):
        print(f"   最新报告: {ev['latest_eval']}")

    print(f"\n{'=' * 60}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show child skill status")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    with LogContext(logger, child_name=args.child_name, step="status"):
        try:
            status = show_status(args.child_name, args.factory_dir)
            if args.json:
                print(json.dumps(status, ensure_ascii=False, indent=2))
            else:
                print_status(status)
        except Exception as e:
            logger.exception("Show status failed for %s: %s", args.child_name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
