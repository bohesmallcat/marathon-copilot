/**
 * API 服务层 - 封装云函数调用
 */

function callCloud(name, action, data = {}) {
  return new Promise((resolve, reject) => {
    wx.cloud.callFunction({
      name,
      data: { action, data },
      success: res => {
        if (res.result.code === 0) {
          resolve(res.result.data)
        } else {
          reject(new Error(res.result.msg || '请求失败'))
        }
      },
      fail: err => reject(err),
    })
  })
}

module.exports = {
  // 用户
  getProfile: () => callCloud('user', 'getProfile'),
  saveProfile: (data) => callCloud('user', 'saveProfile', data),
  updateProfile: (data) => callCloud('user', 'updateProfile', data),
  addPB: (data) => callCloud('user', 'addPB', data),
  getPBList: () => callCloud('user', 'getPBList'),
  saveHRV: (data) => callCloud('user', 'saveHRV', data),
  getHRVData: (data) => callCloud('user', 'getHRVData', data),

  // 赛前目标
  generateRaceGoal: (data) => callCloud('raceGoal', 'generate', data),
  getRaceGoalReport: (reportId) => callCloud('raceGoal', 'getReport', { reportId }),
  getMyRaceGoals: () => callCloud('raceGoal', 'getMyReports'),

  // 赛后复盘
  generateRaceReview: (data) => callCloud('raceReview', 'generate', data),
  getRaceReviewReport: (reportId) => callCloud('raceReview', 'getReport', { reportId }),
  getMyRaceReviews: () => callCloud('raceReview', 'getMyReports'),

  // 天气
  getWeatherForecast: (data) => callCloud('weather', 'getForecast', data),
  calculateWeatherImpact: (data) => callCloud('weather', 'calculateImpact', data),
  trackRaceWeather: (data) => callCloud('weather', 'trackRace', data),
}
