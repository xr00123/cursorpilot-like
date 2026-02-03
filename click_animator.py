"""click_animator.py
Windows 透明点击特效
"""
from __future__ import annotations
import queue
import random
import sys
import time
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
import tkinter as tk

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] [DEBUG] {msg}")

try:
    from pynput import keyboard, mouse
except ImportError:
    print("请安装依赖: pip install pynput")
    sys.exit(1)

@dataclass(frozen=True)
class AppConfig:
    style: str; color: Tuple[int, int, int]; base_radius: int; max_radius: int
    duration_sec: float; fps: int; particle_count: int; quit_hotkey: str; run_seconds: float
    ring_width: int = 3; particle_size: int = 2; opacity: float = 1.0

@dataclass
class Particle:
    id: int
    x: float; y: float
    vx: float; vy: float
    life: float; max_life: float

class EffectWindow:
    def __init__(self, root: tk.Tk, x: int, y: int, config: AppConfig):
        self.root = root; self.config = config; self.created_at = time.monotonic()
        
        # 增加内边距防止圆环粗细或粒子超出边界导致被遮挡
        padding = max(config.ring_width, config.particle_size) + 5
        size = int((config.max_radius + padding) * 2)
        
        left, top = int(x - size/2), int(y - size/2)
        self._title = f"CA-{random.randint(100000, 999999)}"

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.geometry(f"{size}x{size}+{left}+{top}")
        self.win.title(self._title)
        
        bg_color = "#000001"
        
        if sys.platform == "darwin":
            # MacOS 特有透明背景设置
            try:
                self.win.wm_attributes("-transparent", True)
                self.win.configure(bg="systemTransparent")
                bg_color = "systemTransparent"
            except Exception:
                self.win.configure(bg=bg_color)
        else:
            self.win.configure(bg=bg_color)
            if sys.platform == "win32":
                self.win.wm_attributes("-transparentcolor", bg_color)
                self.win.wm_attributes("-topmost", True)
                self.win.wm_attributes("-toolwindow", True)
        
        # Apply initial opacity
        self.win.attributes("-alpha", self.config.opacity)

        self.canvas = tk.Canvas(self.win, width=size, height=size, highlightthickness=0, bd=0, bg=bg_color)
        self.canvas.pack()
        self.particles: List[Particle] = []
        self._init_graphics(size)

        # 核心修复步骤：在显示前注入属性
        self.win.update_idletasks()
        if sys.platform == "win32":
            self._windows_apply_ghost_properties()
        
        self.win.deiconify()
            
        self._tick()

    def _windows_apply_ghost_properties(self):
        try:
            import ctypes
            from ctypes import windll
            # 尝试获取 HWND
            hwnd = windll.user32.GetParent(self.win.winfo_id())
            if not hwnd:
                hwnd = self.win.winfo_id()
                
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            
            style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except Exception as e:
            log(f"Windows 注入失败: {e}")

    def _init_graphics(self, size: int):
        self.cx = self.cy = size / 2.0
        hex_color = "#%02x%02x%02x" % self.config.color
        
        # 主图形
        if self.config.style == "ring":
            self.item = self.canvas.create_oval(0, 0, 0, 0, outline=hex_color, width=self.config.ring_width, fill="")
        elif self.config.style == "circle":
            self.item = self.canvas.create_oval(0, 0, 0, 0, outline="", width=0, fill=hex_color)
        else:
            # particle or burst
            self.item = None

        # 粒子系统初始化
        if self.config.style == "particle" and self.config.particle_count > 0:
            for _ in range(self.config.particle_count):
                angle = random.uniform(0, 2 * math.pi)
                # Calculate speed based on max_radius (Range) and duration_sec
                # We want particles to reach approx max_radius by end of life
                # Speed (pixels/frame) = Distance / (Duration * FPS)
                avg_speed = self.config.max_radius / (self.config.duration_sec * self.config.fps)
                speed = random.uniform(0.8, 1.2) * avg_speed
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                
                # 随机寿命
                life = self.config.duration_sec * random.uniform(0.6, 1.0)
                
                # Particle size
                p_size = self.config.particle_size
                pid = self.canvas.create_oval(0, 0, p_size, p_size, fill=hex_color, outline="")
                # Center the particle
                self.canvas.move(pid, self.cx - p_size/2, self.cy - p_size/2)
                
                self.particles.append(Particle(pid, self.cx, self.cy, vx, vy, life, life))

    def _tick(self):
        now = time.monotonic()
        elapsed = now - self.created_at
        p = min(1.0, elapsed / self.config.duration_sec)
        
        if p >= 1.0:
            self.win.destroy(); return
        
        # 优化缓动：ease-out
        t = 1.0 - (1.0 - p) ** 3
        
        # 更新主图形 (Ring and Circle)
        if self.item:
            r = self.config.base_radius + (self.config.max_radius - self.config.base_radius) * t
            self.canvas.coords(self.item, self.cx-r, self.cy-r, self.cx+r, self.cy+r)
            
            # Windows 特殊处理：使用宽度衰减代替透明度淡出
            if sys.platform == "win32" and self.config.style == "ring" and p > 0.5:
                # 宽度随时间变细
                decay_factor = 1.0 - (p - 0.5) * 2
                new_width = max(0, self.config.ring_width * decay_factor)
                self.canvas.itemconfigure(self.item, width=new_width)

        # 更新粒子
        if self.particles:
            dead_particles = []
            for pt in self.particles:
                # 物理运动
                pt.x += pt.vx
                pt.y += pt.vy
                pt.vx *= 0.95  # 阻力
                pt.vy *= 0.95
                
                # 粒子大小随寿命衰减
                pt_age = now - self.created_at
                pt_p = min(1.0, pt_age / pt.max_life)
                if pt_p >= 1.0:
                    self.canvas.delete(pt.id)
                    dead_particles.append(pt)
                    continue
                
                # pr = 2 * (1.0 - pt_p)  # 粒子半径 (Old hardcoded)
                # Use configured size and decay
                current_size = self.config.particle_size * (1.0 - pt_p)
                pr = current_size / 2.0
                
                self.canvas.coords(pt.id, pt.x-pr, pt.y-pr, pt.x+pr, pt.y+pr)
            
            for dp in dead_particles:
                self.particles.remove(dp)

        # 透明度渐变 (仅在后半段开始淡出，提升前半段观感)
        # Windows 上禁用动态 Alpha 淡出以避免透明色穿透失效（显示方框）
        if sys.platform != "win32":
            alpha_decay = 1.0
            if p > 0.5:
                alpha_decay = 1.0 - (p - 0.5) * 2
            
            final_alpha = self.config.opacity * alpha_decay
            self.win.attributes("-alpha", final_alpha)
        
        self.win.after(int(1000/self.config.fps), self._tick)

