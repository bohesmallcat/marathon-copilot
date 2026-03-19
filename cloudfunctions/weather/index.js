const cloud = require('wx-server-sdk')
const axios = require('axios')
const { calculateEnvironmentalTax, getBodySizeCorrection } = require('../common/utils')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

// 天气 API 配置 - 支持和风天气(QWeather) / wttr.in
const WEATHER_CONFIG = {
  provider: process.env.WEATHER_PROVIDER || 'wttr', // 'qweather' | 'wttr'
  apiKey: process.env.WEATHER_API_KEY || '',
}

exports.main = async (event, context) => {
  const { action, data } = event

  switch (action) {
    case 'getForecast':
      return getForecast(data)
    case 'calculateImpact':
      return calculateImpact(data)
    case 'trackRace':
      return trackRace(data)
    default:
      return { code: -1, msg: '未知操作' }
  }
}

async function getForecast(data) {
  const { location, date } = data

  try {
    let weather
    if (WEATHER_CONFIG.provider === 'qweather' && WEATHER_CONFIG.apiKey) {
      weather = await fetchQWeather(location)
    } else {
      weather = await fetchWttr(location)
    }
    return { code: 0, data: weather }
  } catch (e) {
    console.error('Weather fetch error:', e)
    return { code: -1, msg: e.message || '天气获取失败' }
  }
}

async function fetchWttr(location) {
  const url = `https://wttr.in/${encodeURIComponent(location)}?format=j1`
  const res = await axios.get(url, { timeout: 10000 })
  const data = res.data

  const current = data.current_condition[0]
  const forecast = data.weather[0]

  return {
    provider: 'wttr.in',
    location: location,
    current: {
      temp: parseInt(current.temp_C),
      humidity: parseInt(current.humidity),
      windSpeed: parseInt(current.windspeedMiles),
      windDir: current.winddir16Point,
      condition: current.weatherDesc[0].value,
    },
    forecast: {
      minTemp: parseInt(forecast.mintempC),
      maxTemp: parseInt(forecast.maxtempC),
      avgHumidity: parseInt(forecast.hourly.reduce((sum, h) => sum + parseInt(h.humidity), 0) / forecast.hourly.length),
      avgWindSpeed: parseInt(forecast.hourly.reduce((sum, h) => sum + parseInt(h.windspeedMiles), 0) / forecast.hourly.length),
      chanceOfRain: Math.max(...forecast.hourly.map(h => parseInt(h.chanceofrain))),
    },
    hourly: forecast.hourly.map(h => ({
      time: h.time.padStart(4, '0'),
      temp: parseInt(h.tempC),
      humidity: parseInt(h.humidity),
      windSpeed: parseInt(h.windspeedMiles),
      windDir: h.winddir16Point,
      rain: parseInt(h.chanceofrain),
    })),
  }
}

async function fetchQWeather(location) {
  // 和风天气 API
  const url = `https://devapi.qweather.com/v7/weather/3d?location=${encodeURIComponent(location)}&key=${WEATHER_CONFIG.apiKey}`
  const res = await axios.get(url, { timeout: 10000 })
  const data = res.data
  const day = data.daily[0]

  return {
    provider: 'QWeather',
    location: location,
    current: {
      temp: parseInt(day.tempMax),
      humidity: parseInt(day.humidity),
      windSpeed: Math.round(parseInt(day.windSpeedDay) * 0.621371), // km/h to mph
      windDir: day.windDirDay,
      condition: day.textDay,
    },
    forecast: {
      minTemp: parseInt(day.tempMin),
      maxTemp: parseInt(day.tempMax),
      avgHumidity: parseInt(day.humidity),
      avgWindSpeed: Math.round(parseInt(day.windSpeedDay) * 0.621371),
      chanceOfRain: 0,
    },
  }
}

async function calculateImpact(data) {
  const { weather, runner, race } = data
  const distanceKm = race.distance === 'full' ? 42.195 : 21.0975
  const bodySize = getBodySizeCorrection(runner.height || 170, runner.weight || 65)

  const envTax = calculateEnvironmentalTax({
    windSpeedMph: weather.windSpeed || 0,
    crosswindCoeff: weather.crosswindCoeff || 0.6,
    exposedKm: weather.exposedKm || (distanceKm * 0.85),
    humidity: weather.humidity || 50,
    totalDistanceKm: distanceKm,
    lateTemp: weather.lateTemp || weather.temp || 15,
    penaltyKm: distanceKm / 3,
    bodySizeCorrectionFactor: bodySize.correctionFactor,
    turnaroundCount: race.turnaroundCount || 0,
  })

  return {
    code: 0,
    data: {
      envTax,
      bodySize,
      riskLevel: envTax.total > 60 ? 'high' : envTax.total > 30 ? 'medium' : 'low',
      suggestion: envTax.total > 60
        ? '环境税较高，建议下调目标配速5-10"/km'
        : envTax.total > 30
        ? '环境有一定影响，建议保持计划配速并做好散热'
        : '环境条件良好，可按计划执行',
    }
  }
}

async function trackRace(data) {
  const { raceId, location } = data

  try {
    const weather = await fetchWttr(location)
    await db.collection('weather_tracking').add({
      data: {
        raceId, location,
        weather,
        trackedAt: db.serverDate(),
      }
    })
    return { code: 0, data: weather }
  } catch (e) {
    return { code: -1, msg: e.message }
  }
}
