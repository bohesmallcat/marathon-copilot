#!/usr/bin/env python3
"""Generate Marathon Copilot demo slides as PDF (landscape, one page per slide)."""

import weasyprint
import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: 338mm 190mm;
    margin: 0;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "Helvetica Neue", sans-serif;
    color: #fff;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  /* ── Slide base ── */
  .slide {
    width: 338mm;
    height: 190mm;
    background: #1a1a2e;
    page-break-after: always;
    position: relative;
    overflow: hidden;
    padding: 14mm 20mm;
  }
  .slide:last-child { page-break-after: avoid; }

  /* ── Typography ── */
  h1 { font-size: 32pt; font-weight: 700; margin-bottom: 6mm; }
  h2 { font-size: 22pt; font-weight: 700; margin-bottom: 4mm; }
  h3 { font-size: 16pt; font-weight: 700; margin-bottom: 3mm; }
  .subtitle { font-size: 14pt; color: #b0b0c0; margin-bottom: 8mm; }
  .accent-cyan { color: #00d2ff; }
  .accent-green { color: #00e696; }
  .accent-red { color: #ff6b6b; }
  .accent-yellow { color: #ffd93d; }
  .accent-purple { color: #c084fc; }
  .gray { color: #b0b0c0; }
  .light { color: #e0e0f0; }
  .small { font-size: 10pt; }
  .tag {
    display: inline-block;
    padding: 2mm 5mm;
    border-radius: 3mm;
    font-size: 11pt;
    font-weight: 700;
    margin-right: 3mm;
    color: #1a1a2e;
  }
  .tag-cyan { background: #00d2ff; }
  .tag-green { background: #00e696; }
  .tag-red { background: #ff6b6b; }
  .tag-yellow { background: #ffd93d; }
  .tag-purple { background: #c084fc; }

  /* ── Layout ── */
  .flex { display: flex; gap: 5mm; }
  .flex-2 { display: flex; gap: 5mm; }
  .flex-2 > * { flex: 1; }
  .flex-4 { display: flex; gap: 4mm; }
  .flex-4 > * { flex: 1; }
  .flex-3 { display: flex; gap: 4mm; }
  .flex-3 > * { flex: 1; }
  .col-left { width: 48%; }
  .col-right { width: 48%; }
  .two-col { display: flex; gap: 5mm; }
  .two-col > .col-left, .two-col > .col-right { flex: 1; }

  /* ── Cards ── */
  .card {
    background: #1f2b4d;
    border-radius: 4mm;
    padding: 5mm 6mm;
    margin-bottom: 4mm;
  }
  .card-bordered { border: 1.2px solid; }
  .border-cyan { border-color: #00d2ff; }
  .border-green { border-color: #00e696; }
  .border-red { border-color: #ff6b6b; }
  .border-yellow { border-color: #ffd93d; }
  .border-purple { border-color: #c084fc; }

  .card-header {
    padding: 2mm 0;
    margin: -5mm -6mm 4mm -6mm;
    padding: 3mm 6mm;
    border-radius: 4mm 4mm 0 0;
    font-weight: 700;
    font-size: 13pt;
    color: #1a1a2e;
    text-align: center;
  }

  /* ── Specific layouts ── */
  .pain-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; }
  .pain-card { padding: 5mm 6mm; }
  .pain-card h3 { margin-bottom: 2mm; }
  .pain-card p { font-size: 11pt; color: #e0e0f0; line-height: 1.5; }

  .phase-card {
    text-align: center;
    padding: 4mm 3mm;
    position: relative;
  }
  .phase-label {
    display: inline-block;
    padding: 1.5mm 4mm;
    border-radius: 2.5mm;
    font-size: 10pt;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 3mm;
  }
  .phase-card h3 { font-size: 15pt; margin: 3mm 0; }
  .phase-card ul { list-style: none; text-align: left; padding-left: 3mm; }
  .phase-card li { font-size: 10pt; color: #e0e0f0; line-height: 1.7; }
  .phase-card li::before { content: "▸ "; opacity: 0.5; }
  .arrow {
    display: flex; align-items: center; justify-content: center;
    font-size: 24pt; color: #b0b0c0; flex: 0 0 6mm; align-self: center;
  }

  .feature-item { margin-bottom: 4mm; }
  .feature-item .title { font-size: 12pt; font-weight: 700; margin-bottom: 1mm; }
  .feature-item .desc { font-size: 10pt; color: #b0b0c0; }

  table.data-table { width: 100%; border-collapse: collapse; font-size: 10.5pt; }
  table.data-table td { padding: 1.5mm 2mm; }
  table.data-table .label { color: #b0b0c0; width: 35%; }
  table.data-table .value { color: #fff; font-weight: 700; }
  table.data-table .bad { color: #ff6b6b; }

  .tax-row { display: flex; align-items: center; margin-bottom: 2mm; font-size: 10.5pt; }
  .tax-factor { width: 18mm; font-weight: 700; }
  .tax-desc { flex: 1; color: #b0b0c0; }
  .tax-val { width: 20mm; text-align: right; font-weight: 700; }

  .pace-row { display: flex; margin-bottom: 1.5mm; font-size: 10.5pt; align-items: center; }
  .pace-seg { width: 28mm; color: #fff; }
  .pace-val { width: 28mm; font-weight: 700; }
  .pace-note { flex: 1; color: #b0b0c0; font-size: 10pt; }

  .fuse-item { margin-bottom: 3mm; }
  .fuse-cond { font-size: 10.5pt; font-weight: 700; }
  .fuse-action { font-size: 10pt; color: #e0e0f0; padding-left: 5mm; margin-top: 1mm; }

  .supp-item { font-size: 10.5pt; color: #e0e0f0; line-height: 1.8; }

  .science-row { display: flex; align-items: flex-start; margin-bottom: 3mm; }
  .science-dot { width: 3mm; height: 3mm; border-radius: 50%; margin-top: 2mm; margin-right: 3mm; flex-shrink: 0; }
  .science-title { width: 38mm; font-size: 11pt; font-weight: 700; flex-shrink: 0; }
  .science-desc { font-size: 10pt; color: #e0e0f0; }

  .step-list { list-style: none; }
  .step-list li { margin-bottom: 3mm; }
  .step-num { font-size: 12pt; font-weight: 700; }
  .step-text { font-size: 11pt; }
  .step-sub { font-size: 10pt; color: #b0b0c0; padding-left: 6mm; margin-top: 1mm; }

  .need-row { display: flex; margin-bottom: 2mm; font-size: 10.5pt; }
  .need-label { width: 32mm; font-weight: 700; }
  .need-desc { color: #b0b0c0; }

  /* ── Title slide ── */
  .title-slide { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
  .title-slide h1 { font-size: 38pt; margin-bottom: 2mm; }
  .title-slide .tagline { font-size: 20pt; margin-bottom: 12mm; }
  .title-slide .desc { font-size: 14pt; color: #b0b0c0; margin-bottom: 15mm; }
  .title-slide .footer { font-size: 11pt; color: #b0b0c0; }
  .accent-line {
    width: 100%; height: 1.5px; background: #00d2ff;
    position: absolute; left: 0;
  }

  /* ── End slide ── */
  .end-slide { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
  .end-slide h1 { font-size: 34pt; margin-bottom: 4mm; }
  .end-slide .tagline { font-size: 18pt; margin-top: 8mm; }
  .end-slide .qa { font-size: 26pt; font-weight: 700; margin-top: 14mm; }

  .tab-header {
    text-align: center;
    padding: 2.5mm 0;
    margin: -5mm -6mm 4mm -6mm;
    border-radius: 4mm 4mm 0 0;
    font-weight: 700;
    font-size: 14pt;
    color: #1a1a2e;
  }
  .tab-item { font-size: 10.5pt; line-height: 1.7; }
  .tab-item.sub { color: #b0b0c0; padding-left: 4mm; font-size: 10pt; }
  .tab-item.bold { font-weight: 700; }

  .bottom-note {
    position: absolute; bottom: 6mm; left: 0; width: 100%;
    text-align: center; font-size: 10pt; color: #b0b0c0;
  }
</style>
</head>
<body>

<!-- ═══════ SLIDE 1: Title ═══════ -->
<div class="slide title-slide">
  <div class="accent-line" style="top: 84mm;"></div>
  <h1>Marathon Copilot</h1>
  <div class="tagline accent-cyan">你的 AI 马拉松配速教练</div>
  <div class="desc">长期规划 · 科学备赛 · 精准配速 · 深度复盘</div>
  <div class="footer">从训练周期化到赛后四维分析，覆盖全马备赛全周期</div>
</div>

<!-- ═══════ SLIDE 2: Pain Points ═══════ -->
<div class="slide">
  <h1>你有没有遇到过这些问题？</h1>
  <div class="pain-grid" style="margin-top: 4mm;">
    <div class="card card-bordered border-red pain-card">
      <h3 class="accent-red">比赛配速</h3>
      <p>"我到底该跑多快？"<br>赛前纠结半天，结果一出发就跟着大部队冲，后半程崩得怀疑人生</p>
    </div>
    <div class="card card-bordered border-yellow pain-card">
      <h3 class="accent-yellow">天气影响</h3>
      <p>"天气预报说 15°C 多云，PB 天气！"<br>结果到了现场湿度 90%，跑到半程心率就飘了</p>
    </div>
    <div class="card card-bordered border-cyan pain-card">
      <h3 class="accent-cyan">训练规划</h3>
      <p>"离比赛还有 4 个月，怎么练？"<br>买了训练计划跟不上，跑量不知道怎么加，怕受伤</p>
    </div>
    <div class="card card-bordered border-green pain-card">
      <h3 class="accent-green">赛后复盘</h3>
      <p>"跑完就看个总成绩和平均配速"<br>不知道到底哪里出了问题，下次还是同样的错误</p>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 3: Lifecycle ═══════ -->
<div class="slide">
  <h1>覆盖备赛全周期</h1>
  <p class="subtitle">从长期训练规划到赛后复盘，每个阶段都有对应的 AI 辅助</p>
  <div style="display: flex; align-items: stretch; gap: 0; margin-top: 2mm;">
    <div class="card card-bordered border-purple phase-card" style="flex:1;">
      <div class="phase-label" style="background:#c084fc;">赛前 8-52 周</div>
      <h3 class="accent-purple">长期规划</h3>
      <ul>
        <li>VDOT 递进路径</li>
        <li>分期训练阶段</li>
        <li>跑量周期化递进</li>
        <li>女性周期整合</li>
      </ul>
    </div>
    <div class="arrow">›</div>
    <div class="card card-bordered border-cyan phase-card" style="flex:1;">
      <div class="phase-label" style="background:#00d2ff;">赛前 D-30</div>
      <h3 class="accent-cyan">目标设定</h3>
      <ul>
        <li>VDOT 跑力计算</li>
        <li>A/B/C 三档目标</li>
        <li>PB 达成概率</li>
        <li>配速策略选择</li>
      </ul>
    </div>
    <div class="arrow">›</div>
    <div class="card card-bordered border-green phase-card" style="flex:1;">
      <div class="phase-label" style="background:#00e696;">赛前 D-7 ~ D-1</div>
      <h3 class="accent-green">每日简报</h3>
      <ul>
        <li>天气追踪 + 环境税</li>
        <li>训练 + 饮食计划</li>
        <li>恢复建议</li>
        <li>每周天气排课</li>
      </ul>
    </div>
    <div class="arrow">›</div>
    <div class="card card-bordered border-yellow phase-card" style="flex:1;">
      <div class="phase-label" style="background:#ffd93d;">比赛日 D-0</div>
      <h3 class="accent-yellow">执行方案</h3>
      <ul>
        <li>逐公里配速表</li>
        <li>心率控制区间</li>
        <li>补给时间表</li>
        <li>熔断机制</li>
      </ul>
    </div>
    <div class="arrow">›</div>
    <div class="card card-bordered border-red phase-card" style="flex:1;">
      <div class="phase-label" style="background:#ff6b6b;">赛后</div>
      <h3 class="accent-red">深度复盘</h3>
      <ul>
        <li>四维生物力学</li>
        <li>根因链分析</li>
        <li>偏差分解量化</li>
        <li>能力重估</li>
      </ul>
    </div>
  </div>
  <div class="bottom-note">你只需要提供你的 PB 和手表数据，AI 帮你做长期规划、算目标、盯天气、出方案、做复盘</div>
</div>

<!-- ═══════ SLIDE 4: Training Periodization ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-purple">场景一</span>
    <span style="font-size: 22pt; font-weight: 700;">长期训练规划 —— "离比赛还有 4 个月，怎么练？"</span>
  </div>
  <div class="two-col">
    <div class="col-left">
      <h3 class="accent-purple" style="margin-bottom: 4mm;">它怎么帮你</h3>
      <div class="feature-item">
        <div class="title">▸ VDOT 递进路径规划</div>
        <div class="desc">根据当前跑力和目标成绩，规划每 16 周 VDOT 提升 0.5-1.5 点</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 5-6 个分期训练阶段</div>
        <div class="desc">恢复期 → 有氧基础 → 有氧发展 → 专项 → 巅峰 → 减量</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 跑量安全递进</div>
        <div class="desc">10% 周增量上限 + 每 4 周减载恢复；大体重跑者自动收紧至 8%</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 里程碑测试验证</div>
        <div class="desc">穿插 5km/10km/半马测试赛，验证进步是否达预期</div>
      </div>
      <div class="feature-item">
        <div class="title accent-purple">▸ 女性生理周期整合</div>
        <div class="desc">5 相位周期模型，自动预测比赛日相位，调整训练强度和赛日策略</div>
      </div>
    </div>
    <div class="col-right">
      <div class="card card-bordered border-purple" style="margin-bottom: 4mm;">
        <h3 class="accent-purple" style="margin-bottom: 3mm;">训练分期示例</h3>
        <div style="font-size: 10.5pt; line-height: 2;">
          <div><b class="accent-purple">第 1-4 周</b> &nbsp; 恢复期 · 周跑量 30km · E 配速为主</div>
          <div><b class="accent-purple">第 5-12 周</b> &nbsp; 有氧基础期 · 周跑量 40→55km</div>
          <div><b class="accent-purple">第 13-20 周</b> &nbsp; 有氧发展期 · 加入 T/I 训练</div>
          <div><b class="accent-purple">第 21-26 周</b> &nbsp; 专项期 · MP 配速长距离</div>
          <div><b class="accent-purple">第 27-30 周</b> &nbsp; 巅峰期 · 最高质量训练</div>
          <div><b class="accent-purple">第 31-32 周</b> &nbsp; 减量期 · 跑量递减至 60%</div>
        </div>
      </div>
      <div class="card card-bordered border-purple">
        <h3 class="accent-purple" style="margin-bottom: 2mm;">多因子达成概率</h3>
        <div style="font-size: 10pt; color: #e0e0f0; line-height: 1.6;">
          VDOT 缺口 × 训练年限 × 跑量评级 × 伤病 × 耦合比 × 体重 × 年龄 → 精算 PB 达成概率
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 5: Weekly Training ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-purple">场景二</span>
    <span style="font-size: 22pt; font-weight: 700;">每周训练计划 —— "这周每天练什么？"</span>
  </div>
  <div class="flex-3">
    <div class="card card-bordered border-cyan">
      <div class="tab-header" style="background: #00d2ff;">天气自适应排课</div>
      <div class="tab-item bold">周一 &nbsp; 轻松跑 8km @ E 配速</div>
      <div class="tab-item sub">天气：晴 12°C · 适宜度 92%</div>
      <div class="tab-item bold" style="margin-top: 2mm;">周二 &nbsp; 力量训练（跑步经济性）</div>
      <div class="tab-item sub">弹性髋 + 单腿深蹲 + 核心</div>
      <div class="tab-item bold" style="margin-top: 2mm;">周三 &nbsp; 节奏跑 5km @ T 配速</div>
      <div class="tab-item sub">天气：多云 15°C · 适宜度 85%</div>
      <div class="tab-item bold" style="margin-top: 2mm;">周四 &nbsp; 休息 / 交叉训练</div>
      <div class="tab-item sub">天气：暴雨 · 自动安排室内</div>
      <div style="margin-top: 4mm; padding: 2mm 3mm; background: rgba(0,210,255,0.1); border-radius: 2mm; font-size: 9.5pt; color: #b0b0c0;">质量课自动排在好天气日</div>
    </div>
    <div class="card card-bordered border-green">
      <div class="tab-header" style="background: #00e696;">恢复监控决策树</div>
      <div class="tab-item bold">每日自检清单</div>
      <div class="tab-item sub">晨脉：±5 次/分 → 正常</div>
      <div class="tab-item sub">DOMS：0-3 分制评估</div>
      <div class="tab-item sub">疼痛量表：0-10 分</div>
      <div class="tab-item sub">睡眠：≥ 7h → 绿灯</div>
      <div class="tab-item bold" style="margin-top: 3mm;">自动决策</div>
      <div class="tab-item sub">全绿 → 正常训练</div>
      <div class="tab-item sub">1 项黄 → 降量 20%</div>
      <div class="tab-item sub">2+ 项红 → 休息日</div>
      <div style="margin-top: 4mm; padding: 2mm 3mm; background: rgba(0,230,150,0.1); border-radius: 2mm; font-size: 9.5pt; color: #b0b0c0;">防止过度训练，减少伤病风险</div>
    </div>
    <div class="card card-bordered border-red">
      <div class="tab-header" style="background: #ff6b6b;">饮食 & 力量训练</div>
      <div class="tab-item bold">训练日饮食</div>
      <div class="tab-item sub">碳水 6-8g/kg · 蛋白质 1.6g/kg</div>
      <div class="tab-item bold" style="margin-top: 2mm;">恢复日饮食</div>
      <div class="tab-item sub">碳水 4-5g/kg · 蛋白质 1.8g/kg</div>
      <div class="tab-item bold" style="margin-top: 3mm;">力量训练分期</div>
      <div class="tab-item sub">基础期 → 关节稳定</div>
      <div class="tab-item sub">发展期 → 跑步经济性</div>
      <div class="tab-item sub">赛前 → 维持即可</div>
      <div style="margin-top: 4mm; padding: 2mm 3mm; background: rgba(255,107,107,0.1); border-radius: 2mm; font-size: 9.5pt; color: #b0b0c0;">营养和力量随训练阶段自动调整</div>
    </div>
  </div>
  <div class="bottom-note">所有数值根据跑者体重、VDOT 和当前训练阶段自动计算</div>
</div>

<!-- ═══════ SLIDE 6: Goal Setting ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-cyan">场景三</span>
    <span style="font-size: 22pt; font-weight: 700;">赛前目标设定 —— "我该跑多快？"</span>
  </div>
  <div class="two-col">
    <div class="col-left">
      <h3 class="accent-cyan" style="margin-bottom: 4mm;">它怎么帮你</h3>
      <div class="feature-item">
        <div class="title">▸ 根据 PB 反推跑力值（VDOT）</div>
        <div class="desc">用你最近的比赛成绩，而非训练数据，算出真实跑力</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 多场比赛数据交叉验证</div>
        <div class="desc">对比不同比赛的配速策略、掉速率，找出最优跑法</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 生成 A / B / C 三档目标</div>
        <div class="desc">激进冲 PB / 稳健达标 / 保守完赛，不把鸡蛋放一个篮子</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ PB 达成概率评估</div>
        <div class="desc">综合跑力、训练量、天气、身体状态，给出胜率百分比</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ GPS 距离修正</div>
        <div class="desc">手表显示 42.195km 但你实际跑了 42.6km——修正后配速更准</div>
      </div>
    </div>
    <div class="col-right">
      <div class="card card-bordered border-cyan" style="height: 100%;">
        <h3 class="accent-cyan" style="margin-bottom: 4mm;">示例：全马目标设定</h3>
        <table class="data-table">
          <tr><td class="label">跑者 VDOT</td><td class="value">56.0（基于近两场全马 PB）</td></tr>
          <tr><td class="label">A 目标</td><td class="value">Sub 2:40（配速 3'48"/km）</td></tr>
          <tr><td class="label">B 目标</td><td class="value">Sub 2:45（配速 3'55"/km）</td></tr>
          <tr><td class="label">C 目标</td><td class="value">Sub 2:50（配速 4'02"/km）</td></tr>
          <tr><td class="label">PB 胜率</td><td class="value accent-yellow">65%</td></tr>
          <tr><td class="label">配速策略</td><td class="value">前慢后快（负分段）</td></tr>
          <tr><td class="label">距离修正</td><td class="value">42.6km（+0.4km）</td></tr>
        </table>
        <div style="margin-top: 6mm; padding: 3mm; background: rgba(0,210,255,0.1); border-radius: 2mm;">
          <div style="font-size: 10pt; color: #00d2ff; font-weight: 700;">关键洞察</div>
          <div style="font-size: 10pt; color: #e0e0f0; margin-top: 1mm;">对比两场赛事数据发现：均匀配速策略更优，掉速率仅 3.2%，建议继续采用同样策略</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 7: Weather & Env Tax ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-green">场景四</span>
    <span style="font-size: 22pt; font-weight: 700;">天气追踪 & 环境税 —— "天气对我影响多大？"</span>
  </div>
  <div class="two-col">
    <div class="col-left">
      <h3 class="accent-green" style="margin-bottom: 2mm;">核心概念：环境税</h3>
      <p class="light" style="font-size: 11pt; line-height: 1.6; margin-bottom: 5mm;">天气会给你的配速"加税"。同样的心率和体感努力程度，恶劣天气下你会比理想条件慢 X 秒/公里。这个 X 就是环境税。</p>

      <h3 class="accent-green" style="margin-bottom: 3mm;">环境税拆解</h3>
      <div class="tax-row"><span class="tax-factor accent-green">气温</span><span class="tax-desc">偏离 10-15°C 最佳区间越远，税越高</span><span class="tax-val accent-yellow">+3"/km</span></div>
      <div class="tax-row"><span class="tax-factor accent-green">湿度</span><span class="tax-desc">> 70% 散热困难，心率漂移</span><span class="tax-val accent-yellow">+5"/km</span></div>
      <div class="tax-row"><span class="tax-factor accent-green">风速</span><span class="tax-desc">逆风 > 15km/h 显著影响</span><span class="tax-val accent-yellow">+2"/km</span></div>
      <div class="tax-row"><span class="tax-factor accent-green">紫外线</span><span class="tax-desc">高 UV 加速脱水和体温上升</span><span class="tax-val accent-yellow">+3"/km</span></div>
      <div class="tax-row"><span class="tax-factor accent-green">体感温度</span><span class="tax-desc">综合以上因素的最终修正值</span><span class="tax-val accent-cyan">= 总税</span></div>

      <div style="margin-top: 5mm; padding: 3mm; background: rgba(0,230,150,0.1); border-radius: 2mm;">
        <div style="font-size: 10pt; color: #e0e0f0;">根据你的<b style="color:#00e696;">身高和体重</b>做个性化修正——体重大的跑者散热更慢，环境税更高</div>
      </div>
    </div>
    <div class="col-right">
      <div class="card card-bordered border-green" style="margin-bottom: 4mm;">
        <h3 class="accent-green" style="margin-bottom: 3mm;">良好天气案例（D-2 预报）</h3>
        <div style="font-size: 11pt; line-height: 1.8;">
          <div>气温 10°C → 15°C</div>
          <div>湿度 69% → 52%</div>
          <div>环境税 ≈ <b class="accent-green">10"/km</b></div>
          <div style="margin-top: 2mm;"><b class="accent-green" style="font-size: 13pt;">✓ 绿灯：执行原计划</b></div>
        </div>
      </div>
      <div class="card card-bordered border-red">
        <h3 class="accent-red" style="margin-bottom: 3mm;">恶劣天气案例（赛后复盘数据）</h3>
        <div style="font-size: 11pt; line-height: 1.8;">
          <div>赛道隧道段湿度 > 90%</div>
          <div>CO₂ 浓度升高，体感温度 +3~5°C</div>
          <div>环境税 ≈ <b class="accent-red">92"/km</b></div>
          <div>结果：超出目标 3 分钟+</div>
          <div style="margin-top: 2mm;"><b class="accent-red" style="font-size: 13pt;">✗ 红灯：应启动 B 方案降速</b></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 8: Training & Diet ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-yellow">场景五</span>
    <span style="font-size: 22pt; font-weight: 700;">每日训练 & 饮食 —— "赛前一周怎么练、怎么吃？"</span>
  </div>
  <div class="flex-3">
    <div class="card card-bordered border-cyan">
      <div class="tab-header" style="background: #00d2ff;">训练计划</div>
      <div class="tab-item bold">D-7 &nbsp; 轻松跑 8km @ 5'30"/km</div>
      <div class="tab-item bold">D-6 &nbsp; 节奏跑 5km @ 4'40"/km</div>
      <div class="tab-item bold">D-5 &nbsp; 轻松跑 6km @ 5'30"/km</div>
      <div class="tab-item bold">D-4 &nbsp; 休息日</div>
      <div class="tab-item bold">D-3 &nbsp; 轻松跑 4km @ 5'30"/km</div>
      <div class="tab-item bold">D-2 &nbsp; 抖腿跑 3km @ 5'00"/km</div>
      <div class="tab-item bold">D-1 &nbsp; 激活跑 2km + 3×100m</div>
      <div style="margin-top: 4mm; padding: 2mm 3mm; background: rgba(0,210,255,0.1); border-radius: 2mm; font-size: 9.5pt; color: #b0b0c0;">配速根据 VDOT 个性化计算</div>
    </div>
    <div class="card card-bordered border-green">
      <div class="tab-header" style="background: #00e696;">饮食计划</div>
      <div class="tab-item bold">D-7 ~ D-4 &nbsp; 正常饮食</div>
      <div class="tab-item sub">碳水 5g/kg · 蛋白质 1.5g/kg</div>
      <div class="tab-item bold" style="margin-top: 2mm;">D-3 &nbsp; 开始糖原超补</div>
      <div class="tab-item sub">碳水 8g/kg（60kg = 480g）</div>
      <div class="tab-item bold" style="margin-top: 2mm;">D-2 &nbsp; 继续超补</div>
      <div class="tab-item sub">碳水 10g/kg（60kg = 600g）</div>
      <div class="tab-item bold" style="margin-top: 2mm;">D-1 &nbsp; 高碳水 + 低纤维</div>
      <div class="tab-item sub">充分补水，避免高纤维食物</div>
    </div>
    <div class="card card-bordered border-red">
      <div class="tab-header" style="background: #ff6b6b;">恢复建议</div>
      <div class="tab-item bold">D-7 &nbsp; 泡沫轴全身放松 15min</div>
      <div class="tab-item bold">D-6 &nbsp; 拉伸 + 冰浴</div>
      <div class="tab-item bold">D-5 &nbsp; 轻度按摩 / 散步</div>
      <div class="tab-item bold">D-4 &nbsp; 完全休息，睡足 8h</div>
      <div class="tab-item bold">D-3 &nbsp; 泡沫轴下肢 10min</div>
      <div class="tab-item bold">D-2 &nbsp; 轻度拉伸 + 早睡</div>
      <div class="tab-item bold">D-1 &nbsp; 不做高强度拉伸</div>
      <div style="margin-top: 4mm; padding: 2mm 3mm; background: rgba(255,107,107,0.1); border-radius: 2mm; font-size: 9.5pt; color: #b0b0c0;">赛前 48h 是恢复黄金期</div>
    </div>
  </div>
  <div class="bottom-note">所有数值根据跑者体重和 VDOT 自动计算，不同跑者看到的计划不一样</div>
</div>

<!-- ═══════ SLIDE 9: Race Day Execution ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-yellow">场景六</span>
    <span style="font-size: 22pt; font-weight: 700;">比赛日执行方案 —— "比赛当天看什么？"</span>
  </div>
  <div class="two-col">
    <div class="col-left">
      <h3 class="accent-yellow" style="margin-bottom: 2mm;">赛前状态速览</h3>
      <div class="card card-bordered border-yellow" style="margin-bottom: 4mm;">
        <table class="data-table">
          <tr><td class="label">HRV 评估</td><td class="value">三维分析</td><td style="color:#b0b0c0; font-size:10pt;">基线偏差 + 变异系数 + 赛日回升</td></tr>
          <tr><td class="label">PB 胜率</td><td class="value accent-yellow">65%</td><td style="color:#b0b0c0; font-size:10pt;">可以冲但留余量</td></tr>
          <tr><td class="label">环境税</td><td class="value">10"/km</td><td style="color:#b0b0c0; font-size:10pt;">绿灯，执行原计划</td></tr>
        </table>
      </div>

      <h3 class="accent-yellow" style="margin-bottom: 2mm;">逐段配速表</h3>
      <div class="card" style="margin-bottom: 4mm;">
        <div class="pace-row"><span class="pace-seg">0 ~ 5 km</span><span class="pace-val accent-yellow">3'52"/km</span><span class="pace-note">热身入赛，压住兴奋</span></div>
        <div class="pace-row"><span class="pace-seg">6 ~ 10 km</span><span class="pace-val accent-yellow">3'50"/km</span><span class="pace-note">进入巡航节奏</span></div>
        <div class="pace-row"><span class="pace-seg">11 ~ 30 km</span><span class="pace-val accent-yellow">3'48"/km</span><span class="pace-note">主力巡航段</span></div>
        <div class="pace-row"><span class="pace-seg">31 ~ 35 km</span><span class="pace-val accent-yellow">3'50"/km</span><span class="pace-note">预留撞墙余量</span></div>
        <div class="pace-row"><span class="pace-seg">36 km →</span><span class="pace-val accent-green">3'46"/km</span><span class="pace-note">有余力则提速冲刺</span></div>
      </div>

      <h3 class="accent-green" style="margin-bottom: 2mm;">补给时间表</h3>
      <div class="card">
        <div class="supp-item">赛前 30min &nbsp; 能量胶 1 支 + 200ml 水</div>
        <div class="supp-item">每 5km &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 小口补水 100-150ml</div>
        <div class="supp-item">10 / 20km &nbsp;&nbsp;&nbsp; 能量胶各 1 支</div>
        <div class="supp-item">30km &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 最后一支能量胶 + 电解质</div>
      </div>
    </div>
    <div class="col-right">
      <h3 class="accent-red" style="margin-bottom: 2mm;">熔断机制：什么时候该降速？</h3>
      <div class="card card-bordered border-red" style="margin-bottom: 4mm;">
        <div class="fuse-item">
          <div class="fuse-cond accent-red">⚠ 心率 > 170 bpm 持续 3 分钟</div>
          <div class="fuse-action">→ 立即降速至 B 方案配速</div>
        </div>
        <div class="fuse-item">
          <div class="fuse-cond accent-red">⚠ 配速偏差 > 8"/km 持续 2km</div>
          <div class="fuse-action">→ 评估体感，考虑切换 B 方案</div>
        </div>
        <div class="fuse-item">
          <div class="fuse-cond accent-red">⚠ 体感温度 > 28°C</div>
          <div class="fuse-action">→ 主动降速 10-15"/km，增加补水</div>
        </div>
      </div>
      <div style="background: rgba(255,217,61,0.1); border-radius: 3mm; padding: 4mm 5mm; margin-bottom: 4mm;">
        <div style="font-size: 14pt; font-weight: 700; color: #ffd93d; text-align: center;">"熔断不是认输，是科学止损"</div>
      </div>
      <div style="background: rgba(0,230,150,0.08); border-radius: 3mm; padding: 4mm 5mm;">
        <div style="font-size: 11pt; font-weight: 700; color: #00e696; margin-bottom: 2mm;">手机锁屏备忘</div>
        <div style="font-size: 10pt; color: #e0e0f0; line-height: 1.6;">配速表和熔断规则可以生成为锁屏图片，比赛当天解锁手机就能看到关键数据，不用记住所有数字。</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 10: Post-Race Review ═══════ -->
<div class="slide">
  <div style="margin-bottom: 4mm;">
    <span class="tag tag-red">场景七</span>
    <span style="font-size: 22pt; font-weight: 700;">赛后深度复盘 —— "我为什么崩了？"</span>
  </div>
  <div class="two-col">
    <div class="col-left">
      <h3 class="accent-red" style="margin-bottom: 3mm;">教练级深度分析</h3>
      <div class="feature-item">
        <div class="title accent-red">▸ 四维生物力学分析</div>
        <div class="desc">步幅 × 步频 × 功率 × 配速，逐 5km 关联分析</div>
      </div>
      <div class="feature-item">
        <div class="title accent-red">▸ 步幅衰减三阶段模型</div>
        <div class="desc">稳定期 → 加速衰减期 → 崩塌期，量化步幅贡献率（> 70%）</div>
      </div>
      <div class="feature-item">
        <div class="title accent-red">▸ 心率-配速脱耦诊断</div>
        <div class="desc">区分"心率漂移型"（湿度）和"糖原耗竭型"（配速降 HR 不升）</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 偏差分解量化</div>
        <div class="desc">总偏差拆解到各因子，秒级精度，总和必须吻合</div>
      </div>
      <div class="feature-item">
        <div class="title">▸ 跨赛事对比 & 能力重估</div>
        <div class="desc">多场比赛横向对比，去除可消除因素后重估净完赛能力</div>
      </div>
    </div>
    <div class="col-right">
      <div class="card card-bordered border-red" style="height: 100%;">
        <h3 class="accent-red" style="margin-bottom: 3mm;">示例：全马复盘</h3>
        <table class="data-table">
          <tr><td class="label">目标成绩</td><td class="value">2:40:00</td></tr>
          <tr><td class="label">实际成绩</td><td class="value bad">2:48:30（+8'30"）</td></tr>
        </table>
        <div style="margin-top: 3mm; font-size: 10.5pt; font-weight: 700; color: #ff6b6b;">── 分段执行 ──</div>
        <table class="data-table" style="margin-top: 1mm;">
          <tr><td class="label">0-20km</td><td class="value">完美执行，偏差 < 3"</td></tr>
          <tr><td class="label">25-30km</td><td class="value bad">开始掉速，慢 15"/km</td></tr>
          <tr><td class="label">35-40km</td><td class="value bad">严重掉速，慢 40"/km</td></tr>
        </table>
        <div style="margin-top: 3mm; font-size: 10.5pt; font-weight: 700; color: #ff6b6b;">── 根因链诊断 ──</div>
        <table class="data-table" style="margin-top: 1mm;">
          <tr><td class="label">结构性根因</td><td class="value bad">C 级周跑量</td></tr>
          <tr><td class="label">触发因子</td><td class="value bad">赛间恢复不充分</td></tr>
          <tr><td class="label">放大器</td><td class="value bad">步幅衰减 11%</td></tr>
          <tr><td class="label">边际因子</td><td class="value bad">补给时机偏迟</td></tr>
        </table>
        <div style="margin-top: 3mm; font-size: 10.5pt; font-weight: 700; color: #ff6b6b;">── 偏差分解 ──</div>
        <table class="data-table" style="margin-top: 1mm;">
          <tr><td class="label">跑量不足</td><td class="value bad">+300"</td></tr>
          <tr><td class="label">恢复不充分</td><td class="value bad">+100"</td></tr>
          <tr><td class="label">步幅崩塌</td><td class="value bad">+90"</td></tr>
          <tr><td class="label">其他因子</td><td class="value bad">+20"</td></tr>
          <tr><td class="label">总计</td><td class="value bad">= +510"（≈ 8'30"）</td></tr>
        </table>
      </div>
    </div>
  </div>
</div>

<!-- ═══════ SLIDE 11: Science ═══════ -->
<div class="slide">
  <h1>背后的科学原理</h1>
  <p class="subtitle">每个数字都有运动生理学依据，不是拍脑袋给建议</p>
  <div style="margin-top: 2mm;">
    <div class="science-row"><div class="science-dot" style="background:#00d2ff;"></div><div class="science-title accent-cyan">VDOT 跑力</div><div class="science-desc">Jack Daniels 公式，全球最主流的跑力评估体系——用你的 PB 反推跑力值</div></div>
    <div class="science-row"><div class="science-dot" style="background:#c084fc;"></div><div class="science-title accent-purple">训练周期化</div><div class="science-desc">Daniels / Pfitzinger / Hansons 方法论，10% 周增量 + 4 周减载 + 分阶段峰值控制</div></div>
    <div class="science-row"><div class="science-dot" style="background:#00e696;"></div><div class="science-title accent-green">环境修正</div><div class="science-desc">温度/湿度/风速对配速影响的量化模型，根据身高体重（BSA/体重比）做个性化修正</div></div>
    <div class="science-row"><div class="science-dot" style="background:#00d2ff;"></div><div class="science-title accent-cyan">HRV 评估</div><div class="science-desc">三维度分析（基线偏差 + 变异系数 + 赛日回升），评估恢复状态和比赛日竞技状态</div></div>
    <div class="science-row"><div class="science-dot" style="background:#ffd93d;"></div><div class="science-title accent-yellow">PB 概率</div><div class="science-desc">多因子加权模型：跑力 × 训练量 × 环境条件 × 身体状态 × 耦合比 × 伤病</div></div>
    <div class="science-row"><div class="science-dot" style="background:#ff6b6b;"></div><div class="science-title accent-red">四维生物力学</div><div class="science-desc">步幅-步频-功率-配速逐段关联分析，步幅衰减三阶段模型，量化步幅贡献率</div></div>
    <div class="science-row"><div class="science-dot" style="background:#ff6b6b;"></div><div class="science-title accent-red">HR-配速脱耦</div><div class="science-desc">前后半程配速/HR 比值变化，区分心率漂移（湿度型）和糖原耗竭（崩盘型）</div></div>
    <div class="science-row"><div class="science-dot" style="background:#00e696;"></div><div class="science-title accent-green">营养计算</div><div class="science-desc">基于体重的碳水/蛋白质/脂肪目标，赛前糖原超补递增模型，糖原经济学预测撞墙里程</div></div>
    <div class="science-row"><div class="science-dot" style="background:#c084fc;"></div><div class="science-title accent-purple">女性周期</div><div class="science-desc">5 相位周期模型（Bruinvels 2017 / McNulty 2020），按周期日调节强度、营养和风险预警</div></div>
    <div class="science-row"><div class="science-dot" style="background:#00d2ff;"></div><div class="science-title accent-cyan">天气排课</div><div class="science-desc">7 天天气预报驱动训练排课，自动避开恶劣天气日，高温日自动降速/替换交叉训练</div></div>
  </div>
</div>

<!-- ═══════ SLIDE 12: Get Started ═══════ -->
<div class="slide">
  <h1>怎么开始用？</h1>
  <div class="flex-2" style="margin-top: 4mm;">
    <div class="card card-bordered border-cyan" style="padding: 6mm;">
      <h2 class="accent-cyan" style="margin-bottom: 5mm;">方式一：微信小程序</h2>
      <ul class="step-list">
        <li><span class="step-num accent-cyan">1.</span> <span class="step-text">打开小程序，创建跑者档案</span><div class="step-sub">填写身高、体重、PB 成绩</div></li>
        <li><span class="step-num accent-cyan">2.</span> <span class="step-text">选择目标比赛</span><div class="step-sub">AI 自动生成配速方案和 A/B/C 三档目标</div></li>
        <li><span class="step-num accent-cyan">3.</span> <span class="step-text">每日查看训练 & 饮食计划</span><div class="step-sub">赛前 7 天开始推送个性化建议</div></li>
        <li><span class="step-num accent-cyan">4.</span> <span class="step-text">赛后上传手表数据</span><div class="step-sub">自动生成深度复盘报告</div></li>
      </ul>
    </div>
    <div class="card card-bordered border-green" style="padding: 6mm;">
      <h2 class="accent-green" style="margin-bottom: 5mm;">方式二：发给我，帮你生成</h2>
      <p class="light" style="font-size: 11pt; margin-bottom: 5mm;">目前小程序还在迭代中，你可以把数据发给我，我帮你出完整的作战方案。</p>
      <h3 style="font-size: 13pt; margin-bottom: 3mm;">需要你提供：</h3>
      <div class="need-row"><span class="need-label accent-green">▸ 身高 / 体重</span><span class="need-desc">计算环境税和营养目标</span></div>
      <div class="need-row"><span class="need-label accent-green">▸ 历史 PB</span><span class="need-desc">最好有最近 2-3 场比赛数据</span></div>
      <div class="need-row"><span class="need-label accent-green">▸ 目标比赛</span><span class="need-desc">名称、日期、距离</span></div>
      <div class="need-row"><span class="need-label accent-green">▸ 手表数据</span><span class="need-desc">导出分段配速 + 心率</span></div>
      <div class="need-row"><span class="need-label accent-green">▸ HRV 数据</span><span class="need-desc">可选，有则更准</span></div>
      <div class="need-row"><span class="need-label accent-green">▸ 生理周期</span><span class="need-desc">女性跑者可选，有则更精准</span></div>
      <div style="margin-top: 5mm; padding: 3mm 4mm; background: rgba(0,230,150,0.1); border-radius: 2mm;">
        <div style="font-size: 11pt; font-weight: 700; color: #00e696;">你会得到：</div>
        <div style="font-size: 10.5pt; color: #e0e0f0; margin-top: 1mm;">一份完整的个性化比赛作战方案（PDF），包含目标、配速表、补给计划、熔断规则</div>
      </div>
    </div>
  </div>
  <div class="bottom-note" style="font-size: 12pt;">免费 · 开源 · 你的数据不会上传到任何第三方服务器</div>
</div>

<!-- ═══════ SLIDE 13: End ═══════ -->
<div class="slide end-slide">
  <div class="accent-line" style="top: 84mm;"></div>
  <h1>Marathon Copilot</h1>
  <div class="tagline accent-cyan">你的下一场 PB，从科学备赛开始</div>
  <div class="qa">Q & A</div>
  <div class="footer" style="margin-top: 16mm; font-size: 11pt; color: #b0b0c0;">长期规划 · 科学备赛 · 精准配速 · 深度复盘</div>
</div>

</body>
</html>"""

out_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out_dir, exist_ok=True)

html_path = os.path.join(out_dir, "slides.html")
pdf_path = os.path.join(out_dir, "Marathon_Copilot_跑团Demo.pdf")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print("Generating PDF...")
doc = weasyprint.HTML(filename=html_path)
doc.write_pdf(pdf_path)
print(f"Saved to {pdf_path}")

# Clean up temp html
os.remove(html_path)
print("Done.")
