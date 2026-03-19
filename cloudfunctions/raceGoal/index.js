const cloud = require('wx-server-sdk')
const axios = require('axios')
const {
  calculateVDOT, getBodySizeCorrection, calculateEnvironmentalTax,
  calculateHRVCorrection, calculatePBOdds, generatePacingPlan,
  formatPace, formatTime, parseTimeToSeconds, getTrainingPaces,
} = require('../common/utils')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

// LLM API configuration - 支持 DeepSeek / Kimi / OpenAI 兼容接口
const LLM_CONFIG = {
  // 在云开发环境变量中配置，或在此处修改
  apiUrl: process.env.LLM_API_URL || 'https://api.deepseek.com/v1/chat/completions',
  apiKey: process.env.LLM_API_KEY || '',
  model: process.env.LLM_MODEL || 'deepseek-chat',
}

exports.main = async (event, context) => {
  const { action, data } = event
  const wxContext = cloud.getWXContext()
  const openid = wxContext.OPENID

  switch (action) {
    case 'generate':
      return generateRaceGoal(openid, data)
    case 'getReport':
      return getReport(data.reportId)
    case 'getMyReports':
      return getMyReports(openid)
    default:
      return { code: -1, msg: '未知操作' }
  }
}

async function generateRaceGoal(openid, data) {
  try {
    const { runner, race, weather, hrv } = data

    // Step 1: 预计算核心指标
    const preCalc = preCalculate(runner, race, weather, hrv)

    // Step 2: 构建 prompt 并调用 LLM
    const prompt = buildPrompt(runner, race, weather, hrv, preCalc)
    const report = await callLLM(prompt)

    // Step 3: 保存报告
    const reportData = {
      _openid: openid,
      type: 'race-goal',
      runner: runner,
      race: race,
      weather: weather,
      hrv: hrv || null,
      preCalc: preCalc,
      report: report,
      createdAt: db.serverDate(),
    }

    const res = await db.collection('reports').add({ data: reportData })

    return {
      code: 0,
      data: {
        reportId: res._id,
        report: report,
        preCalc: preCalc,
      }
    }
  } catch (e) {
    console.error('generateRaceGoal error:', e)
    return { code: -1, msg: e.message || '生成失败' }
  }
}

function preCalculate(runner, race, weather, hrv) {
  // VDOT from best PB
  const vdotValues = []
  if (runner.pb10k) {
    vdotValues.push({ distance: 10, vdot: calculateVDOT(10, parseTimeToSeconds(runner.pb10k) / 60) })
  }
  if (runner.pbHalf) {
    vdotValues.push({ distance: 21.0975, vdot: calculateVDOT(21.0975, parseTimeToSeconds(runner.pbHalf) / 60) })
  }
  if (runner.pbFull) {
    vdotValues.push({ distance: 42.195, vdot: calculateVDOT(42.195, parseTimeToSeconds(runner.pbFull) / 60) })
  }

  // Use median VDOT
  vdotValues.sort((a, b) => a.vdot - b.vdot)
  const currentVDOT = vdotValues.length > 0
    ? vdotValues[Math.floor(vdotValues.length / 2)].vdot
    : runner.vdot || 40

  // Body size correction
  const bodySize = getBodySizeCorrection(runner.height || 170, runner.weight || 65)

  // Environmental tax
  const distanceKm = race.distance === 'full' ? 42.195 : 21.0975
  const envTax = calculateEnvironmentalTax({
    windSpeedMph: weather.windSpeed || 0,
    crosswindCoeff: weather.crosswindCoeff || 0.6,
    exposedKm: weather.exposedKm || (distanceKm * 0.85),
    humidity: weather.humidity || 50,
    totalDistanceKm: distanceKm,
    lateTemp: weather.lateTemp || weather.temperature || 15,
    penaltyKm: distanceKm / 3,
    bodySizeCorrectionFactor: bodySize.correctionFactor,
    turnaroundCount: race.turnaroundCount || 0,
  })

  // HRV correction
  let hrvResult = { correction: 1.0, assessment: '无HRV数据' }
  if (hrv && hrv.personalBaseline && hrv.sevenDayAvg) {
    hrvResult = calculateHRVCorrection(hrv)
  }

  // Target VDOT
  const targetTimeSeconds = parseTimeToSeconds(race.targetTime)
  const targetVDOT = calculateVDOT(distanceKm, targetTimeSeconds / 60)

  // Training paces
  const paces = getTrainingPaces(currentVDOT)

  // PB odds
  const pbOdds = calculatePBOdds({
    currentVDOT, targetVDOT,
    weeklyKm: runner.weeklyKm || 50,
    distanceKm,
    envTaxSeconds: envTax.total,
    targetTimeSeconds,
    hrvCorrection: hrvResult.correction,
    injuryCorrection: runner.injuryCorrection || 1.0,
    raceIntervalDays: race.intervalDays || 30,
  })

  // Pacing plan
  const pacingPlan = generatePacingPlan({
    targetTimeSeconds, distanceKm,
    strategy: race.strategy || 'even',
    envTaxSeconds: envTax.total,
  })

  return {
    vdotValues, currentVDOT, targetVDOT,
    bodySize, envTax, hrvResult,
    paces, pbOdds, pacingPlan, distanceKm,
  }
}

