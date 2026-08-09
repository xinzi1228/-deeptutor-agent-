# 前端设计纪律（借鉴 stablyai/orca STYLEGUIDE）

## 单色安静
- 中性灰（--muted-foreground/--border）承载 chrome；**颜色只留给状态**。
- 状态色词汇表：working=amber / done=emerald / waiting=amber question / blocked=failed=red / idle=gray。
- 共享原语：`AgentStateDot`（web/components/common/）。

## 时长反馈（提交/加载）
- 0-100ms 无反馈；100ms-1s 仅禁用；1-3s 禁用+spinner；3s+ 阶段标签。
- **预占空间**：会变长的控件固定 width，避免点击瞬间跳动。
- 远端/慢操作：禁用立即绑定（防双击），可见加载延迟 ~200ms。

## Token 纪律
- 优先用现有 CSS 变量（--primary/--border/--muted-foreground）；需要色调用
  `color-mix(in srgb, var(--token) 12%, var(--background))`，**不造新 hex**。
- token 成对（surface + foreground 对比）。

## 兄弟组件一致性
- 相邻组件读作一个设计（同图标/同快捷键/同提交语义）。
- back-out（Cancel/Close）保持安静，视觉重量留给确认动作。
