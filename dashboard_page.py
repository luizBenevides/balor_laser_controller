import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
_ICON_PATH = os.path.normpath(os.path.join(_ASSETS_DIR, "dashboard.ico"))
_APP_USER_MODEL_ID = "delta.solutions.dashboard"

WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1200

COLOR_BG_TOP = "#1a1a26"
COLOR_BG_BOTTOM = "#06060c"
COLOR_PANEL = "#22222e"
COLOR_PANEL_ALT = "#2a2a36"
COLOR_TEXT = "#f2f2f7"
COLOR_TEXT_MUTED = "#6f6f7f"
COLOR_SCROLL_THUMB = "#4a4a58"
COLOR_SCROLL_THUMB_HOVER = "#6f6f7f"

FONT_LABEL = ("Segoe UI", 10)
FONT_SECTION = ("Segoe UI Semibold", 11, "bold")
FONT_CARD_TITLE = ("Segoe UI Semibold", 22, "bold")
FONT_NAV = ("Segoe UI Semibold", 14, "bold")
FONT_NUMBER = ("Segoe UI", 92, "bold")
FONT_SUB = ("Segoe UI", 13)

CONTENT_PADX = 36

CARD_THEMES = (
    {"label": "APROVADO", "accent": "#5cdb95", "panel": "#1e2a24"},
    {"label": "REPROVADO", "accent": "#e85d5d", "panel": "#2a1e1e"},
    {"label": "TOTAL", "accent": "#7eb8ff", "panel": "#1e2430"},
)


class DashboardPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLOR_BG_BOTTOM, highlightthickness=0)
        self.app = app
        self.records = []
        self.camera_connected = False
        self.var_aprovado = tk.StringVar(value="0")
        self.var_reprovado = tk.StringVar(value="0")
        self.var_total = tk.StringVar(value="0")
        self.var_pct_aprovado = tk.StringVar(value="0%")
        self.var_pct_reprovado = tk.StringVar(value="0%")
        self.var_pct_total = tk.StringVar(value="0%")
        self._configure_window_size()
        self._bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_canvas.bind("<Configure>", self._paint_page_gradient)
        self.build_ui()
        self.refresh_status_loop()

    @staticmethod
    def _hex_to_rgb(color):
        color = color.lstrip("#")
        return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _rgb_to_hex(rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _draw_vertical_gradient(self, canvas, width, height, top_color, bottom_color, tag="gradient"):
        canvas.delete(tag)
        if width < 2 or height < 2:
            return

        r1, g1, b1 = self._hex_to_rgb(top_color)
        r2, g2, b2 = self._hex_to_rgb(bottom_color)
        steps = max(height, 1)

        for i in range(steps):
            ratio = i / steps
            rgb = (
                int(r1 + (r2 - r1) * ratio),
                int(g1 + (g2 - g1) * ratio),
                int(b1 + (b2 - b1) * ratio),
            )
            canvas.create_line(0, i, width, i, fill=self._rgb_to_hex(rgb), tags=tag)

    def _paint_page_gradient(self, event=None):
        width = self._bg_canvas.winfo_width()
        height = self._bg_canvas.winfo_height()
        self._draw_vertical_gradient(self._bg_canvas, width, height, COLOR_BG_TOP, COLOR_BG_BOTTOM)
        self._bg_canvas.tag_lower("gradient")

    @staticmethod
    def _set_window_icon(root):
        if not os.path.isfile(_ICON_PATH):
            return

        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_USER_MODEL_ID)
            except Exception:
                pass

            root.iconbitmap(default=_ICON_PATH)
            return

        try:
            icon = tk.PhotoImage(file=_ICON_PATH)
            root.iconphoto(True, icon)
            root._dashboard_icon = icon
        except tk.TclError:
            pass

    def _configure_window_size(self):
        root = self.winfo_toplevel()
        root.title(getattr(self.app, "window_title", "Dashboard"))
        root.configure(bg=COLOR_BG_BOTTOM)
        self._set_window_icon(root)
        root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _nav_button(self, parent, text, command):
        btn = tk.Button(
            parent,
            text=text,
            font=FONT_NAV,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_MUTED,
            activebackground=COLOR_PANEL_ALT,
            activeforeground=COLOR_TEXT,
            relief="flat",
            bd=0,
            padx=32,
            pady=14,
            cursor="hand2",
            command=command,
        )
        btn.pack(side="left", padx=6)
        btn.bind("<Enter>", lambda _e, b=btn: b.config(bg=COLOR_PANEL_ALT, fg=COLOR_TEXT))
        btn.bind("<Leave>", lambda _e, b=btn: b.config(bg=COLOR_PANEL, fg=COLOR_TEXT_MUTED))
        return btn

    def _build_nav(self, parent):
        nav = tk.Frame(parent, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        nav.pack(fill="x", padx=CONTENT_PADX, pady=(12, 0))

        bar = tk.Frame(nav, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        bar.pack(fill="x")

        self._nav_button(bar, "ROTINA AUTOMÁTICA", self.app.show_auto_page)
        self._nav_button(bar, "PAINEL MANUAL", self.app.show_manual_page)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Dashboard.Treeview", font=FONT_SUB, rowheight=38, background=COLOR_PANEL_ALT, fieldbackground=COLOR_PANEL_ALT, foreground=COLOR_TEXT, borderwidth=0)
        style.configure("Dashboard.Treeview.Heading", font=FONT_SECTION, background=COLOR_PANEL, foreground=COLOR_TEXT_MUTED, borderwidth=0, relief="flat")
        style.layout("Dashboard.Treeview", [("Dashboard.Treeview.treearea", {"sticky": "nswe"})])
        style.map("Dashboard.Treeview", background=[("selected", "#35354a")], foreground=[("selected", "white")])
        style.configure(
            "Dashboard.Vertical.TScrollbar",
            troughcolor=COLOR_PANEL_ALT,
            background=COLOR_SCROLL_THUMB,
            darkcolor=COLOR_PANEL_ALT,
            lightcolor=COLOR_PANEL_ALT,
            bordercolor=COLOR_PANEL_ALT,
            arrowcolor=COLOR_PANEL_ALT,
            relief="flat",
            gripcount=0,
            width=6,
        )
        style.map(
            "Dashboard.Vertical.TScrollbar",
            background=[("active", COLOR_SCROLL_THUMB_HOVER), ("pressed", COLOR_TEXT_MUTED)],
        )
        style.layout(
            "Dashboard.Vertical.TScrollbar",
            [("Vertical.Scrollbar.trough", {"children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})], "sticky": "ns"})],
        )

        content = tk.Frame(self, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        content.pack(fill="both", expand=True)

        main = tk.Frame(content, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        main.pack(fill="both", expand=True)

        self._build_nav(main)

        summary_shell = tk.Frame(main, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        summary_shell.pack(fill="x", padx=CONTENT_PADX, pady=10)

        summary_row = tk.Frame(summary_shell, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        summary_row.pack(fill="x")
        for col in range(3):
            summary_row.columnconfigure(col, weight=1)
        self._summary_card(summary_row, 0, CARD_THEMES[0], self.var_aprovado, "peças aprovadas", self.var_pct_aprovado)
        self._summary_card(summary_row, 1, CARD_THEMES[1], self.var_reprovado, "peças reprovadas", self.var_pct_reprovado)
        self._summary_card(summary_row, 2, CARD_THEMES[2], self.var_total, "peças analisadas", self.var_pct_total)

        table_shell = tk.Frame(main, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        table_shell.pack(fill="both", expand=True, padx=CONTENT_PADX, pady=10)
        table_panel = tk.Frame(table_shell, bg=COLOR_PANEL, highlightthickness=0, bd=0, padx=34, pady=28)
        table_panel.pack(fill="both", expand=True)

        tk.Label(
            table_panel,
            text="SERIAIS GRAVADOS",
            font=FONT_SECTION,
            bg=COLOR_PANEL,
            fg=COLOR_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(0, 14))

        table_inner = tk.Frame(table_panel, bg=COLOR_PANEL_ALT, highlightthickness=0, bd=0)
        table_inner.pack(fill="both", expand=True)

        columns = ("hora", "serial", "frontal", "traseira", "inspecao")
        self.tree = ttk.Treeview(table_inner, columns=columns, show="headings", style="Dashboard.Treeview")
        self.tree.heading("hora", text="Data/Hora")
        self.tree.heading("serial", text="Serial")
        self.tree.heading("frontal", text="Frontal")
        self.tree.heading("traseira", text="Traseira")
        self.tree.heading("inspecao", text="Inspeção")
        self.tree.column("hora", width=180, anchor="center")
        self.tree.column("serial", width=220, anchor="center")
        self.tree.column("frontal", width=140, anchor="center")
        self.tree.column("traseira", width=140, anchor="center")
        self.tree.column("inspecao", width=160, anchor="center")
        self._tree_scroll = ttk.Scrollbar(
            table_inner,
            orient="vertical",
            style="Dashboard.Vertical.TScrollbar",
            command=self.tree.yview,
        )
        self.tree.configure(yscrollcommand=self._on_tree_yscroll)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Configure>", self._sync_tree_scrollbar, add="+")
        table_inner.bind("<Configure>", self._sync_tree_scrollbar, add="+")

        self._build_footer(content)

        for child in self.winfo_children():
            if child is not self._bg_canvas:
                child.lift()
        self._bg_canvas.tk.call("lower", self._bg_canvas._w)

    def _on_tree_yscroll(self, first, last):
        needs_scroll = not (float(first) <= 0.0 and float(last) >= 1.0)
        if needs_scroll:
            if not self._tree_scroll.winfo_ismapped():
                self._tree_scroll.pack(side="right", fill="y", padx=(6, 0))
        elif self._tree_scroll.winfo_ismapped():
            self._tree_scroll.pack_forget()
        self._tree_scroll.set(first, last)

    def _sync_tree_scrollbar(self, _event=None):
        self.tree.update_idletasks()
        self._on_tree_yscroll(*self.tree.yview())

    def _build_footer(self, parent):
        footer_shell = tk.Frame(parent, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        footer_shell.pack(side="bottom", fill="x", padx=CONTENT_PADX, pady=(0, 20))

        footer = tk.Frame(footer_shell, bg=COLOR_PANEL, highlightthickness=0, bd=0, padx=36, pady=16)
        footer.pack(fill="x")
        for col in range(3):
            footer.columnconfigure(col, weight=1)

        self.led_camera = self._status_panel(footer, 0, "CÂMERA")
        self.led_clp = self._status_panel(footer, 1, "CLP")
        self.led_laser = self._status_panel(footer, 2, "LASER")

    def _status_panel(self, parent, col, label):
        panel = tk.Frame(parent, bg=COLOR_PANEL, highlightthickness=0, bd=0)
        panel.grid(row=0, column=col, sticky="nsew", padx=24)

        row = tk.Frame(panel, bg=COLOR_PANEL, highlightthickness=0, bd=0)
        row.pack(anchor="center")

        tk.Label(row, text=label, font=FONT_SECTION, bg=COLOR_PANEL, fg=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 14))

        canvas = tk.Canvas(row, width=18, height=18, highlightthickness=0, bg=COLOR_PANEL)
        dot = canvas.create_oval(2, 2, 16, 16, fill="#e85d5d", outline="")
        canvas.pack(side="left", padx=(0, 10))

        value = tk.Label(row, text="Desconectado", font=("Segoe UI", 15), bg=COLOR_PANEL, fg="#e85d5d")
        value.pack(side="left")

        return {"canvas": canvas, "dot": dot, "value": value}

    def _summary_card(self, parent, col, theme, number_var, subtitle, pct_var):
        gap = 8
        padx = (0, gap) if col < 2 else (0, 0)

        shell = tk.Frame(parent, bg=COLOR_BG_BOTTOM, highlightthickness=0, bd=0)
        shell.grid(row=0, column=col, sticky="nsew", padx=padx, pady=0)

        panel_bg = theme["panel"]
        panel = tk.Frame(shell, bg=panel_bg, highlightthickness=0, bd=0, padx=28, pady=28)
        panel.pack(fill="both", expand=True)

        tk.Label(
            panel,
            text=theme["label"],
            font=FONT_CARD_TITLE,
            bg=panel_bg,
            fg=COLOR_TEXT,
            anchor="center",
        ).pack(fill="x", pady=(0, 8))

        number_font = FONT_NUMBER
        try:
            if "Segoe UI" not in tkfont.families(self):
                number_font = ("Arial", 84, "bold")
        except tk.TclError:
            number_font = ("Arial", 84, "bold")

        tk.Label(
            panel,
            textvariable=number_var,
            font=number_font,
            bg=panel_bg,
            fg=theme["accent"],
            anchor="center",
        ).pack(fill="x", pady=12)

        tk.Label(
            panel,
            text=subtitle,
            font=FONT_SUB,
            bg=panel_bg,
            fg=COLOR_TEXT_MUTED,
            anchor="center",
        ).pack()

        tk.Label(
            panel,
            textvariable=pct_var,
            font=("Segoe UI", 15, "bold"),
            bg=panel_bg,
            fg=COLOR_TEXT,
            anchor="center",
        ).pack(pady=(12, 0))

    def set_led(self, led, connected):
        color = "#5cdb95" if connected else "#e85d5d"
        text = "Conectado" if connected else "Desconectado"
        led["canvas"].itemconfig(led["dot"], fill=color)
        led["value"].config(text=text, fg=color)

    def refresh_status_loop(self):
        clp_ok = bool(getattr(self.app, "dev_clp", None) and self.app.dev_clp.is_connected)
        auto_page = getattr(self.app, "auto_page", None)
        laser_ok = bool(getattr(auto_page, "last_laser_ok", False))
        camera_ok = bool(getattr(self.app, "camera_connected", self.camera_connected))
        if auto_page and hasattr(auto_page, "camera_is_connected"):
            camera_ok = camera_ok or bool(auto_page.camera_is_connected())
        self.set_led(self.led_camera, camera_ok)
        self.set_led(self.led_clp, clp_ok)
        self.set_led(self.led_laser, laser_ok)
        self.after(1000, self.refresh_status_loop)

    def add_record(self, serial, frontal=True, traseira=True, inspecao="Aprovado"):
        self.after(0, lambda: self._add_record(serial, frontal, traseira, inspecao))

    def _add_record(self, serial, frontal=True, traseira=True, inspecao="Aprovado"):
        record = {
            "hora": time.strftime("%d/%m %H:%M:%S"),
            "serial": str(serial),
            "frontal": "OK" if frontal else "Falha",
            "traseira": "OK" if traseira else "Falha",
            "inspecao": inspecao,
        }
        self.records.append(record)
        self.tree.insert("", 0, values=(record["hora"], record["serial"], record["frontal"], record["traseira"], record["inspecao"]))
        self.update_summary()
        self.after_idle(self._sync_tree_scrollbar)

    def update_summary(self):
        total = len(self.records)
        aprovado = sum(1 for r in self.records if str(r["inspecao"]).lower().startswith("aprov"))
        reprovado = total - aprovado
        self.var_aprovado.set(str(aprovado))
        self.var_reprovado.set(str(reprovado))
        self.var_total.set(str(total))
        self.var_pct_aprovado.set(f"{round((aprovado / total) * 100) if total else 0}%")
        self.var_pct_reprovado.set(f"{round((reprovado / total) * 100) if total else 0}%")
        self.var_pct_total.set("100%" if total else "0%")
