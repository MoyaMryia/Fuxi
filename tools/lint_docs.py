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

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6}) (.*)$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
REPORT_RE = re.compile(r"^reports/[^/]+/(RESULTS|AUDIT|REVIEW)\.md$")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "#")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def tracked_files() -> list[str]:
    return [p for p in git("ls-files", "-z", "*.md").split("\0") if p]


def changed_files(base_ref: str) -> list[str]:
    spec = "--cached" if base_ref == "--staged" else f"{base_ref}..HEAD"
    out = git("diff", spec, "--name-only", "--diff-filter=AMR", "-z", "--", "*.md")
    return [p for p in out.split("\0") if p]


def index_paths() -> set[str]:
    return {p for p in git("ls-files", "-z").split("\0") if p}


def read_staged(path: str) -> str:
    return git("show", f":{path}")


def read_worktree(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def scan(text: str) -> tuple[list[tuple[int, str]], list[int]]:
    """返回围栏之外的行（带行号）与未闭合围栏的起始行。"""
    outside: list[tuple[int, str]] = []
    unclosed: list[int] = []
    fence: tuple[str, int, int] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                marker = match.group(1)
                fence = (marker[0], len(marker), number)
                continue
            outside.append((number, line))
        elif (
            match
            and match.group(1)[0] == fence[0]
            and len(match.group(1)) >= fence[1]
            and not match.group(2).strip()
        ):
            fence = None
    if fence is not None:
        unclosed.append(fence[2])
    return outside, unclosed


def check_structure(text: str) -> list[str]:
    problems: list[str] = []

    if not text.endswith("\n"):
        problems.append("文件末尾缺少换行")
    if text.endswith("\n\n"):
        problems.append("文件末尾有多余空行")

    outside, unclosed = scan(text)
    for line in unclosed:
        problems.append(f"第 {line} 行的代码围栏未闭合")

    for number, line in outside:
        if line != line.rstrip():
            problems.append(f"第 {number} 行有行尾空白")
        if "\t" in line:
            problems.append(f"第 {number} 行含制表符")

    headings: list[tuple[int, int]] = []
    for number, line in outside:
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


def check_links(path: str, text: str, exists) -> list[str]:
    problems: list[str] = []
    base = Path(path).parent
    outside, _ = scan(text)
    for number, line in outside:
        for target in LINK_RE.findall(INLINE_CODE_RE.sub("", line)):
            if target.startswith(SKIP_SCHEMES):
                continue
            local = target.split("#", 1)[0]
            if not local:
                continue
            if not exists((base / local).as_posix()):
                problems.append(f"第 {number} 行的链接目标不存在：{local}")
    return problems


def check_report(text: str) -> list[str]:
    outside, _ = scan(text)
    for _, line in outside:
        if re.fullmatch(r"## 适用范围\s*", line):
            return []
    return ["缺少“## 适用范围”一节"]


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

    worktree_exists = lambda rel: Path(rel).exists()  # noqa: E731

    if mode == "all":
        files = tracked_files()
        load = read_worktree
        exists = worktree_exists
    elif mode == "staged":
        files = changed_files("--staged")
        load = read_staged
        known = index_paths()
        exists = lambda rel: rel in known or any(p.startswith(rel.rstrip("/") + "/") for p in known)  # noqa: E731
    else:
        files = changed_files(base_ref)
        load = read_worktree
        exists = worktree_exists

    failures = 0
    for path in files:
        text = load(path)
        problems = check_structure(text)
        problems += check_links(path, text, exists)
        if REPORT_RE.match(path):
            problems += check_report(text)
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
