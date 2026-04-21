#!/usr/bin/env python3
"""
learn_pipeline.py
统一 learn 流程入口：sync → diff → promote → generate candidate → eval → (prune) → (regression-test)。

用法:
    python learn_pipeline.py <child_name> [--factory-dir <dir>] [--project-root <dir>] [--article-id <id>]

选项:
    --article-id         仅处理指定文章（跳过 sync 扫描，直接对该 article_id 执行 diff + promote）
    --skip-eval          跳过最终评估（仅生成 candidate，不运行 eval）
    --dry-run            只展示将要执行的步骤，不实际运行
    --prune              在 promote 后触发规则清理（prune_rules）
    --regression-test    在 eval 后运行回归测试
"""

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger

logger = setup_logger("learn_pipeline")

# 导入同级目录下的脚本模块（不依赖 sys.path 污染）
SCRIPT_DIR = Path(__file__).parent.resolve()


def _import_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_sync(child_name: str, factory_dir: str, project_root: str) -> dict:
    mod = _import_module("sync_visible_edits")
    return mod.sync_visible_edits(child_name, factory_dir, project_root)


def run_diff(child_name: str, article_id: str, factory_dir: str, project_root: str) -> dict:
    mod = _import_module("diff_revision")
    return mod.diff_revision(child_name, article_id, factory_dir, project_root)


def run_promote(child_name: str, article_id: str, factory_dir: str) -> dict:
    mod = _import_module("promote_rules")
    return mod.promote_rules(child_name, article_id, factory_dir)


def run_generate_candidate(child_name: str, factory_dir: str) -> dict:
    mod = _import_module("generate_candidate")
    return mod.generate_candidate(child_name, factory_dir)


def run_eval(child_name: str, factory_dir: str) -> dict:
    mod = _import_module("eval_candidate")
    return mod.eval_candidate(child_name, factory_dir)


def run_git_commit(repo_dir: Path, message: str) -> bool:
    import subprocess
    try:
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"[learn_pipeline] Git commit warning: {e}")
        return False


