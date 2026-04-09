# 项目规则

## 代码规范

- 代码风格遵循项目现有规范
- 避免不必要的注释，除非用户明确要求
- 保持代码简洁

## 操作规范

- 每次修改完成后，自动提交到 git
- 提交信息简洁明了，说明做了什么修改
- 不主动创建新文件，除非用户明确要求

## 文件同步规则

- `sync_list.txt` 文件记录需要同步的文件列表
- 列表中的文件每次修改后，自动复制到 `\\Z4PRO-4B98\nvme13-133XXXX8510\docker\qinglong\scripts`
- 复制使用相对路径，保持目录结构

## Linting & Typecheck

- 修改代码后必须运行 lint 和 typecheck 命令
- 如果存在 lint 命令（如 `npm run lint`、`ruff check`、`eslint` 等），执行它
- 如果存在 typecheck 命令（如 `npm run typecheck`、`mypy` 等），执行它
- 如果项目没有这些命令，跳过此步骤
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
