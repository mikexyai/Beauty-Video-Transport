# 哔哩哔哩 / 抖音视频合规搬运到 YouTube 准备工作计划

> **For Hermes:** 本计划用于 `beauty-video-transport` profile 的运营准备，不执行下载、上传或自动化，只梳理前置准备与落地清单。

**Goal:** 建立一套可持续、合规、可追踪的视频从哔哩哔哩 / 抖音发布到 YouTube 的工作流。

**Architecture:** 先完成账号、授权、素材、工具链、内容规范、审核机制和自动化脚本的准备；再进入小批量试运行；最后沉淀为可重复执行的搬运 SOP。核心原则是只处理自有、已授权或明确可再发布的内容，避免版权、平台 TOS、隐私和广告收益风险。

**Tech Stack:** Hermes Agent profile、浏览器 / CLI 下载工具、视频处理工具 FFmpeg、字幕 / 翻译工具、YouTube Studio / YouTube Data API、表格或数据库记录、云盘 / 本地归档、监控与告警。

---

## 0. 合规边界

- 只搬运以下内容：
  - 自己原创的视频；
  - 已获得创作者明确授权的视频；
  - 公司 / 团队拥有版权的视频；
  - 许可证明确允许二次发布的视频。
- 不建议搬运：
  - 未授权的 B 站 / 抖音博主视频；
  - 带第三方音乐、影视、赛事、直播切片、商品广告素材的视频；
  - 包含未成年人、隐私信息、肖像权风险的视频；
  - 平台明确禁止下载、转载或商业使用的内容。
- 所有授权建议保留截图、聊天记录、合同或邮件，作为 YouTube 版权申诉证据。

---

## 1. 账号与权限准备

### 1.1 YouTube 频道准备

- 明确频道定位：例如美妆教程、好物测评、短视频合集、品牌内容分发等。
- 完成频道基础配置：
  - 频道名称；
  - 头像和 Banner；
  - 简介；
  - 联系邮箱；
  - 默认语言；
  - 国家 / 地区；
  - 品牌账号或个人账号归属。
- 开启必要功能：
  - 上传长视频；
  - 上传 Shorts；
  - 自定义缩略图；
  - 高级功能验证；
  - 两步验证。
- 如需自动上传，准备：
  - Google Cloud Project；
  - YouTube Data API v3；
  - OAuth Client；
  - refresh token 安全保存方式。

### 1.2 来源账号准备

- 哔哩哔哩：确认登录账号、收藏夹、稍后再看、创作者后台或授权来源列表。
- 抖音：确认素材来源、创作者授权记录、下载权限、无水印源文件获取方式。
- 若是团队内容：建立统一素材入口，避免从公开视频二次抓取低清版本。

### 1.3 安全与访问控制

- 不把账号密码写进脚本或明文配置。
- API token 放到 Hermes profile 专属配置或环境变量。
- 重要账号开启 2FA。
- 记录谁有上传、编辑、删除视频的权限。

---

## 2. 内容授权与版权准备

### 2.1 授权台账

建议建立一张表，字段包括：

| 字段 | 说明 |
|---|---|
| source_platform | bilibili / douyin |
| source_url | 原视频链接 |
| creator_name | 原作者 |
| authorization_status | 自有 / 已授权 / 待确认 / 不可用 |
| authorization_evidence | 授权截图 / 邮件 / 合同路径 |
| allowed_regions | 可发布地区 |
| allowed_monetization | 是否允许开收益 |
| allowed_editing | 是否允许剪辑 / 翻译 / 加字幕 |
| music_rights | 音乐版权状态 |
| publish_status | 待处理 / 已上传 / 已下架 |
| youtube_url | YouTube 链接 |

### 2.2 音乐与素材检查

- 确认背景音乐是否可在 YouTube 使用。
- 抖音热门 BGM 很容易触发 YouTube Content ID，需要提前替换或关闭收益预期。
- 贴纸、滤镜、字体、图片素材也可能有授权限制。

### 2.3 肖像权 / 隐私检查

