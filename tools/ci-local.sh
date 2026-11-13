#!/usr/bin/env bash
# 本地与 CI 共用的检查命令。依赖安装留在 workflow 中。
#   tools/ci-local.sh <repo|docs>   运行一个阶段
#   tools/ci-local.sh --staged      提交前检查，pre-commit hook 调用
#   tools/ci-local.sh all           依次运行全部阶段
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

MAX_TRACKED_BYTES=$((5 * 1024 * 1024))

stage_repo() {
    local fails=0

    # 索引必须与忽略规则一致：被忽略却仍在跟踪的文件说明规则或索引有一方错了。
    local drift
    drift=$(git ls-files -i -c --exclude-standard || true)
    if [ -n "$drift" ]; then
        echo "以下文件被 .gitignore 忽略但仍在索引中：" >&2
        echo "$drift" >&2
        echo "取消跟踪（git rm --cached）或修正规则。" >&2
        fails=1
    fi

    # 单个跟踪文件不超过上限：按索引中的 blob 体积判断，工作区与暂存区不一致时也能拦住。
    local big
    big=$(git ls-files -s | while read -r mode sha stage path; do
        [ -n "$sha" ] || continue
        size=$(git cat-file -s "$sha" 2>/dev/null || echo 0)
        if [ "$size" -gt "$MAX_TRACKED_BYTES" ]; then
            awk -v s="$size" -v p="$path" 'BEGIN { printf "  %.1f MiB  %s\n", s / 1048576, p }'
        fi
    done)
    if [ -n "$big" ]; then
        echo "以下跟踪文件超过 5 MiB，请移到仓外并加入 .gitignore：" >&2
        echo "$big" >&2
        fails=1
    fi

    [ "$fails" -eq 0 ] || exit 1
    echo "仓库卫生：通过（$(git ls-files | wc -l) 个跟踪文件）" >&2
}

stage_docs() {
    python3 tools/lint_docs.py "$@"
}

run_stage() {
    case "$1" in
        repo) stage_repo ;;
        docs) shift; stage_docs "$@" ;;
        *) echo "未知阶段：$1" >&2; exit 2 ;;
    esac
}

staged() {
    local changed
    changed=$(git diff --cached --name-only)
    [ -n "$changed" ] || exit 0

    stage_repo
    # 文档阶段只读暂存区内容，工作区可以保持脏。
    stage_docs --staged
}

case "${1:---staged}" in
    --staged) staged ;;
    all) for s in repo docs; do echo "== $s ==" >&2; run_stage "$s"; done ;;
    *) run_stage "$@" ;;
esac
