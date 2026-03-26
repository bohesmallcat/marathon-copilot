const cloud = require('wx-server-sdk')
const {
  calculateVDOT, getTrainingPaces,
  parseTimeToSeconds, formatPace,
} = require('../common/utils')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

// ============================================================
// Cloud Function Entry
// ============================================================

exports.main = async (event, context) => {
  const { action, data } = event
  const wxContext = cloud.getWXContext()
  const openid = wxContext.OPENID

  switch (action) {
    case 'getDailyPlan':
      return getDailyPlan(openid, data)
    case 'savePlan':
      return savePlan(openid, data)
    case 'getMyPlans':
      return getMyPlans(openid)
    default:
      return { code: -1, msg: '未知操作' }
  }
}

// ============================================================
// Action: getDailyPlan
// ============================================================

async function getDailyPlan(openid, data) {
  try {
    const { raceDate, raceName, raceDistance, targetTime, weightKg } = data

    // Calculate days to race
    const now = new Date()
    const race = new Date(raceDate)
    const diffMs = race.setHours(0, 0, 0, 0) - now.setHours(0, 0, 0, 0)
    const daysToRace = Math.round(diffMs / (1000 * 60 * 60 * 24))

    if (daysToRace < 0) {
      return { code: -1, msg: '比赛已结束' }
    }

    // Calculate VDOT and training paces from target time
    const distanceKm = parseFloat(raceDistance) || 42.195
    const targetSeconds = parseTimeToSeconds(targetTime)
    const vdot = calculateVDOT(distanceKm, targetSeconds / 60)
    const trainingPaces = getTrainingPaces(vdot)

    // Generate plans
    const training = getTrainingPlan(daysToRace, distanceKm, trainingPaces)
    const diet = getDietPlan(daysToRace, weightKg || 65)
    const recovery = daysToRace <= 4 ? getRecoveryChecklist(daysToRace) : null

    // Format paces for display
    const paceDisplay = {
      easy: formatPace(trainingPaces.easy),
      marathon: formatPace(trainingPaces.marathon),
      threshold: formatPace(trainingPaces.threshold),
      interval: formatPace(trainingPaces.interval),
      repetition: formatPace(trainingPaces.repetition),
    }

    return {
      code: 0,
      data: {
        daysToRace,
        dayLabel: `D-${daysToRace}`,
        raceName,
        raceDate,
        raceDistance: distanceKm,
        vdot,
        paceDisplay,
        training,
        diet,
        recovery,
        generatedAt: new Date().toISOString(),
      },
    }
  } catch (e) {
    console.error('getDailyPlan error:', e)
    return { code: -1, msg: e.message || '获取每日计划失败' }
  }
}

// ============================================================
// Action: savePlan
// ============================================================

async function savePlan(openid, data) {
  try {
    const { raceDate, raceName, training, diet, daysToRace } = data

    const record = {
      _openid: openid,
      raceDate,
      raceName,
      daysToRace,
      dayLabel: `D-${daysToRace}`,
      training,
      diet,
      savedAt: db.serverDate(),
    }

    const res = await db.collection('daily_plans').add({ data: record })

    return { code: 0, data: { planId: res._id } }
  } catch (e) {
    console.error('savePlan error:', e)
    return { code: -1, msg: e.message || '保存计划失败' }
  }
}

// ============================================================
// Action: getMyPlans
// ============================================================

async function getMyPlans(openid) {
  try {
    const res = await db.collection('daily_plans')
      .where({ _openid: openid })
      .orderBy('savedAt', 'desc')
      .limit(20)
      .get()

    return { code: 0, data: res.data }
  } catch (e) {
    console.error('getMyPlans error:', e)
    return { code: -1, msg: e.message || '获取计划列表失败' }
  }
}

// ============================================================
// Training Plan Generator (D-N based)
// ============================================================