- 避免未经同意搬运真人出镜内容。
- 包含地址、电话、车牌、聊天记录、订单信息时需打码。
- 涉及医疗、美容效果、减肥、投资等内容，要避免夸大宣传。

---

## 3. 素材获取与归档准备

### 3.1 原始素材优先级

优先级从高到低：

1. 创作者提供的原始无水印文件；
2. 团队内部工程文件或成片；
3. 平台允许下载的原文件；
4. 公开视频下载版本，仅在授权且平台规则允许时使用。

### 3.2 目录结构建议

```text
video-transport/
  sources/
    bilibili/
    douyin/
  raw/
    YYYY-MM-DD/<video_id>/
  processed/
    YYYY-MM-DD/<video_id>/
  thumbnails/
  subtitles/
    zh/
    en/
  metadata/
    pending/
    uploaded/
  authorization/
  logs/
```

### 3.3 文件命名规范

```text
<platform>_<source_id>_<creator>_<short_title>_<yyyyMMdd>.mp4
```

示例：

```text
douyin_7123456789_creatorA_makeup_tips_20260623.mp4
```

---

## 4. 视频处理准备

### 4.1 基础工具

- FFmpeg：转码、裁剪、音频替换、抽帧。
- MediaInfo / ffprobe：检查分辨率、码率、时长、音轨。
- 字幕工具：Whisper、剪映导出字幕、人工校对。
- 翻译工具：中英标题、简介、字幕翻译。
- 图片工具：缩略图生成、封面裁剪。

### 4.2 输出规格建议

#### YouTube Shorts

- 竖屏：1080x1920；
- 时长：通常 ≤ 60 秒，按最新 Shorts 规则确认；
- 格式：MP4 / H.264 / AAC；
- 标题可加 `#Shorts`，但不要堆砌标签。

#### YouTube 长视频

- 横屏优先：1920x1080；
- 竖屏合集可加背景 / 模糊填充；
- 音量统一；
- 避免重复片头片尾影响留存。

### 4.3 内容本地化

- 中文标题翻译成自然英文，不要直译。
- 简介中注明来源和授权方式。
- 添加英文字幕可显著提升国际受众理解。
- 根据 YouTube 受众重写标题与描述，而不是复制 B 站 / 抖音标题。

---

## 5. YouTube 元数据准备

### 5.1 每条视频必备信息

- YouTube 标题；
- 简介；
- 标签；
- 分类；
- 是否 Shorts；
- 缩略图路径；
- 字幕路径；
- 发布时间；
- 播放列表；
- 是否开启收益；
- 是否儿童内容；
- 来源链接和授权备注。

### 5.2 标题策略

- 标题前 50–70 个英文字符最重要。
- 不使用误导性标题。
- 保留关键词：makeup、skincare、beauty、tutorial、before after、review 等。
- 避免夸大医疗 / 功效承诺。

### 5.3 简介模板

```text
Original source: <source_url>
Creator / Rights holder: <creator_name>
Uploaded with permission.

English summary:
<short summary>

#beauty #makeup #skincare
```

如是自有内容，可写：

```text
This video is owned by our team and republished for our YouTube audience.
```

---

## 6. 自动化与 Hermes Profile 准备

### 6.1 Hermes profile 配置目标

当前 profile：`beauty-video-transport`

建议它负责：

- 记录待处理来源链接；
- 检查授权台账；
- 生成视频处理任务；
- 生成 YouTube 标题 / 简介 / 标签；
- 调用 FFmpeg 处理视频；
- 调用 YouTube API 上传；
- 上传后写回台账；
- 定期检查上传状态、版权声明、播放数据。

### 6.2 配置项准备

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `YOUTUBE_CHANNEL_ID`
- `BILIBILI_COOKIE`（如确有合规需求）
- `DOUYIN_COOKIE`（如确有合规需求）
- `VIDEO_WORKDIR`
- `AUTHORIZATION_LEDGER_PATH`
- `DEFAULT_LANGUAGE`
- `DEFAULT_UPLOAD_PRIVACY`：建议初期用 `private` 或 `unlisted`

### 6.3 自动化阶段划分

