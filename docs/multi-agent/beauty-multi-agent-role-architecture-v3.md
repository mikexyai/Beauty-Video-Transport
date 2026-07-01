# Beauty Video Transport 多 Agent 角色协作实施方案 v3（空白 Profile 方案）

## 目的

本文档基于 `C:/Project/Multi-Agent/Car/hermes-multi-agent-role-architecture-v3.md` 的空白 profile 方案，为 Beauty Video Transport 设计一套适合当前媒体运营/上传/审计项目的多 Agent 角色协作体系。

核心目标：**降低长期治理风险，同时保持真实平台操作安全可控。** 固定角色 profile 不从当前 `beauty` profile clone，而是使用空白 profile 创建，再逐个配置角色身份、技能、工具边界和可选 Discord/Gateway 路由。

## 核心结论

采用以下结构：

```text
Profile = 固定 Agent 角色身份 / 权限边界
Session = 某个角色的一次对话或任务上下文
Skill = 角色可复用能力和项目操作规程
Kanban = 跨 Agent 任务状态与审计入口
Task packet = 开发/运营任务边界、allowed_files、验收标准
Report / Evidence = 交付结果、测试、审查、平台证据
Git commit = PDD 最终验收后的代码/文档落点
```

不使用单个 session 区分 PM / Dev / Test / Review / Strategy。Session 不能可靠隔离 skills、tools、memory、模型配置、Gateway routing 和角色权限。

固定角色使用独立 profile；短时并行分析仍可使用 `delegate_task`，但 `delegate_task` 不替代长期角色。

## 为什么 v3 不 clone `beauty`

`beauty` 当前是 PDD / 项目主控 / Discord 当前线程 / 最终验收 profile。它包含或可能包含：

- PDD 执行习惯与长期 memory；
- 当前 Discord thread/session routing；
- Kanban、task packet、final gate 上下文；
- YouTube/Douyin/Bilibili 运营历史；
- 较宽的工具、技能、文件访问和平台操作能力；
- 适合主控但不适合 worker 的上下文。

如果直接 clone 给 Dev/Test/Review/Strategy，会带来风险：

1. worker 继承 PDD 行为，越权 mark Kanban done、commit 或做最终验收；
2. worker 带入 PDD session/gateway 状态，造成 Discord routing 混乱；
3. worker 继承过宽工具权限或平台操作权限，增加真实上传/删除/DB 写入风险；
4. 后续清理 profile memory/config/skills 成本高；
5. 独立 Test/Review 是否真的独立会变得难以审计。

空白 profile 的优势：

- 角色边界干净；
- 默认没有历史会话和 memory 污染；
- 默认不会继承 PDD 的 Gateway/Discord 配置；
- 更适合长期固定团队成员；
- 出问题时更容易定位权限和上下文来源。

代价：

- 初始配置量增加；
- 需要手动写入 role identity / SOUL；
- 需要逐个配置常用 skills/toolsets/model/provider；
- 若接入 Discord/Gateway，需要单独配置 bot token 和 channel 权限。

总体判断：**初始治理成本略高，但长期安全性和可审计性显著更好。**

## 推荐 Profile 角色规划

第一阶段推荐创建最小治理角色集：

```text
beauty          = PDD / 主控 / 当前 Discord 执行入口 / 最终验收
beauty-pm       = intake / planning / Kanban planning card
beauty-dev      = development controller / Codex + Claude fallback 调度
beauty-test     = independent QA / evidence collector
beauty-review   = independent code + platform safety reviewer
```

第二阶段可按需增加：

```text
beauty-strategy   = content / analytics / channel strategy
beauty-ops        = media operations runner for approved operational tasks
beauty-compliance = post-upload compliance / health audit specialist
```

### 第一阶段角色职责矩阵

| Profile | 主要职责 | 不应做的事 | 典型 skills |
|---|---|---|---|
| `beauty` | 接需求、建/确认 Kanban、写 task packet、派发开发、最终验证、commit、complete Kanban | 默认不把最终验收交给 worker | `kanban-backed-pm-orchestration`, `codex`, `requesting-code-review`, 项目 skills |
| `beauty-pm` | 需求澄清、架构/运营计划、任务拆解、Kanban intake/planning | 不改生产脚本、不派发开发 worker、不 mark implementation done | `superpowers-brainstorming`, `superpowers-writing-plans`, `kanban-backed-pm-orchestration`, `plan` |
| `beauty-dev` | 读取 PDD task packet，调 Codex，失败后 Claude fallback，检查 result/diff | 不最终验收、不跳过 Test/Review、不扩大 allowed_files、不真实上传/删除 | `test-driven-development`, `systematic-debugging`, `codex`, `claude-code` |
| `beauty-test` | 独立测试、DB/status/dry-run、profile guard、ffprobe/yt-dlp/证据收集、测试报告 | 不修代码、不批准自己的修复、不执行未授权上传/删除 | `agency-evidence-collector`, `agency-api-tester`, 项目 workflow skills |
| `beauty-review` | 审查 diff、scope、安全、DB/cron/upload 平台风险、secret leak、AI Beauty/Cos/Dance 隔离 | 不修代码、不运行真实平台副作用、不关闭任务 | `requesting-code-review`, `agency-code-reviewer`, `github-code-review` |

