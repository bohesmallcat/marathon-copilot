# AGENTS.md — Marathon Copilot 项目规则

## 跑者信息模糊化（强制）

所有提交到仓库的文件（README、SKILL.md、示例配置等）**禁止包含跑者真实身份信息**。

### 规则

- 跑者昵称、真名、社交账号 → 使用 `Runner A` / `Runner B` / `跑者 A` 等匿名标识
- 赛事日期编号（如 315、322、328）→ 如果能关联到特定跑者，移除或泛化为"XX城市半马""YY城市马拉松"等匿名赛事名
- 体重、身高等生物特征 → 在公开文档中使用范围描述或省略，仅在 `.example.yaml` 模板中使用示例值
- 具体装备品牌型号（如能关联跑者）→ 泛化为"碳板跑鞋"等通用描述
- 文件名中的跑者昵称（如 `markdownfile/` 下的报告）→ 这些文件已通过 `.gitignore` 排除，不会提交

### 适用范围

- `README.md`
- `.cognition/skills/*/SKILL.md`
- `api-tools/*.example.yaml`
- 任何会被 `git add` 的文件

### 不受限范围

- 本地报告文件（已在 `.gitignore` 中排除）
- 本地跑者配置（`race_config.yaml`、`runner_profile_*.yaml` 等，已排除）

## 验证命令

```bash
# 构建/测试
python api-tools/training_calculator.py   # 算法库自检

# PDF 生成
python generate_pdf.py <input.md> <output.pdf>
```
