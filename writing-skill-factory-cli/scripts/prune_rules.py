#!/usr/bin/env python3
"""
prune_rules.py
定期/触发式清理过时/低置信度规则。

用法:
    python prune_rules.py <child_name> [--factory-dir <dir>] [--dry-run]
                           [--min-evidence <int>] [--prune-candidate-only]

策略:
    1. 合并同一 bucket 内 description 完全相同的规则（evidence_count 累加）。
    2. 删除 candidate 规则中 evidence_count < min_evidence 的条目。
    3. 删除 candidate 中 description 明显为劣质自动生成的规则（如以"用户将"开头）。
    4. 对 probation 规则：若长期无新 evidence，降级回 candidate（暂不删除）。
    5. 清理 anti_patterns 中的重复项。
    6. 生成 prune 报告并追加到 learning-log.jsonl。
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger, sanitize_child_name

logger = setup_logger("prune_rules")


def _dedup_rules(rules: list[dict]) -> tuple[list[dict], int]:
    """合并 description 完全相同的规则，返回新列表与合并次数。"""
    seen: dict[str, dict] = {}
    merged = 0
    for r in rules:
        desc = r.get("description", "").strip()
        if not desc:
            continue
        if desc in seen:
            seen[desc]["evidence_count"] = seen[desc].get("evidence_count", 0) + r.get("evidence_count", 0)
            # 合并 source_articles
            old_src = set(seen[desc].get("source_articles", []))
            old_src.update(r.get("source_articles", []))
            seen[desc]["source_articles"] = list(old_src)
            merged += 1
        else:
            seen[desc] = dict(r)
    return list(seen.values()), merged


def _is_low_quality_candidate(rule: dict) -> bool:
    """判断是否为劣质自动生成的 candidate 规则。"""
    desc = rule.get("description", "")
    # 旧版 promote_rules 生成的机械描述
    if desc.startswith("用户将") or desc.startswith("'["):
        return True
    # 过短且无意义
    if len(desc) < 10:
        return True
    return False


def prune_rules(
    child_name: str,
    factory_dir: str,
    dry_run: bool = False,
    min_evidence: int = 1,
    prune_candidate_only: bool = False,
) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    skill_dir = repo_dir / "skill"
    state_dir = repo_dir / "state"
    memory_path = skill_dir / "assets" / "style-memory.json"

    if not memory_path.exists():
        return {"status": "error", "message": f"style-memory.json not found for {child_name}"}

    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    buckets = memory.get("confidence_buckets", {})
    original_counts = {k: len(v) for k, v in buckets.items()}

    actions: list[dict] = []

    # ----------------------------------------------------------
    # 1. candidate 清理
    # ----------------------------------------------------------
    candidates = list(buckets.get("candidate", []))
    cleaned_candidates = []
    for r in candidates:
        desc = r.get("description", "")
        evidence = r.get("evidence_count", 0)

        if evidence < min_evidence:
            actions.append({"action": "remove", "bucket": "candidate", "reason": f"evidence_count={evidence} < {min_evidence}", "description": desc[:80]})
            continue

        if _is_low_quality_candidate(r):
            actions.append({"action": "remove", "bucket": "candidate", "reason": "low_quality_auto_gen", "description": desc[:80]})
            continue

        cleaned_candidates.append(r)

    # 去重 + 合并
    cleaned_candidates, merged_cand = _dedup_rules(cleaned_candidates)
    if merged_cand:
        actions.append({"action": "merge", "bucket": "candidate", "count": merged_cand})

    buckets["candidate"] = cleaned_candidates

    # ----------------------------------------------------------
    # 2. probation 降级检查（暂不删除，仅降级）
    # ----------------------------------------------------------
    if not prune_candidate_only:
        probations = list(buckets.get("probation", []))
        # probation 若 evidence_count 仍很低，降级回 candidate
        downgraded = []
        kept = []
        for r in probations:
            if r.get("evidence_count", 0) < min_evidence + 1:
                r["confidence"] = "candidate"
                downgraded.append(r)
                actions.append({"action": "downgrade", "bucket": "probation->candidate", "description": r.get("description", "")[:80]})
            else:
                kept.append(r)
        # probation 也去重
        kept, merged_prob = _dedup_rules(kept)
        if merged_prob:
            actions.append({"action": "merge", "bucket": "probation", "count": merged_prob})
        buckets["probation"] = kept
        if downgraded:
            buckets["candidate"].extend(downgraded)
            # candidate 再次去重
            buckets["candidate"], _ = _dedup_rules(buckets["candidate"])

    # ----------------------------------------------------------
    # 3. active 合并（不删除，只合并重复）
    # ----------------------------------------------------------
    if not prune_candidate_only:
        actives = list(buckets.get("active", []))
        actives, merged_act = _dedup_rules(actives)
        if merged_act:
            actions.append({"action": "merge", "bucket": "active", "count": merged_act})
        buckets["active"] = actives

    # ----------------------------------------------------------
    # 4. anti_patterns 去重
    # ----------------------------------------------------------
    anti_patterns = memory.get("anti_patterns", [])
    if anti_patterns:
        anti_seen: dict[str, dict] = {}
        for r in anti_patterns:
            desc = r.get("description", "").strip()
            if desc in anti_seen:
                anti_seen[desc]["evidence_count"] = anti_seen[desc].get("evidence_count", 0) + r.get("evidence_count", 0)
            else:
                anti_seen[desc] = dict(r)
        if len(anti_seen) < len(anti_patterns):
            actions.append({"action": "dedup", "list": "anti_patterns", "removed": len(anti_patterns) - len(anti_seen)})
            memory["anti_patterns"] = list(anti_seen.values())

    # ----------------------------------------------------------
    # 5. 更新文件
    # ----------------------------------------------------------
    new_counts = {k: len(v) for k, v in buckets.items()}

    if not dry_run:
        memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

        # 记录到 learning-log
        log_entry = {
            "event": "prune_rules",
            "child_name": child_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "original_counts": original_counts,
            "new_counts": new_counts,
            "actions": actions,
        }
        log_path = state_dir / "learning-log.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # git commit
        try:
            subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"prune: cleanup rules for {child_name}\n\nremoved/merged: {len(actions)} actions"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("Git commit failed after prune (possibly no changes): %s", e)

    result = {
        "status": "pruned" if not dry_run else "dry_run",
        "child_name": child_name,
        "original_counts": original_counts,
        "new_counts": new_counts,
        "actions": actions,
    }

    # 生成报告
    report_lines = [
        f"# Prune Report: {child_name}",
        "",
        f"- **Time:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Dry Run:** {dry_run}",
        "",
        "## Counts",
        "",
        "| Bucket | Before | After |",
        "|--------|--------|-------|",
    ]
    for k in ("candidate", "probation", "active"):
        report_lines.append(f"| {k} | {original_counts.get(k, 0)} | {new_counts.get(k, 0)} |")
    report_lines.extend(["", "## Actions", ""])
    for a in actions:
        report_lines.append(f"- {a}")
    report_path = repo_dir / "reports" / "prune-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune outdated/low-confidence rules")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without modifying files")
    parser.add_argument("--min-evidence", type=int, default=1, help="Minimum evidence_count to keep a candidate rule")
    parser.add_argument("--prune-candidate-only", action="store_true", help="Only prune candidate bucket, leave probation/active untouched")
    args = parser.parse_args()
    args.child_name = sanitize_child_name(args.child_name)

    with LogContext(logger, child_name=args.child_name, step="prune"):
        result = prune_rules(
            args.child_name,
            args.factory_dir,
            dry_run=args.dry_run,
            min_evidence=args.min_evidence,
            prune_candidate_only=args.prune_candidate_only,
        )
        logger.info("Prune result: %s", result["status"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