### 第二阶段角色建议

| Profile | 适用时机 | 主要职责 | 禁止事项 |
|---|---|---|---|
| `beauty-strategy` | 需要长期内容/频道策略分离时 | AI Beauty / Cosplay / Dancing 内容策略、标题/tag、analytics 反馈、brief 文档 | 不改生产脚本、不派发 worker、不触碰 OAuth/上传 |
| `beauty-ops` | 运营任务频繁且需要与开发分离时 | 按批准 task packet 执行下载、上传、清理、记录证据 | 不改代码、不创建开发任务、不改变路由规则 |
| `beauty-compliance` | 上传后合规/健康检查复杂化时 | region restriction、版权/processing、post-upload audit、修复建议 | 默认不删除/重传，除非 task/skill 明确授权 |

第一阶段不建议立即启用 `beauty-ops` / `beauty-compliance`，因为它们涉及真实平台副作用和凭证治理。先把 Dev/Test/Review/PM 边界稳定下来。

## 空白 Profile 创建命令

推荐：

```bash
hermes profile create beauty-pm --description "Planning and Kanban intake for Beauty Video Transport. Does not implement production code or dispatch development workers."
hermes profile create beauty-dev --description "Development controller for bounded Beauty Video Transport task packets. Uses Codex first and Claude Code as narrow fallback."
hermes profile create beauty-test --description "Independent QA and evidence collector for Beauty Video Transport. Reports only and does not fix code."
hermes profile create beauty-review --description "Independent code, DB, cron, upload, and platform-safety reviewer for Beauty Video Transport diffs. Reports only."
```

可选第二阶段：

```bash
hermes profile create beauty-strategy --description "Content and analytics strategy advisor for AI Beauty, Beauty Cosplay, and Beauty Dancing. Writes strategy docs only unless explicitly authorized."
hermes profile create beauty-ops --description "Approved media operations runner for Beauty Video Transport. Executes bounded operational task packets and records evidence."
hermes profile create beauty-compliance --description "Independent post-upload compliance and health auditor for Beauty YouTube uploads. Reports or acts only within explicit task authorization."
```

不推荐：

```bash
hermes profile create beauty-dev --clone beauty
hermes profile create beauty-test --clone beauty
hermes profile create beauty-review --clone-all beauty
```

## 创建后验证

创建 profile 后必须验证：

```bash
hermes profile list
hermes profile show beauty-pm
hermes profile show beauty-dev
hermes profile show beauty-test
hermes profile show beauty-review
```

确认：

- 没有继承 `beauty` 的 Discord gateway routing；
- 没有继承 `beauty` 的 PDD memory；
- 没有继承当前 PDD session；
- 没有自动获得生产执行权限；
- description 与职责一致；
- profile-local 配置不提交到仓库。

## Profile 配置策略

### 第一阶段：空白 profile + 显式 skills 启动

先不要急着固化所有默认 skills。建议先用启动参数试运行：

```bash
hermes --profile beauty-pm --skills superpowers-brainstorming,superpowers-writing-plans,kanban-backed-pm-orchestration
hermes --profile beauty-dev --skills test-driven-development,systematic-debugging,codex,claude-code
hermes --profile beauty-test --skills agency-evidence-collector,agency-api-tester,douyin-ai-beauty-channel-manager
hermes --profile beauty-review --skills requesting-code-review,agency-code-reviewer,github-code-review
```

第二阶段角色：

```bash
hermes --profile beauty-strategy --skills douyin-ai-beauty-channel-manager,humanizer,superpowers-brainstorming
hermes --profile beauty-ops --skills douyin-ai-beauty-channel-manager,beauty-bilibili-youtube-pipeline,youtube-data-api-upload
hermes --profile beauty-compliance --skills beauty-youtube-post-upload-compliance-check,youtube-data-api-upload
```

### 第二阶段：pilot 通过后再固化默认配置

原则：

- 先显式，后固化；
- 先本地 CLI，后 Gateway；
- 先文档/低风险任务，后生产代码和真实平台任务；
- 涉及 YouTube 上传/删除、cookies、OAuth、DB migration、cron 的 profile 必须单独审核工具权限。

