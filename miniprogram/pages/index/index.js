const api = require('../../services/api')
const { formatDate } = require('../../utils/util')

Page({
  data: {
    hasProfile: false,
    runner: null,
    recentReports: [],
    loading: true,
  },

  onLoad() {
    this.loadData()
  },

  onShow() {
    this.loadData()
  },

  async loadData() {
    try {
      const runner = await api.getProfile()
      this.setData({ hasProfile: true, runner, loading: false })
    } catch (e) {
      this.setData({ hasProfile: false, runner: null, loading: false })
    }

    try {
      const goals = await api.getMyRaceGoals()
      const reviews = await api.getMyRaceReviews()
      const all = [...(goals || []), ...(reviews || [])]
        .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
        .slice(0, 5)
      this.setData({ recentReports: all })
    } catch (e) {
      console.log('loadReports:', e)
    }
  },

  goToProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },

  goToRaceGoal() {
    if (!this.data.hasProfile) {
      wx.showToast({ title: '请先完善跑者档案', icon: 'none' })
      return
    }
    wx.navigateTo({ url: '/pages/race-goal/race-goal' })
  },

  goToRaceReview() {
    if (!this.data.hasProfile) {
      wx.showToast({ title: '请先完善跑者档案', icon: 'none' })
      return
    }
    wx.navigateTo({ url: '/pages/race-review/race-review' })
  },

  goToReport(e) {
    const { id } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${id}` })
  },
})
