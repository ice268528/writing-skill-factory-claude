#!/usr/bin/env python3
"""
create_child.py
创建 canonical child 仓库与首版 skill 文件。

用法:
    python create_child.py <child_name> <samples_dir> [--output-dir <dir>]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger, sanitize_child_name

logger = setup_logger("create_child")

# 默认输出基目录（相对于项目根）
DEFAULT_FACTORY_DIR = ".claude/writing-factory/children"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_template(template_path: Path, context: dict) -> str:
    """简单的模板渲染，替换 {{key}} 格式"""
    content = template_path.read_text(encoding="utf-8")
    for key, value in context.items():
        placeholder = f"{{{{{key}}}}}"
        if isinstance(value, list):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        content = content.replace(placeholder, value)
    return content


def init_git_repo(repo_dir: Path) -> None:
    if not (repo_dir / ".git").exists():
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "factory@local"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Writing Factory"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )


def create_child(child_name: str, samples_dir: str, factory_base: str) -> Path:
    """
    创建 child 的 canonical repo 并生成首版 skill 文件。
    返回 canonical repo 路径。
    """
    root = Path(factory_base).resolve()
    repo_dir = ensure_dir(root / child_name / "repo")
    skill_dir = ensure_dir(repo_dir / "skill")
    state_dir = ensure_dir(repo_dir / "state")
    reports_dir = ensure_dir(repo_dir / "reports")
    workspace_dir = ensure_dir(repo_dir / "workspace" / "shadow-output")

    # 初始化 state 子目录
    ensure_dir(state_dir / "profiles")
    ensure_dir(state_dir / "baselines")
    ensure_dir(state_dir / "revisions")
    ensure_dir(state_dir / "manifests")
    ensure_dir(state_dir / "candidates")
    ensure_dir(state_dir / "releases")

    # 初始化 git
    init_git_repo(repo_dir)

    # 收集样文信息
    samples_path = Path(samples_dir).resolve()
    sample_files = []
    if samples_path.exists():
        for ext in ("*.md", "*.txt"):
            sample_files.extend(samples_path.glob(ext))
    sample_files = sorted(sample_files)
    sample_sources = [str(f.name) for f in sample_files]

    now = datetime.now(timezone.utc).isoformat()
    version = "1.0.0"

    context = {
        "child_name": child_name,
        "version": version,
        "created_at": now,
        "generated_at": now,
        "sample_count": len(sample_files),
        "sample_sources": json.dumps(sample_sources, ensure_ascii=False),
        # 模板中使用的占位字段，后续由 build_*_profile 填充
        "style_dna": "[待 build_style_profile.py 填充]",
        "style_dimensions_table": "[待填充]",
        "punctuation_preferences": "[待填充]",
        "chunking_habits": "[待填充]",
        "paragraph_formulas": "[待填充]",
        "narrative_moves": "[待填充]",
        "progression_style": "[待填充]",
        "few_shot_examples": "[待填充]",
        "style_notes": "[待填充]",
        "article_prototypes": "[待填充]",
        "boundary_notes": "[待填充]",
    }

    # 模板目录（脚本所在目录的上一级 /templates）
    script_dir = Path(__file__).parent.resolve()
    tpl_dir = script_dir.parent / "templates"

    # 生成子 skill 文件
    files_to_generate = {
        skill_dir / "SKILL.md": tpl_dir / "child-skill-skill.md.tpl",
        skill_dir / "references" / "style-profile.md": tpl_dir / "style-summary.md.tpl",
        skill_dir / "references" / "editorial-rules.md": None,  # 由 build_cognitive_profile 生成
        skill_dir / "references" / "author-boundary.md": None,
        skill_dir / "references" / "anti-patterns.md": None,
        skill_dir / "references" / "examples.md": tpl_dir / "examples.md.tpl",
        skill_dir / "assets" / "style-memory.json": None,
        skill_dir / "assets" / "quality-rubric.json": tpl_dir / "quality-rubric.json.tpl",
        skill_dir / "assets" / "article-schema.json": tpl_dir / "article-schema.json.tpl",
        skill_dir / "assets" / "generation-policy.json": tpl_dir / "generation-policy.json.tpl",
        skill_dir / "evals" / "evals.json": tpl_dir / "evals.json.tpl",
    }

    for dest, tpl in files_to_generate.items():
        ensure_dir(dest.parent)
        if tpl:
            content = render_template(tpl, context)
            dest.write_text(content, encoding="utf-8")
        else:
            dest.write_text("[待生成]\n", encoding="utf-8")

    # 生成 manifest
    manifest_path = repo_dir / "state" / "manifests" / "v1.0.0.json"
    ensure_dir(manifest_path.parent)
    manifest = {
        "child_name": child_name,
        "version": version,
        "created_at": now,
        "sample_count": len(sample_files),
        "sample_sources": sample_sources,
        "files": {str(k.relative_to(skill_dir).as_posix()): True for k in files_to_generate.keys()},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 生成 release-index
    release_index_path = state_dir / "release-index.json"
    release_index = {
        "releases": [
            {
                "version": version,
                "tag": f"v{version}",
                "date": now,
                "type": "create",
                "change_summary": f"初始版本，基于 {len(sample_files)} 篇样文生成",
                "eval_score": None,
            }
        ],
        "active_version": version,
    }
    release_index_path.write_text(json.dumps(release_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 初始化 learning-log
    log_path = state_dir / "learning-log.jsonl"
    log_path.write_text("", encoding="utf-8")

    # 首版提交
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"init: create child {child_name} v{version}"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "tag", f"v{version}"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # 生成 create-summary 报告
    summary_path = reports_dir / "create-summary.md"
    summary_lines = [
        "# Create Summary",
        "",
        f"**Child Name:** {child_name}",
        f"**Version:** {version}",
        f"**Created At:** {now}",
        f"**Sample Count:** {len(sample_files)}",
        "",
        "## Sample Sources",
        "",
    ]
    for src in sample_sources:
        summary_lines.append(f"- `{src}`")
    summary_lines.extend([
        "",
        "## Generated Files",
        "",
    ])
    for dest, tpl in files_to_generate.items():
        rel = dest.relative_to(skill_dir).as_posix()
        status = "from template" if tpl else "placeholder"
        summary_lines.append(f"- `{rel}` ({status})")
    summary_lines.extend([
        "",
        "## Next Steps",
        "",
        "1. Run `build_style_profile.py` to extract 14-dimension style profile.",
        "2. Run `build_cognitive_profile.py` to generate editorial rules and boundary.",
        "3. Publish with `publish_child.py` to activate the skill.",
        "",
    ])
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    logger.info("Canonical repo created at: %s", repo_dir)
    logger.info("Child skill skeleton ready: %s", skill_dir)
    logger.info("Create summary: %s", summary_path)
    return repo_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new writer child skill")
    parser.add_argument("child_name", help="Name of the child skill (e.g., 'example')")
    parser.add_argument("samples_dir", help="Directory containing sample articles")
    parser.add_argument(
        "--factory-dir",
        default=DEFAULT_FACTORY_DIR,
        help="Base directory for writing factory children",
    )
    args = parser.parse_args()
    args.child_name = sanitize_child_name(args.child_name)

    with LogContext(logger, child_name=args.child_name, step="create"):
        try:
            repo_dir = create_child(args.child_name, args.samples_dir, args.factory_dir)
            print(repo_dir)
        except Exception as e:
            logger.exception("Failed to create child %s: %s", args.child_name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
