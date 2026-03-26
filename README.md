# Marathon Copilot — 你的 AI 马拉松配速教练

> 帮你科学备赛、精准配速、赛后复盘的智能助手。
> 不用懂代码，在微信小程序上就能用。

---

## 它能帮你做什么？

### 赛前：帮你定目标、出配速方案

比赛前最纠结的问题："我该跑多快？"

Marathon Copilot 会根据你的真实跑力，帮你算出**靠谱的比赛目标**和**逐公里配速表**：

- 根据你的 PB 计算跑力值（VDOT），给出科学的目标成绩
- 考虑比赛当天的天气（温度、湿度、风速），自动修正配速
- 考虑你的身体状况（HRV 心率变异性、伤病、赛间恢复时间）
- 生成一份完整的配速表：每公里该跑多快、心率控制在多少、什么时候补水补胶
- 设定"熔断机制"：如果比赛中心率飙高或配速偏差过大，告诉你什么时候该果断降速

### 每日训练 & 饮食计划

赛前 7 天到比赛日，每天帮你安排**训练、饮食、恢复**三件事：

- **训练**：根据 VDOT 计算训练配速，从赛前减量跑到赛前激活跑，每天不一样
- **饮食**：基于体重计算碳水/蛋白质/脂肪摄入目标，越接近比赛日碳水占比越高（糖原超补）
- **恢复**：睡眠、拉伸、泡沫轴、冰浴……按天推荐最合适的恢复策略

### 天气追踪 & 每日简报

从报名到比赛日，每天自动追踪赛事城市的天气变化：

- 量化"环境税"对配速的影响（综合气温、湿度、风速、体感温度）
- 根据最新天气动态调整配速建议
- 生成**每日简报**（Markdown + PDF），集成天气、训练计划、饮食建议于一份报告
- 支持多人模式：一次生成多位跑者的个性化简报

### 赛后：帮你复盘、找到进步空间

跑完比赛不只是看个成绩就完了，Marathon Copilot 会帮你做**深度复盘**：

- 逐段对比"计划配速 vs 实际配速"，找出哪里跑快了、哪里崩了
- 分析掉速的根因：是补给没跟上？心率漂移？还是天气太热？
- 评估你的补给执行情况
- 给出下一场比赛的改进建议

### PDF 报告：一键生成精美文档

所有分析结果可以导出为排版精美的 PDF，方便保存和分享给教练、跑友。

---

## 怎么用？

### 微信小程序（推荐）

**第 1 步：建立你的跑者档案**

打开小程序，填写你的基本信息：
- 身高、体重（用于计算环境影响和营养目标）
- 历史 PB 成绩（比如半马最好成绩 1:35:00）
- HRV 数据（可选，有的话分析更准）

**第 2 步：赛前目标设定**

选择你要参加的比赛，填写赛事信息（赛道类型、海拔、预估天气等），AI 会自动生成：
- 推荐目标成绩（A/B/C 三档计划）
- 逐公里配速表
- 补给计划
- 锁屏备忘（比赛当天打开手机就能看）

**第 3 步：每日训练 & 饮食**

进入"每日训练 & 饮食"页面，查看赛前倒计时和当天的：
- 训练安排（项目、配速、时长）
- 饮食建议（碳水/蛋白质/脂肪克数、推荐食物）
- 恢复策略（睡眠、拉伸、补水要点）

**第 4 步：赛后复盘**

比赛结束后，录入实际比赛数据（分段配速、心率等），AI 会生成一份完整的复盘报告，告诉你哪里做得好、哪里可以改进。

### CLI 版（终端工具）

除了小程序，本项目也支持在终端中使用 Python 脚本，适合开发者和需要批量处理的场景。

```bash
# 安装依赖
pip install markdown weasyprint pymupdf requests pyyaml

# 1. 配置跑者信息（复制模板，填入你的数据）
cp race_config.example.yaml race_config.yaml
# 编辑 race_config.yaml，填入你的 PB、体重、目标成绩等

# 2. 生成每日简报（天气 + 训练 + 饮食）
python api-tools/generate_daily_briefing.py --date 2026-03-26

# 3. 生成天气日报
python api-tools/daily_weather_report.py

# 4. 生成 PDF 报告
python generate_pdf.py 输入文件.md 输出文件.pdf
```

多人模式：创建多份配置文件（如 `race_config_b.yaml`），脚本会自动识别并为每位跑者生成独立报告。

---

## 背后的科学原理

Marathon Copilot 不是拍脑袋给建议，每个数字都有运动生理学依据：

| 能力 | 原理 |
|------|------|
| **跑力计算** | 基于 Jack Daniels 的 VDOT 公式，用你的 PB 反推跑力值 |
| **环境修正** | 综合温度、湿度、风速对配速的影响，还会根据你的身高体重做个性化修正 |
| **HRV 评估** | 通过心率变异性数据评估你的身体恢复状态和比赛日竞技状态 |
| **PB 概率** | 综合跑力、训练量、环境、身体状态等多因子，估算你达成目标的概率 |
| **配速策略** | 支持均匀配速、后程加速、保守策略三种方案，自动生成逐公里计划 |
| **营养计算** | 根据体重和赛前天数计算碳水/蛋白质/脂肪目标，支持糖原超补周期 |
| **训练配速** | 基于 VDOT 推算 Easy/Marathon/Threshold 等各档训练配速 |

---

