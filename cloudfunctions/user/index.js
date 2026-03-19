const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command

exports.main = async (event, context) => {
  const { action, data } = event
  const wxContext = cloud.getWXContext()
  const openid = wxContext.OPENID

  switch (action) {
    case 'getProfile':
      return getProfile(openid)
    case 'saveProfile':
      return saveProfile(openid, data)
    case 'updateProfile':
      return updateProfile(openid, data)
    case 'addPB':
      return addPB(openid, data)
    case 'getPBList':
      return getPBList(openid)
    case 'saveHRV':
      return saveHRV(openid, data)
    case 'getHRVData':
      return getHRVData(openid, data)
    default:
      return { code: -1, msg: '未知操作' }
  }
}

async function getProfile(openid) {
  try {
    const res = await db.collection('runners').where({ _openid: openid }).get()
    if (res.data.length > 0) {
      return { code: 0, data: res.data[0] }
    }
    return { code: 1, msg: '未找到档案', data: null }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function saveProfile(openid, data) {
  try {
    const existing = await db.collection('runners').where({ _openid: openid }).get()
    if (existing.data.length > 0) {
      await db.collection('runners').doc(existing.data[0]._id).update({
        data: { ...data, updatedAt: db.serverDate() }
      })
      return { code: 0, msg: '档案已更新' }
    }
    await db.collection('runners').add({
      data: { _openid: openid, ...data, createdAt: db.serverDate(), updatedAt: db.serverDate() }
    })
    return { code: 0, msg: '档案已创建' }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function updateProfile(openid, data) {
  try {
    const existing = await db.collection('runners').where({ _openid: openid }).get()
    if (existing.data.length === 0) return { code: 1, msg: '档案不存在' }
    await db.collection('runners').doc(existing.data[0]._id).update({
      data: { ...data, updatedAt: db.serverDate() }
    })
    return { code: 0, msg: '更新成功' }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function addPB(openid, data) {
  try {
    await db.collection('pb_records').add({
      data: { _openid: openid, ...data, createdAt: db.serverDate() }
    })
    return { code: 0, msg: 'PB 记录已添加' }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function getPBList(openid) {
  try {
    const res = await db.collection('pb_records')
      .where({ _openid: openid })
      .orderBy('date', 'desc')
      .get()
    return { code: 0, data: res.data }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function saveHRV(openid, data) {
  try {
    await db.collection('hrv_data').add({
      data: { _openid: openid, ...data, createdAt: db.serverDate() }
    })
    return { code: 0, msg: 'HRV 数据已保存' }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}

async function getHRVData(openid, data) {
  try {
    const query = { _openid: openid }
    if (data && data.days) {
      const since = new Date()
      since.setDate(since.getDate() - data.days)
      query.date = _.gte(since.toISOString().split('T')[0])
    }
    const res = await db.collection('hrv_data')
      .where(query)
      .orderBy('date', 'desc')
      .limit(data && data.limit || 30)
      .get()
    return { code: 0, data: res.data }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}
