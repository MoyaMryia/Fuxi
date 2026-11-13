# Fuxi

研究文档仓。当前只有仓库骨架、文档检查与 CI，课题内容按后续讨论补充。

## 目录约定

| 目录 | 内容 |
| --- | --- |
| `docs/` | 长期维护的说明、索引与课题文档 |
| `reports/` | 带日期的记录，只跟踪 Markdown |
| `tools/` | 检查与安装脚本 |
| `.claude/`、`CLAUDE.md` | 拒绝在 Claude Code 下工作的阻断配置与声明 |

## 检查

安装 hook：

```bash
tools/install-hooks.sh
```

运行检查：

```bash
tools/ci-local.sh repo      # 仓库卫生：体积上限、索引与忽略规则一致
tools/ci-local.sh docs      # Markdown 结构与链接检查
tools/ci-local.sh all       # 依次运行全部阶段
tools/ci-local.sh --staged  # 提交前检查，pre-commit hook 调用
```

CI 运行 repo 与 docs 两个阶段，命令与本地 pre-commit 相同。

## 文档

| 文档 | 内容 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 代理与提交者的工作约定 |

## 许可

GPL-3.0，见 [LICENSE](LICENSE)。
