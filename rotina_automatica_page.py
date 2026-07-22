import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import db_module

PRESETS_FILE = "laser_presets.json"
AUTO_MEM_PRONTO_GRAVACAO = "1500"
AUTO_MEM_GRAVACAO_INSPECAO_1 = "1510"
AUTO_MEM_GRAVACAO_INSPECAO_2 = "1511"
AUTO_MEM_RESULT_OK = "1120"
AUTO_MEM_RESULT_NG = "1116"
AUTO_MEM_SENSOR_ESTEIRA = "1110"
AUTO_MEM_PECA_NO_PONTO = AUTO_MEM_PRONTO_GRAVACAO
AUTO_MEM_STATUS_ROTINA = AUTO_MEM_SENSOR_ESTEIRA
AUTO_MEM_GIRA_PECA = AUTO_MEM_GRAVACAO_INSPECAO_1
AUTO_MEM_VOLTA_GIRO = AUTO_MEM_GRAVACAO_INSPECAO_2
AUTO_MEM_NG = AUTO_MEM_RESULT_NG
AUTO_MEM_OK = AUTO_MEM_RESULT_OK
AUTO_PRESET_ARTE_1 = "Arte 1 (Serial Banco)"
AUTO_PRESET_ARTE_2 = "Arte 2 (Serial Banco)"
KEYENCE_IP = "192.168.1.29"
KEYENCE_PORT = 8500
KEYENCE_TIMEOUT_S = 5
KEYENCE_RECV_CHUNK = 1024
KEYENCE_IDLE_GRACE_S = 0.25
KEYENCE_TRIGGER_CMD = b"TRG\r"
CAMERA_AFTER_MARK_DELAY_S = 0.0
AUTO_MEM_POLL_FAST_S = 0.05
AUTO_MEM_WAIT_LOG_EVERY_S = 2.0
AUTO_RESULT_HOLD_S = 3.0
AUTO_TEST_SERIAL_COUNT = 10


class RotinaAutomaticaPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.running = False
        self.worker_thread = None
        self.presets = self.load_presets()
        self.db_manager = db_module.DBManager()
        self.db_lock = threading.RLock()
        self.db_serials = []
        self.current_record = None
        self.last_laser_ok = False
        self.camera_sock = None
        self.modbus_lock = threading.RLock()
        self.m70_lock = threading.Lock()
        self.m70_latched = False
        self.m70_last_state = None
        self.m70_monitor_thread = None
        self.job_cache = {}
        self.job_cache_lock = threading.RLock()
        self.job_cache_max = 8
        self.job_cache_dir = os.path.join("temp_auto_job_cache")
        self.db_prebuild_lock = threading.RLock()
        self.db_prebuilt_jobs = {}
        self.db_prebuild_building_ids = set()
        self.db_prebuild_max = 4
        self.db_prebuild_worker_running = False
        self.test_serial_cycle = []
        self.test_serial_index = 0
        self.test_prebuild_lock = threading.RLock()
        self.test_prebuilt_jobs = {}
        self.test_prebuild_building = set()
        self.test_prebuild_started = set()
        self.test_prebuild_worker_running = False

        self.var_serial = tk.StringVar(value="TESTE123")
        self.var_test_serial = tk.StringVar(value="4313110010")
        self.var_preset_arte1 = tk.StringVar(value=AUTO_PRESET_ARTE_1)
        self.var_preset_arte2 = tk.StringVar(value=AUTO_PRESET_ARTE_2)
        self.var_pulse_ms = tk.StringVar(value="1200")
        self.var_after_m70_s = tk.StringVar(value="0.1") #espera do robo deixar a peca no molde
        self.var_after_rotate_s = tk.StringVar(value="0.2")
        self.var_after_return_s = tk.StringVar(value="0.1")
        self.var_robot_routines_started = tk.BooleanVar(value=False)
        self.var_auto_flow_enabled = tk.BooleanVar(value=False)
        self.var_require_m90_ready = tk.BooleanVar(value=True)
        self.var_use_db_auto_sync = tk.BooleanVar(value=True)
        self.var_test_mode = tk.BooleanVar(value=False)
        self.var_db_status = tk.StringVar(value="Auto-Sync banco parado")
        self.var_status = tk.StringVar(value="Modo preparação")
        self.var_m1500 = tk.StringVar(value="---")
        self.var_m1110 = tk.StringVar(value="---")
        self.var_m1120 = tk.StringVar(value="---")
        self.var_m1116 = tk.StringVar(value="---")

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

        ttk.Label(top, text="Pulso sinais CLP (ms):").grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_pulse_ms, width=8).grid(row=2, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera apos M1500 (s):").grid(row=2, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_m70_s, width=8).grid(row=2, column=3, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera apos M1510 (s):").grid(row=2, column=4, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_rotate_s, width=8).grid(row=2, column=5, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Espera apos M1511 (s):").grid(row=2, column=6, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_after_return_s, width=8).grid(row=2, column=7, sticky="w", padx=5, pady=4)

        ttk.Checkbutton(top, text="Escrita manual liberada", variable=self.var_robot_routines_started).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Fluxo por M1500 do CLP", variable=self.var_require_m90_ready).grid(row=3, column=2, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Liberar fluxo automático após ajustar artes", variable=self.var_auto_flow_enabled, command=self.update_auto_button_state).grid(row=3, column=4, sticky="w", padx=5, pady=4)
        ttk.Button(top, text="Abrir Balor GUI", command=self.open_balor_gui).grid(row=3, column=5, sticky="ew", padx=5, pady=4)

        ttk.Checkbutton(top, text="Auto-Sync Banco", variable=self.var_use_db_auto_sync, command=self.toggle_db_auto_sync).grid(row=4, column=0, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(top, text="Modo teste/default (10 seriais)", variable=self.var_test_mode).grid(row=4, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Serial teste:").grid(row=4, column=2, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_test_serial, width=18).grid(row=4, column=3, sticky="ew", padx=5, pady=4)
        ttk.Label(top, textvariable=self.var_db_status, foreground="blue").grid(row=4, column=4, columnspan=2, sticky="w", padx=5, pady=4)

        flow = ttk.LabelFrame(self, text="Sequência", padding=10)
        flow.pack(fill="x", padx=10, pady=5)
        ttk.Label(
            flow,
            text="Novo fluxo: aguarda M1500 TRUE para gravar; avisa M1510 apos Arte 1; avisa M1511 apos Arte 2; libera M1120 OK ou M1116 NG."
        ).pack(anchor="w")
        buttons = ttk.Frame(flow)
        buttons.pack(fill="x", pady=8)
        self.btn_start = ttk.Button(buttons, text="Iniciar Automático", command=self.start_auto)
        self.btn_start.pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Parar", command=self.stop_auto).pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Abrir Balor GUI", command=self.open_balor_gui).pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Ir para Dashboard", command=self.app.show_dashboard_page).pack(side="left", padx=5, ipadx=10, ipady=6)
        ttk.Button(buttons, text="Voltar ao Painel Manual", command=self.app.show_manual_page).pack(side="right", padx=5, ipadx=10, ipady=6)

        manual = ttk.LabelFrame(self, text="Botões Manuais das Memórias", padding=10)
        manual.pack(fill="x", padx=10, pady=5)
        for col in range(6):
            manual.columnconfigure(col, weight=1)
        self._manual_button(manual, 0, 0, "Ler M1500\nPronto gravar", lambda: self.manual_read(AUTO_MEM_PRONTO_GRAVACAO))
        self._manual_button(manual, 0, 1, "Ler M1110\nSensor esteira", lambda: self.manual_read(AUTO_MEM_SENSOR_ESTEIRA))
        self._manual_button(manual, 0, 2, "Pulsa M1510\nFim lado 1", lambda: self.manual_pulse(AUTO_MEM_GRAVACAO_INSPECAO_1))
        self._manual_button(manual, 0, 3, "Pulsa M1511\nFim lado 2", lambda: self.manual_pulse(AUTO_MEM_GRAVACAO_INSPECAO_2))
        self._manual_button(manual, 0, 4, "Liga M1116\nNG", lambda: self.manual_write(AUTO_MEM_RESULT_NG, True))
        self._manual_button(manual, 0, 5, "Liga M1120\nOK", lambda: self.manual_write(AUTO_MEM_RESULT_OK, True))
        self._manual_button(manual, 1, 0, "Desliga M1116", lambda: self.manual_write(AUTO_MEM_RESULT_NG, False))
        self._manual_button(manual, 1, 1, "Desliga M1120", lambda: self.manual_write(AUTO_MEM_RESULT_OK, False))
        self._manual_button(manual, 1, 2, "Abrir\nBalor GUI", self.open_balor_gui)
        self._manual_button(manual, 1, 3, "Recarregar\nPresets", self.reload_presets)

        monitor = ttk.LabelFrame(self, text="Monitoramento", padding=10)
        monitor.pack(fill="x", padx=10, pady=5)
        self._status_label(monitor, "M1500 Pronto", self.var_m1500, 0)
        self._status_label(monitor, "M1110 Esteira", self.var_m1110, 1)
        self._status_label(monitor, "M1116 NG", self.var_m1116, 2)
        self._status_label(monitor, "M1120 OK", self.var_m1120, 3)

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

    def get_pending_serials_safe(self):
        with self.db_lock:
            return self.db_manager.get_pending_serials()

    def mark_as_engraved_safe(self, log_id):
        with self.db_lock:
            return self.db_manager.mark_as_engraved(log_id)

    def sync_db_once(self, silent=False):
        try:
            serials = self.get_pending_serials_safe()
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

    def build_test_serial_cycle(self):
        base = self.var_test_serial.get().strip() or self.var_serial.get().strip() or "TESTE123"
        if base.isdigit():
            width = len(base)
            start = int(base)
            return [f"{start + index:0{width}d}" for index in range(AUTO_TEST_SERIAL_COUNT)]
        return [f"{base}_{index + 1:02d}" for index in range(AUTO_TEST_SERIAL_COUNT)]

    def reset_test_serial_cycle(self):
        self.test_serial_cycle = self.build_test_serial_cycle()
        self.test_serial_index = 0
        with self.test_prebuild_lock:
            self.test_prebuilt_jobs.clear()
            self.test_prebuild_building.clear()
            self.test_prebuild_started.clear()
        self.safe_log(f"[MODO-TESTE] Lista de {len(self.test_serial_cycle)} seriais preparada: {', '.join(self.test_serial_cycle)}")

    def next_test_cycle_serial(self):
        if not self.test_serial_cycle:
            self.reset_test_serial_cycle()
        index = self.test_serial_index % len(self.test_serial_cycle)
        serial = self.test_serial_cycle[index]
        self.test_serial_index += 1
        return serial, index + 1, len(self.test_serial_cycle)

    def prepare_cycle_serial(self):
        if self.var_test_mode.get():
            self.current_record = None
            serial, serial_pos, serial_total = self.next_test_cycle_serial()
            self.var_serial.set(serial)
            self.safe_log(f"[MODO-TESTE] Ciclo serial {serial_pos}/{serial_total}: usando serial {serial}")
            return serial

        if self.var_use_db_auto_sync.get():
            serials = self.get_pending_serials_safe()
            self.db_serials = list(serials or [])
            if not self.db_serials:
                raise RuntimeError("Banco sem seriais pendentes para gravar.")
            selected_record = None
            with self.db_prebuild_lock:
                for row in self.db_serials:
                    row_key = self._record_id_key(row)
                    if row_key in self.db_prebuilt_jobs:
                        selected_record = row
                        break
            if selected_record is None:
                selected_record = self.db_serials[0]
            self.current_record = selected_record
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
        if self.mark_as_engraved_safe(log_id):
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
                "hatch_angle": "90", "hatch_spacing": "10.0", "offset_x": "-1.1317",
                "offset_y": "-35.5651", "scale": "1.0", "barcode_h": "6.0",
                "barcode_w_scale": "1.338", "text_scale": "2.5", "text_x_off": "0.0",
                "text_y_off": "0.0", "barcode_rot": "90", "text_rot": "270",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "text_pos": "bottom", "group_barcode": True
            },
            AUTO_PRESET_ARTE_2: {
                "power": "25", "speed": "3500", "freq": "60", "hatch_enable": True,
                "hatch_angle": "90", "hatch_spacing": "10.0", "offset_x": "-3.8902",
                "offset_y": "-7.6600", "scale": "1.0", "barcode_h": "5.1",
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
                    "base_1": [-1.1317, -35.5651],
                    "base_2": [-3.8902, -7.6600]
                },
                "obj_visibility": {"base_1": True, "base_2": True}
            }
        }

    def load_presets(self):
        presets = self.default_presets()
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for name, preset in loaded.items():
                    if name not in presets:
                        presets[name] = preset
                    elif isinstance(presets[name], dict) and isinstance(preset, dict):
                        presets[name].update(preset)
                    else:
                        presets[name] = preset
            except Exception as exc:
                print(f"[AUTO-ESTADO] Erro ao carregar presets: {exc}")

        combo = presets.get("Arte 1 + 2 (Frontal + Traseira)", {})
        offsets = combo.get("combined_offsets", {}) if isinstance(combo, dict) else {}
        for preset_name, base_name in ((AUTO_PRESET_ARTE_1, "base_1"), (AUTO_PRESET_ARTE_2, "base_2")):
            if base_name not in offsets:
                continue
            try:
                ox, oy = offsets[base_name]
                presets[preset_name]["offset_x"] = f"{float(ox):.4f}"
                presets[preset_name]["offset_y"] = f"{float(oy):.4f}"
            except Exception:
                pass
        return presets

    def reload_presets(self):
        self.presets = self.load_presets()
        self.db_manager = db_module.DBManager()
        self.db_serials = []
        self.current_record = None
        with self.job_cache_lock:
            self.job_cache.clear()
        self.safe_log("Cache de jobs da laser limpo apos recarregar presets.")
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

    def log_tempo(self, label, started_at):
        elapsed = time.perf_counter() - started_at
        self.safe_log(f"[TEMPO] {label}: {elapsed:.3f}s")
        return elapsed

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
        with self.modbus_lock:
            ok, value = self.require_device().send_read(mem)
        if not ok:
            raise RuntimeError(f"Falha ao ler M{mem}: {value}")
        return value

    def write_mem(self, mem, value):
        with self.modbus_lock:
            ok, msg = self.require_device().send_write(mem, value)
        if not ok:
            raise RuntimeError(f"Falha ao escrever M{mem}: {msg}")
        self.safe_log(f"WRITE M{mem} = {value} OK")

    def read_mem_for_log(self, mem):
        try:
            return self.read_mem(mem)
        except Exception as exc:
            return f"ERRO:{exc}"

    def log_clp_snapshot(self, label):
        values = {
            "M1500 pronto": self.read_mem_for_log(AUTO_MEM_PRONTO_GRAVACAO),
            "M1110 esteira": self.read_mem_for_log(AUTO_MEM_SENSOR_ESTEIRA),
            "M1510 fim lado1": self.read_mem_for_log(AUTO_MEM_GRAVACAO_INSPECAO_1),
            "M1511 fim lado2": self.read_mem_for_log(AUTO_MEM_GRAVACAO_INSPECAO_2),
            "M1120 OK": self.read_mem_for_log(AUTO_MEM_RESULT_OK),
            "M1116 NG": self.read_mem_for_log(AUTO_MEM_RESULT_NG),
        }
        snapshot = " | ".join(f"{name}={value}" for name, value in values.items())
        self.safe_log(f"[CLP-SNAPSHOT] {label}: {snapshot}")

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
        self.log_clp_snapshot(f"antes pulso M{mem} - {label}")
        current = self.read_mem_for_log(mem)
        if self.is_true_value(current):
            self.safe_log(f"{label}: M{mem} ja estava TRUE; desligando antes para gerar borda nova.")
            self.write_mem(mem, False)
            time.sleep(0.2)
            self.log_clp_snapshot(f"M{mem} pre-limpo antes do pulso - {label}")
        self.safe_log(f"{label}: ligando M{mem} por {pulse_s:.2f}s")
        self.write_mem(mem, True)
        self.log_clp_snapshot(f"M{mem} ligado - {label}")
        time.sleep(pulse_s)
        self.write_mem(mem, False)
        self.safe_log(f"{label}: M{mem} desligado")
        self.log_clp_snapshot(f"depois pulso M{mem} - {label}")

    def signal_command_until_ack(self, mem, label, ack_mem, ack_expected_true, ack_label):
        self.log_clp_snapshot(f"antes sinal M{mem} - {label}")
        current = self.read_mem_for_log(mem)
        if self.is_true_value(current):
            self.safe_log(f"{label}: M{mem} ja estava TRUE; limpando antes de sinalizar.")
            self.write_mem(mem, False)
            time.sleep(0.2)
            self.log_clp_snapshot(f"M{mem} limpo antes do sinal - {label}")

        self.safe_log(f"{label}: mantendo M{mem}=TRUE ate ACK {ack_label}.")
        self.write_mem(mem, True)
        self.log_clp_snapshot(f"M{mem} TRUE aguardando ACK - {label}")

        ack_value = self.wait_mem_state(ack_mem, ack_expected_true, ack_label)
        self.safe_log(f"{label}: ACK recebido {ack_label} valor={ack_value}; desligando M{mem}.")
        self.write_mem(mem, False)
        self.log_clp_snapshot(f"depois ACK e desligamento M{mem} - {label}")
        return ack_value

    def clear_cycle_signals(self, label):
        self.log_clp_snapshot(f"antes limpeza sinais - {label}")
        for mem, name in (
            (AUTO_MEM_GRAVACAO_INSPECAO_1, "M1510 fim lado 1"),
            (AUTO_MEM_GRAVACAO_INSPECAO_2, "M1511 fim lado 2"),
        ):
            current = self.read_mem_for_log(mem)
            if self.is_true_value(current):
                self.safe_log(f"[LIMPEZA] {name} estava TRUE; escrevendo FALSE antes de iniciar ciclo.")
                self.write_mem(mem, False)
            else:
                self.safe_log(f"[LIMPEZA] {name} ja estava FALSE ({current}).")
        self.safe_log("[LIMPEZA] Mantendo M1120/M1116 do ciclo anterior ativos para o robo consumir.")
        self.log_clp_snapshot(f"depois limpeza sinais - {label}")

    def clear_result_signals_before_new_result(self, label):
        self.log_clp_snapshot(f"antes limpeza resultado - {label}")
        cleared = False
        for mem, name in (
            (AUTO_MEM_RESULT_OK, "M1120 OK"),
            (AUTO_MEM_RESULT_NG, "M1116 NG"),
        ):
            current = self.read_mem_for_log(mem)
            if self.is_true_value(current):
                self.safe_log(f"[RESULTADO] {name} estava TRUE; limpando para gerar novo resultado.")
                self.write_mem(mem, False)
                cleared = True
            else:
                self.safe_log(f"[RESULTADO] {name} ja estava FALSE ({current}).")
        if cleared:
            time.sleep(0.2)
        self.log_clp_snapshot(f"depois limpeza resultado - {label}")

    def is_true_value(self, value):
        return str(value).strip().lower() in ("1", "true", "on")

    def wait_mem_state(self, mem, expected_true, label, poll_s=AUTO_MEM_POLL_FAST_S):
        last_log = 0.0
        last_value = "---"
        target = "TRUE" if expected_true else "FALSE"
        while self.running:
            try:
                last_value = self.read_mem(mem)
                if self.is_true_value(last_value) == expected_true:
                    self.safe_log(f"{label}: M{mem} ficou {target} (valor={last_value}).")
                    return last_value
            except Exception as exc:
                last_value = f"erro: {exc}"

            now = time.monotonic()
            if now - last_log >= AUTO_MEM_WAIT_LOG_EVERY_S:
                self.safe_log(f"{label}: aguardando M{mem} ficar {target}. Ultima leitura={last_value}")
                last_log = now
            time.sleep(poll_s)
        return None

    def wait_mem_true(self, mem, label):
        return self.wait_mem_state(mem, True, label)

    def wait_mem_false(self, mem, label):
        return self.wait_mem_state(mem, False, label)

    def reset_m70_latch(self):
        with self.m70_lock:
            self.m70_latched = False
            self.m70_last_state = None

    def start_m70_monitor(self):
        if self.m70_monitor_thread and self.m70_monitor_thread.is_alive():
            return
        self.m70_monitor_thread = threading.Thread(target=self.m70_monitor_loop, daemon=True)
        self.m70_monitor_thread.start()

    def m70_monitor_loop(self):
        last_error_log = 0.0
        while self.running:
            try:
                value = self.read_mem(AUTO_MEM_PECA_NO_PONTO)
                current = self.is_true_value(value)
                with self.m70_lock:
                    previous = self.m70_last_state
                    if current and previous is not True:
                        self.m70_latched = True
                        self.safe_log(f"M1500 monitor: borda TRUE capturada (valor={value}).")
                    self.m70_last_state = current
            except Exception as exc:
                now = time.monotonic()
                if now - last_error_log >= AUTO_MEM_WAIT_LOG_EVERY_S:
                    self.safe_log(f"M1500 monitor: erro lendo M1500 ({exc})")
                    last_error_log = now
            time.sleep(AUTO_MEM_POLL_FAST_S)

    def consume_m70_latch(self):
        with self.m70_lock:
            if self.m70_latched:
                self.m70_latched = False
                return True
        return False

    def wait_m70_piece_ready(self):
        last_log = 0.0
        last_value = "---"
        while self.running:
            if self.consume_m70_latch():
                self.safe_log("M1500 pronto gravacao: usando evento capturado pelo monitor.")
                return True
            try:
                last_value = self.read_mem(AUTO_MEM_PECA_NO_PONTO)
                if self.is_true_value(last_value):
                    self.safe_log(f"M1500 pronto gravacao: M1500 ficou TRUE (valor={last_value}).")
                    return last_value
            except Exception as exc:
                last_value = f"erro: {exc}"

            now = time.monotonic()
            if now - last_log >= AUTO_MEM_WAIT_LOG_EVERY_S:
                self.safe_log(f"M1500 pronto gravacao: aguardando M1500 ficar TRUE. Ultima leitura={last_value}")
                last_log = now
            time.sleep(AUTO_MEM_POLL_FAST_S)
        return None

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
        if self.var_test_mode.get():
            self.reset_test_serial_cycle()
        self.btn_start.config(state="disabled")
        self.start_test_prebuild_queue()
        self.start_db_prebuild_queue()
        self.worker_thread = threading.Thread(target=self.auto_loop, daemon=True)
        self.worker_thread.start()

    def stop_auto(self):
        self.running = False
        self.update_auto_button_state()
        self.set_status("Parando...")

    def auto_loop(self):
        self.safe_log("Rotina automatica iniciada no novo fluxo CLP (M1500/M1510/M1511/M1120/M1116).")
        try:
            while self.running:
                cycle_started_at = time.perf_counter()
                self.set_status("Preparando serial e jobs antes do M1500...")
                serial_started_at = time.perf_counter()
                serial = self.prepare_cycle_serial()
                self.log_tempo("Serial preparado", serial_started_at)
                self.safe_log(f"[CICLO] Novo ciclo preparado para serial={serial}")
                clear_started_at = time.perf_counter()
                self.clear_cycle_signals("inicio ciclo")
                self.log_tempo("Limpeza sinais CLP inicio ciclo", clear_started_at)
                self.log_clp_snapshot("inicio ciclo antes prebuild")
                prebuild = self.pop_prebuilt_jobs_for_current(serial)
                if prebuild is None:
                    prebuild = self.start_prebuild_jobs(serial)
                    self.start_db_prebuild_queue_after_current_jobs(prebuild)
                else:
                    self.start_db_prebuild_queue()

                self.log_clp_snapshot("antes de aguardar M1500 Arte 1")
                self.set_status("Aguardando M1500 pronto para Arte 1...")
                wait_m1500_started_at = time.perf_counter()
                ready_1 = self.wait_mem_true(AUTO_MEM_PRONTO_GRAVACAO, "Pronto gravacao Arte 1")
                self.log_tempo("Espera M1500 TRUE Arte 1", wait_m1500_started_at)
                if not self.running or ready_1 is None:
                    break
                self.safe_log(f"[HANDSHAKE] M1500 TRUE recebido para Arte 1: valor={ready_1}")
                self.log_clp_snapshot("M1500 TRUE Arte 1")

                wait_ready_s = max(float(self.var_after_m70_s.get()), 0.0)
                if wait_ready_s:
                    self.safe_log(f"Aguardando {wait_ready_s:.2f}s apos M1500 antes da Arte 1.")
                    timer_started_at = time.perf_counter()
                    time.sleep(wait_ready_s)
                    self.log_tempo("Timer apos M1500 antes Arte 1", timer_started_at)
                if not self.running:
                    break

                arte1_total_started_at = time.perf_counter()
                frontal_ok = self.mark_one_arte_with_inspection(prebuild, "arte1", "Arte 1")
                self.log_tempo("Arte 1 total gravacao + espera camera + inspecao", arte1_total_started_at)
                self.safe_log(f"[INSPECAO] Arte 1 resultado={'OK' if frontal_ok else 'NG'}")
                self.log_clp_snapshot("apos gravacao/inspecao Arte 1 antes M1510")

                self.set_status("Avisando CLP: Arte 1 gravada/inspecionada (M1510)...")
                m1510_started_at = time.perf_counter()
                consumed_1 = self.signal_command_until_ack(
                    AUTO_MEM_GRAVACAO_INSPECAO_1,
                    "Gravacao + inspecao lado 1 concluida",
                    AUTO_MEM_PRONTO_GRAVACAO,
                    False,
                    "M1500 consumido apos Arte 1",
                )
                self.log_tempo("Handshake M1510 ate M1500 FALSE", m1510_started_at)
                if not self.running:
                    break
                self.safe_log(f"[HANDSHAKE] M1500 FALSE apos Arte 1: valor={consumed_1}")

                after_1510_s = max(float(self.var_after_rotate_s.get()), 0.0)
                if after_1510_s:
                    self.safe_log(f"Aguardando {after_1510_s:.2f}s apos ACK M1510.")
                    timer_started_at = time.perf_counter()
                    time.sleep(after_1510_s)
                    self.log_tempo("Timer apos M1510 antes Arte 2", timer_started_at)

                self.log_clp_snapshot("antes da Arte 2 apos espera M1510")
                self.set_status("Gravando Arte 2 apos timer M1510...")
                self.safe_log("[HANDSHAKE] M1500 nao sera aguardado para Arte 2; usando timer apos M1510 como liberacao.")

                arte2_total_started_at = time.perf_counter()
                traseira_ok = self.mark_one_arte_with_inspection(prebuild, "arte2", "Arte 2")
                self.log_tempo("Arte 2 total gravacao + espera camera + inspecao", arte2_total_started_at)
                self.safe_log(f"[INSPECAO] Arte 2 resultado={'OK' if traseira_ok else 'NG'}")
                self.log_clp_snapshot("apos gravacao/inspecao Arte 2 antes resultado/M1511")

                aprovado = frontal_ok and traseira_ok
                self.safe_log(f"[RESULTADO] frontal_ok={frontal_ok} traseira_ok={traseira_ok} aprovado={aprovado}")
                self.log_clp_snapshot("antes de liberar resultado final")
                clear_result_started_at = time.perf_counter()
                self.clear_result_signals_before_new_result("novo resultado final")
                self.log_tempo("Limpeza resultado anterior antes novo OK/NG", clear_result_started_at)
                result_started_at = time.perf_counter()
                if aprovado:
                    self.set_status("Liberando resultado OK em M1120 antes do M1511...")
                    self.write_mem(AUTO_MEM_RESULT_NG, False)
                    self.write_mem(AUTO_MEM_RESULT_OK, True)
                    self.safe_log("Resultado preparado. Inspecoes OK; M1120 ligado como aprovado antes do M1511.")
                    inspecao = "Aprovado"
                else:
                    self.set_status("Liberando resultado NG em M1116 antes do M1511...")
                    self.write_mem(AUTO_MEM_RESULT_OK, False)
                    self.write_mem(AUTO_MEM_RESULT_NG, True)
                    self.safe_log("Resultado preparado. Uma ou mais inspecoes reprovaram; M1116 ligado como NG antes do M1511.")
                    inspecao = "Reprovado"
                self.log_tempo("Escrita resultado OK/NG no CLP", result_started_at)
                self.log_clp_snapshot(f"resultado {inspecao} ativo antes M1511")

                self.set_status("Avisando CLP: Arte 2 gravada/inspecionada (M1511) com resultado ativo...")
                m1511_started_at = time.perf_counter()
                self.pulse_command_mem(AUTO_MEM_GRAVACAO_INSPECAO_2, "Gravacao + inspecao lado 2 concluida")
                self.log_tempo("Pulso M1511 com resultado ativo", m1511_started_at)
                if not self.running:
                    break

                after_1511_s = max(float(self.var_after_return_s.get()), 0.0)
                if after_1511_s:
                    self.safe_log(f"Aguardando {after_1511_s:.2f}s apos M1511 mantendo resultado ativo.")
                    timer_started_at = time.perf_counter()
                    time.sleep(after_1511_s)
                    self.log_tempo("Timer apos M1511 com resultado ativo", timer_started_at)

                self.safe_log(f"Ciclo concluido. Resultado final {inspecao} mantido ativo.")
                self.log_clp_snapshot(f"resultado final liberado {inspecao}")
                if AUTO_RESULT_HOLD_S > 0:
                    hold_started_at = time.perf_counter()
                    self.safe_log(f"[RESULTADO] Mantendo {inspecao} ativo por {AUTO_RESULT_HOLD_S:.2f}s para o CLP/robo consumir.")
                    time.sleep(AUTO_RESULT_HOLD_S)
                    self.log_tempo(f"Resultado {inspecao} mantido antes proximo ciclo", hold_started_at)
                    self.log_clp_snapshot(f"apos hold resultado {inspecao}")
                if hasattr(self.app, "add_dashboard_record"):
                    self.app.add_dashboard_record(serial, frontal_ok, traseira_ok, inspecao)
                finish_serial_started_at = time.perf_counter()
                self.finish_cycle_serial()
                self.log_tempo("Finalizacao serial/banco/dashboard", finish_serial_started_at)

                self.set_status("Aguardando M1500 desligar para evitar repetir a mesma peca...")
                final_release_started_at = time.perf_counter()
                final_release = self.wait_mem_false(AUTO_MEM_PRONTO_GRAVACAO, "M1500 liberacao novo ciclo")
                self.log_tempo("Espera M1500 FALSE fim ciclo", final_release_started_at)
                self.safe_log(f"[HANDSHAKE] M1500 FALSE liberacao novo ciclo: valor={final_release}")
                self.log_clp_snapshot("fim ciclo pronto para proxima peca")
                self.log_tempo("Ciclo completo", cycle_started_at)
        except Exception as exc:
            self.safe_log(f"Erro na rotina: {exc}")
            self.set_status("Erro")
        finally:
            self.camera_disconnect()
            self.running = False
            self.after(0, self.update_auto_button_state)
            if self.var_status.get() != "Erro":
                self.set_status("Parado")
            self.safe_log("Rotina automatica parada.")

    def resolve_step_preset(self, selected_name, suffix):
        if selected_name == "Arte 1 + 2 (Frontal + Traseira)":
            resolved = AUTO_PRESET_ARTE_1 if suffix == "arte1" else AUTO_PRESET_ARTE_2
            self.safe_log(f"Preset combinado selecionado em {suffix}; usando {resolved} para gravar separado.")
            return resolved
        return selected_name

    def _record_id_key(self, record):
        if not record:
            return None
        try:
            return str(record["id"])
        except Exception:
            return None

    def pop_prebuilt_jobs_for_current(self, serial):
        if self.var_test_mode.get():
            with self.test_prebuild_lock:
                ctx = self.test_prebuilt_jobs.pop(serial, None)
            if ctx is None:
                self.safe_log(f"[PREBUILD-TESTE] Sem job antecipado para serial {serial}; gerando no ciclo.")
                return None
            self.safe_log(f"[PREBUILD-TESTE] Usando job antecipado do modo teste para serial {serial}.")
            return ctx

        record_key = self._record_id_key(self.current_record)
        if not record_key:
            return None
        with self.db_prebuild_lock:
            ctx = self.db_prebuilt_jobs.pop(record_key, None)
        if ctx is None:
            self.safe_log(f"[PREBUILD-FILA] Sem job antecipado para serial {serial}; gerando agora.")
            return None
        self.safe_log(f"[PREBUILD-FILA] Usando job antecipado do banco para serial {serial} (ID {record_key}).")
        return ctx

    def start_test_prebuild_queue(self):
        if not self.var_test_mode.get() or not self.running:
            return
        with self.test_prebuild_lock:
            if self.test_prebuild_worker_running:
                return
            self.test_prebuild_worker_running = True
        self.safe_log(f"[PREBUILD-TESTE] Worker iniciado para gerar os {len(self.test_serial_cycle)} seriais do modo teste.")
        threading.Thread(target=self._test_prebuild_queue_worker, daemon=True).start()

    def _test_prebuild_queue_worker(self):
        try:
            while self.running and self.var_test_mode.get():
                selected = None
                with self.test_prebuild_lock:
                    for serial in self.test_serial_cycle:
                        if serial in self.test_prebuild_started or serial in self.test_prebuilt_jobs or serial in self.test_prebuild_building:
                            continue
                        self.test_prebuild_started.add(serial)
                        self.test_prebuild_building.add(serial)
                        selected = serial
                        break

                if selected is None:
                    time.sleep(0.5)
                    continue

                serial = selected
                started_at = time.perf_counter()
                self.safe_log(f"[PREBUILD-TESTE] Gerando antecipado serial {serial}.")
                ctx = self.start_prebuild_jobs(serial)
                ctx["serial"] = serial
                ctx["prebuild_started_at"] = started_at
                with self.test_prebuild_lock:
                    self.test_prebuilt_jobs[serial] = ctx

                try:
                    ctx["ready"]["arte1"].wait()
                    if "arte1" in ctx["errors"]:
                        raise ctx["errors"]["arte1"]
                    self.log_tempo(f"PREBUILD-TESTE arte1 pronta serial {serial}", started_at)

                    ctx["ready"]["arte2"].wait()
                    if "arte2" in ctx["errors"]:
                        raise ctx["errors"]["arte2"]
                    self.log_tempo(f"PREBUILD-TESTE arte1+arte2 prontas serial {serial}", started_at)
                except Exception as exc:
                    self.safe_log(f"[PREBUILD-TESTE] Falha ao gerar antecipado serial {serial}: {exc}")
                    with self.test_prebuild_lock:
                        if self.test_prebuilt_jobs.get(serial) is ctx:
                            self.test_prebuilt_jobs.pop(serial, None)
                finally:
                    with self.test_prebuild_lock:
                        self.test_prebuild_building.discard(serial)
        except Exception as exc:
            self.safe_log(f"[PREBUILD-TESTE] Worker parou por erro: {exc}")
        finally:
            with self.test_prebuild_lock:
                self.test_prebuild_worker_running = False

    def start_db_prebuild_queue(self):
        if self.var_test_mode.get() or not self.var_use_db_auto_sync.get() or not self.running:
            return
        with self.db_prebuild_lock:
            if self.db_prebuild_worker_running:
                return
            self.db_prebuild_worker_running = True
        self.safe_log(f"[PREBUILD-FILA] Worker continuo iniciado; mantendo ate {self.db_prebuild_max} seriais prontos.")
        threading.Thread(target=self._db_prebuild_queue_worker, daemon=True).start()

    def start_db_prebuild_queue_after_current_jobs(self, current_ctx):
        if self.var_test_mode.get() or not self.var_use_db_auto_sync.get():
            return

        def _wait_current_then_start():
            try:
                self.safe_log("[PREBUILD-FILA] Fila do banco aguardando jobs atuais prontos antes de buscar proximos seriais.")
                current_ctx["ready"]["arte1"].wait()
                current_ctx["ready"]["arte2"].wait()
                if not self.running:
                    return
                self.safe_log("[PREBUILD-FILA] Jobs atuais prontos. Worker do banco liberado para encher buffer.")
                self.start_db_prebuild_queue()
            except Exception as exc:
                self.safe_log(f"[PREBUILD-FILA] Erro ao liberar fila apos jobs atuais: {exc}")

        threading.Thread(target=_wait_current_then_start, daemon=True).start()

    def _db_prebuild_queue_worker(self):
        try:
            while self.running and self.var_use_db_auto_sync.get() and not self.var_test_mode.get():
                selected = None
                current_key = self._record_id_key(self.current_record)
                try:
                    pending = list(self.get_pending_serials_safe() or [])
                except Exception as exc:
                    self.safe_log(f"[PREBUILD-FILA] Erro lendo banco para antecipar jobs: {exc}")
                    time.sleep(2.0)
                    continue

                with self.db_prebuild_lock:
                    buffered = len(self.db_prebuilt_jobs)
                    if buffered < self.db_prebuild_max:
                        for record in pending:
                            record_key = self._record_id_key(record)
                            if not record_key or record_key == current_key:
                                continue
                            if record_key in self.db_prebuilt_jobs or record_key in self.db_prebuild_building_ids:
                                continue
                            serial = str(record["serial"])
                            self.db_prebuild_building_ids.add(record_key)
                            selected = (record, record_key, serial)
                            break

                if selected is None:
                    time.sleep(0.5)
                    continue

                record, record_key, serial = selected
                started_at = time.perf_counter()
                self.safe_log(f"[PREBUILD-FILA] Gerando antecipado serial {serial} (ID {record_key}); buffer atual={len(self.db_prebuilt_jobs)}/{self.db_prebuild_max}.")
                ctx = self.start_prebuild_jobs(serial)
                ctx["db_record"] = record
                ctx["serial"] = serial
                ctx["prebuild_started_at"] = started_at
                with self.db_prebuild_lock:
                    self.db_prebuilt_jobs[record_key] = ctx

                try:
                    ctx["ready"]["arte1"].wait()
                    if "arte1" in ctx["errors"]:
                        raise ctx["errors"]["arte1"]
                    self.log_tempo(f"PREBUILD-FILA arte1 pronta serial {serial}", started_at)

                    ctx["ready"]["arte2"].wait()
                    if "arte2" in ctx["errors"]:
                        raise ctx["errors"]["arte2"]
                    self.log_tempo(f"PREBUILD-FILA arte1+arte2 prontas serial {serial}", started_at)
                except Exception as exc:
                    self.safe_log(f"[PREBUILD-FILA] Falha ao gerar antecipado serial {serial}: {exc}")
                    with self.db_prebuild_lock:
                        if self.db_prebuilt_jobs.get(record_key) is ctx:
                            self.db_prebuilt_jobs.pop(record_key, None)
                finally:
                    with self.db_prebuild_lock:
                        self.db_prebuild_building_ids.discard(record_key)
        except Exception as exc:
            self.safe_log(f"[PREBUILD-FILA] Worker parou por erro: {exc}")
        finally:
            with self.db_prebuild_lock:
                self.db_prebuild_worker_running = False

    def start_prebuild_jobs(self, serial=None):
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
                ctx["jobs"][suffix] = self.build_laser_job(preset_name, suffix, serial_override=serial)
            except Exception as exc:
                ctx["errors"][suffix] = exc
            finally:
                ctx["ready"][suffix].set()

        def _build_priority_order():
            self.safe_log("Pre-gerando job arte1 com prioridade; arte2 entra depois para nao atrasar inicio da gravacao.")
            _build_job("arte1", preset_arte1)
            if self.running:
                self.safe_log("Job arte1 pronto/liberado. Gerando arte2 em segundo plano.")
                _build_job("arte2", preset_arte2)
            else:
                ctx["ready"]["arte2"].set()

        threading.Thread(target=_build_priority_order, daemon=True).start()
        return ctx

    def wait_prebuilt_job(self, ctx, suffix):
        wait_started_at = time.perf_counter()
        if not ctx["ready"][suffix].is_set():
            self.set_status(f"Aguardando job {suffix} ficar pronto...")
            self.safe_log(f"Aguardando pre-geracao da {suffix} terminar.")
        ctx["ready"][suffix].wait()
        self.log_tempo(f"{suffix} espera prebuild pronto", wait_started_at)
        if suffix in ctx["errors"]:
            raise ctx["errors"][suffix]
        return ctx["jobs"][suffix], ctx["presets"][suffix]

    def mark_one_arte_with_inspection(self, prebuild, suffix, label):
        total_started_at = time.perf_counter()
        commands, preset_name = self.wait_prebuilt_job(prebuild, suffix)
        self.set_status(f"Gravando {label}...")
        laser_started_at = time.perf_counter()
        self.execute_laser_job(commands, preset_name, suffix)
        self.log_tempo(f"{label} execute_laser_job total", laser_started_at)
        camera_wait_started_at = time.perf_counter()
        self.wait_before_camera_trigger(label)
        self.log_tempo(f"{label} espera antes trigger camera", camera_wait_started_at)
        inspection_started_at = time.perf_counter()
        result = self.trigger_camera_inspection(label)
        self.log_tempo(f"{label} trigger + resposta camera", inspection_started_at)
        self.log_tempo(f"{label} mark_one_arte_with_inspection total", total_started_at)
        return result

    def mark_both_artes(self, prebuild=None):
        if prebuild is None:
            self.set_status("Pre-gerando jobs Arte 1 e Arte 2...")
            prebuild = self.start_prebuild_jobs()
        frontal_ok = self.mark_one_arte_with_inspection(prebuild, "arte1", "Arte 1")
        traseira_ok = self.mark_one_arte_with_inspection(prebuild, "arte2", "Arte 2")
        return frontal_ok, traseira_ok

    def mark_preset(self, preset_name, suffix):
        commands = self.build_laser_job(preset_name, suffix)
        self.execute_laser_job(commands, preset_name, suffix)

    def make_job_cache_key(self, preset_name, suffix, serial, preset):
        try:
            preset_signature = json.dumps(preset, sort_keys=True, ensure_ascii=True)
        except TypeError:
            preset_signature = str(sorted(preset.items()))
        cal_signature = None
        if os.path.exists("cal_0002.csv"):
            try:
                cal_signature = os.path.getmtime("cal_0002.csv")
            except OSError:
                cal_signature = "erro_mtime"
        return (preset_name, suffix, serial, preset_signature, cal_signature)

    def job_cache_file_path(self, cache_key, suffix):
        digest = hashlib.sha256(repr(cache_key).encode("utf-8", errors="replace")).hexdigest()
        return os.path.join(self.job_cache_dir, f"{suffix}_{digest}.bin")

    def get_cached_job_data(self, cache_key, suffix):
        with self.job_cache_lock:
            cached = self.job_cache.get(cache_key)
            if cached is not None:
                self.safe_log(f"[CACHE] HIT memoria job {suffix} / bin={len(cached)} bytes")
                return cached

            cache_file = self.job_cache_file_path(cache_key, suffix)
            if os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cached = f.read()
                self.job_cache[cache_key] = cached
                self.safe_log(f"[CACHE] HIT disco job {suffix} / bin={len(cached)} bytes")
                return cached

            self.safe_log(f"[CACHE] MISS job {suffix}; gerando binario novo.")
            return None

    def store_cached_job_data(self, cache_key, suffix, job_data):
        with self.job_cache_lock:
            if cache_key in self.job_cache:
                self.job_cache[cache_key] = job_data
            else:
                if len(self.job_cache) >= self.job_cache_max:
                    oldest_key = next(iter(self.job_cache))
                    self.job_cache.pop(oldest_key, None)
                    self.safe_log("[CACHE] Cache de jobs em memoria cheio; removi o job mais antigo.")
                self.job_cache[cache_key] = job_data

            os.makedirs(self.job_cache_dir, exist_ok=True)
            cache_file = self.job_cache_file_path(cache_key, suffix)
            with open(cache_file, "wb") as f:
                f.write(job_data)
            self.safe_log(f"[CACHE] Job {suffix} salvo no cache / bin={len(job_data)} bytes")

    def build_laser_job(self, preset_name, suffix, serial_override=None, use_cache=True):
        preset = self.presets.get(preset_name)
        if not preset:
            raise RuntimeError(f"Preset não encontrado: {preset_name}")

        import barcode_module
        import balor.command_list
        import composer_module

        serial = str(serial_override).strip() if serial_override is not None else self.var_serial.get().strip()
        serial = serial or "TESTE123"
        total_started_at = time.perf_counter()
        cache_key = self.make_job_cache_key(preset_name, suffix, serial, preset)
        if use_cache:
            cached_job_data = self.get_cached_job_data(cache_key, suffix)
            if cached_job_data is not None:
                parse_started_at = time.perf_counter()
                command_binary = balor.command_list.CommandBinary(cached_job_data)
                self.log_tempo(f"{suffix} parse CommandBinary cache", parse_started_at)
                self.log_tempo(f"{suffix} build_laser_job total cache", total_started_at)
                return command_binary
        else:
            self.safe_log(f"[CACHE] BYPASS job {suffix}; teste forcando geracao nova.")

        raw_svg_file = f"temp_auto_{suffix}_raw.svg"
        svg_file = f"temp_auto_{suffix}.svg"
        job_file = f"temp_auto_{suffix}.bin"
        settings_file = f"temp_auto_{suffix}_settings.csv"

        gen_started_at = time.perf_counter()
        gen = barcode_module.BarcodeGenerator(font_path=preset.get("text_font", "arial.ttf"))
        gen.generate_code128_svg(
            serial,
            raw_svg_file,
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
        self.log_tempo(f"{suffix} SVG bruto barcode/texto", gen_started_at)

        ox = float(preset.get("offset_x", "0.0"))
        oy = float(preset.get("offset_y", "0.0"))
        sc = float(preset.get("scale", "1.0"))
        base_id = "base_1" if suffix == "arte1" else ("base_2" if suffix == "arte2" else suffix)
        compose_started_at = time.perf_counter()
        composer_module.SceneComposer.compose_workspace([
            {
                "id": base_id,
                "file": raw_svg_file,
                "ox": ox,
                "oy": oy,
                "sx": sc,
                "sy": sc,
                "rot": 0.0,
                "z": 10,
                "color": "",
                "visible": True,
                "preserve_ids": False,
            }
        ], svg_file)
        self.log_tempo(f"{suffix} Composer posicao/escala", compose_started_at)

        hatch_spacing = preset.get("hatch_spacing", "10.0") if preset.get("hatch_enable", True) else "0"
        settings_started_at = time.perf_counter()
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(f"000000 {preset.get('freq', '60')} {preset.get('power', '25')} {preset.get('speed', '3500')} {preset.get('hatch_angle', '90')} {hatch_spacing} None 1\n")
        self.log_tempo(f"{suffix} CSV parametros laser", settings_started_at)

        cmd = [
            sys.executable, "balor-svg.py", "mark",
            "-f", svg_file,
            "-o", job_file,
            "--xoff", "0.0",
            "--yoff", "0.0",
            "--xscale", "1.0",
            "--yscale", "1.0",
            "-s", settings_file,
            "--laser-on-delay", "0",
            "--laser-off-delay", "0",
            "--mark-end-delay", "0",
            "--polygon-delay", "50",
            "--hatch-power-scale", "0.90",
            "--hatch-speed-scale", "2.00",
            "--hatch-overrun", "0.00",
            "--hatch-serpentine",
            "--quiet",
        ]
        if os.path.exists("cal_0002.csv"):
            cmd.extend(["-c", "cal_0002.csv"])

        self.safe_log(
            f"Gerando job {suffix}: {preset_name} / serial {serial} / "
            f"pos X={ox:.4f} Y={oy:.4f} / power={preset.get('power', '25')} "
            f"speed={preset.get('speed', '3500')} freq={preset.get('freq', '60')} "
            f"hatch={hatch_spacing}"
        )
        job_started_at = time.perf_counter()
        result = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        job_elapsed = time.perf_counter() - job_started_at
        stderr_len = len(result.stderr or "")
        job_size = os.path.getsize(job_file) if os.path.exists(job_file) else 0
        self.safe_log(f"Job {suffix} gerado em {job_elapsed:.2f}s / bin={job_size} bytes / stderr={stderr_len} chars")

        read_started_at = time.perf_counter()
        with open(job_file, "rb") as f:
            job_data = f.read()
        self.log_tempo(f"{suffix} leitura job binario", read_started_at)
        if use_cache:
            self.store_cached_job_data(cache_key, suffix, job_data)
        else:
            self.safe_log(f"[CACHE] BYPASS job {suffix}; binario gerado nao foi salvo no cache.")

        parse_started_at = time.perf_counter()
        command_binary = balor.command_list.CommandBinary(job_data)
        self.log_tempo(f"{suffix} parse CommandBinary", parse_started_at)
        self.log_tempo(f"{suffix} build_laser_job total", total_started_at)
        return command_binary

    def execute_laser_job(self, commands, preset_name, suffix):
        import balor.sender

        machine = balor.sender.Sender()
        self.last_laser_ok = False
        total_started_at = time.perf_counter()
        try:
            self.safe_log("Abrindo conexao USB da laser...")
            open_started_at = time.perf_counter()
            if not machine.open(machine_index=0):
                raise RuntimeError("Nao foi possivel abrir a placa laser.")
            self.log_tempo(f"Laser {suffix} abertura USB", open_started_at)
            self.safe_log(f"Laser pronto para executar {suffix}: {preset_name}")

            execute_started_at = time.perf_counter()
            self.safe_log(f"[TEMPO] Laser {suffix} execute() chamado; daqui ate retorno e gravacao fisica bloqueante.")
            machine.execute(command_list=commands, loop_count=1)
            self.log_tempo(f"Laser {suffix} execute() bloqueante", execute_started_at)
            self.last_laser_ok = True
            self.safe_log(f"Laser finalizou {suffix}: {preset_name}")
        finally:
            close_started_at = time.perf_counter()
            try:
                machine.close()
            except Exception:
                pass
            self.log_tempo(f"Laser {suffix} fechamento USB", close_started_at)
            self.log_tempo(f"Laser {suffix} total abrir + executar + fechar", total_started_at)



    def camera_is_connected(self):
        return self.camera_sock is not None

    def wait_before_camera_trigger(self, label):
        self.set_status(f"Aguardando fumaca dissipar antes da inspecao {label}...")
        self.safe_log(f"Camera {label}: aguardando {CAMERA_AFTER_MARK_DELAY_S:.1f}s antes do trigger.")
        started_at = time.perf_counter()
        time.sleep(CAMERA_AFTER_MARK_DELAY_S)
        self.log_tempo(f"Camera {label} timer fumaca", started_at)

    def camera_disconnect(self):
        if self.camera_sock:
            try:
                self.camera_sock.close()
            except Exception:
                pass
        self.camera_sock = None
        if hasattr(self.app, "camera_connected"):
            self.app.camera_connected = False

    def camera_connect(self):
        if self.camera_is_connected():
            self.safe_log("Camera: conexao ja aberta, reutilizando socket.")
            return True
        try:
            connect_started_at = time.perf_counter()
            self.safe_log(f"Camera: conectando em {KEYENCE_IP}:{KEYENCE_PORT}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(KEYENCE_TIMEOUT_S)
            sock.connect((KEYENCE_IP, KEYENCE_PORT))
            self.camera_sock = sock
            if hasattr(self.app, "camera_connected"):
                self.app.camera_connected = True
            self.safe_log("Camera: conectada.")
            self.log_tempo("Camera conectar TCP", connect_started_at)
            return True
        except Exception as exc:
            self.camera_disconnect()
            self.safe_log(f"Camera: falha ao conectar ({type(exc).__name__}: {exc})")
            return False

    def camera_clear_buffer(self):
        sock = self.camera_sock
        if not sock:
            return
        sock.setblocking(False)
        try:
            while True:
                chunk = sock.recv(KEYENCE_RECV_CHUNK)
                if not chunk:
                    break
        except BlockingIOError:
            pass
        finally:
            sock.setblocking(True)
            sock.settimeout(KEYENCE_TIMEOUT_S)

    def camera_recv_packet(self):
        sock = self.camera_sock
        chunks = []
        deadline = time.monotonic() + KEYENCE_TIMEOUT_S
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout()
            sock.settimeout(min(remaining, KEYENCE_IDLE_GRACE_S if chunks else remaining))
            try:
                chunk = sock.recv(KEYENCE_RECV_CHUNK)
            except socket.timeout:
                if chunks:
                    break
                raise
            if not chunk:
                self.camera_disconnect()
                raise ConnectionError("camera fechou a conexao")
            chunks.append(chunk)
            if b"\r" in chunk or b"\n" in chunk:
                break
        sock.settimeout(KEYENCE_TIMEOUT_S)
        return b"".join(chunks)

    def parse_camera_response(self, data):
        response = data.decode("ascii", errors="ignore").replace("\x00", "").strip()
        parts = response.replace("\r", "").replace("\n", "").split(",")
        result = "PASS" if parts and parts[0].strip() == "1" else "FAIL"
        serial = parts[1].strip() if len(parts) >= 2 else ""
        if serial == "0":
            serial = ""
        return result, serial, response

    def trigger_camera_inspection(self, label):
        self.set_status(f"Inspecionando {label}...")
        total_started_at = time.perf_counter()
        if not self.camera_connect():
            self.safe_log(f"Camera {label}: FAIL por falha de conexao.")
            self.log_tempo(f"Camera {label} trigger total falha conexao", total_started_at)
            return False
        try:
            clear_started_at = time.perf_counter()
            self.camera_clear_buffer()
            self.log_tempo(f"Camera {label} limpar buffer", clear_started_at)

            send_started_at = time.perf_counter()
            self.safe_log(f"Camera {label}: enviando trigger.")
            self.camera_sock.sendall(KEYENCE_TRIGGER_CMD)
            self.log_tempo(f"Camera {label} envio trigger", send_started_at)

            recv_started_at = time.perf_counter()
            while True:
                data = self.camera_recv_packet()
                probe = data.decode("ascii", errors="ignore").replace("\x00", "").strip()
                if "," in probe:
                    break
                self.safe_log(f"Camera {label}: retorno sem resultado ignorado: {probe!r}")
            self.log_tempo(f"Camera {label} espera resposta", recv_started_at)

            parse_started_at = time.perf_counter()
            result, serial, raw = self.parse_camera_response(data)
            ok = result == "PASS"
            self.log_tempo(f"Camera {label} parse resposta", parse_started_at)
            self.safe_log(f"Camera {label}: {result} serial={serial or '-'} raw={raw!r}")
            self.log_tempo(f"Camera {label} trigger total", total_started_at)
            return ok
        except Exception as exc:
            self.camera_disconnect()
            self.safe_log(f"Camera {label}: FAIL ({type(exc).__name__}: {exc})")
            self.log_tempo(f"Camera {label} trigger total erro", total_started_at)
            return False
    def refresh_status_loop(self):
        def _task():
            values = []
            for mem in (AUTO_MEM_PRONTO_GRAVACAO, AUTO_MEM_SENSOR_ESTEIRA, AUTO_MEM_RESULT_NG, AUTO_MEM_RESULT_OK):
                try:
                    values.append(self.read_mem(mem))
                except Exception:
                    values.append("---")
            self.after(0, lambda: self.apply_status_values(values))
        threading.Thread(target=_task, daemon=True).start()

    def apply_status_values(self, values):
        self.var_m1500.set(values[0])
        self.var_m1110.set(values[1])
        self.var_m1116.set(values[2])
        self.var_m1120.set(values[3])
        self.after(1000, self.refresh_status_loop)