function buildPrompt(runner, race, weather, hrv, preCalc) {
  const distLabel = preCalc.distanceKm === 42.195 ? '全程马拉松' : '半程马拉松'

  return `你是一位融合了运动生理学专家、职业马拉松教练（10年+精英选手执教经验）与气象数据分析师身份的 AI。
你的任务：基于跑者的精细跑力数据，对其在目标赛事中的表现进行量化预测，并输出一份可直接执行的比赛方案。

核心原则：
- 所有配速建议必须精确到秒（如 4'21"），禁止使用模糊区间。
- 所有推理必须标注数据来源，不得凭空断言。
- 态度：教练赛前 briefing 风格，专业、克制、有力。

---

## 跑者数据

- 昵称：${runner.name}
- 体重：${runner.weight}kg / 身高：${runner.height}cm
- BSA：${preCalc.bodySize.bsa} m² / BSA比：${preCalc.bodySize.bsaRatio} m²/kg
- 当前 VDOT：${preCalc.currentVDOT}（基于 PB 数据中位数）
${runner.pb10k ? `- 10km PB：${runner.pb10k}（${runner.pb10kDate || ''}）` : ''}
${runner.pbHalf ? `- 半马 PB：${runner.pbHalf}（${runner.pbHalfDate || ''}）` : ''}
${runner.pbFull ? `- 全马 PB：${runner.pbFull}（${runner.pbFullDate || ''}）` : ''}
- T-Pace：${formatPace(preCalc.paces.threshold)}/km
- 最大心率：${runner.hrMax || '未知'} bpm / 安静心率：${runner.rhr || '未知'} bpm
- 近4周平均周跑量：${runner.weeklyKm || '未知'} km
- 伤病情况：${runner.injury || '无'}
${hrv ? `
## HRV 竞技状态
- 个人基线：${hrv.personalBaseline} ms
- 赛前7天均值：${hrv.sevenDayAvg} ms / SD：${hrv.sevenDaySD} ms
- 基线偏差：${preCalc.hrvResult.baselineDeviation}%
- 稳定性 CV：${preCalc.hrvResult.stabilityCV}%
${hrv.raceDayHRV ? `- 赛日晨起HRV：${hrv.raceDayHRV} ms / 回升：${preCalc.hrvResult.raceDayRebound}%` : ''}
- HRV修正系数：${preCalc.hrvResult.correction}（${preCalc.hrvResult.assessment}）
` : ''}

## 赛事信息

- 赛事：${race.name}
- 日期：${race.date}
- 类型：${distLabel}
- 起跑时间：${race.startTime || '待定'}
- 赛道特征：${race.courseDescription || '标准城市赛道'}
- 折返点：${race.turnaroundCount || 0} 个

## 天气预报

- 天气：${weather.condition || '待定'}
- 气温：${weather.temperature || '?'}°C
- 湿度：${weather.humidity || '?'}%
- 风力：${weather.windSpeed || 0} mph / 风向：${weather.windDirection || '待定'}

## 预计算结果

- 目标时间：${race.targetTime}
- 目标 VDOT：${preCalc.targetVDOT}
- VDOT 缺口：${(preCalc.currentVDOT - preCalc.targetVDOT).toFixed(1)}
- 环境税：${preCalc.envTax.summary}
- PB 胜算：${preCalc.pbOdds.odds}% (${preCalc.pbOdds.confidence})
- 胜算评估：${preCalc.pbOdds.assessment}

---

请按以下结构生成完整的比赛目标设定报告（Markdown 格式）：

# ${runner.name} ${race.name} 目标设定报告

## 1. 跑者数据诊断
### 1.1 个人纪录提取（表格）
### 1.2 VDOT 综合锚定
### 1.3 速度-耐力耦合度
### 1.4 训练状态评估
${hrv ? '### 1.5 HRV 竞技状态评估（三维度量化表 + 修正系数计算）' : ''}

## 2. 赛事环境分析
### 2.1 赛道特征
### 2.2 天气预报分析
### 2.3 环境税精算（含体型修正）

## 3. 目标设定
### 3.1 核心推理
### 3.2 分级目标方案（Plan A/B/C 表格）
### 3.3 推荐目标 + 推荐理由
### 3.4 PB 胜算精算（各因子系数表）+ 做多/做空因子

## 4. 实战配速表
策略核心声明 + 逐段配速表（里程/GPS目标配速/目标心率/分段用时/累计用时/技术指令）

## 5. 补给与散热计划（时间点/动作/逻辑 表格）

## 6. 动态熔断与保护
### 心率熔断线
### 配速熔断线
### Plan 降级对照表

## 7. 教练私房话（3-4条数据支撑的执行建议）

## 8. 赛道锁屏备忘（不超过8行极简格式）

---
要求：语气专业克制，所有数字精确到秒/bpm，禁止模糊表述。`
}

