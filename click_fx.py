# click_fx.py
# Python 3.10
# 渲染进程：负责全屏透明窗口的绘制、鼠标监听与动画逻辑。

import sys
import time
import math
import random
import multiprocessing
from dataclasses import dataclass
from typing import Tuple, List, Any, Dict

import pygame
from pynput import mouse

# 默认配置
DEFAULT_CONFIG = {
    "click_enabled": True,
    "style": "ripple",             # ripple | wave | dust
    "color": (0, 200, 255),        # 点击颜色
    "base_radius": 22,             # 点击初始大小
    "max_scale": 6.0,              # 点击扩散倍数
    "duration_sec": 0.8,           # 动画时长
    
    "highlight_enabled": False,    # 是否开启鼠标跟随高亮
    "highlight_color": (255, 255, 0), # 高亮颜色 (默认黄色)
    "highlight_radius": 30,        # 高亮半径
    "highlight_alpha": 100,        # 高亮透明度 (0-255)
    
    "fps": 60,
}

@dataclass
class Effect:
    kind: str
    start_time: float
    pos: Tuple[int, int]
    color: Tuple[int, int, int]
    base_r: float
    duration: float
    max_scale: float

    def progress(self, now: float) -> float:
        return min(1.0, max(0.0, (now - self.start_time) / self.duration))

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    born: float
    color: Tuple[int, int, int]

