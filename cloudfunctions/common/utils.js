/**
 * Marathon Copilot - Core Algorithm Library
 * 核心算法工具库: VDOT, Environmental Tax, HRV Correction, PB Probability, Pacing
 */

// ============================================================
// VDOT Calculator (Daniels Running Formula)
// ============================================================

function calculateVDOT(distanceKm, timeMinutes) {
  const velocity = distanceKm / timeMinutes * 1000; // meters per minute
  const vo2 = -4.60 + 0.182258 * velocity + 0.000104 * Math.pow(velocity, 2);
  const pctVO2max = 0.8 + 0.1894393 * Math.exp(-0.012778 * timeMinutes)
    + 0.2989558 * Math.exp(-0.1932605 * timeMinutes);
  return Math.round(vo2 / pctVO2max * 10) / 10;
}

function predictTimeFromVDOT(vdot, distanceKm) {
  let lo = distanceKm * 2, hi = distanceKm * 10;
  for (let i = 0; i < 100; i++) {
    const mid = (lo + hi) / 2;
    calculateVDOT(distanceKm, mid) > vdot ? (lo = mid) : (hi = mid);
  }
  return Math.round((lo + hi) / 2 * 10) / 10;
}

function getTrainingPaces(vdot) {
  const mPace = predictTimeFromVDOT(vdot, 42.195) / 42.195 * 60;
  return {
    easy: Math.round(mPace * 1.25),
    marathon: Math.round(mPace),
    threshold: Math.round(mPace * 0.91),
    interval: Math.round(mPace * 0.82),
    repetition: Math.round(mPace * 0.75),
  };
}

// ============================================================
// Body Surface Area (BSA) Calculator
// ============================================================

function calculateBSA(heightCm, weightKg) {
  return 0.007184 * Math.pow(heightCm, 0.725) * Math.pow(weightKg, 0.425);
}

function getBodySizeCorrection(heightCm, weightKg) {
  const bsa = calculateBSA(heightCm, weightKg);
  const bsaRatio = bsa / weightKg;
  const referenceBsaRatio = 0.0270; // 65kg/170cm standard
  const correctionFactor = Math.round(referenceBsaRatio / bsaRatio * 100) / 100;
  return {
    bsa: Math.round(bsa * 1000) / 1000,
    bsaRatio: Math.round(bsaRatio * 10000) / 10000,
    correctionFactor,
  };
}

// ============================================================
// Environmental Tax Calculator
// ============================================================

function calculateEnvironmentalTax(params) {
  const {
    windSpeedMph = 0, crosswindCoeff = 0.6, exposedKm = 0,
    humidity = 50, totalDistanceKm = 21.0975,
    lateTemp = 15, penaltyKm = 0,
    bodySizeCorrectionFactor = 1.0, turnaroundCount = 0,
  } = params;

  const windTax = windSpeedMph * 0.5 * crosswindCoeff * exposedKm;
  const humidityTax = humidity > 70 ? (humidity - 70) * 0.5 * totalDistanceKm : 0;
  const temperatureTax = lateTemp > 15
    ? (lateTemp - 15) * 2 * (penaltyKm || totalDistanceKm / 3) / 6 * bodySizeCorrectionFactor
    : 0;
  const turnaroundTax = turnaroundCount * 4;
  const totalTax = Math.round(windTax + humidityTax + temperatureTax + turnaroundTax);

  return {
    wind: Math.round(windTax),
    humidity: Math.round(humidityTax),
    temperature: Math.round(temperatureTax),
    turnaround: Math.round(turnaroundTax),
    total: totalTax,
    summary: `风阻${Math.round(windTax)}" + 湿度${Math.round(humidityTax)}" + 温度${Math.round(temperatureTax)}" + 折返${Math.round(turnaroundTax)}" = 总计${totalTax}"`,
  };
}

// ============================================================
// HRV Correction Coefficient
// ============================================================

