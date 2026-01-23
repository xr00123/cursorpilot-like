"""click_animator.py

Python 3.10 轻量级鼠标点击动画工具（类似 cursorpilot 的点击波纹效果）。

依赖：
  - pynput（全局鼠标/键盘监听）
  - tkinter（标准库，负责绘制透明小窗动画）

安装：
  pip install pynput

运行：
  python click_animator.py

退出：
  默认热键 Ctrl+Shift+Q（全局生效）

说明：
  - Windows 下使用 Tk 的 -transparentcolor 实现真正透明背景。
  - macOS 下优先尝试 -transparent（取决于 Tk 版本）；若不支持，将退化为小窗整体透明度淡出。
  - macOS 可能需要在“系统设置 -> 隐私与安全性 -> 辅助功能/输入监控”里授权。
"""

from __future__ import annotations

import argparse
import math
import queue
import random
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import tkinter as tk

from pynput import keyboard, mouse


def _ease_out_cubic(t: float) -> float:
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return 1.0 - (1.0 - t) ** 3


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _parse_rgb(s: str) -> Tuple[int, int, int]:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError("color must be like #RRGGBB")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _set_windows_dpi_aware() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        return


def _macos_quartz_ok() -> bool:
    if sys.platform != "darwin":
        return True
    try:
        import Quartz  # type: ignore

        _ = Quartz.CFMachPortCreateRunLoopSource
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class AppConfig:
    style: str
    color: Tuple[int, int, int]
    base_radius: int
    max_radius: int
    duration_sec: float
    fps: int
    particle_count: int
    quit_hotkey: str
    run_seconds: float


