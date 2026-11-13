#!/usr/bin/env bash
# 安装仓库自带的 Git hook。
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* tools/*.sh tools/lint_docs.py
echo "已设置 core.hooksPath=.githooks"
