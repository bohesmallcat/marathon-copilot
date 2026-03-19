/**
 * 前端工具函数 - 与云函数 common/utils.js 保持一致的轻量版
 */

function formatPace(seconds) {
  const min = Math.floor(seconds / 60)
  const sec = Math.round(seconds % 60)
  return `${min}'${sec.toString().padStart(2, '0')}"`
}

function formatTime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = Math.round(totalSeconds % 60)
  if (hours > 0) return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

function parseTimeToSeconds(timeStr) {
  if (!timeStr) return 0
  timeStr = timeStr.trim()
  if (/^\d+$/.test(timeStr)) return parseInt(timeStr)
  const parts = timeStr.split(':')
  if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2])
  if (parts.length === 2) return parseInt(parts[0]) * 60 + parseInt(parts[1])
  return 0
}

function getDistanceLabel(km) {
  if (Math.abs(km - 21.0975) < 0.5) return '半程马拉松'
  if (Math.abs(km - 42.195) < 0.5) return '全程马拉松'
  if (Math.abs(km - 10) < 0.5) return '10公里'
  if (Math.abs(km - 5) < 0.5) return '5公里'
  return `${km}公里`
}

function getOddsColor(odds) {
  if (odds >= 70) return '#27AE60'
  if (odds >= 50) return '#F39C12'
  return '#E74C3C'
}

function getOddsLabel(odds) {
  if (odds >= 80) return '极高'
  if (odds >= 65) return '较高'
  if (odds >= 50) return '中等'
  if (odds >= 35) return '偏低'
  return '较低'
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`
}

function simpleMarkdownToNodes(md) {
  if (!md) return []
  const lines = md.split('\n')
  const nodes = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    if (trimmed.startsWith('### ')) {
      nodes.push({ type: 'h3', text: trimmed.slice(4) })
    } else if (trimmed.startsWith('## ')) {
      nodes.push({ type: 'h2', text: trimmed.slice(3) })
    } else if (trimmed.startsWith('# ')) {
      nodes.push({ type: 'h1', text: trimmed.slice(2) })
    } else if (trimmed.startsWith('> ')) {
      const content = trimmed.slice(2)
      let variant = 'info'
      if (content.includes('警告') || content.includes('注意')) variant = 'warning'
      if (content.includes('危险') || content.includes('红灯')) variant = 'danger'
      nodes.push({ type: 'blockquote', text: content, variant })
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      nodes.push({ type: 'list-item', text: trimmed.slice(2) })
    } else if (trimmed.startsWith('|')) {
      // Table row - collect consecutive table rows
      const lastNode = nodes[nodes.length - 1]
      if (lastNode && lastNode.type === 'table') {
        const cells = trimmed.split('|').filter(c => c.trim()).map(c => c.trim())
        if (!cells.every(c => /^[-:]+$/.test(c))) {
          lastNode.rows.push(cells)
        }
      } else {
        const cells = trimmed.split('|').filter(c => c.trim()).map(c => c.trim())
        nodes.push({ type: 'table', headers: cells, rows: [] })
      }
    } else if (trimmed.startsWith('```')) {
      nodes.push({ type: 'code-start', text: trimmed.slice(3) })
    } else {
      // Bold/italic inline formatting
      const text = trimmed.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1')
      nodes.push({ type: 'paragraph', text })
    }
  }

  return nodes
}

module.exports = {
  formatPace, formatTime, parseTimeToSeconds,
  getDistanceLabel, getOddsColor, getOddsLabel,
  formatDate, simpleMarkdownToNodes,
}
