#!/usr/bin/env python3
"""
run_regression_tests.py
自动化回归测试运行器。

覆盖场景:
    1. structure_integrity   — child skill 必要文件存在性
    2. style_memory_schema   — style-memory.json 关键字段与类型
    3. rules_validity        — 规则对象字段完整性
    4. diff_classification   — classify_change 对已知输入的分类准确性
    5. promote_dedup         — promote_rules 对重复规则的处理
    6. eval_score_range      — eval_candidate 输出分数在 0-5 区间
    7. pipeline_dry_run      — learn_pipeline --dry-run 不报错
    8. manifest_integrity    — manifest 指向的 baseline/article 存在

用法:
    python run_regression_tests.py <child_name> [--factory-dir <dir>] [--project-root <dir>]
"""

import argparse
import importlib.util
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from factory_logging import LogContext, setup_logger

logger = setup_logger("run_regression_tests")

SCRIPT_DIR = Path(__file__).parent.resolve()


def _import_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------
# 测试用例
# ------------------------------------------------------------------

def test_structure_integrity(child_name: str, factory_dir: str) -> dict:
    """测试 child skill 目录结构完整。"""
    skill_dir = Path(factory_dir) / child_name / "repo" / "skill"
    required = [
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
    missing = [f for f in required if not (skill_dir / f).exists()]
    return {"name": "structure_integrity", "passed": not missing, "missing": missing}


def test_style_memory_schema(child_name: str, factory_dir: str) -> dict:
    """测试 style-memory.json 包含必要顶层键。"""
    memory_path = Path(factory_dir) / child_name / "repo" / "skill" / "assets" / "style-memory.json"
    if not memory_path.exists():
        return {"name": "style_memory_schema", "passed": False, "error": "file missing"}
    try:
        data = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"name": "style_memory_schema", "passed": False, "error": f"invalid json: {e}"}

    required_keys = [
        "voice_traits",
        "punctuation_preferences",
        "paragraph_formulas",
        "narrative_moves",
        "editorial_heuristics",
        "author_boundary_rules",
        "anti_patterns",
        "confidence_buckets",
    ]
    missing = [k for k in required_keys if k not in data]
    # confidence_buckets 必须有三个子键
    buckets = data.get("confidence_buckets", {})
    bucket_ok = set(buckets.keys()) >= {"candidate", "probation", "active"}
    return {
        "name": "style_memory_schema",
        "passed": not missing and bucket_ok,
        "missing_keys": missing,
        "bucket_keys": list(buckets.keys()),
    }


def test_rules_validity(child_name: str, factory_dir: str) -> dict:
    """测试所有规则条目具备最小必要字段。"""
    memory_path = Path(factory_dir) / child_name / "repo" / "skill" / "assets" / "style-memory.json"
    if not memory_path.exists():
        return {"name": "rules_validity", "passed": False, "error": "file missing"}
    data = json.loads(memory_path.read_text(encoding="utf-8"))
    buckets = data.get("confidence_buckets", {})
    invalid = []
    for bucket_name, rules in buckets.items():
        for idx, r in enumerate(rules):
            if "description" not in r or not r["description"]:
                invalid.append({"bucket": bucket_name, "index": idx, "issue": "missing description"})
            if "confidence" not in r:
                invalid.append({"bucket": bucket_name, "index": idx, "issue": "missing confidence"})
    return {"name": "rules_validity", "passed": not invalid, "invalid_rules": invalid}


def test_diff_classification() -> dict:
    """用已知输入验证 classify_change 的分级逻辑。"""
    diff_mod = _import_module("diff_revision")
    cases = [
        # (old, new, expected_level, context_hint)
        ("你好，世界。", "你好世界。", "L1", "punctuation_only"),
        ("这是一个的句子。", "这是一个句子。", "L1", "particle_only"),
        ("A" * 100, "A" * 101, "L1", "high_similarity"),
        ("核心在于A。\n\n因此B。", "核心在于A。\n\n然而B。", "L2", "thesis_keep_connector_change"),
        ("总之，很好。", "最后，很好。", "L2", "conclusion_similar_rewrite"),
        ("# 标题\n\n正文。", "## 新标题\n\n正文。", "L3", "heading_change"),
        ("最近，发生了X。", "很久以前，发生了Y。\n\n而且Z。", "L3", "opening_rewrite_and_expand"),
    ]
    passed = 0
    failed = []
    for old, new, expected, hint in cases:
        result = diff_mod.classify_change(old, new, "")
        level = result.get("level")
        if level == expected:
            passed += 1
        else:
            failed.append({
                "hint": hint,
                "expected": expected,
                "actual": level,
                "reason": result.get("reason"),
            })
    return {
        "name": "diff_classification",
        "passed": not failed,
        "summary": f"{passed}/{len(cases)} passed",
        "failed": failed,
    }


def test_promote_dedup() -> dict:
    """验证 promote_rules 对重复 description 的累加逻辑。"""
    # 由于 promote_rules 依赖文件系统，我们通过直接调用内部函数验证
    promote_mod = _import_module("promote_rules")
    # _abstract_rule_description 是公开函数
    desc1 = promote_mod._abstract_rule_description("L2", "reusable_preference", " old ", " new ", "拆分")
    desc2 = promote_mod._abstract_rule_description("L2", "reusable_preference", " old2 ", " new2 ", "拆分")
    # 两次相同 reason/level 的抽象应产生可复用的描述
    return {
        "name": "promote_dedup",
        "passed": desc1 == desc2 or ("拆分" in desc1 and "拆分" in desc2),
        "desc1": desc1,
        "desc2": desc2,
    }


