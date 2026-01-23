# Click Animator（轻量级鼠标点击动画）

一个 Python 3.10 的轻量级鼠标点击动画工具：在你点击鼠标的瞬间，在点击位置弹出丝滑的扩散/波纹/粒子动画，类似 cursorpilot 的“点击提示”。

实现特点：
- 全局监听鼠标点击（后台运行，无主窗口）
- 动画时长 0.5~1 秒，大小/透明度平滑过渡
- 3 种预设风格 + 命令行可自定义颜色/大小/粒子数量/帧率
- 退出无残留进程（全局热键 Ctrl+Shift+Q）

## 依赖安装

`tkinter` 是 Python 标准库自带（大多数 Python 发行版自带 GUI 支持），唯一需要安装的是 `pynput`：

```bash
pip install pynput
```

## 运行

```bash
python click_animator.py
```

退出：按 `Ctrl+Shift+Q`。

## 可编辑的设置 UI

如果你希望像 cursorpilot 那样“开着一个设置面板随时改颜色/大小/样式”，运行：

```bash
python click_animator_ui.py
```

窗口里的参数会实时作用于后续点击产生的动画。

### 预设效果

```bash
python click_animator.py --preset cyan_ring
python click_animator.py --preset white_ripple
python click_animator.py --preset pink_burst
```

### 自定义参数（覆盖预设）

```bash
python click_animator.py --preset cyan_ring --color #00ff66 --max-radius 140 --duration 0.8
python click_animator.py --style burst --color #ffaa00 --particles 30 --duration 0.7
```

常用参数：
- `--style`：`ripple` / `ring` / `burst`
- `--color`：`#RRGGBB`
- `--base-radius`：初始半径
- `--max-radius`：最大半径
- `--duration`：动画时长（秒）
- `--fps`：目标帧率

### 自测（不需要手动退出）

```bash
python click_animator.py --run-seconds 2
```

## macOS 权限说明（重要）

在 macOS 上，全局鼠标/键盘监听通常需要授权，否则会看到类似：
`This process is not trusted! Input event monitoring will not be possible ...`

处理方法（不同版本系统名称略有差异）：
- 系统设置 → 隐私与安全性 → 输入监控（Input Monitoring）/辅助功能（Accessibility）
- 把你运行脚本的终端（如 Terminal / iTerm / VS Code / PyCharm）加入允许列表
- 重新运行脚本

如果出现 Quartz/pyobjc 相关异常（例如 pynput 报错），可尝试升级：

```bash
pip install -U pyobjc-framework-Quartz pynput
```

## Windows 说明

- 脚本会尝试设置进程 DPI Awareness，以减少高 DPI 下坐标偏移。
- Windows 下透明背景使用 Tk 的 `-transparentcolor`，效果最接近“真正悬浮透明叠层”。

## 文件

- [click_animator.py](file:///Users/hxr/Documents/python_workspace/study/click_animator.py)：主程序
