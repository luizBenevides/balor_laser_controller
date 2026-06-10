#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
import time
import json
import subprocess
from svgpathtools import svg2paths2

# Balor Imports
import balor.sender
import balor.command_list

class BalorStudioLite:
    def __init__(self, root):
        self.root = root
        self.root.title("Balor Studio Lite - Laser Controller")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Initial State
        self.current_svg = None
        self.machine = None
        self.is_connected = False
        self.presets_file = "laser_presets.json"
        self.presets = self.load_presets()

        # UI Variables
        self.var_power = tk.StringVar(value="40")
        self.var_speed = tk.StringVar(value="500")
        self.var_freq = tk.StringVar(value="30")
        self.var_offset_x = tk.StringVar(value="0.0")
        self.var_offset_y = tk.StringVar(value="0.0")
        self.var_scale = tk.StringVar(value="1.0")
        self.var_width_cm = tk.StringVar(value="0.0")
        self.var_height_cm = tk.StringVar(value="0.0")
        self.var_status = tk.StringVar(value="Desconectado")
        self.var_cal_file = tk.StringVar(value="cal_0002.csv" if os.path.exists("cal_0002.csv") else "")
        
        # Text/Barcode Variables
        self.var_content_mode = tk.StringVar(value="svg") # "svg", "text", "barcode"
        self.var_input_text = tk.StringVar(value="TESTE123")
        self.var_text_type = tk.StringVar(value="Texto") # "Texto", "QR Code"
        
        # SVG Metadata
        self.svg_raw_width = 1.0
        self.svg_raw_height = 1.0
        self.svg_bounds = (0, 0, 0, 0) # min_x, max_x, min_y, max_y

        self.setup_ui()
        
        # Connection management
        self.machine = balor.sender.Sender()
        self.is_connected = False
        self.abort_op = False
        self.op_running = False
        
        # Handle Window Close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.connect_laser()

    def setup_ui(self):
        # ... (unchanged) ...
        # Configure Grid Weights for Responsiveness
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=3) # Preview area grows more
        main_frame.rowconfigure(1, weight=1)

        # --- TOP: File Selection & Connection ---
        top_frame = ttk.LabelFrame(main_frame, text="Sistema", padding="5")
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        top_frame.columnconfigure(1, weight=1)

        ttk.Button(top_frame, text="Abrir SVG", command=self.browse_svg).grid(row=0, column=0, padx=5)
        self.lbl_filename = ttk.Label(top_frame, text="Nenhum arquivo carregado", font=("Arial", 9, "italic"))
        self.lbl_filename.grid(row=0, column=1, sticky="w", padx=5)

        # Calibration
        cal_frame = ttk.Frame(top_frame)
        cal_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        ttk.Label(cal_frame, text="Calibração:").pack(side=tk.LEFT)
        ttk.Entry(cal_frame, textvariable=self.var_cal_file, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(cal_frame, text="...", width=3, command=self.browse_cal).pack(side=tk.LEFT)
        ttk.Button(cal_frame, text="Gerar Grade", command=self.generate_cal_grid).pack(side=tk.LEFT, padx=10)

        # Connection Indicator
        conn_frame = ttk.Frame(top_frame)
        conn_frame.grid(row=0, column=2, padx=10)
        
        self.conn_canvas = tk.Canvas(conn_frame, width=15, height=15, highlightthickness=0)
        self.conn_canvas.pack(side=tk.LEFT, padx=5)
        self.status_dot = self.conn_canvas.create_oval(2, 2, 13, 13, fill="red")
        
        ttk.Label(conn_frame, textvariable=self.var_status).pack(side=tk.LEFT)
        ttk.Button(conn_frame, text="Testar Conexão", command=self.connect_laser).pack(side=tk.LEFT, padx=5)

        # --- LEFT: Parameters & Offsets ---
        left_scroll_frame = ttk.Frame(main_frame)
        left_scroll_frame.grid(row=1, column=0, sticky="nsw", padx=5)
        
        # Conteúdo Tabs
        content_frame = ttk.LabelFrame(left_scroll_frame, text="Conteúdo", padding="5")
        content_frame.pack(fill="x", pady=5)
        
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill="x", expand=True)
        
        # Tab SVG
        self.tab_svg = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_svg, text="SVG")
        ttk.Button(self.tab_svg, text="Selecionar SVG", command=self.browse_svg).pack(pady=5)
        
        # Tab Text/Code
        self.tab_text = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_text, text="Texto/Código")
        
        ttk.Label(self.tab_text, text="Conteúdo:").pack(anchor="w")
        ttk.Entry(self.tab_text, textvariable=self.var_input_text).pack(fill="x", pady=2)
        
        ttk.Label(self.tab_text, text="Tipo:").pack(anchor="w", pady=(5,0))
        ttk.OptionMenu(self.tab_text, self.var_text_type, "Texto", "Texto", "QR Code").pack(fill="x")
        
        ttk.Button(self.tab_text, text="Gerar / Visualizar", command=self.update_content_mode).pack(pady=10)
        
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Laser Params
        param_frame = ttk.LabelFrame(left_scroll_frame, text="Configurações do Laser", padding="10")
        param_frame.pack(fill="x", pady=5)
        
        self._add_entry(param_frame, "Potência (0-100%):", self.var_power, 0)
        self._add_entry(param_frame, "Velocidade (mm/s):", self.var_speed, 1)
        self._add_entry(param_frame, "Frequência (kHz):", self.var_freq, 2)

        # Offsets and Scaling
        offset_frame = ttk.LabelFrame(left_scroll_frame, text="Transformação", padding="10")
        offset_frame.pack(fill="x", pady=5)
        
        self.entry_x = self._add_entry(offset_frame, "Offset X (mm):", self.var_offset_x, 0)
        self.entry_y = self._add_entry(offset_frame, "Offset Y (mm):", self.var_offset_y, 1)
        self.entry_scale = self._add_entry(offset_frame, "Escala Geral:", self.var_scale, 2)
        
        ttk.Separator(offset_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.entry_width_cm = self._add_entry(offset_frame, "Largura (cm):", self.var_width_cm, 4)
        self.entry_height_cm = self._add_entry(offset_frame, "Altura (cm):", self.var_height_cm, 5)

        # Traces for bidirectional updates
        self.var_scale.trace_add("write", self._on_scale_change)
        self.var_width_cm.trace_add("write", self._on_width_cm_change)
        self.var_height_cm.trace_add("write", self._on_height_cm_change)

        # Presets
        preset_frame = ttk.LabelFrame(left_scroll_frame, text="Presets de Material", padding="10")
        preset_frame.pack(fill="x", pady=5)
        
        self.preset_combo = ttk.Combobox(preset_frame, values=list(self.presets.keys()), state="readonly")
        self.preset_combo.pack(fill="x", pady=2)
        
        btn_p_frame = ttk.Frame(preset_frame)
        btn_p_frame.pack(fill="x", pady=5)
        ttk.Button(btn_p_frame, text="Carregar", command=self.load_selected_preset).pack(side=tk.LEFT, expand=True, padx=2)
        ttk.Button(btn_p_frame, text="Salvar", command=self.save_current_preset).pack(side=tk.RIGHT, expand=True, padx=2)

        # --- RIGHT: Preview ---
        preview_frame = ttk.LabelFrame(main_frame, text="Área de Trabalho (Preview)", padding="5")
        preview_frame.grid(row=1, column=1, sticky="nsew")
        
        self.canvas = tk.Canvas(preview_frame, bg="#f0f0f0", borderwidth=1, relief="solid")
        self.canvas.pack(fill="both", expand=True)
        
        # Draw Crosshair in center of canvas
        self.root.update_idletasks()
        self.draw_preview_grid()

        # --- BOTTOM: Actions ---
        bottom_frame = ttk.Frame(main_frame, padding="10")
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        # Modern Large Buttons
        style = ttk.Style()
        style.configure("Action.TButton", font=("Arial", 10, "bold"))
        
        self.btn_light = ttk.Button(bottom_frame, text="[F1] LUZ GUIA", style="Action.TButton", command=self.start_light_mode)
        self.btn_light.pack(side=tk.LEFT, padx=5, ipadx=10, ipady=10)
        
        ttk.Button(bottom_frame, text="[F3] BORDAS (FRAME)", style="Action.TButton", command=self.start_frame_mode).pack(side=tk.LEFT, padx=5, ipadx=10, ipady=10)

        self.btn_mark = ttk.Button(bottom_frame, text="[F2] GRAVAR", style="Action.TButton", command=self.start_mark_mode)
        self.btn_mark.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=10)
        
        ttk.Button(bottom_frame, text="[ESC] PARAR TUDO", command=self.abort_operation).pack(side=tk.RIGHT, padx=10, ipadx=10, ipady=10)
        
        # Bindings
        self.root.bind("<F1>", lambda e: self.start_light_mode())
        self.root.bind("<F2>", lambda e: self.start_mark_mode())
        self.root.bind("<F3>", lambda e: self.start_frame_mode())
        self.root.bind("<Escape>", lambda e: self.abort_operation())

    def on_closing(self):
        """Called when the user closes the window."""
        if messagebox.askokcancel("Sair", "Deseja realmente sair?"):
            self.abort_op = True
            if self.machine:
                try:
                    self.machine.close()
                    print("[DEBUG] Connection closed on exit.")
                except:
                    pass
            self.root.destroy()

    def _add_entry(self, parent, label, var, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, padx=5, pady=2)

    def draw_preview_grid(self):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        self.canvas.create_line(w/2, 0, w/2, h, fill="#ccc", dash=(4,4))
        self.canvas.create_line(0, h/2, w, h/2, fill="#ccc", dash=(4,4))

    # --- Logic ---

    def connect_laser(self):
        try:
            # Clean up previous instance if exists
            if self.machine:
                try:
                    self.machine.close()
                except:
                    pass
                self.machine = None
                time.sleep(0.5) 

            self.var_status.set("Conectando...")
            self.root.update_idletasks()
            
            self.machine = balor.sender.Sender()
            if self.machine.open(machine_index=0):
                self.is_connected = True
                self.var_status.set("Conectado")
                self.conn_canvas.itemconfig(self.status_dot, fill="#00ff00") # Green
            else:
                raise Exception("Não foi possível abrir o dispositivo.")
        except Exception as e:
            self.is_connected = False
            self.var_status.set("Erro de Acesso")
            self.conn_canvas.itemconfig(self.status_dot, fill="red")
            err_msg = str(e)
            if "Access denied" in err_msg:
                messagebox.showerror("Erro de Permissão", 
                    "Acesso Negado!\n\n1. Feche o EzCAD2 se estiver aberto.\n"
                    "2. Rode este terminal como ADMINISTRADOR.\n"
                    "3. Verifique se outro script Python está rodando.")
            else:
                print(f"Erro de conexão: {e}")

    def browse_svg(self):
        file_path = filedialog.askopenfilename(filetypes=[("SVG files", "*.svg")])
        if file_path:
            self.current_svg = file_path
            self.lbl_filename.config(text=os.path.basename(file_path))
            self.load_svg_preview()

    def browse_cal(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.var_cal_file.set(file_path)

    def generate_cal_grid(self):
        """Generates a calibration grid pattern using balor-test.py."""
        if not self.is_connected:
            messagebox.showwarning("Aviso", "Laser não conectado!"); return
            
        if not messagebox.askyesno("Calibração", 
            "Isso irá gerar uma grade de calibração.\n\n"
            "1. Coloque um material de teste (placa de metal ou plástico).\n"
            "2. Ajuste o foco.\n"
            "3. O laser irá marcar uma grade.\n\n"
            "Deseja continuar?"):
            return
            
        def _run():
            try:
                self.var_status.set("Gerando Grade...")
                job_file = "temp_cal_grid.bin"
                import sys
                cmd = [
                    sys.executable, "balor-test.py", "mark",
                    "-t", "grid",
                    "-o", job_file
                ]
                subprocess.run(cmd, check=True)
                
                if os.path.exists(job_file):
                    with open(job_file, 'rb') as f:
                        data = f.read()
                    import balor.command_list
                    commands = balor.command_list.CommandBinary(data)
                    self.var_status.set("Marcando Grade...")
                    self.machine.execute(command_list=commands, loop_count=1)
                    self.var_status.set("Grade Pronta")
                    messagebox.showinfo("Sucesso", 
                        "Grade marcada!\n\nAgora use um paquímetro para medir as distâncias "
                        "e atualize seu arquivo CSV de calibração.")
            except Exception as e:
                self.var_status.set("Erro")
                messagebox.showerror("Erro", f"Falha ao gerar grade:\n{e}")
        
        threading.Thread(target=_run, daemon=True).start()

    def load_svg_preview(self):
        if not self.current_svg: return
        try:
            self.canvas.delete("all")
            self.draw_preview_grid()
            paths, attributes, svg_attributes = svg2paths2(self.current_svg)

            # Get canvas dimensions
            self.root.update_idletasks()
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w <= 1 or h <= 1:
                # If window not fully mapped, use a reasonable default or wait
                w, h = 600, 450 

            cx, cy = w/2, h/2

            # Calculate bounding box of all paths
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')

            has_paths = False
            for path in paths:
                if len(path) == 0: continue
                has_paths = True
                bbox = path.bbox() # (xmin, xmax, ymin, ymax)
                min_x = min(min_x, bbox[0])
                max_x = max(max_x, bbox[1])
                min_y = min(min_y, bbox[2])
                max_y = max(max_y, bbox[3])

            if not has_paths:
                return

            self.svg_raw_width = max_x - min_x
            self.svg_raw_height = max_y - min_y
            self.svg_bounds = (min_x, max_x, min_y, max_y)

            if self.svg_raw_width == 0: self.svg_raw_width = 1
            if self.svg_raw_height == 0: self.svg_raw_height = 1

            # Initialize CM values based on current scale
            self._on_scale_change()

            # Padding for preview
            margin = 40
            scale = min((w - margin) / self.svg_raw_width, (h - margin) / self.svg_raw_height)

            # Center the SVG in preview
            offset_x = cx - (min_x + self.svg_raw_width/2) * scale
            offset_y = cy - (min_y + self.svg_raw_height/2) * scale

            for path in paths:
                pts = []
                for seg in path:
                    # Adaptive steps based on segment length could be better, but 10 is okay
                    steps = 10
                    for i in range(steps + 1):
                        p = seg.point(i/steps)
                        pts.append((p.real * scale + offset_x, p.imag * scale + offset_y))

                if len(pts) > 1:
                    # Flatten the list of tuples for create_line
                    flat_pts = [item for sublist in pts for item in sublist]
                    self.canvas.create_line(flat_pts, fill="#007bff", width=1)

        except Exception as e:
            print(f"Preview error: {e}")
            import traceback
            traceback.print_exc()

    def _on_scale_change(self, *args):
        if not self.current_svg: return
        try:
            scale_val = self.var_scale.get()
            if not scale_val: return
            scale = float(scale_val)
            w_cm = (self.svg_raw_width * scale) / 10.0
            h_cm = (self.svg_raw_height * scale) / 10.0
            
            # Update vars only if not focused, to avoid typing interference
            if self.root.focus_get() != self.entry_width_cm:
                self.var_width_cm.set(f"{w_cm:.2f}")
            if self.root.focus_get() != self.entry_height_cm:
                self.var_height_cm.set(f"{h_cm:.2f}")
        except:
            pass

    def _on_width_cm_change(self, *args):
        if not self.current_svg: return
        if self.root.focus_get() != self.entry_width_cm: return
        try:
            val = self.var_width_cm.get()
            if not val: return
            w_cm = float(val)
            if self.svg_raw_width > 0:
                scale = (w_cm * 10.0) / self.svg_raw_width
                self.var_scale.set(f"{scale:.4f}")
        except:
            pass

    def _on_height_cm_change(self, *args):
        if not self.current_svg: return
        if self.root.focus_get() != self.entry_height_cm: return
        try:
            val = self.var_height_cm.get()
            if not val: return
            h_cm = float(val)
            if self.svg_raw_height > 0:
                scale = (h_cm * 10.0) / self.svg_raw_height
                self.var_scale.set(f"{scale:.4f}")
        except:
            pass

    def start_frame_mode(self):
        if not self.is_connected: 
            messagebox.showwarning("Aviso", "Laser não conectado!"); return
        if not self.current_svg: return
        self.abort_operation()
        self.root.after(100, lambda: self._start_thread("frame"))

    def start_light_mode(self):
        if not self.is_connected: 
            messagebox.showwarning("Aviso", "Laser não conectado!"); return
        if not self.current_svg: return
        self.abort_operation()
        self.root.after(100, lambda: self._start_thread("light"))

    def start_mark_mode(self):
        if not self.is_connected: 
            messagebox.showwarning("Aviso", "Laser não conectado!"); return
        if not self.current_svg: return
        if messagebox.askyesno("PERIGO", "Iniciar GRAVAÇÃO REAL? Use óculos de proteção!"):
            self.abort_operation()
            self.root.after(100, lambda: self._start_thread("mark"))

    def _start_thread(self, mode):
        self.abort_op = False
        threading.Thread(target=self._run_laser_op, args=(mode,), daemon=True).start()

    def load_presets(self):
        if os.path.exists(self.presets_file):
            with open(self.presets_file, 'r') as f:
                return json.load(f)
        return {"Aço Inox": {"power": "60", "speed": "300", "freq": "20"}, 
                "Alumínio": {"power": "80", "speed": "500", "freq": "35"}}

    def load_selected_preset(self):
        name = self.preset_combo.get()
        if name in self.presets:
            p = self.presets[name]
            self.var_power.set(p["power"])
            self.var_speed.set(p["speed"])
            self.var_freq.set(p["freq"])

    def save_current_preset(self):
        name = tk.simpledialog.askstring("Novo Preset", "Nome do Preset:")
        if name:
            self.presets[name] = {
                "power": self.var_power.get(),
                "speed": self.var_speed.get(),
                "freq": self.var_freq.get()
            }
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f)
            self.preset_combo['values'] = list(self.presets.keys())

    def abort_operation(self):
        self.abort_op = True
        if self.machine:
            try:
                self.machine.abort()
            except:
                pass
            self.var_status.set("Abortado")

    def update_content_mode(self):
        """Called when the user clicks 'Gerar' on the Text/Barcode tab."""
        t = self.var_text_type.get()
        if t == "Texto":
            self.var_content_mode.set("text")
        else:
            self.var_content_mode.set("barcode")
        
        # When generating text/code, we reset scale to 1.0 initially
        # and set a base raw size for framing
        self.svg_raw_width = 50.0 # Standard base width mm
        self.svg_raw_height = 10.0 # Standard base height mm
        if t == "QR Code":
            self.svg_raw_height = 50.0
            
        self.svg_bounds = (0, self.svg_raw_width, 0, self.svg_raw_height)
        self.current_svg = "DUMMY" # To allow scale updates
        self._on_scale_change()
        
        self.canvas.delete("all")
        self.draw_preview_grid()
        self.canvas.create_text(
            self.canvas.winfo_width()/2, 
            self.canvas.winfo_height()/2, 
            text=f"PREVIEW: {self.var_input_text.get()}\n({t})",
            font=("Arial", 14, "bold"),
            fill="#007bff"
        )
        self.lbl_filename.config(text=f"Gerado: {t}")

    def _on_tab_changed(self, event):
        tab_id = self.notebook.index(self.notebook.select())
        if tab_id == 0: # SVG
            self.var_content_mode.set("svg")
        else:
            # Mode set by 'Gerar' button or automatically
            pass

    def _run_laser_op(self, mode):
        if self.op_running:
            return
        self.op_running = True
        try:
            self.var_status.set(f"Processando {mode}...")
            
            # Params
            p = self.var_power.get()
            s = self.var_speed.get()
            q = self.var_freq.get()
            ox = float(self.var_offset_x.get())
            oy = float(self.var_offset_y.get())
            sc = float(self.var_scale.get())
            content_mode = self.var_content_mode.get()
            cal_file = self.var_cal_file.get()
            cal_arg = ["-c", cal_file] if cal_file and os.path.exists(cal_file) else []

            if mode == "frame":
                # Create bounding box job in memory
                import balor.command_list
                import balor.Cal
                cal = balor.Cal.Cal(cal_file if cal_file and os.path.exists(cal_file) else None)
                commands = balor.command_list.CommandList(cal=cal)
                commands.ready()
                commands.set_travel_speed(2000)
                
                min_x, max_x, min_y, max_y = self.svg_bounds
                
                pts = [
                    (min_x * sc + ox, min_y * sc + oy),
                    (max_x * sc + ox, min_y * sc + oy),
                    (max_x * sc + ox, max_y * sc + oy),
                    (min_x * sc + ox, max_y * sc + oy),
                    (min_x * sc + ox, min_y * sc + oy)
                ]
                
                commands.init(pts[0][0], pts[0][1])
                for pt in pts:
                    commands.goto(pt[0], pt[1])
                
                self.var_status.set("Laser Ativo (Bordas)")
                self.machine.light_on()
                try:
                    while not self.abort_op:
                        self.machine.execute(command_list=commands, loop_count=1)
                finally:
                    self.machine.light_off()
                
            else:
                job_file = f"temp_job_{mode}.bin"
                import sys
                
                if content_mode == "svg":
                    cmd = [
                        sys.executable, "balor-svg.py", mode,
                        "-f", self.current_svg,
                        "-o", job_file,
                        "--laser-power", p,
                        "--cut-speed", s,
                        "--q-switch-frequency", q,
                        "--xoff", str(ox),
                        "--yoff", str(oy),
                        "--xscale", str(sc),
                        "--yscale", str(sc)
                    ] + cal_arg
                elif content_mode == "text":
                    cmd = [
                        sys.executable, "balor-text.py", mode,
                        "-i", self.var_input_text.get(),
                        "-o", job_file,
                        "--laser-power", p,
                        "--mark-speed", s,
                        "--q-switch-frequency", q,
                        "--xoffs", str(ox),
                        "--yoffs", str(oy),
                        "--raster-x-res", str(0.1 * sc),
                        "--raster-y-res", str(0.1 * sc)
                    ] + cal_arg
                elif content_mode == "barcode":
                    cmd = [
                        sys.executable, "balor-code.py", mode,
                        "-i", self.var_input_text.get(),
                        "-f", "qr",
                        "-o", job_file,
                        "--laser-power", p,
                        "--mark-speed", s,
                        "--q-switch-frequency", q,
                        "--xoffs", str(ox),
                        "--yoffs", str(oy),
                        "--raster-x-res", str(0.1 * sc),
                        "--raster-y-res", str(0.1 * sc)
                    ] + cal_arg
                
                subprocess.run(cmd, check=True)
                
                if os.path.exists(job_file):
                    with open(job_file, 'rb') as f:
                        data = f.read()
                    
                    import balor.command_list
                    commands = balor.command_list.CommandBinary(data)
                    
                    self.var_status.set("Laser Ativo")
                    if mode == "light":
                        self.machine.light_on()
                        try:
                            while not self.abort_op:
                                self.machine.execute(command_list=commands, loop_count=1)
                        finally:
                            self.machine.light_off()
                    else:
                        self.machine.execute(command_list=commands, loop_count=1)
                
            if not self.abort_op:
                self.var_status.set("Pronto")
        except Exception as e:
            self.var_status.set("Erro")
            if not self.abort_op:
                messagebox.showerror("Erro", f"Falha na execução:\n{e}")
        finally:
            self.abort_op = False
            self.op_running = False

if __name__ == "__main__":
    root = tk.Tk()
    # Adicionando suporte a DPI alto no Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = BalorStudioLite(root)
    root.mainloop()