function getTrainingPlan(daysToRace, raceDistance, trainingPaces) {
  const tPace = formatPace(trainingPaces.threshold)
  const ePace = formatPace(trainingPaces.easy)
  const mPace = formatPace(trainingPaces.marathon)

  const plans = {
    0: {
      phase: '比赛日',
      workout: '比赛',
      distance: raceDistance + 'km',
      rpe: '全力',
      hrCap: '按配速表执行',
      gear: '竞速跑鞋',
      paceTarget: `目标配速 ${mPace}/km`,
      details: '比赛日流程：起床→早餐→到达起点→热身→起跑',
    },
    1: {
      phase: '赛前最终准备',
      workout: '极轻松抖腿跑',
      distance: '2km 慢跑 + 2x100m 大步跑',
      rpe: 'RPE 2-3',
      hrCap: '< 心率区间1上限',
      gear: '日常训练鞋',
      paceTarget: `慢跑 ${ePace}/km 以上（更慢也行）`,
      details: '仅为保持跑感和神经激活。22:00前入睡。',
    },
    2: {
      phase: 'Taper + 碳水负荷',
      workout: '完全休息（散步可）',
      distance: '0km',
      rpe: '—',
      hrCap: '—',
      gear: '—',
      paceTarget: '—',
      details: '完全休息让身体超量恢复。碳水负荷启动日。',
    },
    3: {
      phase: '赛前激活',
      workout: '赛前开腿跑（醒腿）',
      distance: '5km：2km热身 + 4x200m快跑 + 1.5km放松',
      rpe: 'RPE 5-6',
      hrCap: '200m段可至T-Pace心率',
      gear: '日常训练鞋',
      paceTarget: `热身 ${ePace}/km，200m段 @ ${tPace}/km`,
      details: '赛前最后一次有速度的训练。200m间歇调动快肌纤维。',
    },
    4: {
      phase: 'Taper 减量期',
      workout: '轻松跑',
      distance: '5-6km 轻松跑',
      rpe: 'RPE 4',
      hrCap: '< 心率区间2上限',
      gear: '日常训练鞋',
      paceTarget: `${ePace}/km`,
      details: '维持跑感，Taper减量期不追速。',
    },
    5: {
      phase: 'Taper 减量期',
      workout: '轻松跑',
      distance: '6-8km 轻松跑',
      rpe: 'RPE 4',
      hrCap: '< 心率区间2上限',
      gear: '日常训练鞋',
      paceTarget: `${ePace}/km`,
      details: 'Taper期间保持适度活动量。',
    },
    6: {
      phase: 'Taper 减量期',
      workout: '轻松跑 + 短间歇',
      distance: '8km：含4x200m @ T-Pace',
      rpe: 'RPE 4-5',
      hrCap: '200m段可至阈值心率',
      gear: '日常训练鞋',
      paceTarget: `轻松段 ${ePace}/km，200m段 @ ${tPace}/km`,
      details: '减量但保留少量速度刺激。',
    },
    7: {
      phase: 'Taper 减量期',
      workout: '中距离轻松跑',
      distance: '10km 轻松跑',
      rpe: 'RPE 4',
      hrCap: '< 心率区间2上限',
      gear: '日常训练鞋',
      paceTarget: `${ePace}/km`,
      details: '赛前一周最长跑，之后逐日递减。',
    },
  }

  // D-8 to D-14: generic taper
  if (daysToRace > 7 && daysToRace <= 14) {
    return {
      phase: '赛前两周',
      workout: '正常训练（减量10-20%）',
      distance: '按周计划',
      rpe: 'RPE 5-6',
      hrCap: '正常训练心率',
      gear: '日常训练鞋',
      paceTarget: `轻松跑 ${ePace}/km，节奏跑 ${tPace}/km`,
      details: '开始逐渐降低训练量，保持强度。',
    }
  }

  // D-15+: normal training
  if (daysToRace > 14) {
    return {
      phase: '常规训练期',
      workout: '按周训练计划执行',
      distance: '按周计划',
      rpe: 'RPE 5-7',
      hrCap: '按训练类型',
      gear: '日常训练鞋',
      paceTarget: `E ${ePace} / M ${mPace} / T ${tPace}`,
      details: '保持正常训练节奏。',
    }
  }

  return plans[daysToRace] || plans[4] // fallback to easy run
}

// ============================================================
// Diet Plan Generator (D-N based)
// ============================================================