1. 人工准备素材和授权；
2. Hermes 只生成元数据草稿；
3. Hermes 处理视频并输出待审核文件；
4. 人工审核后上传为 private；
5. 人工确认无版权问题后公开；
6. 后续再考虑全自动上传。

---

## 7. 质量审核准备

### 7.1 上传前检查清单

- [ ] 是否有授权证据；
- [ ] 是否有音乐版权风险；
- [ ] 是否有水印 / 平台 Logo；
- [ ] 是否包含敏感个人信息；
- [ ] 分辨率和比例是否正确；
- [ ] 声音是否正常；
- [ ] 字幕是否准确；
- [ ] 标题是否自然；
- [ ] 简介是否包含来源与授权说明；
- [ ] 缩略图是否不误导；
- [ ] 是否设置为 private / unlisted 先检查。

### 7.2 上传后检查清单

- [ ] YouTube 是否转码完成；
- [ ] 是否触发 Content ID；
- [ ] 是否有地区限制；
- [ ] 字幕是否显示正常；
- [ ] Shorts 是否被识别为 Shorts；
- [ ] 播放列表是否正确；
- [ ] 台账是否写回 YouTube URL。

---

## 8. 试运行计划

### 第一阶段：手动试跑 5 条

目标：验证合规链路和内容效果。

步骤：

1. 选择 5 条已授权视频；
2. 建立台账；
3. 手动处理视频；
4. 生成英文标题 / 简介 / 标签；
5. 上传为 private；
6. 检查版权声明；
7. 无问题后改为 public / scheduled；
8. 记录每条的处理时间和问题。

### 第二阶段：半自动处理 20 条

目标：让 Hermes 参与元数据和转码。

步骤：

1. 批量导入来源链接和授权状态；
2. 自动生成文件名和目录；
3. 自动生成元数据草稿；
4. 自动生成 FFmpeg 处理命令；
5. 人工审核输出文件；
6. 上传为 private；
7. 人工确认后公开。

### 第三阶段：稳定 SOP

目标：形成每日 / 每周搬运节奏。

- 每日处理数量；
- 固定发布时间；
- 固定审核人；
- 固定问题反馈方式；
- 固定数据复盘指标。

---

## 9. 数据与复盘准备

### 9.1 关键指标

- 点击率 CTR；
- 平均观看时长；
- 完播率；
- Shorts 推荐流量；
- 订阅转化；
- 版权声明数量；
- 下架 / 限制数量；
- 每条视频处理耗时。

### 9.2 周复盘问题

- 哪类来源视频在 YouTube 表现最好？
- 英文标题是否需要调整？
- 字幕是否提升留存？
- 哪些音乐 / 话题容易触发版权问题？
- 哪些创作者或素材源最稳定？
- 是否值得继续扩大规模？

---

## 10. 风险与应对

| 风险 | 应对 |
|---|---|
| 未授权搬运导致版权投诉 | 只处理自有 / 授权内容，保留证据 |
| 音乐触发 Content ID | 替换音乐或接受不能收益 |
| 平台 TOS 风险 | 使用平台允许的下载和再发布方式 |
| YouTube 重复内容 / reused content | 增加原创解说、字幕、剪辑、整理价值，但仍需版权授权 |
| 账号安全 | 2FA、最小权限、token 不明文保存 |
| 自动化误发 | 初期默认 private / unlisted，人工审核后公开 |
| 翻译质量差 | 人工抽检标题、简介、字幕 |

---

## 11. 待确认问题

1. 这些视频是否全部是自有或已授权内容？
2. 目标 YouTube 频道是新频道还是已有频道？
3. 主要发 Shorts 还是长视频？
4. 目标受众是英语区、中文区，还是多语言？
5. 是否需要开启收益？
6. 是否已有授权台账或素材库？
7. 是否希望 Hermes 后续自动上传，还是只做元数据 / 转码辅助？

---

## 12. 下一步建议

优先做这 5 件事：

1. 建立授权台账；
2. 确认 YouTube 频道和 API 权限；
3. 整理 5 条已授权样片；
4. 定义输出规格和元数据模板；
5. 先用 private 上传试跑，检查版权和 Shorts 识别情况。
