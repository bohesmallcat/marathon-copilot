const api = require('../../services/api')
const { parseTimeToSeconds } = require('../../utils/util')

Page({
  data: {
    step: 1, // 1=赛事信息, 2=天气, 3=HRV(optional), 4=生成中, 5=结果
    runner: null,
    // 赛事
    raceName: '',
    raceDate: '',
    distanceIndex: 0,
    distanceOptions: ['半程马拉松', '全程马拉松'],
    startTime: '',
    targetTime: '',
    courseDescription: '',
    turnaroundCount: '0',
    intervalDays: '30',
    strategyIndex: 0,
    strategyOptions: ['均匀配速', '后程加速', '保守稳健'],
    // 天气
    weatherCondition: '',
    temperature: '',
    humidity: '',
    windSpeed: '',
    windDirection: '',
    // HRV
    useHRV: false,
    sevenDayAvg: '',
    sevenDaySD: '',
    raceDayHRV: '',
    // 结果
    generating: false,
    report: '',
    preCalc: null,
    reportId: '',
  },

  onLoad() {
    this.loadRunner()
  },

  async loadRunner() {
    try {
      const runner = await api.getProfile()
      this.setData({ runner })
    } catch (e) {
      wx.showToast({ title: '请先完善跑者档案', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
    }
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [field]: e.detail.value })
  },

  onPickerChange(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [field]: parseInt(e.detail.value) })
  },

  onDateChange(e) {
    this.setData({ raceDate: e.detail.value })
  },

  toggleHRV() {
    this.setData({ useHRV: !this.data.useHRV })
  },

  nextStep() {
    const { step } = this.data
    if (step === 1) {
      if (!this.data.raceName || !this.data.targetTime) {
        wx.showToast({ title: '请填写赛事名称和目标时间', icon: 'none' })
        return
      }
    }
    this.setData({ step: step + 1 })
  },

  prevStep() {
    this.setData({ step: this.data.step - 1 })
  },

  async generate() {
    this.setData({ step: 4, generating: true })

    const { runner } = this.data
    const strategyMap = ['even', 'negative', 'conservative']

    const requestData = {
      runner: {
        name: runner.name,
        weight: runner.weight,
        height: runner.height,
        vdot: runner.vdot,
        hrMax: runner.hrMax,
        rhr: runner.rhr,
        weeklyKm: runner.weeklyKm,
        pb10k: runner.pb10k,
        pb10kDate: runner.pb10kDate,
        pbHalf: runner.pbHalf,
        pbHalfDate: runner.pbHalfDate,
        pbFull: runner.pbFull,
        pbFullDate: runner.pbFullDate,
        injury: runner.injury,
        injuryCorrection: runner.injury ? 0.97 : 1.0,
      },
      race: {
        name: this.data.raceName,
        date: this.data.raceDate,
        distance: this.data.distanceIndex === 0 ? 'half' : 'full',
        startTime: this.data.startTime,
        targetTime: this.data.targetTime,
        courseDescription: this.data.courseDescription,
        turnaroundCount: parseInt(this.data.turnaroundCount) || 0,
        intervalDays: parseInt(this.data.intervalDays) || 30,
        strategy: strategyMap[this.data.strategyIndex],
      },
      weather: {
        condition: this.data.weatherCondition,
        temperature: parseFloat(this.data.temperature) || 15,
        lateTemp: parseFloat(this.data.temperature) || 15,
        humidity: parseFloat(this.data.humidity) || 50,
        windSpeed: parseFloat(this.data.windSpeed) || 0,
        windDirection: this.data.windDirection,
        crosswindCoeff: 0.6,
        exposedKm: this.data.distanceIndex === 0 ? 18 : 36,
      },
    }

    if (this.data.useHRV && this.data.sevenDayAvg) {
      requestData.hrv = {
        personalBaseline: runner.hrvBaseline || parseFloat(this.data.sevenDayAvg),
        sevenDayAvg: parseFloat(this.data.sevenDayAvg),
        sevenDaySD: parseFloat(this.data.sevenDaySD) || 5,
        sevenDayMin: parseFloat(this.data.sevenDayAvg) - parseFloat(this.data.sevenDaySD || 5),
        raceDayHRV: this.data.raceDayHRV ? parseFloat(this.data.raceDayHRV) : null,
      }
    }

    try {
      const result = await api.generateRaceGoal(requestData)
      this.setData({
        step: 5,
        generating: false,
        report: result.report,
        preCalc: result.preCalc,
        reportId: result.reportId,
      })
    } catch (e) {
      wx.showToast({ title: '生成失败: ' + e.message, icon: 'none' })
      this.setData({ step: 3, generating: false })
    }
  },

  viewFullReport() {
    wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${this.data.reportId}` })
  },

  shareReport() {
    // 可通过分享功能实现
  },

  onShareAppMessage() {
    return {
      title: `${this.data.runner.name} ${this.data.raceName} 目标设定`,
      path: `/pages/report-detail/report-detail?id=${this.data.reportId}`,
    }
  },
})