function getDietPlan(daysToRace, weightKg) {
  const normalCarb = `${Math.round(weightKg * 5)}-${Math.round(weightKg * 6)}g（5-6g/kg）`
  const normalProtein = `${Math.round(weightKg * 1.2)}g（1.2g/kg）`
  const loadCarb = `${Math.round(weightKg * 8)}-${Math.round(weightKg * 10)}g（8-10g/kg）`
  const loadProtein = `${Math.round(weightKg * 1.0)}g（1.0g/kg）`

  const plans = {
    0: {
      phase: '比赛日',
      carbTarget: `${Math.round(weightKg * 2)}-${Math.round(weightKg * 2.5)}g（赛前早餐）`,
      proteinTarget: '低',
      water: '300ml（早餐时）',
      meals: {
        '起床后': '200ml温水',
        '赛前3h早餐': '白米饭/面包 + 果酱（高碳水低纤维）',
        '赛前1h': '100-150mg咖啡因（可选）',
        '赛前10min': '能量胶1支 + 100ml水',
        '赛中每5km': '100-150ml运动饮料/水',
        '赛中10km': '能量胶1支（关键补给点）',
      },
      notes: ['严格复制赛前已验证的早餐方案', '不吃任何赛前没吃过的东西'],
    },
    1: {
      phase: '碳水负荷 Day 2',
      carbTarget: loadCarb,
      proteinTarget: loadProtein,
      water: '2L+',
      meals: {
        '早餐': '大碗白粥/面条 + 面包 + 果汁',
        '午餐': '大碗米饭(300g+) + 少量瘦肉',
        '下午加餐': '香蕉 + 能量棒 + 运动饮料',
        '晚餐': '面条/米饭 + 面包 — 最晚19:00吃完',
      },
      notes: ['碳水负荷第二天，继续高碳水', '晚餐最晚19:00', '22:00前入睡'],
    },
    2: {
      phase: '碳水负荷 Day 1',
      carbTarget: loadCarb,
      proteinTarget: loadProtein,
      water: '2L+',
      meals: {
        '早餐': '大碗白粥 + 馒头/面包 + 果酱 + 果汁',
        '午餐': '大碗米饭(300g+) + 少量瘦肉 + 蔬菜',
        '下午加餐': '香蕉2根 + 运动饮料500ml',
        '晚餐': '大碗面条/米饭 + 面包',
        '睡前': '果汁200ml或蜂蜜水',
      },
      notes: [
        '碳水负荷启动！以米饭、面条、面包、果汁、香蕉为主',
        '蛋白质适当降低，把胃空间留给碳水',
        '少量多餐，避免单次吃太撑',
        '体重上升0.5-1kg属正常（糖原+水分储存）',
      ],
    },
    3: {
      phase: '正常训练期（最后一天）',
      carbTarget: normalCarb,
      proteinTarget: normalProtein,
      water: '1.5-2L',
      meals: {
        '早餐': '粥/面包 + 鸡蛋 + 牛奶',
        '午餐': '米饭 + 瘦肉/鱼 + 蔬菜',
        '训练后': '巧克力牛奶或香蕉+酸奶（30min内）',
        '晚餐': '面条/米饭 + 蛋白质 + 蔬菜',
      },
      notes: ['明天开始碳水负荷，今天正常吃', '训练后及时补充碳水+蛋白'],
    },
    4: {
      phase: '正常训练期',
      carbTarget: normalCarb,
      proteinTarget: normalProtein,
      water: '1.5-2L',
      meals: {
        '早餐': '粥/面包 + 鸡蛋 + 牛奶',
        '午餐': '米饭 + 瘦肉/鱼 + 蔬菜',
        '训练前': '香蕉1根或能量棒（跑前30min）',
        '晚餐': '面条/米饭 + 蛋白质 + 蔬菜',
      },
      notes: ['避免尝试新食物', '少油少辛辣，减少肠胃负担'],
    },
  }

  // D-5 to D-14: pre-race training period
  if (daysToRace > 4 && daysToRace <= 14) {
    return {
      phase: '赛前训练期',
      carbTarget: normalCarb,
      proteinTarget: normalProtein,
      water: '1.5-2L',
      meals: {
        '早餐': '粥/面包+鸡蛋+牛奶',
        '午餐': '米饭+瘦肉/鱼+蔬菜',
        '晚餐': '面条/米饭+蛋白质+蔬菜',
      },
      notes: ['保持正常均衡饮食', '训练日注意补充碳水和蛋白'],
    }
  }

  // D-15+: normal training period
  if (daysToRace > 14) {
    return {
      phase: '常规训练期',
      carbTarget: normalCarb,
      proteinTarget: normalProtein,
      water: '1.5-2L',
      meals: {
        '早餐': '粥/面包+鸡蛋+牛奶',
        '午餐': '米饭+瘦肉/鱼+蔬菜',
        '晚餐': '面条/米饭+蛋白质+蔬菜',
      },
      notes: ['保持正常均衡饮食'],
    }
  }

  return plans[daysToRace] || plans[4]
}

// ============================================================
// Recovery Checklist (D-0 to D-4)
// ============================================================

function getRecoveryChecklist(daysToRace) {
  const baseItems = [
    { item: '晨脉检测', desc: '起床后静躺1min测心率，记录是否高于基线5+bpm', checked: false },
    { item: '睡眠质量', desc: '昨晚睡眠时长及质量（目标≥7h）', checked: false },
    { item: 'DOMS评估', desc: '肌肉酸痛程度 0-10（目标≤3）', checked: false },
    { item: '伤病检查', desc: '关节/肌腱/足底是否有异常疼痛', checked: false },
  ]

  const extraByDay = {
    0: [
      { item: '装备检查', desc: '号码布、芯片、跑鞋、能量胶、手表已就位', checked: false },
      { item: '赛前热身', desc: '慢跑5min + 动态拉伸 + 2-3次加速跑', checked: false },
      { item: '补给确认', desc: '能量胶/盐丸/运动饮料按计划携带', checked: false },
    ],
    1: [
      { item: '装备整理', desc: '明日比赛装备全部准备好并试穿', checked: false },
      { item: '赛前饮食', desc: '晚餐最晚19:00吃完，碳水为主', checked: false },
      { item: '作息确认', desc: '22:00前上床，设好闹钟', checked: false },
    ],
    2: [
      { item: '碳水负荷', desc: '全天高碳水饮食，记录摄入量', checked: false },
      { item: '体重监控', desc: '称重记录，+0.5-1kg为正常', checked: false },
    ],
    3: [
      { item: '训练完成', desc: '醒腿跑按计划完成', checked: false },
      { item: '训练后拉伸', desc: '跑后充分拉伸和泡沫轴放松', checked: false },
    ],
    4: [
      { item: '训练完成', desc: '轻松跑按计划完成', checked: false },
      { item: '补给采购', desc: '确认比赛日能量胶/盐丸/运动饮料已备齐', checked: false },
    ],
  }

  return {
    dayLabel: `D-${daysToRace}`,
    items: [...baseItems, ...(extraByDay[daysToRace] || [])],
  }
}
