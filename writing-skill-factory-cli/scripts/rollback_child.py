#!/usr/bin/env python3
"""
rollback_child.py
从 release 恢复并重新发布 active child。

用法:
    python rollback_child.py <child_name> <version> [--factory-dir <dir>] [--skills-dir <dir>]
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger

logger = setup_logger("rollback_child")


def rollback_child(child_name: str, version: str, factory_dir: str, skills_dir: str) -> dict:
    repo_dir = Path(factory_dir) / child_name / "repo"
    state_dir = repo_dir / "state"

    if not repo_dir.exists():
        logger.error("Repo not found for %s", child_name)
        return {"status": "error", "message": f"Repo not found for {child_name}"}

    tag = f"v{version}"

    # 1) 检测工作区未提交更改
    try:
        status_result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        uncommitted = [line for line in status_result.stdout.strip().split("\n") if line.strip()]
        if uncommitted:
            logger.warning("Uncommitted changes detected in %s: %d files", child_name, len(uncommitted))
            return {
                "status": "blocked",
                "message": f"工作区存在 {len(uncommitted)} 个未提交更改。请先 commit 或 stash 后再 rollback。",
                "uncommitted_files": uncommitted,
            }
    except subprocess.CalledProcessError as e:
        logger.error("Failed to check git status: %s", e)
        return {"status": "error", "message": f"无法检测工作区状态: {e}"}

    # 2) 检出指定 tag
    try:
        subprocess.run(
            ["git", "checkout", tag, "--", "."],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("Failed to checkout %s: %s", tag, e)
        return {"status": "error", "message": f"Failed to checkout {tag}: {e.stderr.decode() if e.stderr else str(e)}"}

    # 更新 active_version
    release_index_path = state_dir / "release-index.json"
    if release_index_path.exists():
        release_index = json.loads(release_index_path.read_text(encoding="utf-8"))
        release_index["active_version"] = version
        release_index_path.write_text(json.dumps(release_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 重新发布
    skill_src = repo_dir / "skill"
    dest_dir = Path(skills_dir) / f"writer-{child_name}"

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for item in skill_src.rglob("*"):
        if item.is_file():
            rel = item.relative_to(skill_src)
            dest_file = dest_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_file)

    # 追加 change-log
    changelog_path = repo_dir / "reports" / "change-log.md"
    if changelog_path.exists():
        log_entry = (
            f"\n## {version} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})\n\n"
            f"- **Type:** rollback\n"
            f"- **Rolled back to:** `{tag}`\n"
            f"- **Destination:** `{dest_dir}`\n"
        )
        existing = changelog_path.read_text(encoding="utf-8")
        changelog_path.write_text(existing + log_entry, encoding="utf-8")

    # 记录日志
    log_path = state_dir / "learning-log.jsonl"
    log_entry = {
        "event": "rollback",
        "child_name": child_name,
        "version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    result = {
        "status": "rolled_back",
        "child_name": child_name,
        "version": version,
        "published_to": str(dest_dir),
    }

    # 3) rollback 后自动运行回归测试验证回滚结果
    try:
        test_proc = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "run_regression_tests.py"), child_name, "--factory-dir", str(factory_dir)],
            capture_output=True,
            text=True,
        )
        # 解析 stdout 中的 JSON summary（定位包含 "run_at" 的最外层 JSON 对象）
        stdout = test_proc.stdout
        marker = '"run_at"'
        marker_pos = stdout.rfind(marker)
        if marker_pos != -1:
            start = stdout.rfind("{", 0, marker_pos)
            # 从 start 开始找匹配的结束括号
            end = -1
            brace_count = 0
            for i in range(start, len(stdout)):
                if stdout[i] == "{":
                    brace_count += 1
                elif stdout[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i
                        break
            if start != -1 and end != -1 and end > start:
                try:
                    summary = json.loads(stdout[start:end + 1])
                    result["regression_test"] = {
                        "passed": summary.get("passed"),
                        "total": summary.get("total"),
                        "failed": summary.get("failed"),
                    }
                except json.JSONDecodeError as je:
                    result["regression_test"] = {"error": f"JSON 解析失败: {je}"}
            else:
                result["regression_test"] = {"error": "无法定位回归测试 summary 的结束括号"}
        else:
            result["regression_test"] = {"error": "无法解析回归测试输出（未找到 run_at 标记）"}
    except Exception as e:
        logger.warning("Regression test after rollback failed: %s", e)
        result["regression_test"] = {"error": str(e)}

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback a child skill to a specific version")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("version", help="Version to rollback to (e.g., 1.0.0)")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--skills-dir", default=".claude/skills", help="Claude skills dir")
    args = parser.parse_args()

    with LogContext(logger, child_name=args.child_name, step="rollback"):
        try:
            result = rollback_child(args.child_name, args.version, args.factory_dir, args.skills_dir)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result.get("status") == "error":
                return 1
        except Exception as e:
            logger.exception("Rollback failed for %s: %s", args.child_name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