## Profile Identity / SOUL 模板

非 secret 角色模板放在：

```text
.hermes/roles/profile/beauty-pm.md
.hermes/roles/profile/beauty-dev.md
.hermes/roles/profile/beauty-test.md
.hermes/roles/profile/beauty-review.md
.hermes/roles/profile/beauty-strategy.md
```

安装到 profile-local 身份文件时，应复制到对应 profile 的本地配置/身份位置，而不是让 worker 读取 PDD 的身份。

每个身份文件至少包含：

```text
Role identity
Allowed responsibilities
Forbidden actions
Required repo protocols
Required report format
Discord/shared-room behavior
Non-recursion rules
Platform safety rules
```

## 统一非递归规则

所有 worker profile 必须遵守：

```text
Do not invoke Hermes unless your role explicitly requires launching a local coding worker and the current task packet authorizes it.
Do not spawn Codex, Claude, OpenCode, Copilot, or subagents unless you are beauty-dev and the task packet explicitly authorizes that worker call.
Do not create cron jobs.
Do not ask another agent to continue your work.
Do not mark Kanban tasks done.
Do not commit unless the PDD task packet explicitly authorizes it.
If blocked, write the blocker in the assigned result/report file and stop.
```

`beauty-dev` 是唯一可在授权 task packet 内调用 Codex/Claude Code 的长期 worker profile。即便如此，也只能按 task packet 执行。

## Discord / Gateway 使用建议

第一阶段先不接 Discord。推荐顺序：

1. 写 repo 方案和身份模板；
2. 创建空白 profile；
3. 配最小 skills/toolsets；
4. 本地 CLI pilot；
5. 通过后再配置 Discord/Gateway。

如果接入 Discord，推荐结构：

```text
#beauty-pdd        → profile: beauty
#beauty-planning   → profile: beauty-pm
#beauty-dev        → profile: beauty-dev
#beauty-test       → profile: beauty-test
#beauty-review     → profile: beauty-review
#beauty-strategy   → profile: beauty-strategy   # optional
```

关键要求：

- 不同 profile 不共用同一个 Discord bot token；
- 每个 bot 只进入自己的 channel/thread；
- worker 默认不响应其他 bot 消息；
- 不建议多个角色 bot 在同一 channel 自由互聊，避免循环触发；
- Discord 用于人类交互和摘要汇报，不作为唯一事实源；
- 正式状态只看 Kanban、task packet、report、evidence 和 git。

## 跨 Profile 通信协议

不同 profile 默认不共享：

- session 历史；
- memory；
- 当前对话上下文；
- 已加载 skills；
- 当前任务理解；
- Gateway routing。

不同 profile 可以共享：

- 同一个项目仓库；
- Kanban board；
- `.hermes/tasks/`；
- `.hermes/evidence/`；
- git diff / 工作区文件。

正式介质：

```text
Kanban board                         = 任务状态
.hermes/tasks/TASK-000N.md            = 任务范围、角色、验收标准
.hermes/tasks/TASK-000N-result.md     = Dev / Ops 结果
.hermes/tasks/TASK-000N-test-report.md = Test 报告
.hermes/tasks/TASK-000N-review.md     = Review 报告
.hermes/evidence/TASK-000N/           = 日志、截图、dry-run、DB/status、ffprobe、API 证据
```

推荐流转：

```text
User
  ↓
beauty / PDD
  ↓
Kanban task + task packet
  ↓
beauty-dev → Codex / Claude fallback
  ↓
TASK result
  ↓
beauty-test independent verification
  ↓
beauty-review independent review
  ↓
beauty / PDD final verification + commit + Kanban done
```

运营任务可使用：

```text
User / scheduled need
  ↓
beauty / PDD
  ↓
Kanban + operational task packet
  ↓
beauty-ops safe dry-run or explicitly approved operation
  ↓
beauty-test evidence verification
  ↓
beauty-review platform safety review
  ↓
beauty / PDD final gate
```

## Task Packet 必填信息

每个正式开发/运营任务必须有 repo-local task packet：

```text
.hermes/tasks/TASK-000N.md
```

至少包含：

```yaml
task_id: TASK-000N
kanban_task_id: <kanban task id>
role: beauty-dev | beauty-test | beauty-review | beauty-ops | beauty-strategy
methodology: obra/superpowers or explicit workflow summary
allowed_files:
  - path/to/file
out_of_scope:
  - path/to/forbidden-area
validation:
  - exact command
result_file: .hermes/tasks/TASK-000N-result.md
evidence_dir: .hermes/evidence/TASK-000N/
```

必须明确写入：

- 背景；
- 目标；
- 允许修改文件；
- 禁止修改文件/行为；
- 验收标准；
- 验证命令；
- 平台安全约束；
- 非递归规则；
- result/report/evidence 路径。

