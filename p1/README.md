# 上传简历页（Upload Your Resume）

按设计稿还原的简历上传页面，**纯 HTML + CSS + 原生 JavaScript**，无框架、无构建、无第三方依赖，双击 `index.html` 即可打开。

## 文件结构

```
p1/
├── index.html     页面结构（语义化标签）
├── styles.css     样式与响应式
├── app.js         上传交互逻辑
├── cat.png        设计稿插画切图
├── preview.png    效果预览（1440 × 900）
└── README.md
```

## 运行

- 直接双击 `index.html`（`file://` 协议下全部功能可用）；
- 或起一个静态服务：`python -m http.server 8080`，访问 `http://localhost:8080/p1/`。

## 还原说明

- 页面结构：白色页面 + 居中两栏容器（最大 1120），左侧文案与插画、右侧上传卡片（550 宽、1px 浅边框 + 柔和投影）。
- 尺寸按设计稿等比换算：卡片内边距 13.8%、拖拽区高 245、按钮 157×37、圆角 20/16/8/6。
- 颜色取自设计稿取色：拖拽区 `#f2faff`、主按钮 `#1b5aff`、次按钮 `#75acff`、虚线 `#4577e8`。
- 插画位于左栏底部，与上传卡片底边对齐，左侧与正文左对齐。
- 断点：`≤1000`（收窄内边距）、`≤860`（左右改上下堆叠）、`≤560`（移动端）、`≤380`（按钮竖排）。

## 交互

| 功能 | 说明 |
| --- | --- |
| 选择文件 | 点击拖拽区或整个已选文件条，打开系统文件选择框 |
| 拖拽上传 | 拖入高亮，松手即选中；拖到页面其他位置不会误打开文件 |
| 文件展示 | 显示文件名、大小，可一键移除后重选 |
| 校验 | 仅支持 PDF / DOC / DOCX，单文件 ≤ 10MB，非法时红框 + 提示 |
| 按钮状态 | `Last step` / `Finish` 均有 hover、active、focus-visible 状态 |
| 提交 | 未选文件时提示并高亮拖拽区；已选时显示「上传中」再提示成功 |
| 键盘 | Tab 聚焦上传区，Enter / 空格 打开文件选择框；Esc 关闭对话框 |

## 无障碍

- `main / section / h1 / h2 / form / ol` 语义化结构；
- 隐藏的 `input[type=file]` 与 `<label>` 关联，`aria-describedby` 指向提示文案；
- 状态区 `role="status" aria-live="polite"`，选文件与提交结果会被读屏播报；
- 步骤条 `aria-current="step"`，圆点图形 `aria-hidden`，文案由 `.visually-hidden` 提供；
- 支持 `prefers-reduced-motion`。