## 部署指南（开发者）

如果你想自己部署这个小程序，或者参与开发，请往下看。

### 环境准备

1. 注册 [微信小程序账号](https://mp.weixin.qq.com/)，获取 AppID
2. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
3. 开通微信云开发

### 项目导入

1. 打开微信开发者工具，导入本项目
2. 在 `project.config.json` 中填入你的 AppID
3. 开通云开发环境

### 数据库配置

在云开发控制台中创建以下数据库集合：

| 集合名 | 用途 |
|--------|------|
| `runners` | 跑者档案 |
| `pb_records` | PB 记录 |
| `hrv_data` | HRV 时序数据 |
| `reports` | 分析报告 |
| `weather_tracking` | 天气追踪记录 |
| `daily_plans` | 每日训练 & 饮食计划 |

### 环境变量配置

在云函数设置中添加以下环境变量：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_URL` | 大模型 API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_API_KEY` | 大模型 API Key | `sk-xxx` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `WEATHER_PROVIDER` | 天气服务 | `wttr` 或 `qweather` |
| `WEATHER_API_KEY` | 天气 API Key（和风天气） | — |

CLI 版额外需要在 `.env` 中配置（参见 `.env.example`）：

| 变量名 | 说明 |
|--------|------|
| `SMTP_HOST` | 邮件服务器地址 |
| `EMAIL_FROM` | 发件人邮箱 |
| `EMAIL_AUTH_CODE` | 邮箱授权码 |
| `REPORTS_DIR` | 报告输出目录 |
| `REPORTS_ONEDRIVE_DIR` | OneDrive 同步目录（可选） |

支持的大模型：
- [DeepSeek](https://platform.deepseek.com/)（推荐，性价比高）
- [Kimi / Moonshot](https://platform.moonshot.cn/)
- [OpenAI](https://platform.openai.com/) 及兼容接口

### 跑者配置文件

CLI 版通过 `race_config.yaml` 管理跑者信息和赛事参数：

```bash
cp race_config.example.yaml race_config.yaml
```

配置文件包含：
- 跑者档案（姓名、身高、体重、PB）
- 赛事信息（名称、日期、距离、起跑时间）
- 目标成绩和配速策略
- 逐公里配速表和熔断规则
- 补给计划和营养参数

> 注意：`race_config.yaml` 已加入 `.gitignore`，不会被提交到仓库。请基于 `race_config.example.yaml` 创建你自己的配置。

### 部署云函数

在微信开发者工具中，右键每个云函数目录 → "上传并部署：云端安装依赖"：
- `cloudfunctions/user` — 用户管理
- `cloudfunctions/raceGoal` — 赛前目标生成
- `cloudfunctions/raceReview` — 赛后复盘分析
- `cloudfunctions/weather` — 天气数据
- `cloudfunctions/dailyPlan` — 每日训练 & 饮食计划

### 项目结构

```
.
├── miniprogram/                    # 微信小程序前端
│   ├── pages/
│   │   ├── index/                  #   首页（功能入口）
│   │   ├── race-goal/              #   赛前目标设定
│   │   ├── daily-plan/             #   每日训练 & 饮食计划
│   │   ├── race-review/            #   赛后复盘
│   │   ├── history/                #   历史记录
│   │   ├── profile/                #   跑者档案
│   │   └── report-detail/          #   报告详情
│   ├── services/api.js             #   云函数调用封装
│   └── utils/util.js               #   工具函数
├── cloudfunctions/                  # 云函数（后端逻辑）
│   ├── user/                       #   用户管理
│   ├── raceGoal/                   #   赛前目标生成（AI + 算法）
│   ├── raceReview/                 #   赛后复盘分析（AI + 算法）
│   ├── weather/                    #   天气数据
│   ├── dailyPlan/                  #   每日训练 & 饮食计划（VDOT + 营养算法）
│   └── common/utils.js             #   核心算法库
├── api-tools/                      # CLI 工具集
│   ├── generate_daily_briefing.py  #   每日简报生成器（天气 + 训练 + 饮食）
│   ├── daily_weather_report.py     #   天气日报生成器
│   ├── weather_client.py           #   天气 API 客户端（共享模块）
│   ├── env_tax.py                  #   环境税计算（共享模块）
│   ├── api_client.py               #   LLM API 客户端
│   └── pdf_styles.py               #   PDF 样式定义
├── .cognition/skills/              # Devin AI Skills
│   ├── race-goal/                  #   赛前目标设定 Skill
│   ├── race-review/                #   赛后复盘 Skill
│   ├── race-weather/               #   赛前天气日报 Skill
│   └── race-training/              #   训练 & 饮食计划 Skill
├── race_config.example.yaml        # 跑者配置模板
├── generate_pdf.py                 # PDF 生成器（通用）
├── md_to_pdf.py                    # Markdown → PDF 转换器
└── prompt.md                       # Prompt 模板
```

---

## 个人数据保护

- 所有跑者的个人数据（PB、体重、HRV、比赛报告等）均已通过 `.gitignore` 排除，不会上传到代码仓库
- `race_config.yaml`（含跑者真实姓名和身体数据）不会被提交；仓库中只保留脱敏后的 `race_config.example.yaml` 模板
- 生成的报告文件（`*报告/`、`*数据/`、`*天气日报*.md`）均已排除
- API 密钥和邮箱授权码通过 `.env` 管理，同样不会提交

## License

MIT
