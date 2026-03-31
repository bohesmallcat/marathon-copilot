---
title: race-training
description: 基于比赛倒计时生成个性化每日训练计划+饮食方案+恢复监控，覆盖 Taper 减量、碳水负荷、赛前激活全流程
tools: ["read", "edit", "grep", "glob", "exec"]
---

# Race Training & Diet Skill

基于比赛日倒计时（D-N），为跑者生成每日训练计划、饮食方案和恢复监控 Checklist。

覆盖赛前全周期：
- **D-7 ~ D-5**: Taper 减量期（保持跑感，逐日递减训练量）
- **D-4 ~ D-3**: 赛前激活（轻松跑 + 开腿跑/短间歇）
- **D-2 ~ D-1**: 碳水负荷 + 完全休息
- **D-0**: 比赛日（赛前流程 + 补给策略 + 装备清单）

---

# 输入

```
跑者配置: api-tools/race_config.yaml（或通过 --config 指定）
  - 比赛日期、距离、目标成绩
  - 跑者体重（用于计算碳水/蛋白目标）
  - T-Pace 心率（用于训练心率上限）
  - 伤病信息（用于恢复监控）
```

---

# 训练计划模型

## D-7: Taper 减量期（起始）
- **训练**: 10km 轻松跑
- **强度**: RPE 4, HR < Zone 2 上限
- **目的**: 赛前一周最长跑，之后逐日递减

## D-6: Taper + 短间歇
- **训练**: 8km，含 4x200m @ T-Pace
- **强度**: RPE 4-5
- **目的**: 减量但保留少量速度刺激

## D-5: Taper
- **训练**: 6-8km 轻松跑
- **强度**: RPE 4
- **目的**: 保持适度活动量

## D-4: Taper
- **训练**: 5km 轻松跑
- **强度**: RPE 4
- **跑后**: 泡沫轴放松 + 拉伸

## D-3: 赛前激活（开腿跑）
- **训练**: 5km = 2km 热身 + 4x200m 快跑 + 1.5km 放松
- **强度**: RPE 5-6, 200m 段可至 T-Pace 心率
- **目的**: 调动快肌纤维，神经系统激活

## D-2: 完全休息 + 碳水负荷 Day 1
- **训练**: 0km（散步可）
- **饮食**: 碳水 8-10g/kg 体重

## D-1: 抖腿跑 + 碳水负荷 Day 2
- **训练**: 2km 慢跑 + 2x100m 大步跑
- **强度**: RPE 2-3
- **饮食**: 继续碳水负荷
- **额外**: 装备检查 + 22:00 前入睡

## D-0: 比赛日
- **流程**: 起床 → 早餐 → 到达起点 → 热身 → 起跑
- **补给**: 赛前能量胶 + 赛中每 5km 补水/补胶
- **装备**: 竞速跑鞋 + 凡士林 + 号码布

---

# 饮食计划模型

## 碳水负荷（D-2 ~ D-1）

| 指标 | 目标 |
|------|------|
| 碳水 | 8-10g/kg 体重/天 |
| 蛋白 | 1.0g/kg 体重/天（降低，让胃给碳水） |
| 水分 | 2L+ |
| 策略 | 以米饭、面条、面包、果汁、香蕉为主 |

## 正常训练期（D-7 ~ D-3）

| 指标 | 目标 |
|------|------|
| 碳水 | 5-6g/kg 体重/天 |
| 蛋白 | 1.2g/kg 体重/天 |
| 水分 | 1.5-2L |

## 比赛日早餐（D-0）
- **时间**: 起跑前 2.5-3 小时
- **碳水**: 2-2.5g/kg 体重
- **原则**: 高碳低纤维，严格复制已验证的方案
- **咖啡因**: 100-150mg（可选）

---

# 恢复监控 Checklist

每日检查项（D-7 ~ D-0）：

| 检查项 | 方法与标准 |
|--------|-----------|
| 晨脉 | 起床后卧床测量，应回到基线 ± 3bpm |
| 伤病 | 0-10 疼痛量表，记录变化趋势 |
| DOMS | 下楼梯/蹲起测试，应无明显酸痛 |
| 睡眠 | 目标 7+ 小时 |

D-1 额外：
- 装备检查清单（跑鞋、号码布、手表、能量胶、帽子、凡士林等）

D-0 额外：
- 赛前热身方案（慢跑 10min + 动态拉伸）
- 补给确认

---

# 工具集成

## CLI 生成（通过 generate_daily_briefing.py）

```bash
# 使用默认配置
python3 api-tools/generate_daily_briefing.py --date YYYY-MM-DD --stdout

# 使用指定配置
python3 api-tools/generate_daily_briefing.py --config api-tools/race_config.yaml --stdout
```

生成的日报自动包含当日训练计划和饮食建议（Section 8 和 Section 9）。

## 小程序（dailyPlan 云函数）

小程序「每日训练 & 饮食」页面调用 `dailyPlan` 云函数：

```javascript
// 获取每日计划
api.getDailyPlan({
  raceDate: '202X-XX-XX',
  raceName: 'XX城市半程马拉松',
  raceDistance: 21.0975,
  targetTime: '1:33:00'
})
```

返回值包含：
- `training`: 训练计划（phase, workout, distance, rpe, hrCap, gear, details, postRun）
- `diet`: 饮食方案（phase, carbTarget, proteinTarget, water, meals, notes）
- `recovery`: 恢复监控项目列表

---

# 配置文件

训练和饮食计划存储在 `api-tools/race_config.yaml`（CLI 工具）和 `dailyPlan` 云函数中。

如需自定义：
1. CLI: 编辑 `race_config.yaml` 的 `training` 和 `diet` 部分
2. 小程序: 修改 `cloudfunctions/dailyPlan/index.js` 中的 `getTrainingPlan()` 和 `getDietPlan()`

---

# 输出格式

## CLI 日报中的训练部分（Markdown）

```markdown
## 8. 今日训练 (D-2 / 03月26日 周四)

| 项目 | 内容 |
| :--- | :--- |
| **阶段** | Taper + 碳水负荷 |
| **训练** | 完全休息（散步可） |
| **距离/配速** | 0km |
| **强度** | — |

**训练说明：** 赛前 2 天，完全休息让身体超量恢复。

## 9. 今日饮食 (D-2)

**阶段：** 碳水负荷 Day 1
**碳水目标：** 8-10g/kg 体重

| 时段 | 建议 |
| :--- | :--- |
| **早餐** | 大碗白粥 + 馒头/面包 + 果酱 + 果汁 |
| **午餐** | 大碗米饭(300g+) + 少量瘦肉 + 蔬菜 |
```

## 小程序中的展示

三 Tab 切换：
- **训练计划 Tab**: 卡片式展示当日训练详情
- **饮食建议 Tab**: 餐食时间表 + 注意事项
- **恢复监控 Tab**: 可勾选的 Checklist
