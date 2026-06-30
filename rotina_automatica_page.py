import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import db_module

PRESETS_FILE = "laser_presets.json"
AUTO_MEM_PECA_NO_PONTO = "70"
AUTO_MEM_STATUS_ROTINA = "90"
AUTO_MEM_GIRA_PECA = "71"
AUTO_MEM_VOLTA_GIRO = "72"
AUTO_MEM_NG = "73"
AUTO_MEM_OK = "74"
AUTO_PRESET_ARTE_1 = "Arte 1 (Serial Banco)"
AUTO_PRESET_ARTE_2 = "Arte 2 (Serial Banco)"


class RotinaAutomaticaPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.running = False
        self.worker_thread = None
        self.presets = self.load_presets()
        self.db_manager = db_module.DBManager()
        self.db_serials = []
        self.current_record = None

        self.var_serial = tk.StringVar(value="TESTE123")
        self.var_test_serial = tk.StringVar(value="4313110010")
        self.var_preset_arte1 = tk.StringVar(value=AUTO_PRESET_ARTE_1)
        self.var_preset_arte2 = tk.StringVar(value=AUTO_PRESET_ARTE_2)
        self.var_pulse_ms = tk.StringVar(value="1500")
        self.var_after_m70_s = tk.StringVar(value="8.0") #espera do robo deixar a peça no molde
        self.var_after_rotate_s = tk.StringVar(value="5.0")
        self.var_after_return_s = tk.StringVar(value="1.0")
        self.var_robot_routines_started = tk.BooleanVar(value=False)
        self.var_auto_flow_enabled = tk.BooleanVar(value=False)
        self.var_require_m90_ready = tk.BooleanVar(value=True)
        self.var_use_db_auto_sync = tk.BooleanVar(value=True)
        self.var_test_mode = tk.BooleanVar(value=False)
        self.var_db_status = tk.StringVar(value="Auto-Sync banco parado")
        self.var_status = tk.StringVar(value="Modo preparação")
        self.var_m80 = tk.StringVar(value="---")
        self.var_m90 = tk.StringVar(value="---")
        self.var_m73 = tk.StringVar(value="---")
        self.var_m74 = tk.StringVar(value="---")

        self.build_ui()
        self.refresh_status_loop()
        self.toggle_db_auto_sync()

    def build_ui(self):
        top = ttk.LabelFrame(self, text="Rotina Automática - Tela Separada", padding=10)
        top.pack(fill="x", padx=10, pady=10)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="Dispositivo:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="CLP da máquina", foreground="blue", font=("Arial", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Serial/teste:").grid(row=0, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_serial, width=24).grid(row=0, column=3, sticky="ew", padx=5, pady=4)
        ttk.Label(top, textvariable=self.var_status, foreground="blue", font=("Arial", 10, "bold")).grid(row=0, column=4, sticky="w", padx=5, pady=4)

        ttk.Label(top, text="Preset Arte 1:").grid(row=1, column=0, sticky="w", padx=5, pady=4)
        self.combo_arte1 = ttk.Combobox(top, textvariable=self.var_preset_arte1, values=list(self.presets.keys()), state="readonly")
        self.combo_arte1.grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        ttk.Label(top, text="Preset Arte 2:").grid(row=1, column=2, sticky="w", padx=5, pady=4)
        self.combo_arte2 = ttk.Combobox(top, textvariable=self.var_preset_arte2, values=list(self.presets.keys()), state="readonly")
        self.combo_arte2.grid(row=1, column=3, sticky="ew", padx=5, pady=4)
        ttk.Button(top, text="Recarregar Presets", command=self.reload_presets).grid(row=1, column=4, sticky="ew", padx=5, pady=4)

        ttk.Label(top, text="Pulso M71/M72 (ms):").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_pulse_ms, width=8).grid(row=2, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera após M70 (s):").grid(row=2, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_m70_s, width=8).grid(row=2, column=3, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera após M71 (s):").grid(row=2, column=4, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_rotate_s, width=8).grid(row=2, column=5, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera após M72 (s):").grid(row=2, column=6, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_return_s, width=8).grid(row=2, column=7, sticky="w", padx=5, pady=4)

        ttk.Checkbutton(top, text="Forçar liberação manual", variable=self.var_robot_routines_started).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Exigir M90 TRUE no CLP", variable=self.var_require_m90_ready).grid(row=3, column=2, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Liberar fluxo automático após ajustar artes", variable=self.var_auto_flow_enabled, command=self.update_auto_button_state).grid(row=3, column=4, sticky="w", padx=5, pady=4)
        ttk.Button(top, text="Abrir Balor GUI", command=self.open_balor_gui).grid(row=3, column=5, sticky="ew", padx=5, pady=4)

        ttk.Checkbutton(top, text="Auto-Sync Banco", variable=self.var_use_db_auto_sync, command=self.toggle_db_auto_sync).grid(row=4, column=0, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Modo teste/default", variable=self.var_test_mode).grid(row=4, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Serial teste:").grid(row=4, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_test_serial, width=18).grid(row=4, column=3, sticky="ew", padx=5, pady=4)
        ttk.Label(top, textvariable=self.var_db_status, foreground="blue").grid(row=4, column=4, columnspan=2, sticky="w", padx=5, pady=4)

        flow = ttk.LabelFrame(self, text="Sequência", padding=10)
        flow.pack(fill="x", padx=10, pady=5)
        ttk.Label(
            flow,
            text="M90 é status/permissivo lido no CLP. A próxima peça só entra depois do M70 cair e subir novamente."
        ).pack(anchor="w")
        buttons = ttk.Frame(flow)
        buttons.pack(fill="x", pady=8)
        self.btn_start = ttk.Button(buttons, text="Iniciar Automático", command=self.start_auto)
        self.btn_start.pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Parar", command=self.stop_auto).pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Abrir Balor GUI", command=self.open_balor_gui).pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Voltar ao Painel Manual", command=self.app.show_manual_page).pack(side="right", padx=5, ipadx=10, ipady=6)

        manual = ttk.LabelFrame(self, text="Botões Manuais das Memórias", padding=10)
        manual.pack(fill="x", padx=10, pady=5)
        for col in range(6):
            manual.columnconfigure(col, weight=1)
        self._manual_button(manual, 0, 0, "Ler M70\nPeça no ponto", lambda: self.manual_read(AUTO_MEM_PECA_NO_PONTO))
        self._manual_button(manual, 0, 1, "Ler M90\nRotina", lambda: self.manual_read(AUTO_MEM_STATUS_ROTINA))
        self._manual_button(manual, 0, 2, "Pulsa M71\nGira peça", lambda: self.manual_pulse(AUTO_MEM_GIRA_PECA))
        self._manual_button(manual, 0, 3, "Pulsa M72\nVolta giro", lambda: self.manual_pulse(AUTO_MEM_VOLTA_GIRO))
        self._manual_button(manual, 0, 4, "Liga M73\nNG", lambda: self.manual_write(AUTO_MEM_NG, True))
        self._manual_button(manual, 0, 5, "Liga M74\nOK", lambda: self.manual_write(AUTO_MEM_OK, True))
        self._manual_button(manual, 1, 0, "Desliga M73", lambda: self.manual_write(AUTO_MEM_NG, False))
        self._manual_button(manual, 1, 1, "Desliga M74", lambda: self.manual_write(AUTO_MEM_OK, False))
        self._manual_button(manual, 1, 2, "Abrir\nBalor GUI", self.open_balor_gui)
        self._manual_button(manual, 1, 3, "Recarregar\nPresets", self.reload_presets)

        monitor = ttk.LabelFrame(self, text="Monitoramento", padding=10)
        monitor.pack(fill="x", padx=10, pady=5)
        self._status_label(monitor, "M70 Peça", self.var_m80, 0)
        self._status_label(monitor, "M90 Rotina", self.var_m90, 1)
        self._status_label(monitor, "M73 NG", self.var_m73, 2)
        self._status_label(monitor, "M74 OK", self.var_m74, 3)

        log_frame = ttk.LabelFrame(self, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text = tk.Text(log_frame, height=12, state="disabled", bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.update_auto_button_state()



    def toggle_db_auto_sync(self):
        if self.var_use_db_auto_sync.get():
            self.var_db_status.set("Auto-Sync banco ativo")
            threading.Thread(target=self._db_auto_sync_loop, daemon=True).start()
        else:
            self.var_db_status.set("Auto-Sync banco parado")

    def _db_auto_sync_loop(self):
        while self.var_use_db_auto_sync.get():
            self.sync_db_once(silent=True)
            time.sleep(3)

    def sync_db_once(self, silent=False):
        try:
            serials = self.db_manager.get_pending_serials()
            self.after(0, lambda s=serials: self.apply_db_serials(s))
        except Exception as exc:
            if not silent:
                self.safe_log(f"Erro Auto-Sync banco: {exc}")

    def apply_db_serials(self, serials):
        self.db_serials = list(serials or [])
        if self.db_serials:
            self.var_db_status.set(f"Auto-Sync: {len(self.db_serials)} pendentes")
            if not self.var_test_mode.get() and not self.current_record:
                self.var_serial.set(str(self.db_serials[0]["serial"]))
        else:
            self.var_db_status.set("Auto-Sync: fila vazia")

    def prepare_cycle_serial(self):
        if self.var_test_mode.get():
            self.current_record = None
            serial = self.var_test_serial.get().strip() or self.var_serial.get().strip() or "TESTE123"
            self.var_serial.set(serial)
            self.safe_log(f"Modo teste: usando serial {serial}")
            return serial

        if self.var_use_db_auto_sync.get():
            serials = self.db_manager.get_pending_serials()
            self.db_serials = list(serials or [])
            if not self.db_serials:
                raise RuntimeError("Banco sem seriais pendentes para gravar.")
            self.current_record = self.db_serials[0]
            serial = str(self.current_record["serial"])
            self.var_serial.set(serial)
            self.safe_log(f"Auto-Sync banco: usando serial {serial} (ID {self.current_record['id']})")
            return serial

        self.current_record = None
        serial = self.var_serial.get().strip() or "TESTE123"
        self.var_serial.set(serial)
        self.safe_log(f"Auto-Sync banco desligado: usando serial manual {serial}")
        return serial

    def finish_cycle_serial(self):
        if not self.current_record:
            return
        log_id = self.current_record["id"]
        if self.db_manager.mark_as_engraved(log_id):
            self.safe_log(f"Banco: ID {log_id} marcado como gravado.")
            self.current_record = None
            self.sync_db_once(silent=True)
        else:
            self.safe_log(f"Banco: falha ao marcar ID {log_id} como gravado.")

    def update_auto_button_state(self):
        if not hasattr(self, "btn_start"):
            return
        state = "normal" if self.var_auto_flow_enabled.get() else "disabled"
        self.btn_start.config(state=state)

    def open_balor_gui(self):
        gui_path = "balor-gui.py"
        if not os.path.exists(gui_path):
            messagebox.showerror("Balor GUI", "Arquivo balor-gui.py não encontrado.")
            return
        try:
            subprocess.Popen([sys.executable, gui_path])
            self.log("Balor GUI aberto para ajuste manual das artes.")
        except Exception as exc:
            messagebox.showerror("Balor GUI", f"Falha ao abrir balor-gui.py:\n{exc}")

    def robot_routines_ready(self):
        if self.var_robot_routines_started.get():
            return True
        try:
            return self.is_true_value(self.read_mem(AUTO_MEM_STATUS_ROTINA))
        except Exception:
            return False

    def assert_robot_routines_started(self):
        if not self.robot_routines_ready():
            raise RuntimeError("M90 está FALSE no CLP. Só pode escrever/pulsar memórias com a rotina liberada.")

    def _manual_button(self, parent, row, col, text, command):
        ttk.Button(parent, text=text, command=command).grid(row=row, column=col, sticky="ew", padx=4, pady=4, ipady=5)

    def _status_label(self, parent, text, variable, col):
        frame = ttk.Frame(parent)
        frame.grid(row=0, column=col, sticky="ew", padx=10, pady=4)
        ttk.Label(frame, text=text, font=("Arial", 9, "bold")).pack(anchor="w")
        ttk.Label(frame, textvariable=variable, foreground="blue").pack(anchor="w")

    def default_presets(self):
        return {
            AUTO_PRESET_ARTE_1: {
                "power": "25", "speed": "3500", "freq": "60", "hatch_enable": True,
                "hatch_angle": "90", "hatch_spacing": "10.0", "offset_x": "-8.4325",
                "offset_y": "-16.0017", "scale": "1.0", "barcode_h": "6.0",
                "barcode_w_scale": "1.338", "text_scale": "2.5", "text_x_off": "0.0",
                "text_y_off": "0.0", "barcode_rot": "90", "text_rot": "270",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "text_pos": "bottom", "group_barcode": True
            },
            AUTO_PRESET_ARTE_2: {
                "power": "25", "speed": "3500", "freq": "60", "hatch_enable": True,
                "hatch_angle": "90", "hatch_spacing": "10.0", "offset_x": "-7.1016",
                "offset_y": "-41.6378", "scale": "1.0", "barcode_h": "5.1",
                "barcode_w_scale": "1.0", "text_scale": "2.5", "text_x_off": "0.0",
                "text_y_off": "0.0", "barcode_rot": "180", "text_rot": "180",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "text_pos": "bottom", "group_barcode": True
            },
            "Arte 1 + 2 (Frontal + Traseira)": {
                "power": "25", "speed": "3500", "freq": "60", "hatch_enable": True,
                "hatch_angle": "90", "hatch_spacing": "10.0", "offset_x": "0.0",
                "offset_y": "0.0", "scale": "1.0", "barcode_h": "6.0",
                "barcode_w_scale": "1.338", "text_scale": "2.5", "text_x_off": "0.0",
                "text_y_off": "0.0", "barcode_rot": "90", "text_rot": "270",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "text_pos": "bottom", "group_barcode": True, "is_combined": True,
                "combined_offsets": {
                    "base_1": [-8.4325, -16.0017],
                    "base_2": [-7.1016, -41.6378]
                },
                "obj_visibility": {"base_1": True, "base_2": True}
            }
        }

    def load_presets(self):
        presets = self.default_presets()
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                    presets.update(json.load(f))
            except Exception as exc:
                print(f"[AUTO-ESTADO] Erro ao carregar presets: {exc}")
        return presets

    def reload_presets(self):
        self.presets = self.load_presets()
        self.db_manager = db_module.DBManager()
        self.db_serials = []
        self.current_record = None
        names = list(self.presets.keys())
        self.combo_arte1["values"] = names
        self.combo_arte2["values"] = names
        self.log("Presets recarregados.")

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        print(f"[AUTO-ESTADO] {msg}")

    def safe_log(self, msg):
        self.after(0, lambda: self.log(msg))

    def set_status(self, msg):
        self.after(0, lambda: self.var_status.set(msg))

    def get_device(self):
        return self.app.dev_clp

    def require_device(self):
        dev = self.get_device()
        if not dev or not dev.is_connected:
            raise RuntimeError("CLP desconectado. Conecte o CLP no Painel Manual primeiro.")
        return dev

    def read_mem(self, mem):
        ok, value = self.require_device().send_read(mem)
        if not ok:
            raise RuntimeError(f"Falha ao ler M{mem}: {value}")
        return value

    def write_mem(self, mem, value):
        self.assert_robot_routines_started()
        ok, msg = self.require_device().send_write(mem, value)
        if not ok:
            raise RuntimeError(f"Falha ao escrever M{mem}: {msg}")

    def pulse_mem(self, mem):
        pulse_s = max(float(self.var_pulse_ms.get()) / 1000.0, 0.05)
        current = self.read_mem(mem)
        if self.is_true_value(current):
            self.safe_log(f"M{mem} já está TRUE; não vou desligar essa memória mantida ativa pelo CLP.")
            return
        self.write_mem(mem, True)
        time.sleep(pulse_s)
        self.write_mem(mem, False)

    def pulse_command_mem(self, mem, label):
        pulse_s = max(float(self.var_pulse_ms.get()) / 1000.0, 0.2)
        self.safe_log(f"{label}: ligando M{mem} por {pulse_s:.2f}s")
        self.write_mem(mem, True)
        time.sleep(pulse_s)
        self.write_mem(mem, False)
        self.safe_log(f"{label}: M{mem} desligado")
    def is_true_value(self, value):
        return str(value).strip().lower() in ("1", "true", "on")

    def manual_read(self, mem):
        self.run_task(lambda: self.safe_log(f"M{mem} = {self.read_mem(mem)}"))

    def manual_write(self, mem, value):
        self.run_task(lambda: (self.write_mem(mem, value), self.safe_log(f"M{mem} {'ON' if value else 'OFF'}")))

    def manual_pulse(self, mem):
        self.run_task(lambda: (self.pulse_mem(mem), self.safe_log(f"Pulso em M{mem} concluído")))

    def manual_mark_one(self, preset_name):
        if not self.var_auto_flow_enabled.get():
            messagebox.showinfo("Preparação", "Ajuste e teste as artes pelo Balor GUI antes de gravar por esta tela.")
            self.open_balor_gui()
            return
        if not messagebox.askyesno("Gravação Real", f"Gravar somente este preset?\n{preset_name}"):
            return
        self.run_task(lambda: self.mark_preset(preset_name, "manual"))

    def manual_mark_both(self):
        if not self.var_auto_flow_enabled.get():
            messagebox.showinfo("Preparação", "Ajuste e teste as artes pelo Balor GUI antes de gravar por esta tela.")
            self.open_balor_gui()
            return
        if not messagebox.askyesno("Gravação Real", "Gravar Arte 1 e depois Arte 2 agora?"):
            return
        self.run_task(self.mark_both_artes)

    def run_task(self, func):
        def _task():
            try:
                func()
            except Exception as exc:
                self.safe_log(f"Erro: {exc}")
                self.set_status("Erro")
        threading.Thread(target=_task, daemon=True).start()

    def start_auto(self):
        if self.running:
            return
        if not self.var_auto_flow_enabled.get():
            messagebox.showwarning("Fluxo bloqueado", "Ajuste as posições no Balor GUI e marque a liberação do fluxo automático.")
            return
        if not messagebox.askyesno("Rotina Automática", "Iniciar rotina automática com gravação real das duas artes?"):
            return
        self.running = True
        self.btn_start.config(state="disabled")
        self.worker_thread = threading.Thread(target=self.auto_loop, daemon=True)
        self.worker_thread.start()

    def stop_auto(self):
        self.running = False
        self.update_auto_button_state()
        self.set_status("Parando...")

    def auto_loop(self):
        self.safe_log("Rotina automática iniciada.")
        try:
            while self.running:
                self.set_status("Preparando serial e jobs antes do M70...")
                self.prepare_cycle_serial()
                prebuild = self.start_prebuild_jobs()

                self.set_status("Aguardando M70 peça no ponto...")
                while self.running:
                    if self.is_true_value(self.read_mem(AUTO_MEM_PECA_NO_PONTO)):
                        break
                    time.sleep(0.5)
                if not self.running:
                    break

                m90 = self.read_mem(AUTO_MEM_STATUS_ROTINA)
                self.safe_log(f"M70 ativo. M90 CLP = {m90}")
                if self.var_require_m90_ready.get() and not self.is_true_value(m90):
                    self.safe_log("M90 está FALSE; aguardando permissivo M90 no CLP.")
                    while self.running:
                        m90 = self.read_mem(AUTO_MEM_STATUS_ROTINA)
                        if self.is_true_value(m90):
                            break
                        time.sleep(0.5)
                    if not self.running:
                        break
                wait_m70_s = max(float(self.var_after_m70_s.get()), 0.0)
                self.set_status("Aguardando robô colocar peça no molde...")
                self.safe_log(f"M70 é sensor da esteira; aguardando {wait_m70_s:.2f}s para o robô posicionar no molde antes da Arte 1.")
                time.sleep(wait_m70_s)
                if not self.running:
                    break

                self.mark_both_artes(prebuild)

                self.set_status("Pulsando M72 para voltar giro...")
                self.pulse_mem(AUTO_MEM_VOLTA_GIRO)
                time.sleep(max(float(self.var_after_return_s.get()), 0.0))

                self.set_status("Liberando M74 OK...")
                self.write_mem(AUTO_MEM_OK, True)
                self.write_mem(AUTO_MEM_NG, False)
                self.safe_log("Ciclo concluído. M74 ligado como OK.")
                self.finish_cycle_serial()

                self.set_status("Aguardando M70 desligar para novo ciclo...")
                while self.running and self.is_true_value(self.read_mem(AUTO_MEM_PECA_NO_PONTO)):
                    time.sleep(0.5)
        except Exception as exc:
            self.safe_log(f"Erro na rotina: {exc}")
            self.set_status("Erro")
        finally:
            self.running = False
            self.after(0, self.update_auto_button_state)
            if self.var_status.get() != "Erro":
                self.set_status("Parado")
            self.safe_log("Rotina automática parada.")

    def resolve_step_preset(self, selected_name, suffix):
        if selected_name == "Arte 1 + 2 (Frontal + Traseira)":
            resolved = AUTO_PRESET_ARTE_1 if suffix == "arte1" else AUTO_PRESET_ARTE_2
            self.safe_log(f"Preset combinado selecionado em {suffix}; usando {resolved} para gravar separado.")
            return resolved
        return selected_name
    def start_prebuild_jobs(self):
        preset_arte1 = self.resolve_step_preset(self.var_preset_arte1.get(), "arte1")
        preset_arte2 = self.resolve_step_preset(self.var_preset_arte2.get(), "arte2")
        ctx = {
            "jobs": {},
            "errors": {},
            "ready": {"arte1": threading.Event(), "arte2": threading.Event()},
            "presets": {"arte1": preset_arte1, "arte2": preset_arte2},
        }

        def _build_job(suffix, preset_name):
            try:
                ctx["jobs"][suffix] = self.build_laser_job(preset_name, suffix)
            except Exception as exc:
                ctx["errors"][suffix] = exc
            finally:
                ctx["ready"][suffix].set()

        self.safe_log("Pré-gerando jobs arte1 e arte2 enquanto aguarda M70.")
        threading.Thread(target=_build_job, args=("arte1", preset_arte1), daemon=True).start()
        threading.Thread(target=_build_job, args=("arte2", preset_arte2), daemon=True).start()
        return ctx

    def wait_prebuilt_job(self, ctx, suffix):
        if not ctx["ready"][suffix].is_set():
            self.set_status(f"Aguardando job {suffix} ficar pronto...")
            self.safe_log(f"Aguardando pré-geração da {suffix} terminar.")
        ctx["ready"][suffix].wait()
        if suffix in ctx["errors"]:
            raise ctx["errors"][suffix]
        return ctx["jobs"][suffix], ctx["presets"][suffix]

    def mark_both_artes(self, prebuild=None):
        if prebuild is None:
            self.set_status("Pré-gerando jobs Arte 1 e Arte 2...")
            prebuild = self.start_prebuild_jobs()

        commands_arte1, preset_arte1 = self.wait_prebuilt_job(prebuild, "arte1")
        self.set_status("Gravando Arte 1...")
        self.execute_laser_job(commands_arte1, preset_arte1, "arte1")

        self.set_status("Acionando M71 para girar peça...")
        self.pulse_command_mem(AUTO_MEM_GIRA_PECA, "Giro da peça")
        wait_rotate_s = max(float(self.var_after_rotate_s.get()), 0.0)
        self.safe_log(f"Aguardando {wait_rotate_s:.2f}s após M71 antes da Arte 2.")
        time.sleep(wait_rotate_s)

        commands_arte2, preset_arte2 = self.wait_prebuilt_job(prebuild, "arte2")
        self.set_status("Gravando Arte 2...")
        self.execute_laser_job(commands_arte2, preset_arte2, "arte2")

    def mark_preset(self, preset_name, suffix):
        commands = self.build_laser_job(preset_name, suffix)
        self.execute_laser_job(commands, preset_name, suffix)

    def build_laser_job(self, preset_name, suffix):
        preset = self.presets.get(preset_name)
        if not preset:
            raise RuntimeError(f"Preset não encontrado: {preset_name}")

        import barcode_module
        import balor.command_list

        serial = self.var_serial.get().strip() or "TESTE123"
        svg_file = f"temp_auto_{suffix}.svg"
        job_file = f"temp_auto_{suffix}.bin"
        settings_file = f"temp_auto_{suffix}_settings.csv"

        gen = barcode_module.BarcodeGenerator(font_path=preset.get("text_font", "arial.ttf"))
        gen.generate_code128_svg(
            serial,
            svg_file,
            barcode_height=float(preset.get("barcode_h", "6.0")),
            text_pos=preset.get("text_pos", "bottom"),
            barcode_w_scale=float(preset.get("barcode_w_scale", "1.0")),
            text_scale=float(preset.get("text_scale", "1.0")),
            text_x_off=float(preset.get("text_x_off", "0.0")),
            text_y_off=float(preset.get("text_y_off", "0.0")),
            barcode_rot=float(preset.get("barcode_rot", "0")),
            text_rot=float(preset.get("text_rot", "0")),
            barcode_type=preset.get("barcode_type", "gs1_128"),
            font_name=preset.get("text_font", "arial.ttf"),
            text_space=float(preset.get("text_space", "0.0")),
            group=bool(preset.get("group_barcode", True)),
        )

        hatch_spacing = preset.get("hatch_spacing", "10.0") if preset.get("hatch_enable", True) else "0"
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(f"000000 {preset.get('freq', '60')} {preset.get('power', '25')} {preset.get('speed', '3500')} {preset.get('hatch_angle', '90')} {hatch_spacing} None 1\n")

        cmd = [
            sys.executable, "balor-svg.py", "mark",
            "-f", svg_file,
            "-o", job_file,
            "--xoff", str(preset.get("offset_x", "0.0")),
            "--yoff", str(preset.get("offset_y", "0.0")),
            "--xscale", str(preset.get("scale", "1.0")),
            "--yscale", str(preset.get("scale", "1.0")),
            "-s", settings_file,
            "--laser-on-delay", "0",
            "--laser-off-delay", "0",
            "--mark-end-delay", "0",
            "--polygon-delay", "50",
            "--hatch-power-scale", "0.90",
            "--hatch-speed-scale", "2.00",
            "--hatch-overrun", "0.00",
            "--hatch-serpentine",
        ]
        if os.path.exists("cal_0002.csv"):
            cmd.extend(["-c", "cal_0002.csv"])

        self.safe_log(f"Gerando job {suffix}: {preset_name} / serial {serial}")
        job_started_at = time.perf_counter()
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        job_elapsed = time.perf_counter() - job_started_at
        self.safe_log(f"Job {suffix} gerado em {job_elapsed:.2f}s")

        with open(job_file, "rb") as f:
            return balor.command_list.CommandBinary(f.read())

    def execute_laser_job(self, commands, preset_name, suffix):
        import balor.sender

        machine = balor.sender.Sender()
        try:
            self.safe_log("Abrindo conexão USB da laser...")
            open_started_at = time.perf_counter()
            if not machine.open(machine_index=0):
                raise RuntimeError("Não foi possível abrir a placa laser.")
            open_elapsed = time.perf_counter() - open_started_at
            self.safe_log(f"Conexão USB laser aberta em {open_elapsed:.2f}s")
            self.safe_log(f"Laser gravando {suffix}: {preset_name}")
            started_at = time.perf_counter()
            machine.execute(command_list=commands, loop_count=1)
            elapsed = time.perf_counter() - started_at
            self.safe_log(f"Laser finalizou {suffix}: {preset_name} ({elapsed:.2f}s)")
        finally:
            try:
                machine.close()
            except Exception:
                pass


    def refresh_status_loop(self):
        def _task():
            values = []
            for mem in (AUTO_MEM_PECA_NO_PONTO, AUTO_MEM_STATUS_ROTINA, AUTO_MEM_NG, AUTO_MEM_OK):
                try:
                    values.append(self.read_mem(mem))
                except Exception:
                    values.append("---")
            self.after(0, lambda: self.apply_status_values(values))
        threading.Thread(target=_task, daemon=True).start()

    def apply_status_values(self, values):
        self.var_m80.set(values[0])
        self.var_m90.set(values[1])
        self.var_m73.set(values[2])
        self.var_m74.set(values[3])
        self.after(1000, self.refresh_status_loop)
