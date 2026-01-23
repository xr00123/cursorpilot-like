import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
import multiprocessing
import sys
import os

# Import the overlay runner
from click_fx import run_overlay_process, DEFAULT_CONFIG

class SettingsUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ClickFX 设置")
        self.root.geometry("400x550")
        self.root.resizable(False, False)
        
        # Data
        self.overlay_process = None
        self.command_queue = multiprocessing.Queue()
        
        # State variables
        self.var_highlight_enabled = tk.BooleanVar(value=DEFAULT_CONFIG["highlight_enabled"])
        self.var_highlight_color = DEFAULT_CONFIG["highlight_color"]
        self.var_highlight_radius = tk.IntVar(value=DEFAULT_CONFIG["highlight_radius"])
        self.var_highlight_alpha = tk.IntVar(value=DEFAULT_CONFIG["highlight_alpha"])
        
        self.var_click_enabled = tk.BooleanVar(value=DEFAULT_CONFIG["click_enabled"])
        self.var_click_style = tk.StringVar(value=DEFAULT_CONFIG["style"])
        self.var_click_color = DEFAULT_CONFIG["color"]
        self.var_click_radius = tk.IntVar(value=DEFAULT_CONFIG["base_radius"])
        
        # Build UI
        self._build_ui()
        
        # Start Overlay automatically
        self._start_overlay()
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Section 1: Mouse Tracking (Highlight) ---
        lf_highlight = ttk.LabelFrame(main_frame, text="鼠标跟随高亮", padding="10")
        lf_highlight.pack(fill=tk.X, pady=5)
        
        # Enable
        chk_hl = ttk.Checkbutton(lf_highlight, text="启用高亮", 
                                 variable=self.var_highlight_enabled, 
                                 command=self._update_config)
        chk_hl.pack(anchor="w")
        
        # Color
        frm_hl_col = ttk.Frame(lf_highlight)
        frm_hl_col.pack(fill=tk.X, pady=5)
        ttk.Label(frm_hl_col, text="颜色：").pack(side=tk.LEFT)
        self.btn_hl_color = tk.Button(frm_hl_col, text="   ", bg=self._rgb_to_hex(self.var_highlight_color),
                                      command=self._pick_highlight_color, width=4)
        self.btn_hl_color.pack(side=tk.LEFT, padx=5)
        
        # Radius
        ttk.Label(lf_highlight, text="半径（大小）：").pack(anchor="w", pady=(5,0))
        scl_hl_radius = ttk.Scale(lf_highlight, from_=10, to=100, 
                                  variable=self.var_highlight_radius, 
                                  command=lambda v: self._update_config())
        scl_hl_radius.pack(fill=tk.X)
        
        # Alpha
        ttk.Label(lf_highlight, text="不透明度（透明）：").pack(anchor="w", pady=(5,0))
        scl_hl_alpha = ttk.Scale(lf_highlight, from_=10, to=255, 
                                 variable=self.var_highlight_alpha, 
                                 command=lambda v: self._update_config())
        scl_hl_alpha.pack(fill=tk.X)

        # --- Section 2: Click Animation ---
        lf_click = ttk.LabelFrame(main_frame, text="点击动画", padding="10")
        lf_click.pack(fill=tk.X, pady=10)
        
        # Enable
        chk_clk = ttk.Checkbutton(lf_click, text="启用点击特效", 
                                  variable=self.var_click_enabled, 
                                  command=self._update_config)
        chk_clk.pack(anchor="w")
        
        # Style
        frm_style = ttk.Frame(lf_click)
        frm_style.pack(fill=tk.X, pady=5)
        ttk.Label(frm_style, text="样式：").pack(side=tk.LEFT)
        style_cb = ttk.Combobox(frm_style, textvariable=self.var_click_style, 
                                values=["ripple", "wave", "dust"], state="readonly", width=10)
        style_cb.pack(side=tk.LEFT, padx=5)
        style_cb.bind("<<ComboboxSelected>>", lambda e: self._update_config())
        
        # Color
        frm_clk_col = ttk.Frame(lf_click)
        frm_clk_col.pack(fill=tk.X, pady=5)
        ttk.Label(frm_clk_col, text="颜色：").pack(side=tk.LEFT)
        self.btn_clk_color = tk.Button(frm_clk_col, text="   ", bg=self._rgb_to_hex(self.var_click_color),
                                       command=self._pick_click_color, width=4)
        self.btn_clk_color.pack(side=tk.LEFT, padx=5)
        
        # Radius
        ttk.Label(lf_click, text="初始大小：").pack(anchor="w", pady=(5,0))
        scl_clk_radius = ttk.Scale(lf_click, from_=10, to=100, 
                                   variable=self.var_click_radius, 
                                   command=lambda v: self._update_config())
        scl_clk_radius.pack(fill=tk.X)

        # --- Status / Footer ---
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        btn_restart = ttk.Button(main_frame, text="重启叠层服务", command=self._restart_overlay)
        btn_restart.pack(pady=5)
        
        ttk.Label(main_frame, text="关闭窗口即可退出", foreground="gray").pack()

    def _start_overlay(self):
        if self.overlay_process and self.overlay_process.is_alive():
            return
        
        # Send initial config immediately after start? 
        # Actually better to pass config in constructor, but our run_overlay_process
        # uses default then listens. So we send config right after.
        
        self.overlay_process = multiprocessing.Process(
            target=run_overlay_process, 
            args=(self.command_queue,),
            daemon=True
        )
        self.overlay_process.start()
        # Sync current UI state to overlay
        self.root.after(500, self._update_config)

    def _restart_overlay(self):
        if self.overlay_process:
            self.overlay_process.terminate()
            self.overlay_process.join()
        self._start_overlay()

    def _update_config(self):
        """Send current configuration to overlay process"""
        cfg = {
            "highlight_enabled": self.var_highlight_enabled.get(),
            "highlight_color": self.var_highlight_color,
            "highlight_radius": self.var_highlight_radius.get(),
            "highlight_alpha": self.var_highlight_alpha.get(),
            
            "click_enabled": self.var_click_enabled.get(),
            "style": self.var_click_style.get(),
            "color": self.var_click_color,
            "base_radius": self.var_click_radius.get(),
        }
        self.command_queue.put({"type": "update_config", "data": cfg})

    def _pick_highlight_color(self):
        color = colorchooser.askcolor(color=self._rgb_to_hex(self.var_highlight_color))[0]
        if color:
            self.var_highlight_color = tuple(map(int, color))
            self.btn_hl_color.config(bg=self._rgb_to_hex(self.var_highlight_color))
            self._update_config()

    def _pick_click_color(self):
        color = colorchooser.askcolor(color=self._rgb_to_hex(self.var_click_color))[0]
        if color:
            self.var_click_color = tuple(map(int, color))
            self.btn_clk_color.config(bg=self._rgb_to_hex(self.var_click_color))
            self._update_config()

    def _rgb_to_hex(self, rgb):
        return "#%02x%02x%02x" % rgb

    def _on_close(self):
        if self.overlay_process:
            self.command_queue.put({"type": "quit"})
            self.overlay_process.terminate()
        self.root.destroy()

if __name__ == "__main__":
    # Mac multiprocessing fix
    multiprocessing.set_start_method("spawn")
    
    root = tk.Tk()
    app = SettingsUI(root)
    root.mainloop()
