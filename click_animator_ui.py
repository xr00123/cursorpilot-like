"""click_animator_ui.py

可编辑的设置 UI：在不影响后台运行的前提下，提供点击特效的样式/颜色/大小/时长等配置。

依赖：
  pip install pynput

运行：
  python click_animator_ui.py

退出：
  点击窗口里的 Exit，或全局热键 Ctrl+Shift+Q。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, ttk

from click_animator import AppConfig, ClickAnimatorApp


PRESETS = {
    "cyan_ring": {
        "style": "ring",
        "color": "#00c8ff",
        "base_radius": 18,
        "max_radius": 110,
        "duration_sec": 0.75,
        "fps": 60,
        "particle_count": 18,
    },
    "white_ripple": {
        "style": "ripple",
        "color": "#ffffff",
        "base_radius": 12,
        "max_radius": 85,
        "duration_sec": 0.65,
        "fps": 60,
        "particle_count": 0,
    },
    "pink_burst": {
        "style": "burst",
        "color": "#ff4fd8",
        "base_radius": 16,
        "max_radius": 120,
        "duration_sec": 0.8,
        "fps": 60,
        "particle_count": 24,
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
        self.win.geometry("420x460")
        self.win.resizable(False, False)

        self.var_preset = tk.StringVar(value="cyan_ring")
        self.var_style = tk.StringVar(value=PRESETS["cyan_ring"]["style"])
        self.var_color = tk.StringVar(value=PRESETS["cyan_ring"]["color"])
        self.var_base = tk.IntVar(value=PRESETS["cyan_ring"]["base_radius"])
        self.var_max = tk.IntVar(value=PRESETS["cyan_ring"]["max_radius"])
        self.var_duration = tk.DoubleVar(value=PRESETS["cyan_ring"]["duration_sec"])
        self.var_fps = tk.IntVar(value=PRESETS["cyan_ring"]["fps"])
        self.var_particles = tk.IntVar(value=PRESETS["cyan_ring"]["particle_count"])

        cfg = self._build_config(run_seconds=0.0)
        self.app = ClickAnimatorApp(cfg, root=self.app_root, with_ui=False)
        self.app.start_background()

        self._build_ui()
        self.win.protocol("WM_DELETE_WINDOW", self._on_exit)

    def _build_ui(self) -> None:
        frm = ttk.Frame(self.win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        lf = ttk.LabelFrame(frm, text="点击特效", padding=10)
        lf.pack(fill=tk.BOTH, expand=True)

        row = 0

        ttk.Label(lf, text="预设：").grid(row=row, column=0, sticky="w")
        cb = ttk.Combobox(lf, textvariable=self.var_preset, values=list(PRESETS.keys()), state="readonly", width=16)
        cb.grid(row=row, column=1, sticky="w", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        row += 1

        ttk.Label(lf, text="样式：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        cb_style = ttk.Combobox(lf, textvariable=self.var_style, values=["ripple", "ring", "burst"], state="readonly", width=16)
        cb_style.grid(row=row, column=1, sticky="w", padx=8, pady=(10, 0))
        cb_style.bind("<<ComboboxSelected>>", lambda _e: self._sync_config())
        row += 1

        ttk.Label(lf, text="颜色：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        btn_color = tk.Button(lf, text="选择…", width=10, command=self._pick_color, bg=self.var_color.get())
        btn_color.grid(row=row, column=1, sticky="w", padx=8, pady=(10, 0))
        self._btn_color = btn_color
        row += 1

        ttk.Label(lf, text="起始半径：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        s_base = ttk.Scale(lf, from_=4, to=60, variable=self.var_base, command=lambda _v: self._sync_config())
        s_base.grid(row=row, column=1, sticky="we", padx=8, pady=(10, 0))
        row += 1

        ttk.Label(lf, text="最大半径：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        s_max = ttk.Scale(lf, from_=30, to=220, variable=self.var_max, command=lambda _v: self._sync_config())
        s_max.grid(row=row, column=1, sticky="we", padx=8, pady=(10, 0))
        row += 1

        ttk.Label(lf, text="时长（秒）：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        s_dur = ttk.Scale(lf, from_=0.5, to=1.0, variable=self.var_duration, command=lambda _v: self._sync_config())
        s_dur.grid(row=row, column=1, sticky="we", padx=8, pady=(10, 0))
        row += 1

        ttk.Label(lf, text="帧率（FPS）：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        s_fps = ttk.Scale(lf, from_=30, to=120, variable=self.var_fps, command=lambda _v: self._sync_config())
        s_fps.grid(row=row, column=1, sticky="we", padx=8, pady=(10, 0))
        row += 1

        ttk.Label(lf, text="粒子数量：").grid(row=row, column=0, sticky="w", pady=(10, 0))
        s_pt = ttk.Scale(lf, from_=0, to=60, variable=self.var_particles, command=lambda _v: self._sync_config())
        s_pt.grid(row=row, column=1, sticky="we", padx=8, pady=(10, 0))
        row += 1

        lf.columnconfigure(1, weight=1)

        sep = ttk.Separator(frm, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=10)

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="最小化", command=self.win.iconify).pack(side=tk.LEFT)
        ttk.Button(btns, text="退出", command=self._on_exit).pack(side=tk.RIGHT)
        ttk.Label(frm, text="全局退出热键：Ctrl+Shift+Q", foreground="gray").pack(pady=(8, 0))

    def _apply_preset(self) -> None:
        p = PRESETS.get(self.var_preset.get(), PRESETS["cyan_ring"])
        self.var_style.set(p["style"])
        self.var_color.set(p["color"])
        self.var_base.set(p["base_radius"])
        self.var_max.set(p["max_radius"])
        self.var_duration.set(p["duration_sec"])
        self.var_fps.set(p["fps"])
        self.var_particles.set(p["particle_count"])
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
            base_radius=max(1, int(float(self.var_base.get()))),
            max_radius=max(10, int(float(self.var_max.get()))),
            duration_sec=float(self.var_duration.get()),
            fps=max(10, int(float(self.var_fps.get()))),
            particle_count=max(0, int(float(self.var_particles.get()))),
            quit_hotkey="ctrl+shift+q",
            run_seconds=run_seconds,
        )

    def _sync_config(self) -> None:
        self.app.update_config(self._build_config(run_seconds=0.0))

    def _on_exit(self) -> None:
        try:
            self.app.shutdown()
        finally:
            try:
                self.win.destroy()
            except Exception:
                pass
            try:
                self.app_root.destroy()
            except Exception:
                pass


def main() -> int:
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
