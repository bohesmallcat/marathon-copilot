# Marathon Copilot — AI 马拉松配速教练

基于运动生理学的智能马拉松备赛工具，支持 **Devin CLI** 和 **微信小程序** 双端使用。

## 项目结构

```
.
├── miniprogram/               # 微信小程序前端
│   ├── pages/
│   │   ├── index/             #   首页（功能入口 + 快速概览）
│   │   ├── profile/           #   跑者档案（PB/HRV/体型数据录入）
│   │   ├── race-goal/         #   赛前目标设定（分步表单）
│   │   ├── race-review/       #   赛后复盘（数据录入 + AI分析）
│   │   ├── history/           #   历史报告列表
│   │   └── report-detail/     #   报告详情（Markdown渲染）
│   ├── services/api.js        #   云函数调用封装
│   ├── utils/util.js          #   前端工具函数
│   ├── app.js / app.json      #   小程序配置
│   └── app.wxss               #   全局样式（设计系统）
├── cloudfunctions/            # 微信云开发（云函数）
│   ├── user/                  #   用户管理（档案CRUD/PB记录/HRV数据）
│   ├── raceGoal/              #   赛前目标生成（LLM + 算法引擎）
│   ├── raceReview/            #   赛后复盘分析（LLM + 偏差分解）
│   ├── weather/               #   天气追踪（wttr.in / 和风天气）
│   └── common/utils.js        #   核心算法库（VDOT/环境税/HRV/PB概率）
├── .cognition/skills/         # Devin AI Skills（CLI版核心能力）
│   ├── race-goal/SKILL.md     #   赛前目标设定 Skill
│   └── race-review/SKILL.md   #   赛后复盘 Skill
├── api-tools/                 # 天气 & 通知 API 工具（CLI版）
├── generate_pdf.py            # Markdown → PDF 生成器
├── project.config.json        # 小程序项目配置
└── .gitignore
```

## 核心功能

### 1. 赛前目标设定 (`race-goal` skill)

基于跑者跑力数据生成完整比赛方案：
- VDOT 跑力量化分析
- 多场历史比赛数据对比
- 天气 & 赛道环境修正
- 逐公里配速表（含心率区间、技术指令、补给提示）
- 动态熔断保护机制（心率 / 配速 / 体感三级熔断）
- 锁屏备忘（比赛当天速查）

### 2. 赛后复盘 (`race-review` skill)

基于实际比赛数据生成深度复盘：
- 配速偏差分解（计划 vs 实际，逐段根因分析）
- 心率漂移分析
- 补给执行评估
- 环境因素影响量化
- 下一场比赛改进建议

### 3. PDF 生成 (`generate_pdf.py`)

将 Markdown 报告转为精排版 PDF：
- 深色表头 + 交替行色表格
- 彩色提示框（info / warning / danger）
- 自动分页 & 锁屏备忘单页排版
- 中文字体支持

```bash
python generate_pdf.py 输入文件.md 输出文件.pdf
```

### 4. 天气追踪 (`api-tools/`)

赛前每日自动追踪比赛日天气变化，量化环境税对配速的影响。

## 快速开始

### 方式一：微信小程序（推荐跑友使用）

#### 1. 准备工作

1. 注册 [微信小程序账号](https://mp.weixin.qq.com/)，获取 AppID
2. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
3. 开通微信云开发

#### 2. 项目导入

1. 打开微信开发者工具，导入本项目
2. 在 `project.config.json` 中填入你的 AppID
3. 开通云开发环境

#### 3. 云开发配置

**数据库集合（需手动创建）：**

| 集合名 | 用途 |
|--------|------|
| `runners` | 跑者档案 |
| `pb_records` | PB 记录 |
| `hrv_data` | HRV 时序数据 |
| `reports` | 分析报告 |
| `weather_tracking` | 天气追踪记录 |

**环境变量（云函数配置）：**

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_URL` | 大模型 API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_API_KEY` | 大模型 API Key | `sk-xxx` |
| `LLM_MODEL` | 模型名称 | `deepseek-chat` |
| `WEATHER_PROVIDER` | 天气服务 | `wttr` 或 `qweather` |
| `WEATHER_API_KEY` | 天气 API Key（和风天气） | — |

**支持的 LLM 接口：**
- [DeepSeek](https://platform.deepseek.com/)（推荐，性价比高）
- [Kimi / Moonshot](https://platform.moonshot.cn/)
- [OpenAI](https://platform.openai.com/) 及兼容接口

#### 4. 部署云函数

在微信开发者工具中，右键每个云函数目录 → "上传并部署：云端安装依赖"：
- `cloudfunctions/user`
- `cloudfunctions/raceGoal`
- `cloudfunctions/raceReview`
- `cloudfunctions/weather`

#### 5. 使用

1. 首页 → 创建跑者档案（填写体重、身高、PB 等）
2. 赛前目标设定 → 填写赛事信息 → AI 生成配速方案
3. 赛后复盘 → 填写比赛数据 → AI 生成偏差分析

### 方式二：Devin CLI（开发者版）

```bash
# PDF 生成
pip install markdown weasyprint pymupdf

# 天气 API
pip install requests
cd api-tools && cp .env.example .env  # 填入 API 密钥
```

在 [Devin CLI](https://cli.devin.ai/docs) 中调用：
- `/skill race-goal <跑者> <比赛>` — 生成赛前目标方案
- `/skill race-review <跑者> <比赛>` — 生成赛后复盘报告

## 核心算法

小程序内置的算法引擎（`cloudfunctions/common/utils.js`）：

| 算法 | 说明 |
|------|------|
| **VDOT 计算** | Daniels Running Formula，基于 PB 反推跑力值 |
| **环境税精算** | 风阻 + 湿度 + 温度（含 BSA 体型修正）+ 折返损耗 |
| **HRV 修正** | 三维度评估（基线偏差 × 稳定性CV × 赛日回升能力） |
| **PB 概率** | 多因子综合：VDOT基准 × 训练支撑 × 环境 × HRV × 伤病 × 赛间恢复 |
| **配速方案** | 支持均匀/后程加速/保守三种策略，自动生成逐公里配速表 |

## 个人数据保护

`.gitignore` 已配置排除：
- `*数据/` — 跑者原始数据（截图、HRV 图片）
- `*报告/` — 生成的 PDF 报告
- `*_*.md` — 个人 Markdown 报告
- `*.pdf` — 所有生成的 PDF
- `api-tools/.env` — API 密钥

## License

MIT
