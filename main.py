"""main.py

可编辑的设置 UI：在不影响后台运行的前提下，提供点击特效的样式/颜色/大小/时长等配置。

依赖：
  pip install pynput

运行：
  python main.py

退出：
  点击窗口里的 Exit，或全局热键 Ctrl+Shift+Q。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk

from click_animator import AppConfig, ClickAnimatorApp, setup_dpi


PRESETS = {
    "cyan_ring": {
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
    "white_circle": {
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
    "pink_particle": {
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


def _parse_rgb(s: str):
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b)


class SettingsUI:
    def __init__(self, win: tk.Toplevel, app_root: tk.Tk) -> None:
        self.win = win
        self.app_root = app_root
        self.win.title("点击特效设置")
        self.win.geometry("450x550")
        self.win.resizable(False, False)

        self.var_preset = tk.StringVar(value="cyan_ring")
        self.var_style = tk.StringVar(value=PRESETS["cyan_ring"]["style"])
        self.var_color = tk.StringVar(value=PRESETS["cyan_ring"]["color"])
        self.var_base = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["base_radius"]))
        self.var_max = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["max_radius"]))
        self.var_duration = tk.DoubleVar(value=PRESETS["cyan_ring"]["duration_sec"])
        self.var_fps = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["fps"]))
        self.var_particles = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["particle_count"]))
        
        # New vars
        self.var_ring_width = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["ring_width"]))
        self.var_particle_size = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["particle_size"]))
        self.var_opacity = tk.DoubleVar(value=float(PRESETS["cyan_ring"]["opacity"]))

        self.txt_base = tk.StringVar()
        self.txt_max = tk.StringVar()
        self.txt_duration = tk.StringVar()
        self.txt_fps = tk.StringVar()
        self.txt_particles = tk.StringVar()
        self.txt_ring_width = tk.StringVar()
        self.txt_particle_size = tk.StringVar()
        self.txt_opacity = tk.StringVar()

        cfg = self._build_config(run_seconds=0.0)
        self.app = ClickAnimatorApp(cfg, root=self.app_root, with_ui=False, on_toggle_settings=self._toggle_visibility)
        self.app.start_background()

        self.row_widgets = {} # To store widget lists by row index or name
        
        self._build_ui()
        self._refresh_value_labels()
        self._update_visibility() # Initial visibility update
        self.win.protocol("WM_DELETE_WINDOW", self._on_exit)

    def _toggle_visibility(self) -> None:
        try:
            state = str(self.win.state())
        except Exception:
            return

        if state in {"withdrawn", "iconic"}:
            self._show_window()
        else:
            self._hide_window()

    def _hide_window(self) -> None:
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _show_window(self) -> None:
        try:
            self.win.deiconify()
            self.win.lift()
        except Exception:
            pass

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        lf = ttk.LabelFrame(frm, text="点击特效", padding=10)
        lf.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Helper to create scale with entry
        def create_slider_row(name, label, var, from_, to_, txt_var, row_idx):
            lbl = ttk.Label(lf, text=label)
            lbl.grid(row=row_idx, column=0, sticky="w", pady=(10, 0))
            s = ttk.Scale(lf, from_=from_, to=to_, variable=var, command=lambda _v: self._sync_config())
            s.grid(row=row_idx, column=1, sticky="we", padx=8, pady=(10, 0))
            
            e = ttk.Entry(lf, textvariable=txt_var, width=6)
            e.grid(row=row_idx, column=2, sticky="e", pady=(10, 0))
            
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

        ttk.Label(lf, text="预设：").grid(row=row, column=0, sticky="w")
        cb = ttk.Combobox(lf, textvariable=self.var_preset, values=list(PRESETS.keys()), state="readonly", width=16)
        cb.grid(row=row, column=1, sticky="w", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        row += 1

        ttk.Label(lf, text="样式：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        cb_style = ttk.Combobox(lf, textvariable=self.var_style, values=["ring", "particle", "circle"], state="readonly", width=16)
        cb_style.grid(row=row, column=1, sticky="w", padx=8, pady=(10, 0))
        cb_style.bind("<<ComboboxSelected>>", lambda _e: self._sync_config())
        row += 1

        ttk.Label(lf, text="颜色：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        btn_color = tk.Button(lf, text="选择…", width=10, command=self._pick_color, bg=self.var_color.get())
        btn_color.grid(row=row, column=1, sticky="w", padx=8, pady=(10, 0))
        self._btn_color = btn_color
        row += 1
        
        create_slider_row("opacity", "透明度：", self.var_opacity, 0.1, 1.0, self.txt_opacity, row); row += 1
        create_slider_row("base_radius", "起始半径：", self.var_base, 0, 60, self.txt_base, row); row += 1
        create_slider_row("max_radius", "最大半径(范围)：", self.var_max, 10, 300, self.txt_max, row); row += 1
        create_slider_row("duration", "时长(反比速度)：", self.var_duration, 0.1, 3.0, self.txt_duration, row); row += 1
        create_slider_row("ring_width", "圆环粗细：", self.var_ring_width, 1, 20, self.txt_ring_width, row); row += 1
        create_slider_row("particle_size", "粒子大小：", self.var_particle_size, 1, 10, self.txt_particle_size, row); row += 1
        create_slider_row("particle_count", "粒子数量：", self.var_particles, 0, 100, self.txt_particles, row); row += 1
        create_slider_row("fps", "帧率：", self.var_fps, 30, 120, self.txt_fps, row); row += 1
        
        lf.columnconfigure(1, weight=1)

        sep = ttk.Separator(frm, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=10)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="最小化", command=self._hide_window).pack(side=tk.LEFT)
        ttk.Button(btns, text="退出", command=self._on_exit).pack(side=tk.RIGHT)
        ttk.Label(frm, text="全局热键：Ctrl+Shift+S 显示/隐藏设置；Ctrl+Shift+Q 退出", foreground="gray").pack(pady=(8, 0))


    def _apply_preset(self) -> None:
        p = PRESETS.get(self.var_preset.get(), PRESETS["cyan_ring"])
        self.var_style.set(p["style"])
        self.var_color.set(p["color"])
        self.var_base.set(float(p["base_radius"]))
        self.var_max.set(float(p["max_radius"]))
        self.var_duration.set(p["duration_sec"])
        self.var_fps.set(float(p["fps"]))
        self.var_particles.set(float(p["particle_count"]))
        self.var_ring_width.set(float(p.get("ring_width", 3)))
        self.var_particle_size.set(float(p.get("particle_size", 2)))
        self.var_opacity.set(float(p.get("opacity", 1.0)))
        
        self._btn_color.configure(bg=self.var_color.get())
        self._sync_config()

    def _pick_color(self) -> None:
        rgb, hexv = colorchooser.askcolor(color=self.var_color.get())
        if not hexv:
            return
        self.var_color.set(hexv)
        self._btn_color.configure(bg=hexv)
        self._sync_config()

    def _build_config(self, run_seconds: float) -> AppConfig:
        return AppConfig(
            style=self.var_style.get(),
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
        style = self.var_style.get()
        
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

    def _on_exit(self) -> None:
        try:
            self.app.shutdown()
        except: pass
        try:
            self.win.destroy()
        except: pass
        try:
            self.app_root.destroy()
        except: pass

def main() -> int:
    setup_dpi()
    app_root = tk.Tk()
    try:
        app_root.withdraw()
    except Exception:
        pass
    win = tk.Toplevel(app_root)
    SettingsUI(win, app_root)
    app_root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