function calculateHRVCorrection(params) {
  const { personalBaseline, sevenDayAvg, sevenDaySD, sevenDayMin, raceDayHRV } = params;
  const baselineDeviation = ((sevenDayAvg - personalBaseline) / personalBaseline) * 100;
  const stabilityCV = (sevenDaySD / sevenDayAvg) * 100;
  const raceDayRebound = raceDayHRV && sevenDayMin
    ? ((raceDayHRV - sevenDayMin) / sevenDayMin) * 100 : null;

  const fBaseline = baselineDeviation > 5 ? 1.02 : baselineDeviation >= -3 ? 1.00 : baselineDeviation >= -10 ? 0.98 : 0.95;
  const fStability = stabilityCV < 10 ? 1.02 : stabilityCV <= 15 ? 1.00 : 0.97;
  const fRebound = raceDayRebound === null ? 1.00 : raceDayRebound > 30 ? 1.01 : raceDayRebound >= 15 ? 1.00 : 0.98;
  const correction = Math.round(fBaseline * fStability * fRebound * 1000) / 1000;

  return {
    baselineDeviation: Math.round(baselineDeviation * 10) / 10,
    stabilityCV: Math.round(stabilityCV * 10) / 10,
    raceDayRebound: raceDayRebound !== null ? Math.round(raceDayRebound * 10) / 10 : null,
    factors: { baseline: fBaseline, stability: fStability, rebound: fRebound },
    correction,
    assessment: correction >= 1.02 ? '状态极佳' : correction >= 1.00 ? '状态正常' : correction >= 0.97 ? '状态偏低' : '状态较差，建议保守目标',
  };
}

// ============================================================
// PB Probability Calculator
// ============================================================

function calculatePBOdds(params) {
  const {
    currentVDOT, targetVDOT, weeklyKm = 50,
    distanceKm = 21.0975, envTaxSeconds = 0, targetTimeSeconds,
    hrvCorrection = 1.0, injuryCorrection = 1.0, raceIntervalDays = 30,
  } = params;

  const vdotGap = currentVDOT - targetVDOT;
  const baseProbability = vdotGap >= 2 ? 0.90 : vdotGap >= 1 ? 0.85 : vdotGap >= 0 ? 0.78
    : vdotGap >= -0.5 ? 0.70 : vdotGap >= -1 ? 0.60 : vdotGap >= -2 ? 0.45 : 0.30;

  const minWeeklyKm = distanceKm === 42.195 ? 60 : 40;
  const optWeeklyKm = distanceKm === 42.195 ? 80 : 55;
  const trainingCoeff = weeklyKm >= optWeeklyKm ? 1.00 : weeklyKm >= minWeeklyKm ? 0.95 : weeklyKm >= minWeeklyKm * 0.75 ? 0.90 : 0.85;
  const trainingGrade = weeklyKm >= optWeeklyKm ? 'A' : weeklyKm >= minWeeklyKm ? 'B' : weeklyKm >= minWeeklyKm * 0.75 ? 'C' : 'D';

  const envTaxPct = targetTimeSeconds > 0 ? envTaxSeconds / targetTimeSeconds : 0;
  const envCoeff = 1 - envTaxPct;
  const intervalCoeff = raceIntervalDays >= 21 ? 1.00 : raceIntervalDays >= 14 ? 0.97 : raceIntervalDays >= 7 ? 0.93 : 0.88;

  const rawOdds = baseProbability * trainingCoeff * envCoeff * hrvCorrection * injuryCorrection * intervalCoeff;
  const odds = Math.round(Math.min(Math.max(rawOdds, 0.05), 0.95) * 100);

  let assessment;
  if (odds >= 80) assessment = '目标非常可行，建议勇敢冲击';
  else if (odds >= 65) assessment = '目标合理，有较大把握达成';
  else if (odds >= 50) assessment = '目标有挑战性，需要良好的执行';
  else if (odds >= 35) assessment = '目标偏激进，建议准备保守备选方案';
  else assessment = '目标风险较高，强烈建议调整目标';

  return {
    odds, confidence: `${Math.max(odds - 5, 5)}%-${Math.min(odds + 5, 95)}%`, assessment,
    factors: {
      baseProbability: Math.round(baseProbability * 100),
      trainingCoeff: { value: trainingCoeff, grade: trainingGrade, weeklyKm },
      envCoeff: { value: Math.round(envCoeff * 1000) / 1000, taxSeconds: envTaxSeconds, taxPct: Math.round(envTaxPct * 10000) / 100 },
      hrvCorrection, injuryCorrection,
      intervalCoeff: { value: intervalCoeff, days: raceIntervalDays },
    },
  };
}