async function callLLM(prompt) {
  if (!LLM_CONFIG.apiKey) {
    return generateFallbackReport(prompt)
  }

  try {
    const response = await axios.post(LLM_CONFIG.apiUrl, {
      model: LLM_CONFIG.model,
      messages: [
        { role: 'system', content: '你是一位专业马拉松教练和运动生理学专家。请输出结构化的 Markdown 格式报告。' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.3,
      max_tokens: 8000,
    }, {
      headers: {
        'Authorization': `Bearer ${LLM_CONFIG.apiKey}`,
        'Content-Type': 'application/json',
      },
      timeout: 120000,
    })

    return response.data.choices[0].message.content
  } catch (e) {
    console.error('LLM API error:', e.message)
    return generateFallbackReport(prompt)
  }
}

function generateFallbackReport(prompt) {
  return `> 注意：LLM API 未配置或调用失败，以下为基于算法引擎的精简报告。配置 LLM API Key 后可获得完整的教练级分析报告。

报告数据已通过算法引擎预计算完成，请查看下方的预计算结果。

---

*请在云开发环境变量中配置 LLM_API_URL、LLM_API_KEY、LLM_MODEL 以启用 AI 分析。*
*支持 DeepSeek、Kimi（Moonshot）、OpenAI 等兼容接口。*`
}

async function getReport(reportId) {
  try {
    const res = await db.collection('reports').doc(reportId).get()
    return { code: 0, data: res.data }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function getMyReports(openid) {
  try {
    const res = await db.collection('reports')
      .where({ _openid: openid, type: 'race-goal' })
      .orderBy('createdAt', 'desc')
      .limit(20)
      .get()
    return { code: 0, data: res.data }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}
