const api = require('../../services/api')

Page({
  data: {
    step: 1, // 1=赛前方案, 2=赛后数据, 3=生成中, 4=结果
    runner: null,
    // 赛前方案
    raceName: '',
    distanceIndex: 0,
    distanceOptions: ['半程马拉松', '全程马拉松'],
    targetTime: '',
    targetPace: '',
    pbOdds: '',
    envTaxSeconds: '',
    // 赛后数据
    finishTime: '',
    avgPace: '',
    avgHR: '',
    maxHR: '',
    gpsDistance: '',
    cadence: '',
    splits: '',
    feedback: '',
    equipment: '',
    injuryFeedback: '',
    // 天气
    actualCondition: '',
    actualTemp: '',
    actualHumidity: '',
    actualWindSpeed: '',
    // 结果
    generating: false,
    report: '',
    preCalc: null,
    reportId: '',
  },

  onLoad() { this.loadRunner() },

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

  nextStep() { this.setData({ step: this.data.step + 1 }) },
  prevStep() { this.setData({ step: this.data.step - 1 }) },

  async generate() {
    if (!this.data.finishTime) {
      wx.showToast({ title: '请填写完赛时间', icon: 'none' })
      return
    }
    this.setData({ step: 3, generating: true })

    const { runner } = this.data
    const requestData = {
      runner: {
        name: runner.name,
        weight: runner.weight,
        height: runner.height,
        vdot: runner.vdot,
        weeklyKm: runner.weeklyKm,
        injury: runner.injury,
      },
      prePlan: {
        raceName: this.data.raceName,
        distance: this.data.distanceIndex === 0 ? 'half' : 'full',
        targetTime: this.data.targetTime,
        targetPace: this.data.targetPace,
        pbOdds: this.data.pbOdds,
        envTaxSeconds: this.data.envTaxSeconds,
        turnaroundCount: 0,
      },
      actual: {
        finishTime: this.data.finishTime,
        avgPace: this.data.avgPace,
        avgHR: this.data.avgHR,
        maxHR: this.data.maxHR,
        gpsDistance: this.data.gpsDistance,
        cadence: this.data.cadence,
        splits: this.data.splits,
        feedback: this.data.feedback,
        equipment: this.data.equipment,
        injuryFeedback: this.data.injuryFeedback,
      },
      weather: {
        actualCondition: this.data.actualCondition,
        actualTemp: parseFloat(this.data.actualTemp) || 15,
        actualHumidity: parseFloat(this.data.actualHumidity) || 50,
        actualWindSpeed: parseFloat(this.data.actualWindSpeed) || 0,
        crosswindCoeff: 0.6,
        exposedKm: this.data.distanceIndex === 0 ? 18 : 36,
      },
    }

    try {
      const result = await api.generateRaceReview(requestData)
      this.setData({
        step: 4, generating: false,
        report: result.report, preCalc: result.preCalc, reportId: result.reportId,
      })
    } catch (e) {
      wx.showToast({ title: '生成失败: ' + e.message, icon: 'none' })
      this.setData({ step: 2, generating: false })
    }
  },

  viewFullReport() {
    wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${this.data.reportId}` })
  },

  onShareAppMessage() {
    return {
      title: `${this.data.runner.name} ${this.data.raceName} 赛后复盘`,
      path: `/pages/report-detail/report-detail?id=${this.data.reportId}`,
    }
  },
})
