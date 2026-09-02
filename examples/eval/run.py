#!/usr/bin/env python3
"""plan-preflight regression eval.

Three commands:

  python3 examples/eval/run.py list
      Show the cases and what each one tests.

  python3 examples/eval/run.py prepare [CASE ...]
      Copy the chosen cases (default: all) into a fresh run directory under
      examples/eval/.runs/<UTC stamp>/ and print the /plan-preflight
      invocation for each. Only the case files are copied; the answer keys
      stay in keys/ so reviewers never see them.

  python3 examples/eval/run.py check RUN_DIR [CASE ...]
      After the gate has run, compare each case's outcome (review log,
      edited plan, companions) against its key. Exit code 1 on any failure.

The checker reads the gate's default log location, <plan-stem>.review.md
next to the plan (it also accepts <plan>.review.md and any *.review.md in
the case directory).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
CASES_DIR = EVAL_DIR / "cases"
KEYS_DIR = EVAL_DIR / "keys"
RUNS_DIR = EVAL_DIR / ".runs"


# ---------- helpers ----------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def all_cases() -> list[str]:
    return sorted(p.name for p in CASES_DIR.iterdir() if p.is_dir())


def load_key(case: str) -> dict:
    return json.loads((KEYS_DIR / f"{case}.json").read_text(encoding="utf-8"))


def section_text(markdown: str, heading: str) -> str | None:
    """Return the body of the section whose heading line equals `heading`,
    up to the next heading of the same or a higher level."""
    lines = markdown.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading.strip():
            start = i
            break
    if start is None:
        return None
    body = []
    for line in lines[start + 1:]:
        m = re.match(r"^(#{1,6})\s", line)
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body).strip()


def find_log(case_dir: Path, plan: str) -> Path | None:
    stem = Path(plan).stem
    candidates = [case_dir / f"{stem}.review.md", case_dir / f"{plan}.review.md"]
    for c in candidates:
        if c.exists():
            return c
    found = sorted(case_dir.glob("*.review.md"))
    return found[0] if found else None


def parse_log(text: str) -> dict:
    verdicts = re.findall(r"GATE\s*[:\-]?\s*(PASS|FAIL)", text, re.I)
    rounds = [int(n) for n in re.findall(r"^#{1,6}\s*R(\d+)\b", text, re.M)]
    if not rounds:
        rounds = [int(n) for n in re.findall(r"\[PROGRESS\]\s*R(\d+)", text)]
    if not rounds:
        rounds = [int(n) for n in re.findall(r"\bR(\d+)\s*[:\-]", text)]
    tags = sorted(set(re.findall(r"\[[a-z][a-z0-9-]*\]", text)))
    return {
        "verdict": verdicts[-1].upper() if verdicts else None,
        "rounds": max(rounds) if rounds else None,
        "tags": tags,
    }


# ---------- commands ----------

def cmd_list() -> int:
    for case in all_cases():
        key = load_key(case)
        exp = key["expect"]
        print(f"{case}")
        print(f"  expect: {exp['verdict']} within {exp['max_rounds']} round(s); "
              f"plan {'unchanged' if exp['plan_unchanged'] else 'edited'}; "
              f"must catch {len(exp['must_catch'])}")
        print(f"  tests:  {key['tests']}")
    return 0


def cmd_prepare(cases: list[str]) -> int:
    cases = cases or all_cases()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / stamp
    run_dir.mkdir(parents=True)
    print(f"run dir: {run_dir}\n")
    for case in cases:
        src = CASES_DIR / case
        if not src.is_dir():
            print(f"unknown case: {case}", file=sys.stderr)
            return 2
        dst = run_dir / case
        shutil.copytree(src, dst)
        manifest = {str(p.relative_to(dst)): sha256(p) for p in sorted(dst.rglob("*")) if p.is_file()}
        (dst / ".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        key = load_key(case)
        targets = ",".join(str(dst / f) for f in [key["plan"], *key["companions"]])
        print(f"{case}\n  /plan-preflight {targets} --codex off\n")
    print("Run each invocation in Claude Code, then:\n"
          f"  python3 {Path(__file__).relative_to(Path.cwd()) if Path(__file__).is_relative_to(Path.cwd()) else Path(__file__)} check {run_dir}")
    return 0


def check_case(run_dir: Path, case: str) -> tuple[bool, list[str]]:
    key = load_key(case)
    exp = key["expect"]
    case_dir = run_dir / case
    lines: list[str] = []
    ok_all = True

    def result(name: str, ok: bool, detail: str = "") -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        mark = "PASS" if ok else "FAIL"
        lines.append(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    if not case_dir.is_dir():
        return False, [f"  [FAIL] case directory missing: {case_dir}"]

    manifest_path = case_dir / ".manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    # Log-based assertions
    log_path = find_log(case_dir, key["plan"])
    if log_path is None:
        result("review log present", False, "no *.review.md in the case directory")
        parsed = {"verdict": None, "rounds": None, "tags": []}
        log_text = ""
    else:
        log_text = log_path.read_text(encoding="utf-8")
        parsed = parse_log(log_text)
        result("review log present", True, log_path.name)

    result("verdict", parsed["verdict"] == exp["verdict"],
           f"expected {exp['verdict']}, got {parsed['verdict']}")
    if parsed["rounds"] is None:
        result("rounds", False, "round count not found in log")
    else:
        result("rounds", parsed["rounds"] <= exp["max_rounds"],
               f"{parsed['rounds']} round(s), max {exp['max_rounds']}")

    # File-based assertions
    plan_path = case_dir / key["plan"]
    plan_changed = manifest.get(key["plan"]) != sha256(plan_path) if plan_path.exists() else None
    if plan_changed is None:
        result("plan file present", False, "plan missing")
    elif exp["plan_unchanged"]:
        result("plan unchanged", not plan_changed, "edited" if plan_changed else "byte-identical")
    else:
        result("plan edited", bool(plan_changed), "byte-identical (no fix applied)" if not plan_changed else "edited")

    for rel in exp["unchanged_files"]:
        p = case_dir / rel
        same = p.exists() and manifest.get(rel) == sha256(p)
        result(f"unchanged: {rel}", same, "" if same else "modified or missing")

    baseline_plan = (CASES_DIR / case / key["plan"]).read_text(encoding="utf-8")
    current_plan = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    for heading in exp["unchanged_sections"]:
        before = section_text(baseline_plan, heading)
        after = section_text(current_plan, heading)
        result(f"section unchanged: {heading}", before is not None and before == after,
               "missing" if after is None else ("modified" if before != after else ""))

    low = log_text.lower()
    for item in exp["must_catch"]:
        hit = next((k for k in item["any_of"] if k.lower() in low), None)
        result(f"caught {item['id']}", hit is not None,
               f"matched '{hit}'" if hit else f"none of {item['any_of']} in log")

    for tag in exp["required_tags"]:
        result(f"tag {tag}", tag in log_text)

    restore = sorted(case_dir.glob("*.pre-gate-*"))
    lines.append(f"  info: tags {parsed['tags'] or '-'} · restore points {len(restore)}")
    return ok_all, lines


def cmd_check(run_dir: Path, cases: list[str]) -> int:
    if not run_dir.is_dir():
        print(f"not a directory: {run_dir}", file=sys.stderr)
        return 2
    # Accept either the run root or a single case directory.
    if (run_dir / ".manifest.json").exists():
        cases = [run_dir.name]
        run_dir = run_dir.parent
    if not cases:
        cases = sorted(p.name for p in run_dir.iterdir() if (p / ".manifest.json").exists())
    if not cases:
        print("no prepared cases found under the run dir", file=sys.stderr)
        return 2
    failures = 0
    for case in cases:
        ok, lines = check_case(run_dir, case)
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {case}")
        print("\n".join(lines))
        print()
    total = len(cases)
    print(f"{total - failures}/{total} cases passed")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__.strip())
        return 0
    cmd, args = argv[1], argv[2:]
    if cmd == "list":
        return cmd_list()
    if cmd == "prepare":
        return cmd_prepare(args)
    if cmd == "check":
        if not args:
            print("check needs a run directory", file=sys.stderr)
            return 2
        return cmd_check(Path(args[0]).resolve(), args[1:])
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
