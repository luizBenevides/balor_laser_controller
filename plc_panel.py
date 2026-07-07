import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import threading
import time
from pyModbusTCP.client import ModbusClient
from rotina_automatica_page import RotinaAutomaticaPage
from dashboard_page import DashboardPage

CONFIG_FILE = "plc_config.json"
DEFAULT_MODBUS_SLAVE_ID = 1

class ModbusDevice:
    """
    Classe base para comunicação com qualquer dispositivo Modbus TCP.
    """
    def __init__(self, name, ip, port=502, unit_id=DEFAULT_MODBUS_SLAVE_ID):
        self.name = name
        self.ip = ip
        self.port = port
        self.unit_id = int(unit_id)
        self.client = None
        self.is_connected = False
        self.lock = threading.RLock()

    def connect(self):
        with self.lock:
            self.disconnect()
            port = int(self.port)

            last_error = None
            for port in [port]:
                client = None
                try:
                    print(f"[MODBUS - {self.name}] Tentando abrir conexao com {self.ip}:{port} slave_id={self.unit_id}...")
                    client = ModbusClient(host=self.ip, port=port, unit_id=self.unit_id, auto_open=False, timeout=1.0)
                    if client.open():
                        self.client = client
                        self.port = port
                        self.is_connected = True
                        print(f"[MODBUS - {self.name}] Sucesso! Conectado a: {self.ip}:{port}")
                        return True, f"Conectado ({self.ip}:{port}, slave {self.unit_id})"
                    last_error = f"Conexao recusada ({self.ip}:{port})"
                except Exception as e:
                    last_error = str(e)
                    print(f"[MODBUS - {self.name}] Erro ao conectar em {self.ip}:{port}: {e}")
                finally:
                    if client is not None and not self.is_connected:
                        try:
                            client.close()
                        except Exception:
                            pass
                time.sleep(0.2)

            self.is_connected = False
            self.client = None
            return False, last_error or f"Conexao recusada ({self.ip}:{self.port})"

    def disconnect(self):
        with self.lock:
            if self.client:
                try:
                    print(f"[MODBUS - {self.name}] Fechando conexão...")
                    self.client.close()
                except Exception as e:
                    print(f"[MODBUS - {self.name}] Erro ao fechar: {e}")
                finally:
                    self.client = None
            self.is_connected = False

    def _modbus_status(self):
        if not self.client:
            return ""
        parts = []
        for attr_name in ("last_error_as_txt", "last_except_as_txt", "last_error", "last_except"):
            try:
                attr = getattr(self.client, attr_name, None)
                if attr is None:
                    continue
                value = attr() if callable(attr) else attr
                if value:
                    parts.append(f"{attr_name}={value}")
            except Exception:
                pass
        return " | ".join(parts)

    def send_write(self, memory_address, value=True):
        with self.lock:
            if not self.is_connected or not self.client:
                return False, "Não conectado"
            try:
                addr = int(memory_address)
                val_int = 1 if value else 0

                if addr >= 40000:
                    reg_addr = addr - 40000 if addr > 40000 else addr
                    success = self.client.write_single_register(reg_addr, val_int)
                else:
                    print(f"[MODBUS WRITE - {self.name}] Tentando Coil no endereço {addr}...")
                    success = self.client.write_single_coil(addr, value)

                    if not success and self.name.startswith("Rob"):
                        print(f"[MODBUS WRITE - {self.name}] Coil falhou. Tentando como Register no {addr}...")
                        success = self.client.write_single_register(addr, val_int)

                if success:
                    print(f"[MODBUS WRITE - {self.name}] Sucesso no endereço {addr}!")
                    return True, "Escrita OK"

                detail = self._modbus_status()
                print(f"[MODBUS WRITE ERROR - {self.name}] Ambas tentativas (Coil/Register) falharam no endereco {addr}. {detail}")
                return False, f"Falha na escrita ({detail})" if detail else "Falha na escrita"
            except Exception as e:
                return False, str(e)

    def send_read(self, memory_address):
        with self.lock:
            if not self.is_connected or not self.client:
                return False, "Não conectado"
            try:
                addr = int(memory_address)

                if addr >= 40000:
                    reg_addr = addr - 40000 if addr > 40000 else addr
                    result = self.client.read_holding_registers(reg_addr, 1)
                elif addr >= 30000:
                    reg_addr = addr - 30000 if addr > 30000 else addr
                    result = self.client.read_input_registers(reg_addr, 1)
                elif addr >= 10000:
                    reg_addr = addr - 10000 if addr > 10000 else addr
                    result = self.client.read_discrete_inputs(reg_addr, 1)
                else:
                    result = self.client.read_coils(addr, 1)

                    if result is None and self.name.startswith("Rob"):
                        print(f"[MODBUS READ - {self.name}] Coil {addr} falhou. Tentando Holding Register...")
                        result = self.client.read_holding_registers(addr, 1)
                        if result is None:
                            print(f"[MODBUS READ - {self.name}] Holding falhou. Tentando Input Register...")
                            result = self.client.read_input_registers(addr, 1)

                if result is not None:
                    return True, str(result[0])

                detail = self._modbus_status()
                return False, f"Falha na leitura ({detail})" if detail else "Falha na leitura"
            except Exception as e:
                return False, str(e)


class PLCPanelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Painel de Controle Mestre - CLP e Robô (Modbus TCP)")
        self.root.geometry("1000x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 1. Carrega dados do JSON ANTES de tudo
        self.config_data = self.load_config_data()

        self.dev_clp = None
        self.dev_robo = None
        self.polling_active = False
        self.current_page = None

        self.camera_connected = False
        # Variáveis Conexão
        self.var_ip_clp = tk.StringVar(value=self.config_data.get("ip_clp", "192.168.1.5"))
        self.var_port_clp = tk.StringVar(value=self.config_data.get("port_clp", "502"))

        self.var_ip_robo = tk.StringVar(value=self.config_data.get("ip_robo", "192.168.1.8"))
        self.var_port_robo = tk.StringVar(value=self.config_data.get("port_robo", "502"))

        
        # 3. Estruturas Dinâmicas
        self.action_items = {}
        self.action_counter = 0
        self.status_items = {}
        self.status_counter = 0

        # 4. Constrói UI e Restaura Itens
        self.build_ui()
        self.restore_dynamic_items()

    def on_close(self):
        self.polling_active = False
        self.current_page = None
        self.camera_connected = False
        if self.dev_clp:
            self.dev_clp.disconnect()
        if self.dev_robo:
            self.dev_robo.disconnect()
        self.root.destroy()

    def load_config_data(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao carregar config: {e}")
        return {}

    def save_config(self):
        actions_data = []
        for uid, item in self.action_items.items():
            actions_data.append({
                "name": item["name_var"].get(),
                "mem": item["mem_var"].get(),
                "tgt": item["tgt_var"].get()
            })
            
        status_data = []
        for uid, item in self.status_items.items():
            status_data.append({
                "name": item["name_var"].get(),
                "mem": item["mem_var"].get(),
                "tgt": item["tgt_var"].get()
            })

        data = {
            "ip_clp": self.var_ip_clp.get(),
            "port_clp": self.var_port_clp.get(),
            "ip_robo": self.var_ip_robo.get(),
            "port_robo": self.var_port_robo.get(),
            "actions": actions_data,
            "statuses": status_data
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Sucesso", "Configurações salvas!")
            self.log("Configurações salvas no arquivo JSON.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar:\n{e}")

    def restore_dynamic_items(self):
        actions = self.config_data.get("actions", [])
        statuses = self.config_data.get("statuses", [])

        for act in actions:
            self.add_action_row(act["name"], act["mem"], act["tgt"])
            
        for st in statuses:
            self.add_status_row(st["name"], st["mem"], st["tgt"])

    def build_ui(self):
        self.style = ttk.Style()
        self.style.configure("ToggleOff.TButton", font=("Arial", 11, "bold"), foreground="black")
        self.style.configure("ToggleOn.TButton", font=("Arial", 11, "bold"), foreground="white", background="red")

        self.nav_frame = ttk.Frame(self.root)
        self.nav_frame.pack(fill="x", padx=10, pady=(8, 0))
        ttk.Button(self.nav_frame, text="Painel Manual", command=self.show_manual_page).pack(side="left", padx=(0, 5))
        ttk.Button(self.nav_frame, text="Rotina Automática", command=self.show_auto_page).pack(side="left", padx=5)
        ttk.Button(self.nav_frame, text="Dashboard", command=self.show_dashboard_page).pack(side="left", padx=5)

        self.page_container = ttk.Frame(self.root)
        self.page_container.pack(fill="both", expand=True)

        self.manual_page = ttk.Frame(self.page_container)
        self.auto_page = RotinaAutomaticaPage(self.page_container, self)
        self.dashboard_page = DashboardPage(self.page_container, self)

        header_frame = ttk.Frame(self.manual_page)
        header_frame.pack(fill="x", padx=10, pady=5)
        header_frame.columnconfigure(0, weight=1)
        header_frame.columnconfigure(1, weight=1)

        clp_frame = ttk.LabelFrame(header_frame, text="Conexão CLP (Delta)", padding=10)
        clp_frame.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        ttk.Label(clp_frame, text="IP:").pack(side="left")
        ttk.Entry(clp_frame, textvariable=self.var_ip_clp, width=13).pack(side="left", padx=5)
        ttk.Label(clp_frame, text="Port:").pack(side="left")
        ttk.Entry(clp_frame, textvariable=self.var_port_clp, width=5).pack(side="left", padx=5)
        self.btn_conn_clp = ttk.Button(clp_frame, text="Conectar CLP", command=lambda: self.toggle_connection("CLP"))
        self.btn_conn_clp.pack(side="left", padx=10)
        self.lbl_status_clp = ttk.Label(clp_frame, text="Desconectado", foreground="red")
        self.lbl_status_clp.pack(side="left")

        robo_frame = ttk.LabelFrame(header_frame, text="Conexão Robô (Modbus)", padding=10)
        robo_frame.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        ttk.Label(robo_frame, text="IP:").pack(side="left")
        ttk.Entry(robo_frame, textvariable=self.var_ip_robo, width=13).pack(side="left", padx=5)
        ttk.Label(robo_frame, text="Port:").pack(side="left")
        ttk.Entry(robo_frame, textvariable=self.var_port_robo, width=5).pack(side="left", padx=5)
        self.btn_conn_robo = ttk.Button(robo_frame, text="Conectar Robô", command=lambda: self.toggle_connection("ROBO"))
        self.btn_conn_robo.pack(side="left", padx=10)
        self.lbl_status_robo = ttk.Label(robo_frame, text="Desconectado", foreground="red")
        self.lbl_status_robo.pack(side="left")

        body_container = ttk.Frame(self.manual_page)
        body_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.body_canvas = tk.Canvas(body_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body_container, orient="vertical", command=self.body_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.body_canvas)
        
        self.scrollable_frame.bind("<Configure>", lambda e: self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all")))
        self.body_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.body_canvas.configure(yscrollcommand=scrollbar.set)
        self.body_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.scrollable_frame.columnconfigure(0, weight=6)
        self.scrollable_frame.columnconfigure(1, weight=4)

        self.config_frame = ttk.LabelFrame(self.scrollable_frame, text="Mapeamento de Endereços", padding=10)
        self.config_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        ttk.Label(self.config_frame, text="Nome da Ação/Status", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(self.config_frame, text="Endereço", font=("Arial", 9, "bold")).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(self.config_frame, text="Enviar para", font=("Arial", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5)
        
        self.config_rows_frame = ttk.Frame(self.config_frame)
        self.config_rows_frame.grid(row=1, column=0, columnspan=4, sticky="nsew")

        btn_frame = ttk.Frame(self.config_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=15, sticky="ew")
        ttk.Button(btn_frame, text="+ Adicionar Ação", command=lambda: self.add_action_row()).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="+ Adicionar Status", command=lambda: self.add_status_row()).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="SCAN ROBO", command=self.quick_scan_robo, style="ToggleOn.TButton").pack(side="left", padx=20)
        ttk.Button(btn_frame, text="Salvar Configurações", command=self.save_config).pack(side="right", padx=5)

        self.action_panel_frame = ttk.LabelFrame(self.scrollable_frame, text="Controle Manual", padding=10)
        self.action_panel_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        self.monitor_frame = ttk.LabelFrame(self.manual_page, text="Monitoramento de Retorno (Polling)", padding=10)
        self.monitor_frame.pack(fill="both", expand=False, padx=10, pady=5)

        self.status_disp_frame = ttk.Frame(self.monitor_frame)
        self.status_disp_frame.pack(fill="x", pady=5)

        self.log_text = tk.Text(self.monitor_frame, height=6, state="disabled", bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, pady=5)
        self.show_manual_page()

    def show_manual_page(self):
        self._show_page(self.manual_page)

    def show_auto_page(self):
        self._show_page(self.auto_page)

    def show_dashboard_page(self):
        self._show_page(self.dashboard_page)

    def add_dashboard_record(self, serial, frontal=True, traseira=True, inspecao="Aprovado"):
        if hasattr(self, "dashboard_page"):
            self.dashboard_page.add_record(serial, frontal, traseira, inspecao)

    def _show_page(self, page):
        if self.current_page is page:
            return
        if self.current_page is not None:
            self.current_page.pack_forget()
        self.current_page = page
        self.current_page.pack(fill="both", expand=True)

    def add_action_row(self, name="Nova Ação", mem="", tgt="CLP"):
        uid = f"act_{self.action_counter}"
        self.action_counter += 1
        item = {
            "name_var": tk.StringVar(value=name),
            "mem_var": tk.StringVar(value=mem),
            "tgt_var": tk.StringVar(value=tgt),
            "state": False,
            "btn_widget": None,
            "row_frame": None
        }
        self.action_items[uid] = item
        row_frame = ttk.Frame(self.config_rows_frame)
        row_frame.pack(fill="x", pady=2)
        item["row_frame"] = row_frame
        ttk.Label(row_frame, text="[Ação]", foreground="blue").pack(side="left")
        ttk.Entry(row_frame, textvariable=item["name_var"], width=20).pack(side="left", padx=5)
        ttk.Entry(row_frame, textvariable=item["mem_var"], width=10).pack(side="left", padx=5)
        ttk.Combobox(row_frame, textvariable=item["tgt_var"], values=["CLP", "Robô"], state="readonly", width=8).pack(side="left", padx=5)
        ttk.Button(row_frame, text="X", width=3, command=lambda u=uid: self.remove_action(u)).pack(side="left", padx=5)
        item["name_var"].trace_add("write", lambda *args, u=uid: self.update_action_button_text(u))
        btn = ttk.Button(self.action_panel_frame, text=f"{name} (OFF)", style="ToggleOff.TButton", command=lambda u=uid: self.toggle_dynamic_action(u))
        btn.pack(fill="x", pady=5, ipady=8)
        item["btn_widget"] = btn

    def remove_action(self, uid):
        if uid in self.action_items:
            self.action_items[uid]["row_frame"].destroy()
            self.action_items[uid]["btn_widget"].destroy()
            del self.action_items[uid]

    def update_action_button_text(self, uid):
        if uid in self.action_items:
            item = self.action_items[uid]
            state_txt = "ON" if item["state"] else "OFF"
            item["btn_widget"].config(text=f"{item['name_var'].get()} ({state_txt})")

    def add_status_row(self, name="Novo Status", mem="", tgt="CLP"):
        uid = f"st_{self.status_counter}"
        self.status_counter += 1
        item = {
            "name_var": tk.StringVar(value=name),
            "mem_var": tk.StringVar(value=mem),
            "tgt_var": tk.StringVar(value=tgt),
            "val_var": tk.StringVar(value="---"),
            "row_frame": None,
            "disp_frame": None,
            "led_canvas": None,
            "led_circle": None
        }
        self.status_items[uid] = item
        row_frame = ttk.Frame(self.config_rows_frame)
        row_frame.pack(fill="x", pady=2)
        item["row_frame"] = row_frame
        ttk.Label(row_frame, text="[Status]", foreground="green").pack(side="left")
        ttk.Entry(row_frame, textvariable=item["name_var"], width=20).pack(side="left", padx=5)
        ttk.Entry(row_frame, textvariable=item["mem_var"], width=10).pack(side="left", padx=5)
        ttk.Combobox(row_frame, textvariable=item["tgt_var"], values=["CLP", "Robô"], state="readonly", width=8).pack(side="left", padx=5)
        ttk.Button(row_frame, text="X", width=3, command=lambda u=uid: self.remove_status(u)).pack(side="left", padx=5)
        disp_frame = ttk.Frame(self.status_disp_frame)
        disp_frame.pack(side="left", padx=15, pady=5)
        item["disp_frame"] = disp_frame
        canvas = tk.Canvas(disp_frame, width=20, height=20, highlightthickness=0)
        canvas.pack(side="left", padx=2)
        item["led_circle"] = canvas.create_oval(2, 2, 18, 18, fill="gray", outline="black")
        item["led_canvas"] = canvas
        lbl_name = ttk.Label(disp_frame, text=f"{name}:", font=("Arial", 10, "bold"))
        lbl_name.pack(side="left", padx=(5, 2))
        ttk.Label(disp_frame, textvariable=item["val_var"], font=("Arial", 10), foreground="blue").pack(side="left")
        item["name_var"].trace_add("write", lambda *args, l=lbl_name, iv=item["name_var"]: l.config(text=f"{iv.get()}:"))

    def remove_status(self, uid):
        if uid in self.status_items:
            self.status_items[uid]["row_frame"].destroy()
            self.status_items[uid]["disp_frame"].destroy()
            del self.status_items[uid]

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _get_device(self, target_name):
        if target_name == "CLP": return self.dev_clp
        if target_name == "Robô": return self.dev_robo
        return None

    def toggle_connection(self, device_type):
        if device_type == "CLP":
            ip, name = self.var_ip_clp.get(), "CLP"
            port = int(self.var_port_clp.get())
            btn, lbl = self.btn_conn_clp, self.lbl_status_clp
            dev = self.dev_clp
        else:
            ip, name = self.var_ip_robo.get(), "Robô"
            port = int(self.var_port_robo.get())
            btn, lbl = self.btn_conn_robo, self.lbl_status_robo
            dev = self.dev_robo

        if dev and dev.is_connected:
            dev.disconnect()
            if device_type == "CLP": self.dev_clp = None
            else: self.dev_robo = None
            btn.config(text=f"Conectar {name}")
            lbl.config(text="Desconectado", foreground="red")
            self.log(f"{name} Desconectado.")
        else:
            new_dev = ModbusDevice(name, ip, port=port)
            success, msg = new_dev.connect()
            if success:
                if device_type == "CLP": self.dev_clp = new_dev
                else: self.dev_robo = new_dev
                btn.config(text=f"Desconectar {name}")
                lbl.config(text="Conectado", foreground="green")
                self.log(f"[{name}] {msg}")
                self._ensure_polling()
            else:
                messagebox.showerror("Erro", msg)

    def _ensure_polling(self):
        if not self.polling_active and ((self.dev_clp and self.dev_clp.is_connected) or (self.dev_robo and self.dev_robo.is_connected)):
            self.polling_active = True
            threading.Thread(target=self.poll_status, daemon=True).start()

    def toggle_dynamic_action(self, uid):
        item = self.action_items.get(uid)
        if not item: return
        dev = self._get_device(item["tgt_var"].get())
        if not dev or not dev.is_connected:
            messagebox.showwarning("Aviso", "Dispositivo desconectado!")
            return
        new_state = not item["state"]
        def _task():
            success, msg = dev.send_write(item["mem_var"].get(), new_state)
            if success:
                self.root.after(0, lambda: self._update_dynamic_btn_ui(uid, new_state))
            else:
                self.root.after(0, lambda: self.log(f"Erro: {msg}"))
        threading.Thread(target=_task, daemon=True).start()

    def _update_dynamic_btn_ui(self, uid, new_state):
        item = self.action_items.get(uid)
        if item:
            item["state"] = new_state
            style = "ToggleOn.TButton" if new_state else "ToggleOff.TButton"
            item["btn_widget"].config(text=f"{item['name_var'].get()} ({'ON' if new_state else 'OFF'})", style=style)

    def _update_led(self, uid, value):
        item = self.status_items.get(uid)
        if not item: return
        
        canvas = item["led_canvas"]
        circle = item["led_circle"]
        
        # Determina a cor baseada no valor
        try:
            val_int = int(value)
            color, txt = ("lime", "TRUE") if val_int > 0 else ("red", "FALSE")
        except:
            if str(value).lower() in ["true", "on", "1"]:
                color, txt = ("lime", "TRUE")
            elif str(value).lower() in ["false", "off", "0"]:
                color, txt = ("red", "FALSE")
            else:
                color, txt = ("gray", str(value))

        canvas.itemconfig(circle, fill=color)
        item["val_var"].set(txt)

    def _set_led_error(self, uid):
        item = self.status_items.get(uid)
        if item:
            item["led_canvas"].itemconfig(item["led_circle"], fill="orange")
            item["val_var"].set("Erro")

    def poll_status(self):
        while self.polling_active:
            # list() para evitar erro se a dict mudar durante o loop
            for uid, item in list(self.status_items.items()):
                mem_str = item["mem_var"].get()
                tgt = item["tgt_var"].get()
                dev = self._get_device(tgt)
                
                if dev and dev.is_connected and mem_str.isdigit():
                    ok, val = dev.send_read(mem_str)
                    if ok:
                        self.root.after(0, lambda u=uid, v=val: self._update_led(u, v))
                    else: 
                        self.root.after(0, lambda u=uid: self._set_led_error(u))
                else:
                    self.root.after(0, lambda u=uid: self._clear_led(u))
                    
            time.sleep(1.0)

    def _clear_led(self, uid):
        item = self.status_items.get(uid)
        if item:
            item["led_canvas"].itemconfig(item["led_circle"], fill="gray")
            item["val_var"].set("---")

    def quick_scan_robo(self):
        if not self.dev_robo or not self.dev_robo.is_connected:
            messagebox.showwarning("Aviso", "Conecte o Robô primeiro!")
            return
        
        self.log("Iniciando SCAN ampliado no Robô (Blocos 0, 1000, 2000)...")
        def _task():
            found = []
            
            # Vamos testar 3 blocos comuns em robôs industriais
            blocks = [0, 1000, 2000]
            limit = 120
            
            with self.dev_robo.lock:
                client = self.dev_robo.client
                if not self.dev_robo.is_connected or not client:
                    self.root.after(0, lambda: self.log("SCAN cancelado: Robô desconectado."))
                    return
                for start in blocks:
                    print(f"[SCAN] Verificando faixa {start} a {start+limit}...")
                
                    # Scan Coils
                    res = client.read_coils(start, limit)
                    if res:
                        for i, v in enumerate(res):
                            if v: found.append(f"Coil {start+i}: {v}")
                
                    # Scan Inputs
                    res = client.read_discrete_inputs(start, limit)
                    if res:
                        for i, v in enumerate(res):
                            if v: found.append(f"Input {start+i}: {v}")

                    # Scan Holding
                    res = client.read_holding_registers(start, limit)
                    if res:
                        for i, v in enumerate(res):
                            if v != 0: found.append(f"Holding {start+i}: {v}")

                    # Scan InRegs
                    res = client.read_input_registers(start, limit)
                    if res:
                        for i, v in enumerate(res):
                            if v != 0: found.append(f"InReg {start+i}: {v}")

            if found:
                msg_text = f"Sucesso! Encontrados {len(found)} endereços ativos:\n\n" + "\n".join(found[:25])
                self.root.after(0, lambda: messagebox.showinfo("Scan Concluído", msg_text))
                for f in found: print(f"[SCAN SUCESSO] {f}")
            else:
                self.root.after(0, lambda: messagebox.showinfo("Scan Concluído", "Nenhum valor ativo encontrado nas faixas 0, 1000 e 2000.\n\nCertifique-se de que o Robô está em modo Automático ou com alguma I/O ligada."))
        
        threading.Thread(target=_task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = PLCPanelApp(root)
    root.mainloop()