class ClickFXApp:
    def __init__(self, command_queue: multiprocessing.Queue = None):
        self.config = DEFAULT_CONFIG.copy()
        self.command_queue = command_queue
        
        pygame.init()
        disp_info = pygame.display.Info()
        self.w = disp_info.current_w
        self.h = disp_info.current_h
        
        # macOS: 尝试全屏无边框
        flags = pygame.NOFRAME | pygame.SRCALPHA
        self.screen = pygame.display.set_mode((self.w, self.h), flags)
        pygame.display.set_caption("ClickFXOverlay")

        self._clickthrough_ready = False
        self._last_clickthrough_try = 0.0
        self._clickthrough_ready = self._make_window_topmost_and_clickthrough()

        self.clock = pygame.time.Clock()
        self.effects: List[Effect] = []
        self.particles: List[Particle] = []
        self.running = True

        # 鼠标控制器 (用于获取实时位置)
        self.mouse_ctl = mouse.Controller()
        
        # 鼠标监听器 (用于检测点击)
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()

    def _process_queue(self):
        """处理来自UI进程的配置更新"""
        if not self.command_queue:
            return
        
        while not self.command_queue.empty():
            try:
                cmd = self.command_queue.get_nowait()
                if cmd["type"] == "update_config":
                    # 更新配置
                    for k, v in cmd["data"].items():
                        if k in self.config:
                            self.config[k] = v
                elif cmd["type"] == "quit":
                    self.running = False
            except Exception:
                break

    def _on_click(self, x, y, button, pressed):
        if pressed or not self.config["click_enabled"]:
            return
        try:
            # 只有左键才触发(可选，目前所有键都触发)
            style = self.config["style"]
            color = self.config["color"]
            
            eff = Effect(
                kind=style,
                start_time=time.time(),
                pos=(int(x), int(y)),
                color=color,
                base_r=float(self.config["base_radius"]),
                duration=float(self.config["duration_sec"]),
                max_scale=float(self.config["max_scale"])
            )
            self.effects.append(eff)

            if style == "dust":
                self._spawn_particles(x, y, color)
        except Exception as e:
            print(f"[ClickFX] on_click error: {e}", file=sys.stderr)

    def _spawn_particles(self, x, y, color):
        now = time.time()
        count = 28
        speed_min, speed_max = 120, 420
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(speed_min, speed_max)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = random.uniform(self.config["duration_sec"] * 0.5,
                                  self.config["duration_sec"] * 1.1)
            self.particles.append(Particle(
                x=float(x), y=float(y), vx=vx, vy=vy,
                life=life, born=now, color=color
            ))

    def _make_window_topmost_and_clickthrough(self) -> bool:
        info = pygame.display.get_wm_info()
        try:
            if sys.platform.startswith("win"):
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = info.get("window")
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_SHOWWINDOW = 0x0040
                HWND_TOPMOST = -1
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                GWL_EXSTYLE = -20
                WS_EX_LAYERED = 0x00080000
                WS_EX_TRANSPARENT = 0x00000020
                current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                      current | WS_EX_LAYERED | WS_EX_TRANSPARENT)
                return True
            elif sys.platform == "darwin":
                try:
                    from AppKit import NSApp, NSApplication, NSWindow, NSColor
                    app = NSApplication.sharedApplication()
                    windows = app.windows()
                    target_window = None
                    for win in windows:
                        if win.title() == "ClickFXOverlay":
                            target_window = win
                            break
                    if not target_window and len(windows) > 0:
                        target_window = windows[0]
                    if target_window:
                        target_window.setLevel_(1000) 
                        target_window.setIgnoresMouseEvents_(True)
                        target_window.setCollectionBehavior_(1 << 0)
                        target_window.setOpaque_(False)
                        target_window.setBackgroundColor_(NSColor.clearColor())
                        return True
                except Exception:
                    pass
        except Exception as e:
            print(f"[ClickFX] window attributes error: {e}", file=sys.stderr)
        return False

    def _draw_effect(self, surf: pygame.Surface, eff: Effect, now: float):
        p = eff.progress(now)
        if p <= 0.0 or p > 1.0:
            return False
        
        t = 1 - (1 - p) ** 3
        radius = eff.base_r * (1.0 + t * (eff.max_scale - 1.0))
        alpha = int(255 * (1.0 - (p ** 1.6)))
        color = (*eff.color, max(0, min(255, alpha)))

        if eff.kind == "ripple":
            pygame.draw.circle(surf, color, eff.pos, int(radius))
        elif eff.kind == "wave":
            thickness = max(1, int(eff.base_r * 0.25 + t * 4))
            pygame.draw.circle(surf, color, eff.pos, int(radius), thickness)
        elif eff.kind == "dust":
            core_alpha = int(alpha * 0.25)
            core_col = (*eff.color, core_alpha)
            pygame.draw.circle(surf, core_col, eff.pos, max(1, int(eff.base_r * 0.6)))
        else:
            pygame.draw.circle(surf, color, eff.pos, int(radius))
        return True

    def _update_particles(self, surf: pygame.Surface, now: float):
        alive: List[Particle] = []
        for pt in self.particles:
            age = now - pt.born
            if age >= pt.life:
                continue
            dt = self.clock.get_time() / 1000.0
            drag = 0.92
            pt.vx *= drag
            pt.vy *= drag
            pt.x += pt.vx * dt
            pt.y += pt.vy * dt
            fade = 1.0 - (age / pt.life)
            fade = max(0.0, min(1.0, fade ** 1.4))
            alpha = int(255 * fade)
            col = (*pt.color, alpha)
            size = max(1, int(2 + 2 * (1.0 - fade)))
            pygame.draw.circle(surf, col, (int(pt.x), int(pt.y)), size)
            alive.append(pt)
        self.particles = alive

    def _draw_highlight(self, surf: pygame.Surface):
        """绘制鼠标跟随高亮"""
        try:
            # 获取当前鼠标位置 (全局坐标)
            # 注意：在全屏 overlay 模式下，global pos 通常等于窗口坐标
            mx, my = self.mouse_ctl.position
            # 简单边界检查
            # if 0 <= mx < self.w and 0 <= my < self.h:
            
            radius = self.config["highlight_radius"]
            color_rgb = self.config["highlight_color"]
            alpha = self.config["highlight_alpha"]
            
            # 绘制半透明圆
            # pygame.draw.circle 支持 alpha 需要传入带 alpha 的 color，但必须绘制在支持 alpha 的 surface 上
            # self.screen 已经是 SRCALPHA
            color = (*color_rgb, alpha)
            
            # 绘制一个柔和的光圈
            pygame.draw.circle(surf, color, (int(mx), int(my)), radius)
            
            # 可选：加个实心中心点方便定位
            pygame.draw.circle(surf, (*color_rgb, 200), (int(mx), int(my)), 4)
            
        except Exception:
            pass

    def run(self):
        try:
            while self.running:
                # 1. 处理 UI 消息
                self._process_queue()
                
                # 2. Pygame 事件
                now = time.time()

                if not self._clickthrough_ready and (now - self._last_clickthrough_try) >= 0.2:
                    self._last_clickthrough_try = now
                    self._clickthrough_ready = self._make_window_topmost_and_clickthrough()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False

                self.screen.fill((0, 0, 0, 0))

                # 3. 绘制鼠标高亮 (如果开启)
                if self.config["highlight_enabled"]:
                    self._draw_highlight(self.screen)

                # 4. 绘制点击特效
                active: List[Effect] = []
                for eff in self.effects:
                    if self._draw_effect(self.screen, eff, now):
                        active.append(eff)
                self.effects = active

                self._update_particles(self.screen, now)

                pygame.display.update()
                self.clock.tick(self.config["fps"])
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"[ClickFX] runtime error: {e}", file=sys.stderr)
        finally:
            try:
                self.listener.stop()
            except Exception:
                pass
            pygame.quit()
            sys.exit(0)

def run_overlay_process(queue):
    """Entry point for the multiprocessing Process"""
    app = ClickFXApp(command_queue=queue)
    app.run()

if __name__ == "__main__":
    # 独立运行测试
    app = ClickFXApp()
    app.run()