def learn_pipeline(child_name: str, factory_dir: str, project_root: str, article_id: str | None, skip_eval: bool, dry_run: bool) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"

    results = {
        "child_name": child_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "steps": [],
    }

    with LogContext(logger, child_name=child_name, step="pipeline") as log:
        # ------------------------------------------------------------------
        # Step 1: Sync
        # ------------------------------------------------------------------
        if dry_run:
            log.info(f"[DRY-RUN] 将执行 sync_visible_edits({child_name})")
            results["steps"].append({"step": "sync", "status": "dry_run"})
        else:
            log.info("Step 1/5: Syncing visible edits...")
            try:
                sync_result = run_sync(child_name, factory_dir, project_root)
            except Exception as e:
                log.error("Sync failed: %s", e)
                results["steps"].append({"step": "sync", "status": "error", "error": str(e)})
                return results
            results["steps"].append({"step": "sync", "status": sync_result.get("status"), "changes": sync_result.get("changes", [])})
            log.info("Sync result: %s, changes: %d", sync_result.get("status"), len(sync_result.get("changes", [])))

            if sync_result.get("changes"):
                run_git_commit(repo_dir, f"sync: visible edits for {child_name}\n\n{json.dumps(sync_result['changes'], ensure_ascii=False)}")

        # ------------------------------------------------------------------
        # 确定需要 diff + promote 的 article_ids
        # ------------------------------------------------------------------
        target_article_ids = []
        if article_id:
            target_article_ids.append(article_id)
        elif not dry_run:
            for change in results["steps"][-1].get("changes", []):
                if change.get("action") in ("edit", "add"):
                    target_article_ids.append(change["article_id"])

        if not target_article_ids and not article_id:
            log.info("No edited articles found. Skipping diff & promote.")

        # ------------------------------------------------------------------
        # Step 2: Diff
        # ------------------------------------------------------------------
        diff_results = []
        if dry_run:
            for aid in target_article_ids or ["<detected>"]:
                log.info(f"[DRY-RUN] 将执行 diff_revision({child_name}, {aid})")
            results["steps"].append({"step": "diff", "status": "dry_run", "article_ids": target_article_ids})
        else:
            log.info("Step 2/5: Diffing %d article(s)...", len(target_article_ids))
            for aid in target_article_ids:
                try:
                    diff_result = run_diff(child_name, aid, factory_dir, project_root)
                except Exception as e:
                    log.error("Diff failed for %s: %s", aid, e)
                    diff_result = {"status": "error", "article_id": aid, "error": str(e)}
                diff_results.append(diff_result)
                log.info("Diff %s: %s", aid, diff_result.get("diff_summary", {}))
            results["steps"].append({"step": "diff", "status": "done", "results": diff_results})

        # ------------------------------------------------------------------
        # Step 3: Promote
        # ------------------------------------------------------------------
        promote_results = []
        if dry_run:
            for aid in target_article_ids or ["<detected>"]:
                log.info(f"[DRY-RUN] 将执行 promote_rules({child_name}, {aid})")
            results["steps"].append({"step": "promote", "status": "dry_run"})
        else:
            log.info("Step 3/5: Promoting rules for %d article(s)...", len(target_article_ids))
            for aid in target_article_ids:
                try:
                    promote_result = run_promote(child_name, aid, factory_dir)
                except Exception as e:
                    log.error("Promote failed for %s: %s", aid, e)
                    promote_result = {"status": "error", "article_id": aid, "error": str(e)}
                promote_results.append(promote_result)
                log.info("Promote %s: %s, promoted=%d", aid, promote_result.get("status"), len(promote_result.get("promoted", [])))

            if promote_results:
                run_git_commit(repo_dir, f"learn: promoted rules from {len(target_article_ids)} articles\n\n{json.dumps([r.get('promoted', []) for r in promote_results], ensure_ascii=False)[:500]}")
            results["steps"].append({"step": "promote", "status": "done", "results": promote_results})

        # ------------------------------------------------------------------
        # Step 4: Generate Candidate
        # ------------------------------------------------------------------
        if dry_run:
            log.info(f"[DRY-RUN] 将执行 generate_candidate({child_name})")
            results["steps"].append({"step": "generate_candidate", "status": "dry_run"})
        else:
            log.info("Step 4/5: Generating candidate...")
            try:
                candidate_result = run_generate_candidate(child_name, factory_dir)
            except Exception as e:
                log.error("Generate candidate failed: %s", e)
                results["steps"].append({"step": "generate_candidate", "status": "error", "error": str(e)})
                return results
            results["steps"].append({"step": "generate_candidate", "status": "done", "candidate": candidate_result})
            log.info("Candidate generated: %s", candidate_result.get("version", "unknown"))

        # ------------------------------------------------------------------
        # Step 5: Eval
        # ------------------------------------------------------------------
        if skip_eval:
            log.info("Step 5/5: Skipping eval (--skip-eval)")
            results["steps"].append({"step": "eval", "status": "skipped"})
        elif dry_run:
            log.info(f"[DRY-RUN] 将执行 eval_candidate({child_name})")
            results["steps"].append({"step": "eval", "status": "dry_run"})
        else:
            log.info("Step 5/5: Evaluating candidate...")
            try:
                eval_result = run_eval(child_name, factory_dir)
            except Exception as e:
                log.error("Eval failed: %s", e)
                results["steps"].append({"step": "eval", "status": "error", "error": str(e)})
                return results
            results["steps"].append({"step": "eval", "status": "done", "eval": eval_result})
            log.info("Eval total score: %s", eval_result.get("total_score", "N/A"))

        results["finished_at"] = datetime.now(timezone.utc).isoformat()

        if not dry_run:
            pipeline_log_path = state_dir / "learning-log.jsonl"
            with pipeline_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event": "learn_pipeline",
                    "child_name": child_name,
                    "timestamp": results["finished_at"],
                    "result_summary": {s["step"]: s["status"] for s in results["steps"]},
                }, ensure_ascii=False) + "\n")

        log.info("Pipeline complete.")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified learn pipeline")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--article-id", default=None, help="Process specific article ID only")
    parser.add_argument("--skip-eval", action="store_true", help="Skip final eval step")
    parser.add_argument("--dry-run", action="store_true", help="Show steps without executing")
    args = parser.parse_args()

    try:
        result = learn_pipeline(
            args.child_name,
            args.factory_dir,
            args.project_root,
            args.article_id,
            args.skip_eval,
            args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if any(s.get("status") == "error" for s in result.get("steps", [])):
            return 1
    except Exception as e:
        logger.exception("Pipeline crashed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
