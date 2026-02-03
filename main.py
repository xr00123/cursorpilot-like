"""main.py

可编辑的设置 UI：在不影响后台运行的前提下，提供点击特效的样式/颜色/大小/时长等配置。

依赖：
  pip install pynput customtkinter

运行：
  python main.py

退出：
  点击窗口里的 Exit，或全局热键 Ctrl+Shift+Q。
"""

from __future__ import annotations

import os
import threading
import ctypes
import tkinter as tk
from tkinter import colorchooser
import customtkinter as ctk
import pystray
from PIL import Image, ImageTk

from click_animator import AppConfig, ClickAnimatorApp, setup_dpi, load_settings, save_settings


ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"


PRESETS = {
    "圆环": {
        "style": "ring",
        "color": "#00c8ff",
        "base_radius": 18,
        "max_radius": 110,
        "duration_sec": 0.75,
        "fps": 60,
        "particle_count": 0,
        "ring_width": 3,
        "particle_size": 2,
        "opacity": 1.0,
    },
    "圆": {
        "style": "circle",
        "color": "#ffffff",
        "base_radius": 12,
        "max_radius": 85,
        "duration_sec": 0.65,
        "fps": 60,
        "particle_count": 0,
        "ring_width": 0,
        "particle_size": 0,
        "opacity": 0.6,
    },
    "粒子": {
        "style": "particle",
        "color": "#ff4fd8",
        "base_radius": 16,
        "max_radius": 120,
        "duration_sec": 0.8,
        "fps": 60,
        "particle_count": 24,
        "ring_width": 0,
        "particle_size": 3,
        "opacity": 1.0,
    },
}

STYLE_MAP_CN = {"ring": "圆环", "particle": "粒子", "circle": "圆"}
STYLE_MAP_EN = {"圆环": "ring", "粒子": "particle", "圆": "circle"}


def _parse_rgb(s: str):
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b)