// ============================================================
// Pacing Plan Generator
// ============================================================

function generatePacingPlan(params) {
  const { targetTimeSeconds, distanceKm = 21.0975, strategy = 'even', envTaxSeconds = 0 } = params;
  const totalKm = Math.ceil(distanceKm);
  const lastKmFraction = distanceKm - Math.floor(distanceKm);
  const adjustedTime = targetTimeSeconds - envTaxSeconds * 0.5;
  const avgPaceSeconds = adjustedTime / distanceKm;

  const plan = [];
  for (let km = 1; km <= totalKm; km++) {
    const isLastKm = km === totalKm;
    const kmDistance = isLastKm && lastKmFraction > 0 ? lastKmFraction : 1;
    let paceAdjust = 0;

    if (strategy === 'even') {
      if (km <= 2) paceAdjust = -2;
      else if (km > distanceKm * 0.85) paceAdjust = 1;
    } else if (strategy === 'negative') {
      if (km <= distanceKm * 0.5) paceAdjust = 3;
      else if (km <= distanceKm * 0.75) paceAdjust = 0;
      else paceAdjust = -3;
    } else if (strategy === 'conservative') {
      paceAdjust = 2;
      if (km <= 3) paceAdjust = 0;
    }

    plan.push({
      km, distance: kmDistance,
      paceSeconds: Math.round(avgPaceSeconds + paceAdjust),
      paceDisplay: formatPace(Math.round(avgPaceSeconds + paceAdjust)),
      cumTimeSeconds: 0,
      segment: getSegmentName(km, distanceKm),
    });
  }

  let cumTime = 0;
  for (const item of plan) {
    cumTime += item.paceSeconds * item.distance;
    item.cumTimeSeconds = Math.round(cumTime);
    item.cumTimeDisplay = formatTime(Math.round(cumTime));
  }
  return plan;
}

function getSegmentName(km, distanceKm) {
  const pct = km / distanceKm;
  if (pct <= 0.15) return '起步段';
  if (pct <= 0.5) return '巡航段';
  if (pct <= 0.75) return '维持段';
  if (pct <= 0.9) return '坚持段';
  return '冲刺段';
}

// ============================================================
// Utility Functions
// ============================================================

function formatPace(seconds) {
  const min = Math.floor(seconds / 60);
  const sec = Math.round(seconds % 60);
  return `${min}'${sec.toString().padStart(2, '0')}"`;
}

function formatTime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.round(totalSeconds % 60);
  if (hours > 0) return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function parseTimeToSeconds(timeStr) {
  if (!timeStr) return 0;
  timeStr = timeStr.trim();
  if (/^\d+$/.test(timeStr)) return parseInt(timeStr);
  const parts = timeStr.split(':');
  if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
  if (parts.length === 2) return parseInt(parts[0]) * 60 + parseInt(parts[1]);
  return 0;
}

function parsePaceToSeconds(paceStr) {
  if (!paceStr) return 0;
  paceStr = paceStr.trim();
  if (/^\d+$/.test(paceStr)) return parseInt(paceStr);
  const m = paceStr.match(/(\d+)['':](\d+)/);
  return m ? parseInt(m[1]) * 60 + parseInt(m[2]) : 0;
}

function getDistanceLabel(km) {
  if (Math.abs(km - 21.0975) < 0.5) return '半程马拉松';
  if (Math.abs(km - 42.195) < 0.5) return '全程马拉松';
  if (Math.abs(km - 10) < 0.5) return '10公里';
  if (Math.abs(km - 5) < 0.5) return '5公里';
  return `${km}公里`;
}

module.exports = {
  calculateVDOT, predictTimeFromVDOT, getTrainingPaces,
  calculateBSA, getBodySizeCorrection,
  calculateEnvironmentalTax, calculateHRVCorrection, calculatePBOdds,
  generatePacingPlan, formatPace, formatTime,
  parseTimeToSeconds, parsePaceToSeconds, getDistanceLabel,
};