class ClickAnimatorApp:
    def __init__(self, config: AppConfig, root=None, with_ui=False, on_toggle_settings=None):
        self.config = config
        self.root = root if root else tk.Tk()
        if not with_ui: self.root.withdraw()
        self._queue = queue.Queue()
        self._running = True
        self._on_toggle_settings = on_toggle_settings
        self._listeners = []

    def start_background(self):
        log("后台监听启动...")
        def on_click(x, y, button, pressed):
            if not pressed: self._queue.put(("click", (int(x), int(y))))
        
        def on_press(key):
            ctrl = any(k in self._pressed for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r))
            shift = any(k in self._pressed for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))
            try:
                if hasattr(key, 'char') and key.char:
                    if key.char.lower() == 's' and ctrl and shift and self._on_toggle_settings:
                        self._queue.put(("toggle_settings", None))
                    if key.char.lower() == 'q' and ctrl and shift:
                        self._queue.put(("quit", None))
            except: pass

        self._pressed = set()
        def _kp(k): self._pressed.add(k); on_press(k)
        def _kr(k): self._pressed.discard(k)

        ml = mouse.Listener(on_click=on_click)
        kl = keyboard.Listener(on_press=_kp, on_release=_kr)
        ml.start(); kl.start()
        self._listeners = [ml, kl]
        self._poll()

    def _poll(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "click":
                    EffectWindow(self.root, payload[0], payload[1], self.config)
                elif kind == "toggle_settings":
                    if self._on_toggle_settings: self._on_toggle_settings()
                elif kind == "quit":
                    self.shutdown(); return
        except queue.Empty: pass
        if self._running: self.root.after(10, self._poll)

    def update_config(self, cfg): self.config = cfg
    def shutdown(self):
        print("程序已退出")
        self._running = False
        for l in self._listeners: l.stop()
        self.root.quit()
    def start(self):
        self.start_background()
        self.root.mainloop()

def main():
    cfg = AppConfig("ring", (0, 200, 255), 18, 110, 0.6, 60, 0, "ctrl+shift+q", 0.0)
    ClickAnimatorApp(cfg).start()

def setup_dpi():
    if sys.platform == "win32":
        try:
            import ctypes
            # 告诉系统当前进程是 DPI 感知的，防止坐标错位
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

if __name__ == "__main__":
    setup_dpi()
    main()
