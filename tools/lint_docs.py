#!/usr/bin/env python3
"""Markdown 检查。只用标准库，不联网。

用法：
    tools/lint_docs.py                  检查全部跟踪的 Markdown
    tools/lint_docs.py --staged         检查暂存区中的 Markdown
    tools/lint_docs.py --base-ref <sha> 检查提交范围内的 Markdown
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6}) (.*)$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
REPORT_RE = re.compile(r"^reports/[^/]+/(RESULTS|AUDIT|REVIEW)\.md$")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "#")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def tracked_files() -> list[str]:
    return [p for p in git("ls-files", "-z", "*.md").split("\0") if p]


def staged_files() -> list[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=AM", "-z", "--", "*.md")
    return [p for p in out.split("\0") if p]


def changed_files(base_ref: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=AM", "-z", f"{base_ref}..HEAD", "--", "*.md")
    return [p for p in out.split("\0") if p]


def read_staged(path: str) -> str:
    return git("show", f":{path}")


def read_worktree(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def outside_fences(text: str) -> list[tuple[int, str]]:
    """返回代码围栏之外的行，保留行号。"""
    rows: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            rows.append((number, line))
    return rows


def check_structure(path: str, text: str) -> list[str]:
    problems: list[str] = []

    if not text.endswith("\n"):
        problems.append("文件末尾缺少换行")
    if text.endswith("\n\n"):
        problems.append("文件末尾有多余空行")

    fence_count = sum(1 for line in text.splitlines() if FENCE_RE.match(line))
    if fence_count % 2:
        problems.append(f"代码围栏未闭合（{fence_count} 个）")

    for number, line in outside_fences(text):
        if line != line.rstrip():
            problems.append(f"第 {number} 行有行尾空白")
        if "\t" in line:
            problems.append(f"第 {number} 行含制表符")

    headings: list[tuple[int, int]] = []
    for number, line in outside_fences(text):
        match = HEADING_RE.match(line)
        if match:
            headings.append((number, len(match.group(1))))

    h1 = [n for n, level in headings if level == 1]
    if not h1:
        problems.append("缺少一级标题")
    elif len(h1) > 1:
        problems.append(f"一级标题出现 {len(h1)} 次（第 {h1[0]}、{h1[-1]} 行）")

    for index, (number, level) in enumerate(headings):
        if index == 0 and level != 1:
            problems.append(f"第 {number} 行的首个标题不是一级标题")
        elif index > 0 and level > headings[index - 1][1] + 1:
            problems.append(f"第 {number} 行的标题层级跳跃")

    return problems


def check_links(path: str, text: str) -> list[str]:
    problems: list[str] = []
    base = Path(path).parent
    for number, line in outside_fences(text):
        for target in LINK_RE.findall(line):
            if target.startswith(SKIP_SCHEMES):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            if not (base / local).exists():
                problems.append(f"第 {number} 行的链接目标不存在：{local}")
    return problems


def check_report(path: str, text: str) -> list[str]:
    if not REPORT_RE.match(path):
        return []
    if "## 适用范围" not in text:
        return ["缺少“## 适用范围”一节"]
    return []


def main(argv: list[str]) -> int:
    mode = "all"
    base_ref = ""
    args = argv[1:]
    while args:
        arg = args.pop(0)
        if arg == "--staged":
            mode = "staged"
        elif arg == "--base-ref":
            if not args:
                print("--base-ref 缺少参数", file=sys.stderr)
                return 2
            mode = "base"
            base_ref = args.pop(0)
        else:
            print(f"未知参数：{arg}", file=sys.stderr)
            return 2

    if mode == "all":
        files = tracked_files()
        load = read_worktree
    elif mode == "staged":
        files = staged_files()
        load = read_staged
    else:
        files = changed_files(base_ref)
        load = read_worktree

    failures = 0
    for path in files:
        text = load(path)
        problems = check_structure(path, text)
        problems += check_links(path, text)
        problems += check_report(path, text)
        for problem in problems:
            print(f"{path}: {problem}", file=sys.stderr)
        if problems:
            failures += 1

    if failures:
        print(f"文档检查未通过：{failures}/{len(files)} 个文件有问题。", file=sys.stderr)
        return 1

    print(f"文档检查：通过（{len(files)} 个文件）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
