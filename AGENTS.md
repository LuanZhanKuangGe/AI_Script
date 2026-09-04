# 项目规则

## 项目概览

个人媒体管理工具集合：视频网站爬虫/下载器、文件整理脚本和浏览器油猴脚本。

## 目录结构

- `script/` — Python 爬虫脚本（各站点一个文件，如 `iwara.py`、`hanime.py`、`rule34.py`），以及对应的 `data-*.json` 配置/数据文件
- `userscripts/` — 油猴用户脚本（`.user.js`）
- 根目录 — 独立工具脚本（文件清理、视频处理等）和 GUI 入口（`run_all_gui.py`、`tdl_ui.py`）
- `rss-bridge/` — RSS Bridge 相关
- 运行时产物（`logs/`、`__pycache__/`、`crawl_cache.json`、`artist_last_run.json`）不要手动编辑或提交无关改动

## 代码规范

- 代码风格遵循项目现有规范
- 避免不必要的注释，除非用户明确要求
- 保持代码简洁

## 操作规范

- 每次修改完成后，自动提交到 git
- 提交信息简洁明了，说明做了什么修改
- 不主动创建新文件，除非用户明确要求

## Linting & Typecheck

- 本仓库无统一构建/包管理（无 package.json、requirements.txt），纯 Python 脚本 + 油猴脚本
- 修改 Python 脚本后可用 `python -m py_compile <file>` 做语法检查；无正式 lint/typecheck 命令时跳过
- 如果 lint/typecheck 失败，修复问题后重新提交

## Git 提交规则

- 提交前必须先运行 lint 和 typecheck
- 如果 lint/typecheck 失败，不要提交
- 提交信息格式：`{short summary}`
- 简短描述修改内容即可

## 完成标准

- 功能实现完成
- Linting/Typecheck 通过
- Git 提交完成
