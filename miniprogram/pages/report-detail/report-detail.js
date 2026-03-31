const api = require('../../services/api')
const { simpleMarkdownToNodes } = require('../../utils/util')

Page({
  data: {
    loading: true,
    report: null,
    reportNodes: [],
    preCalc: null,
    reportType: '',
  },

  onLoad(options) {
    if (options.id) {
      this.loadReport(options.id)
    }
  },

  async loadReport(id) {
    try {
      // Try race-goal first, then race-review
      let data
      try {
        data = await api.getRaceGoalReport(id)
      } catch (e) {
        data = await api.getRaceReviewReport(id)
      }

      const nodes = simpleMarkdownToNodes(data.report)

      this.setData({
        loading: false,
        report: data,
        reportNodes: nodes,
        preCalc: data.preCalc,
        reportType: data.type,
      })
    } catch (e) {
      wx.showToast({ title: '报告加载失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },

  onShareAppMessage() {
    const { report } = this.data
    if (!report) return { title: 'Marathon Copilot 报告' }
    const name = report.runner ? report.runner.name : ''
    const race = report.race ? report.race.name : (report.prePlan ? report.prePlan.raceName : '')
    return {
      title: `${name} ${race} - Marathon Copilot`,
      path: `/pages/report-detail/report-detail?id=${report._id}`,
    }
  },
})