对于真实平台任务，还必须写明：

- 是否允许真实 upload/delete；
- 使用哪个 YouTube profile/channel；
- 是否需要 dry-run；
- DB 表范围；
- cleanup 规则；
- rollback 或 stop condition。

## Dev / Codex / Claude 策略

`beauty-dev` 是开发控制层，不建议直接承担大段代码开发。推荐：

```text
beauty-dev profile
  ↓ 读取 PDD task packet、检查范围
Codex CLI
  ↓ 修改代码、运行 cheap validation、写 result
Claude Code
  ↓ Codex 失败后的 narrow fallback
beauty-dev profile
  ↓ 检查 result / diff / validation 摘要
PDD → Test → Review
```

失败策略：

```text
Codex normal attempt
  ↓ failed
Codex retry exactly once using same model name with -pro suffix and reasoning effort medium
  ↓ failed
Claude Code narrow fallback
  ↓ failed
Report blocked
```

Codex/Claude 不应：

- 调 Hermes；
- 再调 Codex/Claude/OpenCode/subagents；
- 创建 cron jobs；
- 擅自 commit；
- 修改 allowed_files 外文件；
- 运行真实上传/删除，除非 task packet 明确授权且平台安全 gate 已写清。

## Test / Review Gate

PDD 在关闭任务前必须检查：

- Kanban task 状态与链接完整；
- task packet 存在；
- result 文件存在；
- test report 存在并通过；
- review report 存在并通过；
- 必要 evidence 存在；
- `git status --short --untracked-files=all` 只包含任务相关变更；
- `git diff --check` 通过；
- secret/cookie/token/client secret/password 扫描通过；
- 生成/下载/分析产物未误提交；
- DB/cron/upload 任务有 rollback/stop condition/verification evidence；
- AI Beauty / Cosplay / Dancing 隔离未破坏。

PDD 只有在 Test 和 Review gate 均通过后，才能 commit 和 complete Kanban。

## 项目共享文件位置

共享规则：

```text
AGENTS.md
AGENTS.zh-CN.md
.hermes/protocols/*.md
.hermes/roles/*.md
.hermes/templates/*.md
docs/multi-agent/*.md
```

任务与证据：

```text
.hermes/tasks/TASK-000N.md
.hermes/tasks/TASK-000N-result.md
.hermes/tasks/TASK-000N-test-report.md
.hermes/tasks/TASK-000N-review.md
.hermes/evidence/TASK-000N/
```

profile-local 配置不提交：

```text
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-dev/
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-test/
C:/Users/Michael Xiao/AppData/Local/hermes/profiles/beauty-review/
```

## 推荐落地步骤

### Step 1：写 repo 方案和 role identity 模板

产出：

```text
docs/multi-agent/beauty-multi-agent-role-architecture-v3.md
.hermes/roles/profile/beauty-pm.md
.hermes/roles/profile/beauty-dev.md
.hermes/roles/profile/beauty-test.md
.hermes/roles/profile/beauty-review.md
.hermes/roles/profile/beauty-strategy.md
```

### Step 2：创建空白 profiles

```bash
hermes profile create beauty-pm --description "Planning and Kanban intake for Beauty Video Transport. Does not implement production code or dispatch development workers."
hermes profile create beauty-dev --description "Development controller for bounded Beauty Video Transport task packets. Uses Codex first and Claude Code as narrow fallback."
hermes profile create beauty-test --description "Independent QA and evidence collector for Beauty Video Transport. Reports only and does not fix code."
hermes profile create beauty-review --description "Independent code, DB, cron, upload, and platform-safety reviewer for Beauty Video Transport diffs. Reports only."
```

### Step 3：安装 profile-local identity

把 `.hermes/roles/profile/*.md` 的内容复制到各 profile 的身份配置中。此步骤修改 profile-local 文件，不提交到项目仓库。

### Step 4：本地 CLI pilot

先不要接 Discord。使用低风险任务验证角色：

- `beauty-review` 审查一个 doc-only diff；
- `beauty-test` 对一个已完成 task 只跑测试并写报告；
- `beauty-pm` 对一个需求写 planning card；
- `beauty-dev` 消费一个 very small bounded packet。

### Step 5：评估后再配置 Discord/Gateway

只有在本地 pilot 成功后，才配置 Gateway。

## 一句话总结

**用空白 profile 创建固定角色，用 repo 文件定义共享规则，用 Kanban/task packet 限定任务，用 Codex 实现代码，用 Claude Code 兜底，用 Test/Review 独立验证；媒体运营和策略角色按第二阶段逐步启用，最后始终由 `beauty` / PDD 做最终验收。**
