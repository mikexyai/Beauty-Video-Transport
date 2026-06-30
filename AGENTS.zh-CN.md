# AGENTS.zh-CN.md

这是 `AGENTS.md` 的中文参考副本；`AGENTS.md` 是 worker-facing canonical 文件。

## 项目概览

Beauty Video Transport 是一个视频内容运营自动化项目，用于从 Douyin/Bilibili 收集、筛选、下载、验证、上传并审计 beauty 视频内容。

核心领域：

- AI Beauty Douyin → YouTube AI Beauty channel 自动化。
- Bilibili → YouTube 搬运 pipeline。
- YouTube 上传、上传后合规/健康检查。
- PostgreSQL 中的 upload/candidate/run-log 记录。
- 本地媒体验证和运营审计证据。

## PDD / Kanban / Codex 协作

`beauty` Hermes profile 是本项目的运营/PM 上下文。实现类工作应走 PDD-centered Kanban 流程，而不是临时直接改代码。

角色边界：

- `PDD` 负责执行落地：task packet、开发派发、证据、Test/Review gate、commit、Kanban completion。
- `PM` 负责 intake/planning：运营需求、实现计划、Kanban intake/planning card。
- `PD` / 内容策略 session 可提出频道、选题、标题/标签、视觉方向建议；不得修改生产脚本、创建开发 packet、派发 worker 或标记任务完成。
- Codex/Claude Code 只作为 development-stage worker。
- Test Agent / Reviewer Agent 只报告问题；修复必须通过新的 PDD-created task。

强制流程：

```text
Kanban → .hermes/tasks/TASK-000N.md → Codex/Claude dev → Test Agent → Reviewer Agent → PDD final gate → commit → Kanban done
```

必须遵守：

- `.hermes/protocols/non-recursion.md`
- `.hermes/protocols/codex-task-packet.md`
- `.hermes/protocols/verification-gates.md`
- `.hermes/protocols/platform-safety.md`
- Discord thread/session 身份检查见 `.hermes/protocols/discord-session-identity.md`

## 常用验证

AI Beauty 代码：

```bash
python -m unittest discover -s tests -p 'test_ai_beauty_core.py' -v
python -m compileall -q scripts tests/test_ai_beauty_core.py
```

YouTube profile/upload：

```bash
cd youtube-upload && python youtube_upload.py check-auth --profile default
cd youtube-upload && python youtube_upload.py list-channels --profile default
python scripts/youtube_profile_guard.py --profile default
python scripts/ai_beauty/upload_ai_beauty.py --aweme-id <aweme_id> --dry-run
```

## 安全约束

- 不提交 OAuth token、cookies、API key、client secret、DB password、下载媒体或分析帧。
- 不提交 `apiKey/`、`youtube-upload/config/`、`config/*`（示例文件除外）、`downloads/`、`outputs/`、`analysis/`。
- AI Beauty 与 Beauty Cosplay / Beauty Dancing 工作流保持隔离，除非用户明确要求修改共享逻辑。
- 真实 YouTube upload/delete 需要明确授权或已写入项目 skill/task 的 standing approval；默认先 dry-run。
- cron 修改必须记录 schedule、delivery、rollback 和验证证据。
