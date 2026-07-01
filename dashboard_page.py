import time
import tkinter as tk
from tkinter import ttk


class DashboardPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.records = []
        self.camera_connected = False
        self.var_aprovado = tk.StringVar(value="0")
        self.var_reprovado = tk.StringVar(value="0")
        self.var_total = tk.StringVar(value="0")
        self.var_pct_aprovado = tk.StringVar(value="0%")
        self.var_pct_reprovado = tk.StringVar(value="0%")
        self.var_pct_total = tk.StringVar(value="0%")
        self.build_ui()
        self.refresh_status_loop()

    def build_ui(self):
        style = ttk.Style(self)
        style.configure("Dashboard.Treeview", font=("Arial", 14), rowheight=34)
        style.configure("Dashboard.Treeview.Heading", font=("Arial", 13, "bold"))

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Dashboard de Produção", font=("Arial", 22, "bold")).pack(side="left")
        ttk.Button(top, text="Voltar à Rotina Automática", command=self.app.show_auto_page).pack(side="right", padx=5)
        ttk.Button(top, text="Painel Manual", command=self.app.show_manual_page).pack(side="right", padx=5)

        status = ttk.LabelFrame(self, text="Status dos Dispositivos", padding=10)
        status.pack(fill="x", padx=12, pady=(0, 10))
        self.led_camera = self._status_led(status, "Câmera", 0)
        self.led_clp = self._status_led(status, "CLP", 1)
        self.led_laser = self._status_led(status, "Laser", 2)

        summary = ttk.LabelFrame(self, text="Resumo de produção", padding=10)
        summary.pack(fill="x", padx=12, pady=10)
        for col in range(3):
            summary.columnconfigure(col, weight=1)
        self._summary_card(summary, 0, "Aprovado", self.var_aprovado, "peças aprovadas", self.var_pct_aprovado, "#2e7d32")
        self._summary_card(summary, 1, "Reprovado", self.var_reprovado, "peças reprovadas", self.var_pct_reprovado, "#b71c1c")
        self._summary_card(summary, 2, "Total", self.var_total, "peças analisadas", self.var_pct_total, "#1557a6")

        table_frame = ttk.LabelFrame(self, text="Seriais gravados", padding=10)
        table_frame.pack(fill="both", expand=True, padx=12, pady=10)
        columns = ("hora", "serial", "frontal", "traseira", "inspecao")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12, style="Dashboard.Treeview")
        self.tree.heading("hora", text="Data/Hora")
        self.tree.heading("serial", text="Serial")
        self.tree.heading("frontal", text="Frontal")
        self.tree.heading("traseira", text="Traseira")
        self.tree.heading("inspecao", text="Inspeção")
        self.tree.column("hora", width=145, anchor="center")
        self.tree.column("serial", width=180, anchor="center")
        self.tree.column("frontal", width=110, anchor="center")
        self.tree.column("traseira", width=110, anchor="center")
        self.tree.column("inspecao", width=120, anchor="center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _status_led(self, parent, label, col):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=col, sticky="w", padx=18, pady=4)
        canvas = tk.Canvas(frame, width=26, height=26, highlightthickness=0)
        dot = canvas.create_oval(4, 4, 22, 22, fill="red", outline="black")
        canvas.pack(side="left", padx=(0, 6))
        ttk.Label(frame, text=label, font=("Arial", 14, "bold")).pack(side="left")
        value = ttk.Label(frame, text="Desconectado", foreground="red", font=("Arial", 13, "bold"))
        value.pack(side="left", padx=6)
        return {"canvas": canvas, "dot": dot, "value": value}

    def _summary_card(self, parent, col, title, number_var, subtitle, pct_var, color):
        frame = tk.Frame(parent, bg="#f5f7fb", highlightbackground="#9eb0c0", highlightthickness=1)
        frame.grid(row=0, column=col, sticky="nsew", padx=7, pady=4)
        header = tk.Label(frame, text=title, bg=color, fg="white", font=("Arial", 16, "bold"), anchor="w", padx=12, pady=8)
        header.pack(fill="x")
        tk.Label(frame, textvariable=number_var, bg="#f5f7fb", fg=color, font=("Arial", 54, "bold"), pady=12).pack()
        tk.Label(frame, text=subtitle, bg="#f5f7fb", fg="#555", font=("Arial", 14)).pack()
        tk.Label(frame, textvariable=pct_var, bg="#e8eef7", fg=color, font=("Arial", 14, "bold"), padx=12, pady=4).pack(pady=10)

    def set_led(self, led, connected):
        color = "#00c853" if connected else "red"
        text = "Conectado" if connected else "Desconectado"
        led["canvas"].itemconfig(led["dot"], fill=color)
        led["value"].config(text=text, foreground=color)

    def refresh_status_loop(self):
        clp_ok = bool(getattr(self.app, "dev_clp", None) and self.app.dev_clp.is_connected)
        auto_page = getattr(self.app, "auto_page", None)
        laser_ok = bool(getattr(auto_page, "last_laser_ok", False))
        self.set_led(self.led_camera, self.camera_connected)
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