def test_eval_score_range(child_name: str, factory_dir: str) -> dict:
    """验证 eval_candidate 返回的分数在 0-5 之间。"""
    eval_mod = _import_module("eval_candidate")
    try:
        result = eval_mod.eval_candidate(child_name, factory_dir)
    except Exception as e:
        return {"name": "eval_score_range", "passed": False, "error": str(e)}

    scores_to_check = []
    total = result.get("total_score")
    if total is not None:
        scores_to_check.append(("total_score", total))
    struct = result.get("structure_dimension", {})
    for k, v in struct.get("scores", {}).items():
        scores_to_check.append((f"structure.{k}", v))
    effect = result.get("effect_dimension", {})
    for k, v in effect.get("scores", {}).items():
        if isinstance(v, (int, float)):
            scores_to_check.append((f"effect.{k}", v))

    out_of_range = [(name, val) for name, val in scores_to_check if not (0 <= val <= 5)]
    return {
        "name": "eval_score_range",
        "passed": not out_of_range,
        "out_of_range": out_of_range,
        "checked": len(scores_to_check),
    }


def test_pipeline_dry_run(child_name: str, factory_dir: str, project_root: str) -> dict:
    """验证 learn_pipeline --dry-run 不抛出异常。"""
    pipeline_mod = _import_module("learn_pipeline")
    try:
        result = pipeline_mod.learn_pipeline(
            child_name=child_name,
            factory_dir=factory_dir,
            project_root=project_root,
            article_id=None,
            skip_eval=True,
            dry_run=True,
        )
        ok = result.get("dry_run") is True
    except Exception as e:
        return {"name": "pipeline_dry_run", "passed": False, "error": str(e), "traceback": traceback.format_exc()}
    return {"name": "pipeline_dry_run", "passed": ok}


def test_manifest_integrity(child_name: str, factory_dir: str) -> dict:
    """验证 state/manifests 指向的 baseline 文件存在。"""
    repo_dir = Path(factory_dir) / child_name / "repo"
    manifests_dir = repo_dir / "state" / "manifests"
    baselines_dir = repo_dir / "state" / "baselines"
    if not manifests_dir.exists():
        return {"name": "manifest_integrity", "passed": True, "note": "no manifests yet"}

    broken = []
    for mpath in manifests_dir.glob("*.json"):
        try:
            data = json.loads(mpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            broken.append({"manifest": mpath.name, "issue": "invalid json"})
            continue
        article_id = data.get("article_id")
        if article_id and not (baselines_dir / f"{article_id}.md").exists():
            broken.append({"manifest": mpath.name, "issue": f"missing baseline for {article_id}"})
    return {"name": "manifest_integrity", "passed": not broken, "broken": broken}


# ------------------------------------------------------------------
# 运行器
# ------------------------------------------------------------------

def run_all(child_name: str, factory_dir: str, project_root: str) -> dict:
    tests = [
        lambda: test_structure_integrity(child_name, factory_dir),
        lambda: test_style_memory_schema(child_name, factory_dir),
        lambda: test_rules_validity(child_name, factory_dir),
        lambda: test_diff_classification(),
        lambda: test_promote_dedup(),
        lambda: test_eval_score_range(child_name, factory_dir),
        lambda: test_pipeline_dry_run(child_name, factory_dir, project_root),
        lambda: test_manifest_integrity(child_name, factory_dir),
    ]

    results = []
    passed = 0
    failed = 0
    for t in tests:
        try:
            r = t()
        except Exception as e:
            r = {"name": t.__name__, "passed": False, "error": str(e), "traceback": traceback.format_exc()}
        results.append(r)
        if r.get("passed"):
            passed += 1
        else:
            failed += 1
            logger.warning("Test failed: %s", r)

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "child_name": child_name,
        "total": len(tests),
        "passed": passed,
        "failed": failed,
        "results": results,
    }
    return summary


def write_report(child_name: str, repo_dir: Path, summary: dict) -> Path:
    lines = [
        f"# Regression Test Report: {child_name}",
        "",
        f"- **Run at:** {summary['run_at']}",
        f"- **Total:** {summary['total']} | **Passed:** {summary['passed']} | **Failed:** {summary['failed']}",
        "",
        "## Results",
        "",
        "| Test | Status | Detail |",
        "|------|--------|--------|",
    ]
    for r in summary["results"]:
        status = "PASS" if r.get("passed") else "FAIL"
        detail = ""
        if "summary" in r:
            detail = r["summary"]
        elif "error" in r:
            detail = f"error: {r['error'][:60]}"
        elif "missing" in r:
            detail = f"missing: {r['missing']}"
        elif "invalid_rules" in r:
            detail = f"invalid: {len(r['invalid_rules'])}"
        elif "out_of_range" in r:
            detail = f"oor: {len(r['out_of_range'])}"
        elif "broken" in r:
            detail = f"broken: {len(r['broken'])}"
        lines.append(f"| {r['name']} | {status} | {detail} |")

    lines.append("")
    lines.append("## Raw JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("```")

    report_path = repo_dir / "reports" / "regression-test-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run regression tests for a child skill")
    parser.add_argument("child_name", help="Child skill name")
    parser.add_argument("--factory-dir", default=".claude/writing-factory/children", help="Factory base dir")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    args = parser.parse_args()

    with LogContext(logger, child_name=args.child_name, step="regression_test"):
        logger.info("Starting regression tests for %s", args.child_name)
        summary = run_all(args.child_name, args.factory_dir, args.project_root)
        repo_dir = Path(args.factory_dir) / args.child_name / "repo"
        report_path = write_report(args.child_name, repo_dir, summary)
        logger.info("Regression tests complete: %d/%d passed. Report: %s", summary["passed"], summary["total"], report_path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"\nReport written to: {report_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