class EffectWindow:
    """每次点击创建一个透明小窗，窗口内做 0.5~1s 的动画并自动销毁。"""

    TRANSPARENT_KEY_COLOR = "#ff00ff"  # Windows 下用于 -transparentcolor 的 key 色

    def __init__(
        self,
        root: tk.Tk,
        x: int,
        y: int,
        config: AppConfig,
    ) -> None:
        self.root = root
        self.config = config
        self.created_at = time.monotonic()

        size = int(config.max_radius * 2)
        left = int(x - config.max_radius)
        top = int(y - config.max_radius)

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{size}x{size}+{left}+{top}")

        self._title = f"ClickAnimatorEffect-{id(self)}"
        try:
            self.win.title(self._title)
        except Exception:
            pass

        self._apply_platform_background()

        self._setup_transparency()
        self._setup_clickthrough_best_effort()

        self.canvas = tk.Canvas(
            self.win,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg=self._canvas_bg_color(),
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.cx = size / 2.0
        self.cy = size / 2.0
        self.items: Dict[str, int] = {}
        self.particles: List[Tuple[float, float, float, float]] = []
        self._init_items()

        self.win.deiconify()
        try:
            self.win.update_idletasks()
        except Exception:
            pass
        self._setup_clickthrough_after_show()
        self._tick()

    def _setup_clickthrough_after_show(self) -> None:
        if sys.platform == "darwin":
            self._retry_enable_clickthrough_macos(tries_left=6)

    def _retry_enable_clickthrough_macos(self, tries_left: int) -> None:
        if tries_left <= 0:
            return
        ok = False
        try:
            ok = self._enable_clickthrough_macos_best_effort()
        except Exception:
            ok = False
        if ok:
            return
        try:
            self.win.after(15, lambda: self._retry_enable_clickthrough_macos(tries_left=tries_left - 1))
        except Exception:
            return

    def _apply_platform_background(self) -> None:
        if sys.platform == "darwin":
            try:
                self.win.configure(bg="systemTransparent")
            except Exception:
                self.win.configure(bg="black")
        else:
            self.win.configure(bg=self.TRANSPARENT_KEY_COLOR)

    def _canvas_bg_color(self) -> str:
        if sys.platform == "darwin":
            return "systemTransparent"
        return self.TRANSPARENT_KEY_COLOR

    def _setup_transparency(self) -> None:
        """尽可能获得真正透明的背景。"""
        if sys.platform.startswith("win"):
            try:
                self.win.wm_attributes("-transparentcolor", self.TRANSPARENT_KEY_COLOR)
            except Exception:
                pass

            try:
                self._enable_clickthrough_windows()
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                self.win.wm_attributes("-transparent", True)
            except Exception:
                pass

            try:
                self._enable_clickthrough_macos_best_effort()
            except Exception:
                pass

        try:
            self.win.wm_attributes("-alpha", 1.0)
        except Exception:
            pass

    def _enable_clickthrough_windows(self) -> None:
        import ctypes

        hwnd = int(self.win.winfo_id())
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_NOACTIVATE = 0x08000000

        user32 = ctypes.windll.user32
        current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd,
            GWL_EXSTYLE,
            current | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        HWND_TOPMOST = -1
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _enable_clickthrough_macos_best_effort(self) -> bool:
        try:
            from AppKit import NSApplication, NSColor
        except Exception:
            return False

        try:
            app = NSApplication.sharedApplication()
            windows = app.windows()
        except Exception:
            return False

        target = None
        for w in windows:
            try:
                if str(w.title()) == self._title:
                    target = w
                    break
            except Exception:
                continue

        if target is None:
            return False

        try:
            target.setIgnoresMouseEvents_(True)
        except Exception:
            pass
        try:
            target.setOpaque_(False)
            target.setBackgroundColor_(NSColor.clearColor())
        except Exception:
            pass

        return True

    def _setup_clickthrough_best_effort(self) -> None:
        """尽可能避免窗口抢焦点/影响点击（不同平台支持程度不同）。"""
        try:
            self.win.wm_attributes("-disabled", True)
        except Exception:
            pass

    def _init_items(self) -> None:
        color = _rgb_to_hex(self.config.color)

        if self.config.style == "ripple":
            self.items["core"] = self.canvas.create_oval(
                0, 0, 0, 0, outline="", fill=color
            )
        elif self.config.style == "ring":
            self.items["ring"] = self.canvas.create_oval(
                0, 0, 0, 0, outline=color, width=3, fill=""
            )
        elif self.config.style == "burst":
            self.items["ring"] = self.canvas.create_oval(
                0, 0, 0, 0, outline=color, width=3, fill=""
            )
            self._spawn_particles()
            for i in range(len(self.particles)):
                self.items[f"p{i}"] = self.canvas.create_oval(
                    0, 0, 0, 0, outline="", fill=color
                )
        else:
            self.items["ring"] = self.canvas.create_oval(
                0, 0, 0, 0, outline=color, width=3, fill=""
            )

    def _spawn_particles(self) -> None:
        rng = random.Random()
        self.particles.clear()
        for _ in range(max(0, int(self.config.particle_count))):
            ang = rng.uniform(0.0, math.tau)
            spd = rng.uniform(140.0, 520.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            self.particles.append((self.cx, self.cy, vx, vy))

    def _tick(self) -> None:
        try:
            now = time.monotonic()
            elapsed = now - self.created_at
            p = _clamp(elapsed / self.config.duration_sec, 0.0, 1.0)
            t = _ease_out_cubic(p)

            radius = self.config.base_radius + (self.config.max_radius - self.config.base_radius) * t
            alpha = _clamp(1.0 - p, 0.0, 1.0)

            self._render(radius=float(radius), alpha=float(alpha), dt=1.0 / max(1, self.config.fps))

            if p >= 1.0:
                self._destroy()
                return

            delay_ms = max(1, int(1000 / max(1, self.config.fps)))
            self.win.after(delay_ms, self._tick)
        except Exception:
            self._destroy()

    def _render(self, radius: float, alpha: float, dt: float) -> None:
        try:
            self.win.wm_attributes("-alpha", alpha)
        except Exception:
            pass

        x1 = self.cx - radius
        y1 = self.cy - radius
        x2 = self.cx + radius
        y2 = self.cy + radius

        if self.config.style == "ripple":
            self.canvas.coords(self.items["core"], x1, y1, x2, y2)
        else:
            if "ring" in self.items:
                width = 2 + int(6 * (1.0 - alpha))
                self.canvas.itemconfigure(self.items["ring"], width=width)
                self.canvas.coords(self.items["ring"], x1, y1, x2, y2)

        if self.config.style == "burst" and self.particles:
            drag = 0.90
            for i, (px, py, vx, vy) in enumerate(self.particles):
                vx *= drag
                vy *= drag
                px += vx * dt
                py += vy * dt
                self.particles[i] = (px, py, vx, vy)

                size = 2 + int(3 * (1.0 - alpha))
                self.canvas.coords(
                    self.items[f"p{i}"],
                    px - size,
                    py - size,
                    px + size,
                    py + size,
                )

    def _destroy(self) -> None:
        try:
            self.win.destroy()
        except Exception:
            pass

    def destroy(self) -> None:
        self._destroy()


class QuitHotkey:
    """全局退出热键（默认 Ctrl+Shift+Q）。"""

    def __init__(self, spec: str) -> None:
        self.spec = spec.lower().replace(" ", "")
        self._pressed: set = set()

        if self.spec in {"ctrl+shift+q", "control+shift+q"}:
            self._trigger_key = "q"
        else:
            raise ValueError("only quit-hotkey=ctrl+shift+q is supported in this demo")

    def on_press(self, key) -> bool:
        try:
            self._pressed.add(key)
            if self._is_triggered():
                return False
            return True
        except Exception:
            return True

    def on_release(self, key) -> None:
        try:
            if key in self._pressed:
                self._pressed.remove(key)
        except Exception:
            pass

    def _is_triggered(self) -> bool:
        ctrl_down = any(k in self._pressed for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r))
        shift_down = any(k in self._pressed for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))
        if not (ctrl_down and shift_down):
            return False

        for k in list(self._pressed):
            if isinstance(k, keyboard.KeyCode) and k.char:
                if k.char.lower() == self._trigger_key:
                    return True
        return False


