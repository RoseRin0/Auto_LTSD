# LTSD 打轴器 - MuMu 模拟器操作录制与回放工具

本项目为一款面向 MuMu 模拟器窗口的游戏自动化脚本工具，支持以下功能：

- ✅ 鼠标点击与键盘按键操作的录制与回放
- ✅ 使用 OCR 技术实时识别技能冷却时间
- ❓ DPI 缩放适配，保证不同分辨率下的操作一致性
- ✅ 支持识别技能释放时机，精确控制操作顺序
- ✅ 自动记录操作流程至 JSON 文件，可重复使用

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

> ⚠️ 请确保你已安装 [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract) 并将其路径配置为：
>
> ```python
> pytesseract.pytesseract.tesseract_cmd = r'D:\Tesseract-OCR\tesseract.exe'
> ```

## 🚀 使用方式

### 1. 启动程序

```bash
python main.py
```

### 2. 菜单操作

- `1`：录制操作流程（支持角色名称输入，录制点击与键盘）
- `2`：回放操作流程（会自动识别技能冷却时间并精确释放）
- `3`：退出程序

## 📁 文件结构说明

- `main.py`：主程序，包含录制、回放与识别逻辑
- `script/`：保存录制的操作脚本 JSON 文件
- `ocr_debug/`（可选）：调试用图像输出目录

## 🧠 技术亮点

- OCR 识别采用 `pytesseract + OpenCV` 双重处理，增强识别准确性
- 使用 `pynput` 捕获全局输入
- 基于窗口 PID 绑定，避免误触其他窗口
- DPI 缩放计算精准，适配多显示器场景

## ✅ 系统需求

- Windows 操作系统
- MuMu 模拟器窗口名包含 `MuMuPlayer`
- 安装 Microsoft Visual C++ Redistributable（部分 win32 接口需要）

## ⚙ 测试环境

- MuMu模拟器12，2560x1440分辨率(只适配了MuMu模拟器，其它模拟器需要自行更改窗口类名和窗口标题等)
- 系统显示设置：3840x2160分辨率，3.0缩放
- tesseract版本5.4.0.20240606
- 游戏设置：60帧，关闭全屏显示技能特效
- 硬件配置： 显卡：4070 CPU：i7-12650H
- 其它环境待测试

## 📃 Todo

- 1.完善脚本生成功能
- 2.添加一键中途重试功能
- 3.自动完成每日功能（可能会鸽）

## 📜 License

MIT License