class SettingsUI:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("点击特效设置")
        self.root.geometry("460x600")
        self.root.resizable(False, False)

        # Set application icon
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "favicon1.ico")
            
            # 1. For Windows Taskbar Icon (Important for separating from Python icon)
            # Try to set iconbitmap which is standard for Windows .ico
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

            # 2. Cross-platform runtime window icon
            img_icon = Image.open(icon_path)
            self.root.wm_iconphoto(True, ImageTk.PhotoImage(img_icon))
        except Exception as e:
            print(f"Warning: Failed to set window icon: {e}")

        # 1. Load settings or use defaults
        self.current_style_name = "圆环"
        self.configs = {}
        
        loaded = load_settings()
        if loaded:
            self.current_style_name, self.configs = loaded
        
        # Ensure all presets exist in configs (fill missing with defaults)
        for name, p_data in PRESETS.items():
            if name not in self.configs:
                # Convert dict to AppConfig
                # We need to handle default values that might be missing in PRESETS dict
                # But PRESETS dicts seem complete enough for now
                cfg_kwargs = p_data.copy()
                # Parse color if it is string
                if isinstance(cfg_kwargs["color"], str):
                    cfg_kwargs["color"] = _parse_rgb(cfg_kwargs["color"])
                
                # Fill missing fields with defaults from AppConfig if necessary
                # Here we assume PRESETS keys match AppConfig fields mostly
                
                # Create a temporary default config to get defaults
                # But simpler is to just construct it.
                # Let's ensure we have all required fields.
                # AppConfig requires: style, color, base_radius, max_radius, duration_sec, fps, particle_count, quit_hotkey, run_seconds
                if "quit_hotkey" not in cfg_kwargs: cfg_kwargs["quit_hotkey"] = "ctrl+shift+q"
                if "run_seconds" not in cfg_kwargs: cfg_kwargs["run_seconds"] = 0.0
                
                self.configs[name] = AppConfig(**cfg_kwargs)

        # 2. Init UI Variables with current config
        cur_cfg = self.configs.get(self.current_style_name, self.configs["圆环"])
        
        self.var_preset = tk.StringVar(value=self.current_style_name)
        self.var_style = tk.StringVar(value=STYLE_MAP_CN.get(cur_cfg.style, "圆环"))
        self.var_color = tk.StringVar(value="#{:02x}{:02x}{:02x}".format(*cur_cfg.color))
        self.var_base = tk.DoubleVar(value=float(cur_cfg.base_radius))
        self.var_max = tk.DoubleVar(value=float(cur_cfg.max_radius))
        self.var_duration = tk.DoubleVar(value=cur_cfg.duration_sec)
        self.var_fps = tk.DoubleVar(value=float(cur_cfg.fps))
        self.var_particles = tk.DoubleVar(value=float(cur_cfg.particle_count))
        
        # New vars
        self.var_ring_width = tk.DoubleVar(value=float(cur_cfg.ring_width))
        self.var_particle_size = tk.DoubleVar(value=float(cur_cfg.particle_size))
        self.var_opacity = tk.DoubleVar(value=cur_cfg.opacity)
        
        self.txt_base = tk.StringVar()
        self.txt_max = tk.StringVar()
        self.txt_duration = tk.StringVar()
        self.txt_fps = tk.StringVar()
        self.txt_particles = tk.StringVar()
        self.txt_ring_width = tk.StringVar()
        self.txt_particle_size = tk.StringVar()
        self.txt_opacity = tk.StringVar()

        # 3. Start App
        # Note: We pass the CURRENT config to the app
        self.app = ClickAnimatorApp(cur_cfg, root=self.root, with_ui=True, on_toggle_settings=self._toggle_visibility)
        self.app.start_background()

        self.row_widgets = {} # To store widget lists by row index or name
        
        self._build_ui()
        self._refresh_value_labels()
        self._update_visibility() # Initial visibility update
        
        # Ensure window is shown
        self.root.deiconify()
        
        self.root.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self.tray_icon = None

    def _minimize_to_tray(self) -> None:
        self._hide_window()
        if self.tray_icon is None:
            threading.Thread(target=self._run_tray, daemon=True).start()

    def _run_tray(self) -> None:
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon", "favicon1.ico")
        try:
            image = Image.open(image_path)
        except Exception as e:
            print(f"Failed to load icon: {e}")
            # Fallback to a simple colored block if icon missing
            image = Image.new('RGB', (64, 64), color = (73, 109, 137))

        menu = pystray.Menu(
            pystray.MenuItem("显示", self._show_from_tray, default=True),
            pystray.MenuItem("退出", self._quit_app)
        )

        self.tray_icon = pystray.Icon("CursorPilot", image, "CursorPilot", menu)
        self.tray_icon.run()

    def _show_from_tray(self, icon=None, item=None) -> None:
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
        # Must be called from main thread
        self.root.after(0, self._show_window)

    def _quit_app(self, icon=None, item=None) -> None:
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        
        # Schedule the actual shutdown on the main thread
        self.root.after(0, self._perform_shutdown)

    def _perform_shutdown(self) -> None:
        try:
            # Update current config one last time
            self.configs[self.current_style_name] = self._build_config(0.0)
            save_settings(self.current_style_name, self.configs)
        except Exception: pass
        
        try:
            self.app.shutdown()
        except: pass
        try:
            self.root.destroy()
        except: pass

    def _toggle_visibility(self) -> None:
        try:
            state = str(self.root.state())
        except Exception:
            return

        if state in {"withdrawn", "iconic"}:
            self._show_window()
        else:
            self._minimize_to_tray()

    def _hide_window(self) -> None:
        try:
            self.root.withdraw()
        except Exception:
            pass

    def _show_window(self) -> None:
        if self.tray_icon:
            icon = self.tray_icon
            self.tray_icon = None
            try:
                icon.stop()
            except: pass

        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Main container
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Settings group
        # Using a Frame with a label to simulate LabelFrame or just use CTkLabel
        title_label = ctk.CTkLabel(main_frame, text="特效参数配置", font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=(10, 5), anchor="w", padx=10)
        
        lf = ctk.CTkFrame(main_frame)
        lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Grid configuration for lf
        lf.columnconfigure(1, weight=1)

        row = 0

        # Helper to create slider with entry
        def create_slider_row(name, label, var, from_, to_, txt_var, row_idx):
            lbl = ctk.CTkLabel(lf, text=label)
            lbl.grid(row=row_idx, column=0, sticky="w", padx=(15, 5), pady=10)
            
            # CTkSlider passes value to command, but we can also rely on variable
            s = ctk.CTkSlider(lf, from_=from_, to=to_, variable=var, command=lambda _v: self._sync_config())
            s.grid(row=row_idx, column=1, sticky="we", padx=5, pady=10)
            
            e = ctk.CTkEntry(lf, textvariable=txt_var, width=60)
            e.grid(row=row_idx, column=2, sticky="e", padx=(5, 15), pady=10)
            
            def on_entry_change(event):
                try:
                    val = float(txt_var.get())
                    val = max(from_, min(to_, val))
                    var.set(val)
                    self._sync_config()
                except ValueError:
                    pass
            e.bind("<Return>", on_entry_change)
            e.bind("<FocusOut>", on_entry_change)
            
            self.row_widgets[name] = [lbl, s, e]

        # Preset
        ctk.CTkLabel(lf, text="预设：").grid(row=row, column=0, sticky="w", padx=(15, 5), pady=10)
        
        def on_preset_change(value):
            self.var_preset.set(value)
            self._apply_preset()

        cb = ctk.CTkComboBox(lf, values=list(PRESETS.keys()), variable=self.var_preset, command=on_preset_change)
        cb.grid(row=row, column=1, sticky="w", padx=5, pady=10)
        row += 1

        # Color
        ctk.CTkLabel(lf, text="颜色：").grid(row=row, column=0, sticky="w", padx=(15, 5), pady=10)
        
        self.btn_color = ctk.CTkButton(lf, text="选择颜色", width=100, command=self._pick_color, fg_color=self.var_color.get())
        self.btn_color.grid(row=row, column=1, sticky="w", padx=5, pady=10)
        row += 1
        
        create_slider_row("opacity", "透明度：", self.var_opacity, 0.1, 1.0, self.txt_opacity, row); row += 1
        create_slider_row("base_radius", "起始半径：", self.var_base, 0, 60, self.txt_base, row); row += 1
        create_slider_row("max_radius", "最大半径(范围)：", self.var_max, 10, 300, self.txt_max, row); row += 1
        create_slider_row("duration", "时长(反比速度)：", self.var_duration, 0.1, 3.0, self.txt_duration, row); row += 1
        create_slider_row("ring_width", "圆环粗细：", self.var_ring_width, 1, 20, self.txt_ring_width, row); row += 1
        create_slider_row("particle_size", "粒子大小：", self.var_particle_size, 1, 10, self.txt_particle_size, row); row += 1
        create_slider_row("particle_count", "粒子数量：", self.var_particles, 0, 100, self.txt_particles, row); row += 1
        create_slider_row("fps", "帧率：", self.var_fps, 30, 120, self.txt_fps, row); row += 1
        
        # Footer buttons
        btns_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btns_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkButton(btns_frame, text="最小化", command=self._minimize_to_tray, width=100).pack(side=tk.LEFT)
        ctk.CTkButton(btns_frame, text="退出", command=self._perform_shutdown, width=100, fg_color="red", hover_color="#8B0000").pack(side=tk.RIGHT)
        
        ctk.CTkLabel(main_frame, text="全局热键：Ctrl+Shift+S 显示/隐藏设置；Ctrl+Shift+Q 退出", 
                     text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=(0, 10))


    def _apply_preset(self) -> None:
        # Save current settings to current style config before switching
        old_style = self.current_style_name
        self.configs[old_style] = self._build_config(0.0)
        
        # Switch to new style
        new_style = self.var_preset.get()
        self.current_style_name = new_style
        
        # Load settings from memory
        p = self.configs.get(new_style, self.configs["圆环"])
        
        self.var_style.set(STYLE_MAP_CN.get(p.style, "圆环"))
        self.var_color.set("#{:02x}{:02x}{:02x}".format(*p.color))
        self.var_base.set(float(p.base_radius))
        self.var_max.set(float(p.max_radius))
        self.var_duration.set(p.duration_sec)
        self.var_fps.set(float(p.fps))
        self.var_particles.set(float(p.particle_count))
        self.var_ring_width.set(float(p.ring_width))
        self.var_particle_size.set(float(p.particle_size))
        self.var_opacity.set(float(p.opacity))
        
        self.btn_color.configure(fg_color=self.var_color.get())
        self._sync_config()

    def _pick_color(self) -> None:
        # CustomTkinter doesn't have a color chooser, use tk's
        rgb, hexv = colorchooser.askcolor(color=self.var_color.get())
        if not hexv:
            return
        self.var_color.set(hexv)
        self.btn_color.configure(fg_color=hexv)
        self._sync_config()

    def _build_config(self, run_seconds: float) -> AppConfig:
        return AppConfig(
            style=STYLE_MAP_EN.get(self.var_style.get(), "ring"),
            color=_parse_rgb(self.var_color.get()),
            base_radius=max(0, int(float(self.var_base.get()))),
            max_radius=max(10, int(float(self.var_max.get()))),
            duration_sec=float(self.var_duration.get()),
            fps=max(10, int(float(self.var_fps.get()))),
            particle_count=max(0, int(float(self.var_particles.get()))),
            ring_width=max(1, int(float(self.var_ring_width.get()))),
            particle_size=max(1, int(float(self.var_particle_size.get()))),
            opacity=max(0.0, min(1.0, float(self.var_opacity.get()))),
            quit_hotkey="ctrl+shift+q",
            run_seconds=run_seconds,
        )

    def _sync_config(self) -> None:
        self._refresh_value_labels()
        self._update_visibility()
        self.app.update_config(self._build_config(run_seconds=0.0))

    def _refresh_value_labels(self) -> None:
        try:
            self.txt_base.set(str(int(float(self.var_base.get()))))
            self.txt_max.set(str(int(float(self.var_max.get()))))
            self.txt_duration.set(f"{float(self.var_duration.get()):.2f}")
            self.txt_fps.set(str(int(float(self.var_fps.get()))))
            self.txt_particles.set(str(int(float(self.var_particles.get()))))
            self.txt_ring_width.set(str(int(float(self.var_ring_width.get()))))
            self.txt_particle_size.set(str(int(float(self.var_particle_size.get()))))
            self.txt_opacity.set(f"{float(self.var_opacity.get()):.1f}")
        except Exception:
            return

    def _update_visibility(self):
        style_cn = self.var_style.get()
        style = STYLE_MAP_EN.get(style_cn, "ring")
        
        def show(name):
            if name in self.row_widgets:
                for w in self.row_widgets[name]: w.grid()
        
        def hide(name):
            if name in self.row_widgets:
                for w in self.row_widgets[name]: w.grid_remove()

        # Always show: opacity, base_radius, max_radius, duration, fps
        
        if style == "ring":
            show("ring_width")
            hide("particle_size")
            hide("particle_count")
            show("base_radius")
        elif style == "particle":
            hide("ring_width")
            show("particle_size")
            show("particle_count")
            hide("base_radius") # Particles don't use base_radius
        elif style == "circle":
            hide("ring_width")
            hide("particle_size")
            hide("particle_count")
            show("base_radius")

def main() -> int:
    # Windows Taskbar Icon Fix
    try:
        # 任意唯一字符串
        myappid = 'cursorpilot.click.animator.v1' 
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    setup_dpi()
    # Use CTk instead of Tk
    app = ctk.CTk()
    # Initially hide if needed, but we rely on SettingsUI to manage logic
    # Actually ClickAnimatorApp will hide it, then SettingsUI will show it.
    
    SettingsUI(app)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