class ClickAnimatorApp:
    def __init__(self, config: AppConfig, root: Optional[tk.Tk] = None, with_ui: bool = False) -> None:
        self.config = config
        self.root = root if root is not None else tk.Tk()
        if not with_ui:
            try:
                self.root.withdraw()
            except Exception:
                pass
        self._queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self._running = True
        self._mouse_listener: Optional[mouse.Listener] = None
        self._kb_listener: Optional[keyboard.Listener] = None
        self._effects: List[EffectWindow] = []

    def start(self) -> None:
        self.start_background()
        self.root.mainloop()

    def start_background(self) -> None:
        self._start_listeners()
        if self.config.run_seconds > 0:
            ms = max(1, int(self.config.run_seconds * 1000))
            self.root.after(ms, lambda: self._queue.put(("quit", None)))
        self.root.after(10, self._poll_queue)

    def update_config(self, cfg: AppConfig) -> None:
        self.config = cfg

    def _start_listeners(self) -> None:
        if sys.platform == "darwin" and not _macos_quartz_ok():
            print(
                "[click_animator] 检测到 macOS 的 Quartz/pyobjc 环境异常，已跳过全局监听。\n"
                "请尝试：pip install -U pyobjc-framework-Quartz pynput",
                file=sys.stderr,
            )
            return

        try:
            def on_click(x, y, _button, pressed):
                if pressed:
                    return
                try:
                    self._queue.put(("click", (int(x), int(y))))
                except Exception:
                    return

            self._mouse_listener = mouse.Listener(on_click=on_click)
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
        except Exception:
            print(
                "[click_animator] 无法启动鼠标监听（macOS 可能需要授权 输入监控/辅助功能）。",
                file=sys.stderr,
            )
            traceback.print_exc()

        try:
            quit_hotkey = QuitHotkey(self.config.quit_hotkey)

            def on_press(key):
                cont = quit_hotkey.on_press(key)
                if not cont:
                    self._queue.put(("quit", None))
                return cont

            def on_release(key):
                quit_hotkey.on_release(key)

            self._kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._kb_listener.daemon = True
            self._kb_listener.start()
        except Exception:
            print(
                "[click_animator] 无法启动键盘监听（macOS 可能需要授权 输入监控/辅助功能）。",
                file=sys.stderr,
            )
            traceback.print_exc()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "click":
                    x, y = payload
                    self._spawn_effect(x, y)
                elif kind == "quit":
                    self.shutdown()
                    return
        except queue.Empty:
            pass
        except Exception:
            traceback.print_exc()

        if self._running:
            self.root.after(10, self._poll_queue)

    def _spawn_effect(self, x: int, y: int) -> None:
        try:
            self._effects = [e for e in self._effects if e.win.winfo_exists()]

            max_active = 32
            if len(self._effects) >= max_active:
                try:
                    self._effects[0].destroy()
                except Exception:
                    pass
                self._effects = self._effects[1:]

            eff = EffectWindow(self.root, x, y, self.config)
            self._effects.append(eff)
        except Exception:
            traceback.print_exc()

    def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            if self._mouse_listener:
                self._mouse_listener.stop()
        except Exception:
            pass
        try:
            if self._kb_listener:
                self._kb_listener.stop()
        except Exception:
            pass
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument(
        "--preset",
        choices=["cyan_ring", "white_ripple", "pink_burst"],
        default=None,
        help="预设效果（可再叠加 --color/--max-radius 等参数覆盖）",
    )
    p.add_argument("--style", choices=["ripple", "ring", "burst"], default=None)
    p.add_argument("--color", default=None, help="#RRGGBB")
    p.add_argument("--base-radius", type=int, default=None)
    p.add_argument("--max-radius", type=int, default=None)
    p.add_argument("--duration", type=float, default=None, help="0.5~1.0 recommended")
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--particles", type=int, default=None)
    p.add_argument("--quit-hotkey", default="ctrl+shift+q")
    p.add_argument(
        "--run-seconds",
        type=float,
        default=0.0,
        help="用于自测：运行指定秒数后自动退出（0 表示一直运行）",
    )
    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    _set_windows_dpi_aware()

    args = _build_arg_parser().parse_args(list(argv) if argv is not None else None)

    presets = {
        "cyan_ring": {
            "style": "ring",
            "color": "#00c8ff",
            "base_radius": 18,
            "max_radius": 110,
            "duration": 0.75,
            "fps": 60,
            "particles": 18,
        },
        "white_ripple": {
            "style": "ripple",
            "color": "#ffffff",
            "base_radius": 12,
            "max_radius": 85,
            "duration": 0.65,
            "fps": 60,
            "particles": 0,
        },
        "pink_burst": {
            "style": "burst",
            "color": "#ff4fd8",
            "base_radius": 16,
            "max_radius": 120,
            "duration": 0.8,
            "fps": 60,
            "particles": 24,
        },
    }

    base = presets.get(args.preset, presets["cyan_ring"]) if args.preset else presets["cyan_ring"]

    style = args.style if args.style is not None else base["style"]
    color_str = args.color if args.color is not None else base["color"]
    base_radius = args.base_radius if args.base_radius is not None else base["base_radius"]
    max_radius = args.max_radius if args.max_radius is not None else base["max_radius"]
    duration = args.duration if args.duration is not None else base["duration"]
    fps = args.fps if args.fps is not None else base["fps"]
    particles = args.particles if args.particles is not None else base["particles"]

    cfg = AppConfig(
        style=style,
        color=_parse_rgb(color_str),
        base_radius=max(1, int(base_radius)),
        max_radius=max(10, int(max_radius)),
        duration_sec=_clamp(float(duration), 0.25, 3.0),
        fps=max(10, int(fps)),
        particle_count=max(0, int(particles)),
        quit_hotkey=str(args.quit_hotkey),
        run_seconds=max(0.0, float(args.run_seconds)),
    )

    app = ClickAnimatorApp(cfg)
    try:
        app.start()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception:
        traceback.print_exc()
        app.shutdown()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
