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

### 赛后：帮你复盘、找到进步空间

跑完比赛不只是看个成绩就完了，Marathon Copilot 会帮你做**深度复盘**：

- 逐段对比"计划配速 vs 实际配速"，找出哪里跑快了、哪里崩了
- 分析掉速的根因：是补给没跟上？心率漂移？还是天气太热？
- 评估你的补给执行情况
- 给出下一场比赛的改进建议

### 天气追踪：赛前每天帮你盯天气

从报名到比赛日，每天自动追踪赛事城市的天气变化，量化"环境税"对你配速的影响，让你提前做好应对准备。

### PDF 报告：一键生成精美文档

所有分析结果可以导出为排版精美的 PDF，方便保存和分享给教练、跑友。

---

## 怎么用？

### 微信小程序（推荐）

**第 1 步：建立你的跑者档案**

打开小程序，填写你的基本信息：
- 身高、体重（用于计算环境影响）
- 历史 PB 成绩（比如半马最好成绩 1:35:00）
- HRV 数据（可选，有的话分析更准）

**第 2 步：赛前目标设定**

选择你要参加的比赛，填写赛事信息（赛道类型、海拔、预估天气等），AI 会自动生成：
- 推荐目标成绩（A/B/C 三档计划）
- 逐公里配速表
- 补给计划
- 锁屏备忘（比赛当天打开手机就能看）

**第 3 步：赛后复盘**

比赛结束后，录入实际比赛数据（分段配速、心率等），AI 会生成一份完整的复盘报告，告诉你哪里做得好、哪里可以改进。

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

### 环境变量配置

在云函数设置中添加以下环境变量：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_URL` | 大模型 API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_API_KEY` | 大模型 API Key | `sk-xxx` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `WEATHER_PROVIDER` | 天气服务 | `wttr` 或 `qweather` |
| `WEATHER_API_KEY` | 天气 API Key（和风天气） | — |

支持的大模型：
- [DeepSeek](https://platform.deepseek.com/)（推荐，性价比高）
- [Kimi / Moonshot](https://platform.moonshot.cn/)
- [OpenAI](https://platform.openai.com/) 及兼容接口

### 部署云函数

在微信开发者工具中，右键每个云函数目录 → "上传并部署：云端安装依赖"：
- `cloudfunctions/user`
- `cloudfunctions/raceGoal`
- `cloudfunctions/raceReview`
- `cloudfunctions/weather`

### CLI 版（Devin 开发者工具）

除了小程序，本项目也支持通过 [Devin CLI](https://cli.devin.ai/docs) 在终端中使用：

```bash
# 安装依赖
pip install markdown weasyprint pymupdf requests

# 生成 PDF 报告
python generate_pdf.py 输入文件.md 输出文件.pdf
```

### 项目结构

```
.
├── miniprogram/               # 微信小程序前端
│   ├── pages/                 #   各功能页面
│   ├── services/api.js        #   云函数调用封装
│   └── utils/util.js          #   工具函数
├── cloudfunctions/            # 云函数（后端逻辑）
│   ├── user/                  #   用户管理
│   ├── raceGoal/              #   赛前目标生成（AI + 算法）
│   ├── raceReview/            #   赛后复盘分析（AI + 算法）
│   ├── weather/               #   天气数据
│   └── common/utils.js        #   核心算法库
├── .cognition/skills/         # Devin AI Skills（CLI 版）
├── api-tools/                 # 天气工具（CLI 版）
├── generate_pdf.py            # PDF 生成器
└── prompt.md                  # Prompt 模板
```

---

## 个人数据保护

所有跑者的个人数据（PB、HRV、比赛报告、API 密钥等）均已通过 `.gitignore` 排除，不会上传到代码仓库。

## License

MIT
