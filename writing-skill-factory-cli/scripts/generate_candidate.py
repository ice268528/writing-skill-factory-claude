#!/usr/bin/env python3
"""
generate_candidate.py
从当前 canonical repo 生成 candidate 版本并保存 manifest。

用法:
    python generate_candidate.py <child_name> [--factory-dir <dir>]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger

logger = setup_logger("generate_candidate")


def bump_version(current_version: str, existing_versions: list[str]) -> str:
    """自动递增 patch 版本号，避开已存在的版本。"""
    parts = current_version.split(".")
    if len(parts) != 3:
        parts = ["1", "0", "0"]
    major, minor, patch = parts
    try:
        patch_int = int(patch)
    except ValueError:
        patch_int = 0

    new_version = f"{major}.{minor}.{patch_int + 1}"
    # 如果该版本已存在（在 candidates 或 releases 中），继续递增
    while new_version in existing_versions:
        patch_int += 1
        new_version = f"{major}.{minor}.{patch_int + 1}"
    return new_version


def get_git_sha(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_git_diff_summary(repo_dir: Path) -> str:
    """获取当前工作区相对于 HEAD 的变更摘要（commit 前调用）"""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--stat"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_changed_files(repo_dir: Path) -> list:
    """获取当前工作区相对于 HEAD 的变更文件列表（commit 前调用）"""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--name-only"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return files
    except subprocess.CalledProcessError:
        return []


def read_recent_learning_events(repo_dir: Path, limit: int = 5) -> list:
    """读取最近的 learning-log 事件"""
    log_path = repo_dir / "state" / "learning-log.jsonl"
    if not log_path.exists():
        return []
    events = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events[-limit:]


def generate_candidate(child_name: str, factory_dir: str) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"
    skill_dir = repo_dir / "skill"
    candidates_dir = state_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    # 读取当前版本
    release_index_path = state_dir / "release-index.json"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        current_version = release_index.get("active_version", "1.0.0")
    else:
        current_version = "1.0.0"
        release_index = {"releases": [], "active_version": current_version}

    existing_versions = [r.get("version", "") for r in release_index.get("releases", [])]
    new_version = bump_version(current_version, existing_versions)
    tag = f"v{new_version}"

    # 收集变更信息
    git_sha = get_git_sha(repo_dir)
    diff_summary = get_git_diff_summary(repo_dir)
    changed_files = get_changed_files(repo_dir)
    recent_events = read_recent_learning_events(repo_dir)

    # 生成变更摘要
    event_summaries = []
    for ev in recent_events:
        event_type = ev.get("event", "unknown")
        if event_type == "promote_rules":
            count = ev.get("promoted_count", 0)
            event_summaries.append(f"从 {ev.get('article_id', 'unknown')} 提取并升级了 {count} 条规则")
        elif event_type == "publish":
            event_summaries.append(f"发布了版本 {ev.get('version', 'unknown')}")
        elif event_type == "rollback":
            event_summaries.append(f"回滚到版本 {ev.get('version', 'unknown')}")
        else:
            # 对未知事件类型，提取关键字段生成可读摘要，避免截断 JSON
            key_fields = []
            if ev.get("article_id"):
                key_fields.append(f"article={ev['article_id']}")
            if ev.get("version"):
                key_fields.append(f"version={ev['version']}")
            if ev.get("promoted_count") is not None:
                key_fields.append(f"promoted={ev['promoted_count']}")
            summary_text = ", ".join(key_fields) if key_fields else "未解析事件"
            event_summaries.append(f"{event_type}: {summary_text}")

    change_summary = "；".join(event_summaries) if event_summaries else "基于学习迭代自动生成的候选版本"

    # 生成 candidate manifest
    candidate_manifest = {
        "version": new_version,
        "parent_version": current_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "change_summary": change_summary,
        "diff_summary": diff_summary,
        "changed_files": changed_files,
        "git_sha": git_sha,
        "learning_events": recent_events,
    }

    # 保存 candidate manifest
    candidate_path = candidates_dir / f"v{new_version}.json"
    candidate_path.write_text(json.dumps(candidate_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 在 canonical repo 中提交并打 tag
    try:
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"candidate: generate v{new_version} from {current_version}\n\n{change_summary}"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "tag", "-a", tag, "-m", f"Candidate version {new_version}"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        logger.info("Committed and tagged %s", tag)
    except subprocess.CalledProcessError as e:
        logger.warning("Git commit/tag failed: %s", e)
        # 如果 commit 失败（比如没有变更），仍然保留 manifest 但标记为 dirty
        candidate_manifest["git_dirty"] = True
        candidate_path.write_text(json.dumps(candidate_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新 release-index（添加 candidate 记录，但不改变 active_version）
    release_index.setdefault("releases", []).append({
        "version": new_version,
        "tag": tag,
        "date": datetime.now(timezone.utc).isoformat(),
        "type": "candidate",
        "change_summary": change_summary,
        "parent_version": current_version,
        "eval_score": None,
    })
    release_index_path.write_text(json.dumps(release_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 追加 change-log
    changelog_path = repo_dir / "reports" / "change-log.md"
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    log_entry = (
        f"\n## {new_version} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})\n\n"
        f"- **Type:** candidate\n"
        f"- **Parent:** {current_version}\n"
        f"- **SHA:** `{git_sha[:8] if git_sha else 'N/A'}`\n"
        f"- **Changes:** {change_summary}\n"
        f"- **Changed files:** {', '.join(changed_files) if changed_files else 'N/A'}\n"
    )
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        if "# Change Log" not in existing:
            existing = "# Change Log\n" + existing
    else:
        existing = "# Change Log\n"
    changelog_path.write_text(existing + log_entry, encoding="utf-8")

    logger.info("Candidate v%s generated for %s", new_version, child_name)
    logger.info("Manifest: %s", candidate_path)
    logger.info("Change log: %s", changelog_path)

    return candidate_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate candidate version from canonical repo")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    args = parser.parse_args()

    with LogContext(logger, child_name=args.child_name, step="generate_candidate"):
        try:
            result = generate_candidate(args.child_name, args.factory_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.exception("Generate candidate failed for %s: %s", args.child_name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
