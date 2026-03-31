const api = require('../../services/api')

Page({
  data: {
    activeTab: 0, // 0=全部, 1=目标设定, 2=赛后复盘
    reports: [],
    loading: true,
    empty: false,
  },

  onLoad() { this.loadReports() },
  onShow() { this.loadReports() },

  async loadReports() {
    this.setData({ loading: true })
    try {
      const [goals, reviews] = await Promise.all([
        api.getMyRaceGoals().catch(() => []),
        api.getMyRaceReviews().catch(() => []),
      ])

      const all = [
        ...(goals || []).map(r => ({ ...r, typeLabel: '目标设定', typeClass: 'tag-info' })),
        ...(reviews || []).map(r => ({ ...r, typeLabel: '赛后复盘', typeClass: 'tag-warning' })),
      ].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))

      this.setData({ reports: all, loading: false, empty: all.length === 0 })
    } catch (e) {
      this.setData({ loading: false, empty: true })
    }
  },

  onTabChange(e) {
    this.setData({ activeTab: parseInt(e.currentTarget.dataset.tab) })
  },

  getFilteredReports() {
    const { activeTab, reports } = this.data
    if (activeTab === 0) return reports
    if (activeTab === 1) return reports.filter(r => r.type === 'race-goal')
    return reports.filter(r => r.type === 'race-review')
  },

  goToReport(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${id}` })
  },

  goToRaceGoal() {
    wx.navigateTo({ url: '/pages/race-goal/race-goal' })
  },

  goToRaceReview() {
    wx.navigateTo({ url: '/pages/race-review/race-review' })
  },
})
