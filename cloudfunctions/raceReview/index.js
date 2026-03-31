const cloud = require('wx-server-sdk')
const axios = require('axios')
const {
  calculateVDOT, getBodySizeCorrection, calculateEnvironmentalTax,
  formatPace, formatTime, parseTimeToSeconds,
} = require('../common/utils')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

const LLM_CONFIG = {
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
      return generateReview(openid, data)
    case 'getReport':
      return getReport(data.reportId)
    case 'getMyReports':
      return getMyReports(openid)
    default:
      return { code: -1, msg: '未知操作' }
  }
}

async function generateReview(openid, data) {
  try {
    const { runner, prePlan, actual, weather } = data

    // 计算实际环境税
    const distanceKm = prePlan.distance === 'full' ? 42.195 : 21.0975
    const bodySize = getBodySizeCorrection(runner.height || 170, runner.weight || 65)
    const actualEnvTax = calculateEnvironmentalTax({
      windSpeedMph: weather.actualWindSpeed || 0,
      crosswindCoeff: weather.crosswindCoeff || 0.6,
      exposedKm: weather.exposedKm || (distanceKm * 0.85),
      humidity: weather.actualHumidity || 50,
      totalDistanceKm: distanceKm,
      lateTemp: weather.actualLateTemp || weather.actualTemp || 15,
      penaltyKm: distanceKm / 3,
      bodySizeCorrectionFactor: bodySize.correctionFactor,
      turnaroundCount: prePlan.turnaroundCount || 0,
    })

    // 实际 VDOT
    const actualTimeSeconds = parseTimeToSeconds(actual.finishTime)
    const actualVDOT = calculateVDOT(distanceKm, actualTimeSeconds / 60)

    // 偏差
    const targetTimeSeconds = parseTimeToSeconds(prePlan.targetTime)
    const deviation = actualTimeSeconds - targetTimeSeconds

    const preCalc = { bodySize, actualEnvTax, actualVDOT, deviation, distanceKm }

    // 构建 prompt
    const prompt = buildReviewPrompt(runner, prePlan, actual, weather, preCalc)
    const report = await callLLM(prompt)

    const reportData = {
      _openid: openid,
      type: 'race-review',
      runner, prePlan, actual, weather, preCalc,
      report, createdAt: db.serverDate(),
    }

    const res = await db.collection('reports').add({ data: reportData })

    return { code: 0, data: { reportId: res._id, report, preCalc } }
  } catch (e) {
    console.error('generateReview error:', e)
    return { code: -1, msg: e.message || '生成失败' }
  }
}

function buildReviewPrompt(runner, prePlan, actual, weather, preCalc) {
  const devSign = preCalc.deviation > 0 ? '+' : ''
  const distLabel = preCalc.distanceKm === 42.195 ? '全程马拉松' : '半程马拉松'

  return `你是一位融合了运动生理学专家、职业马拉松教练（10年+精英选手执教经验）与气象/赛道数据分析师身份的 AI。
你的任务：基于跑者的赛前方案与赛后实际数据，对其比赛表现进行深度复盘，找出偏差根因，输出一份可指导下一场比赛的复盘报告。

核心原则：
- 所有分析必须基于数据，禁止凭空断言。
- 配速精确到秒，心率精确到 bpm。
- 复盘核心目的是找出可改进的因子，态度是"教练帮选手复盘"。

---

## 跑者档案
- 昵称：${runner.name}
- 体重：${runner.weight}kg / 身高：${runner.height}cm
- VDOT：${runner.vdot || preCalc.actualVDOT}
- 周跑量：${runner.weeklyKm || '未知'} km
- 伤病：${runner.injury || '无'}

## 赛前方案
- 赛事：${prePlan.raceName}（${distLabel}）
- 目标时间：${prePlan.targetTime}
- 目标配速：${prePlan.targetPace || '未知'}
- 赛前 PB 胜算：${prePlan.pbOdds || '未知'}%
- 预估环境税：${prePlan.envTaxSeconds || '未知'} 秒

## 赛后实际数据
- 完赛时间：${actual.finishTime}
- 平均配速：${actual.avgPace || '未知'}
- 平均心率：${actual.avgHR || '未知'} bpm / 最大心率：${actual.maxHR || '未知'} bpm
- GPS距离：${actual.gpsDistance || '未知'} km
- 步频：${actual.cadence || '未知'} spm
${actual.splits ? `- 分段数据：${actual.splits}` : ''}
${actual.feedback ? `- 赛后体感：${actual.feedback}` : ''}
${actual.equipment ? `- 装备问题：${actual.equipment}` : ''}
${actual.injuryFeedback ? `- 伤病反馈：${actual.injuryFeedback}` : ''}

## 实际赛日天气
- 天气：${weather.actualCondition || '未知'}
- 气温：${weather.actualTemp || '?'}°C
- 湿度：${weather.actualHumidity || '?'}%
- 风力：${weather.actualWindSpeed || 0} mph

## 预计算
- 偏差：${devSign}${preCalc.deviation} 秒（${devSign}${formatTime(Math.abs(preCalc.deviation))}）
- 实际 VDOT：${preCalc.actualVDOT}
- 实际环境税：${preCalc.actualEnvTax.summary}

---

请按以下结构生成复盘报告（Markdown 格式）：

# ${runner.name} ${prePlan.raceName} 赛后复盘

## 1. 比赛数据核心提取
赛前 vs 赛后核心指标对比表（完赛时间/配速/心率/距离/步频 的偏差分析）

## 2. 实际天气 vs 预报对比
环境税重算 + 差异分析

## 3. 分段执行力分析
按蓄力/巡航/维持/冲刺 4 个阶段逐段对比，给出 A/B/C/F 执行力评分

## 4. 失利/超预期根因分析
### 4.1 核心事件分析（崩盘起爆点/超预期提速点的因果链）
### 4.2 装备与生物力学分析（如适用）
### 4.3 偏差分解量化（总偏差 = 各因子之和，必须吻合）

## 5. 关键结论
- 可控因子（下一场可消除）
- 能力因子（需训练改善）
- 净能力重估
- 下一场初步建议

## 6. 教练私房话（数据支撑的个性化建议，禁止鸡汤）

---
要求：语气专业克制，所有数字精确到秒/bpm，禁止模糊表述。`
}

async function callLLM(prompt) {
  if (!LLM_CONFIG.apiKey) {
    return '> LLM API 未配置，请在云开发环境变量中设置 LLM_API_KEY。\n\n预计算数据已完成，请查看报告数据中的 preCalc 字段。'
  }

  try {
    const response = await axios.post(LLM_CONFIG.apiUrl, {
      model: LLM_CONFIG.model,
      messages: [
        { role: 'system', content: '你是一位专业马拉松教练和运动生理学专家。请输出结构化的 Markdown 格式复盘报告。' },
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
    return `> LLM 调用失败：${e.message}\n\n预计算数据已完成，请查看报告数据中的 preCalc 字段。`
  }
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
      .where({ _openid: openid, type: 'race-review' })
      .orderBy('createdAt', 'desc')
      .limit(20)
      .get()
    return { code: 0, data: res.data }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}
