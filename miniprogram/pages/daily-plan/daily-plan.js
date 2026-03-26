const api = require('../../services/api')

Page({
  data: {
    hasRace: false,
    raceName: '',
    raceDate: '',
    raceDistance: 21.0975,
    targetTime: '',
    daysToRace: 0,
    activeTab: 'training',
    training: null,
    diet: null,
    recovery: null,
    loading: false,
  },

  onLoad() {
    // Try loading saved race info from storage
    const raceInfo = wx.getStorageSync('raceInfo')
    if (raceInfo && raceInfo.raceDate) {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const raceDay = new Date(raceInfo.raceDate)
      raceDay.setHours(0, 0, 0, 0)
      const daysToRace = Math.round((raceDay - today) / (1000 * 60 * 60 * 24))
      
      if (daysToRace >= 0) {
        this.setData({
          hasRace: true,
          raceName: raceInfo.raceName,
          raceDate: raceInfo.raceDate,
          raceDistance: raceInfo.raceDistance || 21.0975,
          targetTime: raceInfo.targetTime || '',
          daysToRace,
        })
        this.loadDailyPlan()
      }
    }
  },

  onRaceNameInput(e) { this.setData({ raceName: e.detail.value }) },
  onDateChange(e) { this.setData({ raceDate: e.detail.value }) },
  onTargetInput(e) { this.setData({ targetTime: e.detail.value }) },
  setDistance(e) { this.setData({ raceDistance: parseFloat(e.currentTarget.dataset.km) }) },

  confirmRace() {
    const { raceName, raceDate, raceDistance, targetTime } = this.data
    if (!raceName || !raceDate) {
      wx.showToast({ title: '请填写比赛名称和日期', icon: 'none' })
      return
    }
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const raceDay = new Date(raceDate)
    raceDay.setHours(0, 0, 0, 0)
    const daysToRace = Math.round((raceDay - today) / (1000 * 60 * 60 * 24))
    
    if (daysToRace < 0) {
      wx.showToast({ title: '比赛日期已过', icon: 'none' })
      return
    }
    
    wx.setStorageSync('raceInfo', { raceName, raceDate, raceDistance, targetTime })
    this.setData({ hasRace: true, daysToRace })
    this.loadDailyPlan()
  },

  async loadDailyPlan() {
    this.setData({ loading: true })
    try {
      const result = await api.getDailyPlan({
        raceDate: this.data.raceDate,
        raceName: this.data.raceName,
        raceDistance: this.data.raceDistance,
        targetTime: this.data.targetTime,
      })
      
      // Convert meals object to array for wx:for
      let mealList = []
      if (result.diet && result.diet.meals) {
        mealList = Object.entries(result.diet.meals).map(([time, desc]) => ({ time, desc }))
      }
      
      this.setData({
        training: result.training,
        diet: { ...result.diet, mealList },
        recovery: result.recovery || [],
        loading: false,
      })
    } catch (e) {
      console.error('loadDailyPlan error:', e)
      wx.showToast({ title: '获取计划失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab })
  },

  toggleRecovery(e) {
    const idx = e.currentTarget.dataset.index
    const recovery = this.data.recovery
    recovery[idx].checked = !recovery[idx].checked
    this.setData({ recovery })
  },
})
