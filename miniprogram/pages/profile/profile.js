const api = require('../../services/api')

Page({
  data: {
    name: '',
    weight: '',
    height: '',
    vdot: '',
    hrMax: '',
    rhr: '',
    weeklyKm: '',
    pb10k: '',
    pb10kDate: '',
    pbHalf: '',
    pbHalfDate: '',
    pbFull: '',
    pbFullDate: '',
    tPace: '',
    injury: '',
    hrvDevice: '',
    hrvBaseline: '',
    hrvBaselineSD: '',
    isEdit: false,
    saving: false,
  },

  onLoad() {
    this.loadProfile()
  },

  async loadProfile() {
    try {
      const profile = await api.getProfile()
      if (profile) {
        this.setData({ ...profile, isEdit: true })
      }
    } catch (e) {
      // New user
    }
  },

  onInput(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [field]: e.detail.value })
  },

  async onSave() {
    const { name, weight, height } = this.data
    if (!name.trim()) {
      wx.showToast({ title: '请输入昵称', icon: 'none' })
      return
    }
    if (!weight || !height) {
      wx.showToast({ title: '请输入体重和身高', icon: 'none' })
      return
    }

    this.setData({ saving: true })

    const profileData = {
      name: this.data.name,
      weight: parseFloat(this.data.weight),
      height: parseFloat(this.data.height),
      vdot: this.data.vdot ? parseFloat(this.data.vdot) : null,
      hrMax: this.data.hrMax ? parseInt(this.data.hrMax) : null,
      rhr: this.data.rhr ? parseInt(this.data.rhr) : null,
      weeklyKm: this.data.weeklyKm ? parseFloat(this.data.weeklyKm) : null,
      pb10k: this.data.pb10k || null,
      pb10kDate: this.data.pb10kDate || null,
      pbHalf: this.data.pbHalf || null,
      pbHalfDate: this.data.pbHalfDate || null,
      pbFull: this.data.pbFull || null,
      pbFullDate: this.data.pbFullDate || null,
      tPace: this.data.tPace || null,
      injury: this.data.injury || null,
      hrvDevice: this.data.hrvDevice || null,
      hrvBaseline: this.data.hrvBaseline ? parseFloat(this.data.hrvBaseline) : null,
      hrvBaselineSD: this.data.hrvBaselineSD ? parseFloat(this.data.hrvBaselineSD) : null,
    }

    try {
      await api.saveProfile(profileData)
      wx.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 1000)
    } catch (e) {
      wx.showToast({ title: '保存失败: ' + e.message, icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  onDateChange(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [field]: e.detail.value })
  },
})
