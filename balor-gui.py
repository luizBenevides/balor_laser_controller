#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import threading
import time
import json
import subprocess
from svgpathtools import svg2paths2

# Modular Features
import barcode_module
import pdf_module
import preview_module
import composer_module
import db_module

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
        self.current_svg = "temp_workspace.svg" # Now everything points to the composer output
        self.machine = None
        self.is_connected = False
        self.presets_file = "laser_presets.json"
        self.presets = self.load_presets()

        # UI Variables
        self.var_power = tk.StringVar(value="25")
        self.var_speed = tk.StringVar(value="3500")
        self.var_freq = tk.StringVar(value="60")
        self.var_offset_x = tk.StringVar(value="0.0")
        self.var_offset_y = tk.StringVar(value="0.0")
        self.var_scale = tk.StringVar(value="1.0")
        self.var_width_mm = tk.StringVar(value="0.0")
        self.var_height_mm = tk.StringVar(value="0.0")
        self.var_status = tk.StringVar(value="Desconectado")
        self.var_cal_file = tk.StringVar(value="cal_0002.csv" if os.path.exists("cal_0002.csv") else "")
        
        # Hatch Variables
        self.var_hatch_enable = tk.BooleanVar(value=True)
        self.var_hatch_angle = tk.StringVar(value="90")
        self.var_hatch_spacing = tk.StringVar(value="10.0") # microns

        # Text/Barcode Variables
        self.var_content_mode = tk.StringVar(value="code128_serial") 
        self.var_input_text = tk.StringVar(value="TESTE123")
        self.var_text_type = tk.StringVar(value="Code 128 + Serial") 
        self.var_text_pos = tk.StringVar(value="bottom") 
        
        # Generic Object Adjustment Variables
        self.var_obj_scale_x = tk.StringVar(value="1.0")
        self.var_obj_scale_y = tk.StringVar(value="1.0")
        self.var_obj_off_x = tk.StringVar(value="0.0")
        self.var_obj_off_y = tk.StringVar(value="0.0")
        self.var_obj_rot = tk.StringVar(value="0")
        
        # Legacy Barcode/Text Variables (Still bound to UI)
        self.var_barcode_h = tk.StringVar(value="20.0")
        self.var_barcode_w_scale = tk.StringVar(value="1.0")
        self.var_barcode_rot = tk.StringVar(value="0")
        self.var_text_scale = tk.StringVar(value="1.0")
        self.var_text_x_off = tk.StringVar(value="0.0")
        self.var_text_y_off = tk.StringVar(value="0.0")
        self.var_text_rot = tk.StringVar(value="0")
        
        self.var_text_font = tk.StringVar(value="arial.ttf")
        self.var_text_space = tk.StringVar(value="0.906")
        self.var_barcode_type = tk.StringVar(value="code128")
        self.var_group_barcode = tk.BooleanVar(value=True)
        
        self.selected_obj = tk.StringVar(value="")
        
        # SCENE GRAPH (Composition Engine)
        self.custom_scene_items = [] 
        # Will hold dicts: {'id', 'file', 'ox', 'oy', 'sx', 'sy', 'rot', 'color', 'visible'}
        self.combined_offsets = {
            'base_1': [-20.0, 0.0],
            'base_2': [20.0, 0.0]
        }
        self.is_combined_mode = False
        
        # Pen (Layer) Management

        # Pre-defined EzCAD-like pens: Black, Red, Blue
        self.pens = {
            "Preto (#000000)": {"color_hex": "#000000", "power": "25", "speed": "3500", "freq": "60", "hatch_ena": True, "hatch_ang": "90", "hatch_spc": "10.0"},
            "Vermelho (#FF0000)": {"color_hex": "#FF0000", "power": "80", "speed": "200", "freq": "20", "hatch_ena": True, "hatch_ang": "45", "hatch_spc": "30.0"},
            "Azul (#0000FF)": {"color_hex": "#0000FF", "power": "30", "speed": "1000", "freq": "40", "hatch_ena": False, "hatch_ang": "0", "hatch_spc": "0.0"}
        }
        self.current_pen_name = tk.StringVar(value="Preto (#000000)")
        
        # Track object layers (colors)
        self.obj_colors = {"barcode": "Preto (#000000)", "text": "Preto (#000000)"}
        self.obj_visibility = {}
        self.pdf_serials = []
        self.db_serials = [] # Records from database: [{'id', 'serial', 'criado_em'}]
        self.current_serial_idx = -1
        self.var_batch_active = tk.BooleanVar(value=False)
        self.var_db_mode = tk.BooleanVar(value=False) # True if using Database instead of PDF
        self.var_auto_sync = tk.BooleanVar(value=False) # True if auto-polling DB
        self.var_current_serial = tk.StringVar(value="")
        
        # Database Manager
        self.db_manager = db_module.DBManager()
        
        # SVG Metadata
        self.svg_raw_width = 1.0
        self.svg_raw_height = 1.0
        self.svg_bounds = (0, 0, 0, 0) # min_x, max_x, min_y, max_y

        self.setup_ui()
        self.preview_manager = preview_module.PreviewManager(self.canvas, self)
        
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
        main_frame.columnconfigure(0, weight=1) # Left Panel
        main_frame.columnconfigure(1, weight=4) # Center Preview
        main_frame.columnconfigure(2, weight=1) # Right Panel
        main_frame.rowconfigure(1, weight=1)

        # --- TOP: File Selection & Connection ---
        top_frame = ttk.LabelFrame(main_frame, text="Sistema", padding="5")
        top_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        top_frame.columnconfigure(1, weight=1)

        ttk.Button(top_frame, text="Abrir SVG", command=self.browse_svg).grid(row=0, column=0, padx=5)
        self.lbl_filename = ttk.Label(top_frame, text="Nenhum arquivo carregado", font=("Arial", 9, "italic"))
        self.lbl_filename.grid(row=0, column=1, sticky="w", padx=5)

        # Calibration
        cal_frame = ttk.Frame(top_frame)
        cal_frame.grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=2)
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

        # --- LEFT: Parameters (Scrollable Canvas) ---
        left_container = ttk.Frame(main_frame)
        left_container.grid(row=1, column=0, sticky="nsew", padx=5)
        
        bg_color = ttk.Style().lookup("TFrame", "background")
        left_canvas = tk.Canvas(left_container, borderwidth=0, highlightthickness=0, bg=bg_color, width=280)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        left_scrollbar = ttk.Scrollbar(left_container, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_scroll_frame = ttk.Frame(left_canvas)
        canvas_window = left_canvas.create_window((0, 0), window=left_scroll_frame, anchor="nw")
        
        left_scroll_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.bind("<Configure>", lambda e: left_canvas.itemconfig(canvas_window, width=e.width))
        
        # Left sidebar Notebook to save vertical space
        left_notebook = ttk.Notebook(left_scroll_frame)
        left_notebook.pack(fill="x", pady=5)
        
        tab_left_pen = ttk.Frame(left_notebook)
        tab_left_trans = ttk.Frame(left_notebook)
        
        left_notebook.add(tab_left_pen, text="Caneta / Hatch")
        left_notebook.add(tab_left_trans, text="Posição / Escala")
        
        # Laser Params -> Pen Params (Tab 1)
        param_frame = ttk.LabelFrame(tab_left_pen, text="Parâmetros da Caneta", padding="10")
        param_frame.pack(fill="x", pady=5)
        
        pen_sel_frame = ttk.Frame(param_frame)
        pen_sel_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        ttk.Label(pen_sel_frame, text="Caneta:").pack(side=tk.LEFT)
        self.combo_pens = ttk.Combobox(pen_sel_frame, textvariable=self.current_pen_name, values=list(self.pens.keys()), state="readonly", width=15)
        self.combo_pens.pack(side=tk.LEFT, padx=5)
        self.combo_pens.bind("<<ComboboxSelected>>", self.on_pen_selected)
        
        self._add_entry(param_frame, "Potência (0-100%):", self.var_power, 1)
        self._add_entry(param_frame, "Velocidade (mm/s):", self.var_speed, 2)
        self._add_entry(param_frame, "Frequência (kHz):", self.var_freq, 3)

        # Hatch Params (Tab 1)
        hatch_frame = ttk.LabelFrame(tab_left_pen, text="Preenchimento da Caneta", padding="10")
        hatch_frame.pack(fill="x", pady=5)
        
        chk_hatch = ttk.Checkbutton(hatch_frame, text="Ativar Hatch", variable=self.var_hatch_enable)
        chk_hatch.grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        
        self._add_entry(hatch_frame, "Ângulo (°):", self.var_hatch_angle, 1)
        self._add_entry(hatch_frame, "Espaçamento (um):", self.var_hatch_spacing, 2)
        
        ttk.Button(hatch_frame, text="Salvar Caneta", command=self.save_pen_settings).grid(row=3, column=0, columnspan=2, pady=5)

        # Offsets and Scaling (Tab 2)
        offset_frame = ttk.LabelFrame(tab_left_trans, text="Global Transform", padding="10")
        offset_frame.pack(fill="x", pady=5)
        
        self.entry_x = self._add_entry(offset_frame, "Offset X (mm):", self.var_offset_x, 0)
        self.entry_y = self._add_entry(offset_frame, "Offset Y (mm):", self.var_offset_y, 1)
        self.entry_scale = self._add_entry(offset_frame, "Escala Geral:", self.var_scale, 2)
        
        ttk.Separator(offset_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.entry_width_mm = self._add_entry(offset_frame, "Largura (mm):", self.var_width_mm, 4)
        self.entry_height_mm = self._add_entry(offset_frame, "Altura (mm):", self.var_height_mm, 5)

        # Traces for bidirectional updates
        self.var_scale.trace_add("write", self._on_scale_change)
        self.var_width_mm.trace_add("write", self._on_width_mm_change)
        self.var_height_mm.trace_add("write", self._on_height_mm_change)

        # Selected Object Transform Adjustment Panel (Tab 2)
        self.obj_adj_frame = ttk.LabelFrame(tab_left_trans, text="Ajuste do Objeto Selecionado", padding="10")
        self.obj_adj_frame.pack(fill="x", pady=5)
        
        self.lbl_selected_obj_name = ttk.Label(self.obj_adj_frame, text="Nenhum objeto selecionado", font=("Arial", 9, "bold"))
        self.lbl_selected_obj_name.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))
        
        ttk.Label(self.obj_adj_frame, text="Escala X | Escala Y:").grid(row=1, column=0, columnspan=2, sticky="w")
        self.entry_obj_scale_x = ttk.Entry(self.obj_adj_frame, textvariable=self.var_obj_scale_x, width=10)
        self.entry_obj_scale_x.grid(row=2, column=0, padx=2, sticky="w")
        self.entry_obj_scale_y = ttk.Entry(self.obj_adj_frame, textvariable=self.var_obj_scale_y, width=10)
        self.entry_obj_scale_y.grid(row=2, column=1, padx=2, sticky="w")
        
        ttk.Label(self.obj_adj_frame, text="Offset X | Offset Y (mm):").grid(row=3, column=0, columnspan=2, sticky="w", pady=(5,0))
        self.entry_obj_off_x = ttk.Entry(self.obj_adj_frame, textvariable=self.var_obj_off_x, width=10)
        self.entry_obj_off_x.grid(row=4, column=0, padx=2, sticky="w")
        self.entry_obj_off_y = ttk.Entry(self.obj_adj_frame, textvariable=self.var_obj_off_y, width=10)
        self.entry_obj_off_y.grid(row=4, column=1, padx=2, sticky="w")
        
        ttk.Label(self.obj_adj_frame, text="Rotação (graus):").grid(row=5, column=0, columnspan=2, sticky="w", pady=(5,0))
        self.entry_obj_rot = ttk.Entry(self.obj_adj_frame, textvariable=self.var_obj_rot, width=10)
        self.entry_obj_rot.grid(row=6, column=0, padx=2, sticky="w")
        
        ttk.Button(self.obj_adj_frame, text="Aplicar no Objeto", command=self.apply_selected_object_adjustments).grid(row=7, column=0, columnspan=2, pady=10)

        # Presets (Always visible at the bottom of the left sidebar)
        preset_frame = ttk.LabelFrame(left_scroll_frame, text="Presets", padding="10")
        preset_frame.pack(fill="x", pady=5)
        
        self.preset_combo = ttk.Combobox(preset_frame, values=list(self.presets.keys()), state="readonly")
        self.preset_combo.pack(fill="x", pady=2)
        
        btn_p_frame = ttk.Frame(preset_frame)
        btn_p_frame.pack(fill="x", pady=5)
        ttk.Button(btn_p_frame, text="Carregar", command=self.load_selected_preset).pack(side=tk.LEFT, expand=True, padx=2)
        ttk.Button(btn_p_frame, text="Salvar", command=self.save_current_preset).pack(side=tk.RIGHT, expand=True, padx=2)

        # --- CENTER: Preview ---
        preview_frame = ttk.LabelFrame(main_frame, text="Área de Trabalho (Preview)", padding="5")
        preview_frame.grid(row=1, column=1, sticky="nsew", padx=5)
        
        self.canvas = tk.Canvas(preview_frame, bg="#f0f0f0", borderwidth=1, relief="solid")
        self.canvas.pack(fill="both", expand=True)
        
        # Mouse Wheel Zoom on Canvas
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel) # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mouse_wheel) # Linux scroll down
        
        # Draw Crosshair
        self.root.update_idletasks()
        self.draw_preview_grid()

        # --- RIGHT: Contents & Adjustment ---
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=2, sticky="nse", padx=5)
        
        # Lista de Objetos (Árvore)
        list_frame = ttk.LabelFrame(right_frame, text="Lista de Objetos (Camadas)", padding="5")
        list_frame.pack(fill="x", pady=5)
        
        # State dictionary to track visibility
        self.obj_visibility = {}
        
        columns = ("tipo", "visivel", "cor")
        self.tree_objs = ttk.Treeview(list_frame, columns=columns, show="headings", height=4)
        self.tree_objs.heading("tipo", text="Objeto")
        self.tree_objs.heading("visivel", text="Gravar?")
        self.tree_objs.heading("cor", text="Cor (Caneta)")
        self.tree_objs.column("tipo", width=90)
        self.tree_objs.column("visivel", width=50, anchor="center")
        self.tree_objs.column("cor", width=120, anchor="center")
        self.tree_objs.pack(fill="x", pady=2)
        
        self.tree_objs.bind('<ButtonRelease-1>', self.on_tree_click)
        self.tree_objs.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        # Right-click menu for color assignment
        self.color_menu = tk.Menu(self.root, tearoff=0)
        for pen_name in self.pens.keys():
            self.color_menu.add_command(label=f"Atribuir {pen_name}", command=lambda p=pen_name: self.assign_pen_to_selected(p))
        self.tree_objs.bind("<Button-3>", self.show_color_menu)

        
        # Conteúdo Tabs
        content_frame = ttk.LabelFrame(right_frame, text="Conteúdo Dinâmico", padding="5")
        content_frame.pack(fill="x", pady=5, expand=True)
        
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill="x", expand=True)
        
        # Tab SVG
        self.tab_svg = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_svg, text="SVG")
        ttk.Button(self.tab_svg, text="Carregar SVG Principal", command=self.browse_svg).pack(fill="x", pady=5)
        ttk.Button(self.tab_svg, text="Adicionar Arte (Compor)", command=self.add_to_scene).pack(fill="x", pady=5)
        
        # Tab Text/Code
        self.tab_text = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_text, text="Texto/Código")
        
        ttk.Label(self.tab_text, text="Conteúdo:").pack(anchor="w")
        ttk.Entry(self.tab_text, textvariable=self.var_input_text).pack(fill="x", pady=2)
        
        ttk.Label(self.tab_text, text="Tipo:").pack(anchor="w", pady=(5,0))
        ttk.OptionMenu(self.tab_text, self.var_text_type, "Texto", "Texto", "QR Code", "Code 128 + Serial").pack(fill="x")
        
        ttk.Label(self.tab_text, text="Posição Texto:").pack(anchor="w", pady=(5,0))
        ttk.OptionMenu(self.tab_text, self.var_text_pos, "bottom", "bottom", "top").pack(fill="x")

        ttk.Button(self.tab_text, text="Gerar / Visualizar", command=lambda: self.update_content_mode(from_btn=True)).pack(pady=10)
        
        # Painel de Ajuste Individual
        self.adj_frame = ttk.LabelFrame(self.tab_text, text="Ajuste Individual (Selecione no Preview)", padding="5")
        self.adj_frame.pack(fill="x", pady=5)
        
        ttk.Label(self.adj_frame, text="Barcode: Altura | Escala W | Rotação").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Entry(self.adj_frame, textvariable=self.var_barcode_h, width=8).grid(row=1, column=0, padx=2)
        ttk.Entry(self.adj_frame, textvariable=self.var_barcode_w_scale, width=8).grid(row=1, column=1, padx=2)
        ttk.Entry(self.adj_frame, textvariable=self.var_barcode_rot, width=8).grid(row=1, column=2, padx=2)
        
        ttk.Label(self.adj_frame, text="Serial: Escala | Offset Y | Rotação").grid(row=2, column=0, columnspan=3, sticky="w", pady=(5,0))
        ttk.Entry(self.adj_frame, textvariable=self.var_text_scale, width=8).grid(row=3, column=0, padx=2)
        ttk.Entry(self.adj_frame, textvariable=self.var_text_y_off, width=8).grid(row=3, column=1, padx=2)
        ttk.Entry(self.adj_frame, textvariable=self.var_text_rot, width=8).grid(row=3, column=2, padx=2)
        
        ttk.Label(self.adj_frame, text="Tipo | Fonte (TTF) | Text Space").grid(row=4, column=0, columnspan=3, sticky="w", pady=(5,0))
        ttk.OptionMenu(self.adj_frame, self.var_barcode_type, "code128", "code128", "gs1_128").grid(row=5, column=0, padx=2, sticky="ew")
        ttk.Entry(self.adj_frame, textvariable=self.var_text_font, width=12).grid(row=5, column=1, padx=2)
        ttk.Entry(self.adj_frame, textvariable=self.var_text_space, width=8).grid(row=5, column=2, padx=2)
        
        ttk.Checkbutton(self.adj_frame, text="Agrupar Código + Serial (1 Objeto)", variable=self.var_group_barcode, command=lambda: self.update_content_mode(from_btn=True)).grid(row=6, column=0, columnspan=3, pady=5, sticky="w")
        ttk.Button(self.adj_frame, text="Aplicar Ajustes", command=lambda: self.update_content_mode(from_btn=True)).grid(row=7, column=0, columnspan=3, pady=5)


        
        # Painel de Transformação Rápida
        self.trans_frame = ttk.LabelFrame(self.tab_text, text="Transformação Rápida", padding="5")
        self.trans_frame.pack(fill="x", pady=5)
        
        btn_rot_frame = ttk.Frame(self.trans_frame)
        btn_rot_frame.pack(fill="x")
        ttk.Button(btn_rot_frame, text="Girar 90°", width=10, command=lambda: self.apply_quick_transform("rotate")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_rot_frame, text="Espelhar H", width=10, command=lambda: self.apply_quick_transform("mirror_h")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_rot_frame, text="Espelhar V", width=10, command=lambda: self.apply_quick_transform("mirror_v")).pack(side=tk.LEFT, padx=2)
        
        btn_align_frame = ttk.Frame(self.trans_frame)
        btn_align_frame.pack(fill="x", pady=5)
        ttk.Button(btn_align_frame, text="Centralizar", width=10, command=lambda: self.apply_quick_transform("center")).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_align_frame, text="Resetar", width=10, command=lambda: self.apply_quick_transform("reset")).pack(side=tk.LEFT, padx=2)
        
        # Tab Batch PDF
        self.tab_batch = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_batch, text="Lote (PDF)")
        
        ttk.Button(self.tab_batch, text="Carregar Seriais de PDF", command=self.load_pdf_batch).pack(fill="x", pady=5)
        
        # Batch List (Treeview)
        batch_list_frame = ttk.Frame(self.tab_batch)
        batch_list_frame.pack(fill="both", expand=True, pady=5)
        
        # Scrollbar for batch list
        batch_scroll = ttk.Scrollbar(batch_list_frame)
        batch_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_batch = ttk.Treeview(batch_list_frame, columns=("status", "serial"), show="headings", yscrollcommand=batch_scroll.set)
        self.tree_batch.heading("status", text="Status")
        self.tree_batch.heading("serial", text="Serial")
        self.tree_batch.column("status", width=80, anchor="center")
        self.tree_batch.column("serial", width=200, anchor="center")
        self.tree_batch.pack(side=tk.LEFT, fill="both", expand=True)
        batch_scroll.config(command=self.tree_batch.yview)
        
        self.tree_batch.bind('<Double-1>', self.on_batch_tree_double_click)
        
        self.lbl_batch_status = ttk.Label(self.tab_batch, text="Nenhum lote carregado")
        self.lbl_batch_status.pack(pady=2)
        
        self.btn_next_serial = ttk.Button(self.tab_batch, text="Avançar Manual", command=self.next_batch_serial, state="disabled")
        self.btn_next_serial.pack(fill="x", pady=2)
        
        # Tab Batch Database
        self.tab_db = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_db, text="Lote (Banco)")
        
        db_top_frame = ttk.Frame(self.tab_db)
        db_top_frame.pack(fill="x", pady=5)
        ttk.Button(db_top_frame, text="Sincronizar Banco (Rpi)", command=self.load_db_batch).pack(side=tk.LEFT, expand=True, padx=2)
        ttk.Button(db_top_frame, text="Limpar Lista", command=self.clear_db_list).pack(side=tk.LEFT, expand=True, padx=2)
        
        ttk.Checkbutton(db_top_frame, text="Auto-Sync (Real-time)", variable=self.var_auto_sync, command=self.toggle_auto_sync).pack(side=tk.LEFT, padx=10)
        
        db_list_frame = ttk.Frame(self.tab_db)
        db_list_frame.pack(fill="both", expand=True, pady=5)
        
        db_scroll = ttk.Scrollbar(db_list_frame)
        db_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_db = ttk.Treeview(db_list_frame, columns=("id", "serial", "data"), show="headings", yscrollcommand=db_scroll.set)
        self.tree_db.heading("id", text="ID")
        self.tree_db.heading("serial", text="Serial")
        self.tree_db.heading("data", text="Data/Hora")
        self.tree_db.column("id", width=50, anchor="center")
        self.tree_db.column("serial", width=120, anchor="center")
        self.tree_db.column("data", width=150, anchor="center")
        self.tree_db.pack(side=tk.LEFT, fill="both", expand=True)
        db_scroll.config(command=self.tree_db.yview)
        
        self.tree_db.bind('<Double-1>', self.on_db_tree_double_click)
        
        self.lbl_db_status = ttk.Label(self.tab_db, text="Banco desconectado")
        self.lbl_db_status.pack(pady=2)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # --- BOTTOM: Actions ---
        bottom_frame = ttk.Frame(main_frame, padding="10")
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        
        # Modern Large Buttons
        style = ttk.Style()
        style.configure("Action.TButton", font=("Arial", 10, "bold"))
        
        self.btn_light = ttk.Button(bottom_frame, text="[F1] CONTORNO (LUZ)", style="Action.TButton", command=self.start_light_mode)
        self.btn_light.pack(side=tk.LEFT, padx=5, ipadx=10, ipady=10)
        
        ttk.Button(bottom_frame, text="[F3] BORDAS (QUADRO)", style="Action.TButton", command=self.start_frame_mode).pack(side=tk.LEFT, padx=5, ipadx=10, ipady=10)

        self.btn_mark = ttk.Button(bottom_frame, text="[F2] GRAVAR", style="Action.TButton", command=self.start_mark_mode)
        self.btn_mark.pack(side=tk.LEFT, padx=10, ipadx=10, ipady=10)
        
        ttk.Button(bottom_frame, text="[ESC] PARAR TUDO", command=self.abort_operation).pack(side=tk.RIGHT, padx=10, ipadx=10, ipady=10)
        
        # Bindings
        self.root.bind("<F1>", lambda e: self.start_light_mode())
        self.root.bind("<F2>", lambda e: self.start_mark_mode())
        self.root.bind("<F3>", lambda e: self.start_frame_mode())
        self.root.bind("<Escape>", lambda e: self.abort_operation())
        
        # Bind MouseWheel to the left scrollable canvas recursively for all widgets inside left_container
        def bind_left_mousewheel(widget):
            widget.bind("<MouseWheel>", lambda e: left_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"), add="+")
            for child in widget.winfo_children():
                bind_left_mousewheel(child)
        bind_left_mousewheel(left_container)

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
        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", pady=2)
        ent = ttk.Entry(parent, textvariable=var, width=12)
        ent.grid(row=row, column=1, padx=5, pady=2)
        return ent

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
            self.main_svg_file = file_path
            self.lbl_filename.config(text=os.path.basename(file_path))
            self.var_content_mode.set("svg")
            
            # Reset any generated text context so it doesn't conflict
            # self.var_text_type.set("Texto") # Optional, but we just want to ensure we compose the SVG
            
            # Switch to SVG tab automatically
            self.notebook.select(self.tab_svg)
            
            # Use composer to render it cleanly and register paths
            self.update_content_mode(from_btn=False)

    def add_to_scene(self):
        file_path = filedialog.askopenfilename(filetypes=[("SVG files", "*.svg")])
        if file_path:
            obj_id = f"custom_{len(self.custom_scene_items)}"
            self.custom_scene_items.append({
                'id': obj_id,
                'file': file_path,
                'source_id': '*',
                'ox': 0.0, 'oy': 0.0,
                'sx': 1.0, 'sy': 1.0,
                'rot': 0.0,
                'z': 100.0 + len(self.custom_scene_items),
                'color': '', 
                'visible': True,
                'preserve_ids': False
            })
            # Ensure we treat everything as a composite SVG now
            self.var_content_mode.set("svg")
            self.update_content_mode(from_btn=False)

    def browse_cal(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if file_path:
            self.var_cal_file.set(file_path)

    def load_pdf_batch(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            extractor = pdf_module.PDFSerialExtractor(file_path)
            self.pdf_serials = extractor.extract_serials()
            if self.pdf_serials:
                self.current_serial_idx = 0
                self.var_batch_active.set(True)
                self.var_db_mode.set(False)
                self.btn_next_serial.config(state="normal")
                
                # Popula a arvore
                for i in self.tree_batch.get_children():
                    self.tree_batch.delete(i)
                for i, s in enumerate(self.pdf_serials):
                    self.tree_batch.insert("", "end", iid=str(i), values=("Pendente", s))
                
                self._update_batch_ui()
                self.var_input_text.set(self.pdf_serials[0])
                self.update_content_mode()
                messagebox.showinfo("Lote", f"Carregadas {len(self.pdf_serials)} seriais do PDF.")
            else:
                messagebox.showwarning("Aviso", "Nenhuma serial encontrada no PDF.")

    def next_batch_serial(self):
        if self.var_db_mode.get():
            self._next_db_serial()
        else:
            self._next_pdf_serial()

    def _next_pdf_serial(self):
        if not self.pdf_serials: return
        
        # Mark current as Done if progressing naturally
        if self.current_serial_idx >= 0 and self.current_serial_idx < len(self.pdf_serials):
             item_id = str(self.current_serial_idx)
             if self.tree_batch.exists(item_id):
                 vals = self.tree_batch.item(item_id, "values")
                 self.tree_batch.item(item_id, values=("Gravado", vals[1]))
                 self.tree_batch.item(item_id, tags=("gravado",))
                 self.tree_batch.tag_configure("gravado", foreground="green")

        if self.current_serial_idx < len(self.pdf_serials) - 1:
            self.current_serial_idx += 1
            self._update_batch_ui()
            self.var_input_text.set(self.pdf_serials[self.current_serial_idx])
            self.update_content_mode()
        else:
            messagebox.showinfo("Fim do Lote", "Todas as seriais foram processadas.")
            self.var_batch_active.set(False)
            self.btn_next_serial.config(state="disabled")

    def _update_batch_ui(self):
        self.lbl_batch_status.config(text=f"Item {self.current_serial_idx + 1} de {len(self.pdf_serials)}")
        # Highlight in Treeview
        item_id = str(self.current_serial_idx)
        if self.tree_batch.exists(item_id):
            self.tree_batch.selection_set(item_id)
            self.tree_batch.see(item_id)

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

    def on_batch_tree_double_click(self, event):
        item = self.tree_batch.identify_row(event.y)
        if item:
            # Extract serial from the clicked row
            vals = self.tree_batch.item(item, "values")
            serial_clicked = vals[1]
            try:
                idx = self.pdf_serials.index(serial_clicked)
                self.current_serial_idx = idx
                self._update_batch_ui()
                self.var_input_text.set(self.pdf_serials[self.current_serial_idx])
                self.update_content_mode()
            except ValueError:
                pass

    def load_svg_preview(self, reset_fit=False):
        print(f"[DEBUG] Delegating load_svg_preview to PreviewManager: {self.current_svg} reset_fit={reset_fit}")
        self.preview_manager.load_svg(self.current_svg, reset_fit=reset_fit)

    def _on_scale_change(self, *args):
        if not self.current_svg: return
        try:
            scale_val = self.var_scale.get()
            if not scale_val: return
            scale = float(scale_val)
            w_mm = self.svg_raw_width * scale
            h_mm = self.svg_raw_height * scale
            
            # Update vars only if not focused, to avoid typing interference
            if self.root.focus_get() != self.entry_width_mm:
                self.var_width_mm.set(f"{w_mm:.2f}")
            if self.root.focus_get() != self.entry_height_mm:
                self.var_height_mm.set(f"{h_mm:.2f}")
        except:
            pass

    def _on_width_mm_change(self, *args):
        if not self.current_svg: return
        if self.root.focus_get() != self.entry_width_mm: return
        try:
            val = self.var_width_mm.get()
            if not val: return
            w_mm = float(val)
            if self.svg_raw_width > 0:
                scale = w_mm / self.svg_raw_width
                self.var_scale.set(f"{scale:.4f}")
        except:
            pass

    def _on_height_mm_change(self, *args):
        if not self.current_svg: return
        if self.root.focus_get() != self.entry_height_mm: return
        try:
            val = self.var_height_mm.get()
            if not val: return
            h_mm = float(val)
            if self.svg_raw_height > 0:
                scale = h_mm / self.svg_raw_height
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
        default_presets = {
            "Aço Inox": {"power": "60", "speed": "300", "freq": "20"}, 
            "Alumínio": {"power": "80", "speed": "500", "freq": "35"},
            "Arte 1 (Serial Banco)": {
                "power": "25", "speed": "3500", "freq": "60",
                "hatch_enable": True, "hatch_angle": "90", "hatch_spacing": "10.0",
                "offset_x": "-15.24", "offset_y": "-31.89", "scale": "1.0",
                "width_mm": "14.00", "height_mm": "39.62",
                "text_type": "Code 128 + Serial", "text_pos": "bottom",
                "barcode_h": "6.0", "barcode_w_scale": "1.338",
                "text_scale": "2.5", "text_x_off": "0.0", "text_y_off": "0.0",
                "barcode_rot": "90", "text_rot": "270",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "group_barcode": True
            },
            "Arte 2 (Serial Banco)": {
                "power": "25", "speed": "3500", "freq": "60",
                "hatch_enable": True, "hatch_angle": "90", "hatch_spacing": "10.0",
                "offset_x": "0.0", "offset_y": "0.0", "scale": "1.0",
                "width_mm": "29.00", "height_mm": "9.00",
                "text_type": "Code 128 + Serial", "text_pos": "bottom",
                "barcode_h": "5.1", "barcode_w_scale": "1.0",
                "text_scale": "2.5", "text_x_off": "0.0", "text_y_off": "0.0",
                "barcode_rot": "180", "text_rot": "180",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "group_barcode": True
            },
            "Arte 1 + 2 (Frontal + Traseira)": {
                "power": "25", "speed": "3500", "freq": "60",
                "hatch_enable": True, "hatch_angle": "90", "hatch_spacing": "10.0",
                "offset_x": "0.0", "offset_y": "0.0", "scale": "1.0",
                "text_type": "Code 128 + Serial", "text_pos": "bottom",
                "barcode_h": "6.0", "barcode_w_scale": "1.338",
                "text_scale": "2.5", "text_x_off": "0.0", "text_y_off": "0.0",
                "barcode_rot": "90", "text_rot": "270",
                "text_font": "arial.ttf", "text_space": "0.0", "barcode_type": "gs1_128",
                "group_barcode": True,
                "is_combined": True
            }
        }
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge default preset or overwrite "Arte 1" / "Arte 2" to match current specs
                    for k, v in default_presets.items():
                        if k not in loaded or k in ("Arte 1 (Serial Banco)", "Arte 2 (Serial Banco)", "Arte 1 + 2 (Frontal + Traseira)"):
                            loaded[k] = v
                    return loaded
            except:
                pass
        return default_presets

    def load_selected_preset(self):
        name = self.preset_combo.get()
        if name in self.presets:
            self.selected_obj.set("")
            self.tree_objs.selection_set(())
            self.sync_selected_object_controls()
            p = self.presets[name]
            # Standard laser parameters
            if "power" in p: self.var_power.set(p["power"])
            if "speed" in p: self.var_speed.set(p["speed"])
            if "freq" in p: self.var_freq.set(p["freq"])
            # Hatch parameters
            if "hatch_enable" in p: self.var_hatch_enable.set(p["hatch_enable"])
            if "hatch_angle" in p: self.var_hatch_angle.set(p["hatch_angle"])
            if "hatch_spacing" in p: self.var_hatch_spacing.set(p["hatch_spacing"])
            # Offsets and Scaling
            if "offset_x" in p: self.var_offset_x.set(p["offset_x"])
            if "offset_y" in p: self.var_offset_y.set(p["offset_y"])
            if "scale" in p: self.var_scale.set(p["scale"])
            
            # MM sizes with backward compatibility for CM
            if "width_mm" in p:
                self.var_width_mm.set(p["width_mm"])
            elif "width_cm" in p:
                try: self.var_width_mm.set(f"{float(p['width_cm']) * 10.0:.2f}")
                except: pass
                
            if "height_mm" in p:
                self.var_height_mm.set(p["height_mm"])
            elif "height_cm" in p:
                try: self.var_height_mm.set(f"{float(p['height_cm']) * 10.0:.2f}")
                except: pass

            # Barcode/Text settings
            if "text_type" in p: self.var_text_type.set(p["text_type"])
            if "text_pos" in p: self.var_text_pos.set(p["text_pos"])
            if "barcode_h" in p: self.var_barcode_h.set(p["barcode_h"])
            if "barcode_w_scale" in p: self.var_barcode_w_scale.set(p["barcode_w_scale"])
            if "text_scale" in p: self.var_text_scale.set(p["text_scale"])
            if "text_x_off" in p: self.var_text_x_off.set(p["text_x_off"])
            if "text_y_off" in p: self.var_text_y_off.set(p["text_y_off"])
            if "barcode_rot" in p: self.var_barcode_rot.set(p["barcode_rot"])
            if "text_rot" in p: self.var_text_rot.set(p["text_rot"])
            if "text_font" in p: self.var_text_font.set(p["text_font"])
            if "text_space" in p: self.var_text_space.set(p["text_space"])
            if "barcode_type" in p: self.var_barcode_type.set(p["barcode_type"])
            if "Serial Banco" in name:
                self.current_pen_name.set("Preto (#000000)")
                self._sync_serial_black_pen_settings()
            if "is_combined" in p:
                self.is_combined_mode = bool(p["is_combined"])
            else:
                self.is_combined_mode = False
            
            # Force UI workspace refresh
            self.update_content_mode(from_btn=True)

    def save_current_preset(self):
        name = tk.simpledialog.askstring("Novo Preset", "Nome do Preset:")
        if name:
            self.presets[name] = {
                "power": self.var_power.get(),
                "speed": self.var_speed.get(),
                "freq": self.var_freq.get(),
                "hatch_enable": self.var_hatch_enable.get(),
                "hatch_angle": self.var_hatch_angle.get(),
                "hatch_spacing": self.var_hatch_spacing.get(),
                "offset_x": self.var_offset_x.get(),
                "offset_y": self.var_offset_y.get(),
                "scale": self.var_scale.get(),
                "width_mm": self.var_width_mm.get(),
                "height_mm": self.var_height_mm.get(),
                "text_type": self.var_text_type.get(),
                "text_pos": self.var_text_pos.get(),
                "barcode_h": self.var_barcode_h.get(),
                "barcode_w_scale": self.var_barcode_w_scale.get(),
                "text_scale": self.var_text_scale.get(),
                "text_x_off": self.var_text_x_off.get(),
                "text_y_off": self.var_text_y_off.get(),
                "barcode_rot": self.var_barcode_rot.get(),
                "text_rot": self.var_text_rot.get(),
                "text_font": self.var_text_font.get(),
                "text_space": self.var_text_space.get(),
                "barcode_type": self.var_barcode_type.get(),
                "group_barcode": self.var_group_barcode.get(),
                "is_combined": getattr(self, 'is_combined_mode', False)
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

    def apply_quick_transform(self, op):
        """Phase 2: Quick transformations like rotate, mirror, etc."""
        sel = self.selected_obj.get()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um objeto no preview primeiro.")
            return

        custom_item = next((i for i in self.custom_scene_items if i['id'] == sel), None)
        if custom_item:
            if op == "rotate":
                custom_item['rot'] = (float(custom_item.get('rot', 0.0)) + 90.0) % 360.0
            elif op == "mirror_h":
                custom_item['sx'] = -float(custom_item.get('sx', 1.0))
            elif op == "mirror_v":
                custom_item['sy'] = -float(custom_item.get('sy', 1.0))
            elif op == "center":
                custom_item['ox'] = 0.0
                custom_item['oy'] = 0.0
            elif op == "reset":
                custom_item['sx'] = 1.0
                custom_item['sy'] = 1.0
                custom_item['ox'] = 0.0
                custom_item['oy'] = 0.0
                custom_item['rot'] = 0.0
            self.sync_selected_object_controls()
            self.update_content_mode()
            return

        if op == "rotate":
            if sel == "barcode":
                val = float(self.var_barcode_rot.get())
                self.var_barcode_rot.set(str((val + 90) % 360))
            else:
                val = float(self.var_text_rot.get())
                self.var_text_rot.set(str((val + 90) % 360))
        elif op == "mirror_h":
            if sel == "barcode":
                val = float(self.var_barcode_w_scale.get())
                self.var_barcode_w_scale.set(str(-val))
            else:
                val = float(self.var_text_scale.get())
                self.var_text_scale.set(str(-val))
        elif op == "center":
            self.var_offset_x.set("0.0")
            self.var_offset_y.set("0.0")
            self.var_text_x_off.set("0.0")
            self.var_text_y_off.set("0.0")
        elif op == "reset":
            self.var_barcode_h.set("20.0")
            self.var_barcode_w_scale.set("1.0")
            self.var_barcode_rot.set("0")
            self.var_text_scale.set("1.0")
            self.var_text_x_off.set("0.0")
            self.var_text_y_off.set("0.0")
            self.var_text_rot.set("0")
            
        self.update_content_mode()

    def sync_selected_object_controls(self):
        """Sync selected custom SVG object transform values into UI fields and update Global Scale."""
        sel = self.selected_obj.get()
        if not sel:
            if hasattr(self, 'lbl_selected_obj_name'):
                self.lbl_selected_obj_name.config(text="Nenhum objeto selecionado")
            self.var_obj_scale_x.set("1.0000")
            self.var_obj_scale_y.set("1.0000")
            self.var_obj_off_x.set("0.0000")
            self.var_obj_off_y.set("0.0000")
            self.var_obj_rot.set("0.0")
            return
            
        if hasattr(self, 'lbl_selected_obj_name'):
            display_name = sel
            if sel == "base_1": display_name = "Arte 1 (Frontal)"
            elif sel == "base_2": display_name = "Arte 2 (Traseira)"
            elif sel == "barcode": display_name = "Código de Barras"
            elif sel == "text": display_name = "Texto Serial"
            elif sel.startswith("custom_"):
                custom_item = next((i for i in self.custom_scene_items if i['id'] == sel), None)
                if custom_item:
                    display_name = f"Arte ({os.path.basename(custom_item['file'])})"
            self.lbl_selected_obj_name.config(text=f"Objeto: {display_name}")
        if hasattr(self, 'preview_manager') and hasattr(self.preview_manager, 'obj_dims'):
            dims = self.preview_manager.obj_dims.get(sel)
            if dims and dims[0] > 0 and dims[1] > 0:
                # dims are in mm. The Global panel uses mm.
                # Only update if the object actually has a non-zero size
                self.svg_raw_width = dims[0]
                self.svg_raw_height = dims[1]
                
                # Apply current scale to show final mm size
                try:
                    sc = float(self.var_scale.get())
                except:
                    sc = 1.0
                    
                self.var_width_mm.set(f"{(dims[0] * sc):.2f}")
                self.var_height_mm.set(f"{(dims[1] * sc):.2f}")

        # Sync Transform Controls
        if sel in ("base_1", "base_2"):
            ox, oy = self.combined_offsets[sel]
            self.var_obj_scale_x.set("1.0000")
            self.var_obj_scale_y.set("1.0000")
            self.var_obj_off_x.set(f"{ox:.4f}")
            self.var_obj_off_y.set(f"{oy:.4f}")
            self.var_obj_rot.set("0.0")
            return

        custom_item = next((i for i in self.custom_scene_items if i['id'] == sel), None)
        if not custom_item:
            self.var_obj_scale_x.set("1.0000")
            self.var_obj_scale_y.set("1.0000")
            self.var_obj_off_x.set("0.0000")
            self.var_obj_off_y.set("0.0000")
            self.var_obj_rot.set("0.0")
            return
        self.var_obj_scale_x.set(f"{float(custom_item.get('sx', 1.0)):.4f}")
        self.var_obj_scale_y.set(f"{float(custom_item.get('sy', 1.0)):.4f}")
        self.var_obj_off_x.set(f"{float(custom_item.get('ox', 0.0)):.4f}")
        self.var_obj_off_y.set(f"{float(custom_item.get('oy', 0.0)):.4f}")
        self.var_obj_rot.set(f"{float(custom_item.get('rot', 0.0)):.4f}")

    def apply_selected_object_adjustments(self):
        """Apply manual transform values to selected custom SVG object."""
        sel = self.selected_obj.get()
        if sel in ("base_1", "base_2"):
            try:
                self.combined_offsets[sel][0] = float(self.var_obj_off_x.get())
                self.combined_offsets[sel][1] = float(self.var_obj_off_y.get())
                self.update_content_mode()
            except ValueError:
                messagebox.showerror("Erro", "Valores invalidos nos campos da arte selecionada.")
            return

        custom_item = next((i for i in self.custom_scene_items if i['id'] == sel), None)
        if not custom_item:
            messagebox.showinfo("Aviso", "Selecione uma arte SVG (custom_*) para aplicar escala/offset/rotacao.")
            return
        try:
            sx = float(self.var_obj_scale_x.get())
            sy = float(self.var_obj_scale_y.get())
            ox = float(self.var_obj_off_x.get())
            oy = float(self.var_obj_off_y.get())
            rot = float(self.var_obj_rot.get())
        except ValueError:
            messagebox.showerror("Erro", "Valores invalidos nos campos da arte SVG selecionada.")
            return

        custom_item['sx'] = sx
        custom_item['sy'] = sy
        custom_item['ox'] = ox
        custom_item['oy'] = oy
        custom_item['rot'] = rot
        # Keep selected custom art on top of barcode/text in the composed workspace.
        max_z = max(([float(i.get('z', 0.0)) for i in self.custom_scene_items] + [100.0]))
        custom_item['z'] = max_z + 1.0
        self.update_content_mode()

    def _apply_selected_custom_transform_from_ui(self):
        """Silently apply object transform fields to currently selected custom item, if any."""
        sel = self.selected_obj.get()
        if sel in ("base_1", "base_2"):
            try:
                self.combined_offsets[sel][0] = float(self.var_obj_off_x.get())
                self.combined_offsets[sel][1] = float(self.var_obj_off_y.get())
            except ValueError:
                pass
            return

        custom_item = next((i for i in self.custom_scene_items if i['id'] == sel), None)
        if not custom_item:
            return
        try:
            custom_item['sx'] = float(self.var_obj_scale_x.get())
            custom_item['sy'] = float(self.var_obj_scale_y.get())
            custom_item['ox'] = float(self.var_obj_off_x.get())
            custom_item['oy'] = float(self.var_obj_off_y.get())
            custom_item['rot'] = float(self.var_obj_rot.get())
        except ValueError:
            return

    def on_mouse_wheel(self, event):
        """Handle zooming in the canvas with mouse wheel"""
        if not self.current_svg or self.current_svg == "DUMMY": return
        
        # Windows/Mac use delta, Linux uses button 4/5
        if event.num == 5 or event.delta < 0:
            self.preview_zoom *= 0.9 # Zoom out
        if event.num == 4 or event.delta > 0:
            self.preview_zoom *= 1.1 # Zoom in
            
        self.load_svg_preview()

    def on_pen_selected(self, event=None):
        name = self.current_pen_name.get()
        if name in self.pens:
            p = self.pens[name]
            self.var_power.set(p["power"])
            self.var_speed.set(p["speed"])
            self.var_freq.set(p["freq"])
            self.var_hatch_enable.set(p["hatch_ena"])
            self.var_hatch_angle.set(p["hatch_ang"])
            self.var_hatch_spacing.set(p["hatch_spc"])

    def _sync_current_pen_settings(self):
        name = self.current_pen_name.get()
        if name in self.pens:
            self.pens[name]["power"] = self.var_power.get()
            self.pens[name]["speed"] = self.var_speed.get()
            self.pens[name]["freq"] = self.var_freq.get()
            self.pens[name]["hatch_ena"] = self.var_hatch_enable.get()
            self.pens[name]["hatch_ang"] = self.var_hatch_angle.get()
            self.pens[name]["hatch_spc"] = self.var_hatch_spacing.get()


    def _sync_serial_black_pen_settings(self):
        name = "Preto (#000000)"
        if name in self.pens:
            self.pens[name]["power"] = self.var_power.get()
            self.pens[name]["speed"] = self.var_speed.get()
            self.pens[name]["freq"] = self.var_freq.get()
            self.pens[name]["hatch_ena"] = self.var_hatch_enable.get()
            self.pens[name]["hatch_ang"] = self.var_hatch_angle.get()
            self.pens[name]["hatch_spc"] = self.var_hatch_spacing.get()

    def save_pen_settings(self):
        name = self.current_pen_name.get()
        if name in self.pens:
            self._sync_current_pen_settings()
            messagebox.showinfo("Sucesso", f"Parametros salvos para a caneta {name}.")

    def show_color_menu(self, event):
        item = self.tree_objs.identify_row(event.y)
        if item:
            self.tree_objs.selection_set(item)
            self.selected_obj.set(item)
            self.preview_manager.draw_selection()
            self.color_menu.tk_popup(event.x_root, event.y_root)

    def assign_pen_to_selected(self, pen_name):
        sel = self.selected_obj.get()
        if sel:
            self.obj_colors[sel] = pen_name
            # Refresh Treeview UI
            col = "Preto" if "Preto" in pen_name else ("Vermelho" if "Vermelho" in pen_name else "Azul")
            self.tree_objs.set(sel, column="cor", value=col)
            # Update SVG colors immediately
            self.update_content_mode()

    def update_content_mode(self, from_btn=False):
        """Called when the user clicks 'Gerar' on the Text/Barcode tab, or after drag/add."""
        # Apply pending values from object transform fields so both buttons keep behavior consistent.
        self._apply_selected_custom_transform_from_ui()

        if from_btn:
            t = self.var_text_type.get()
            if t == "Texto": self.var_content_mode.set("text")
            elif t == "QR Code": self.var_content_mode.set("barcode")
            else: self.var_content_mode.set("code128_serial")
            
            # If user explicitly clicked Generate on the text tab, clear main custom SVG base
            if hasattr(self, 'main_svg_file'):
                self.main_svg_file = None

        current_sel = self.selected_obj.get()
        t = self.var_text_type.get()
        print(f"[DEBUG] update_content_mode: mode={self.var_content_mode.get()}, type={t}, text={self.var_input_text.get()}")

        base_items = []
        
        if self.var_content_mode.get() == "svg" and hasattr(self, 'main_svg_file') and self.main_svg_file and os.path.exists(self.main_svg_file):
            base_items.append({
                'id': 'main_svg', 'file': self.main_svg_file,
                'ox': 0, 'oy': 0, 'sx': 1, 'sy': 1, 'rot': 0, 'z': 0, 'color': '',
                'visible': True, 'preserve_ids': True
            })
        elif self.var_content_mode.get() == "code128_serial" or self.var_content_mode.get() == "svg":
            gen = barcode_module.BarcodeGenerator()
            if getattr(self, 'is_combined_mode', False):
                try:
                    bc_1_hex = self.pens.get(self.obj_colors.get("base_1", "Preto (#000000)"), {}).get("color_hex", "#000000")
                    tc_1_hex = self.pens.get(self.obj_colors.get("base_1", "Preto (#000000)"), {}).get("color_hex", "#000000")
                    bc_2_hex = self.pens.get(self.obj_colors.get("base_2", "Preto (#000000)"), {}).get("color_hex", "#000000")
                    tc_2_hex = self.pens.get(self.obj_colors.get("base_2", "Preto (#000000)"), {}).get("color_hex", "#000000")
                except:
                    bc_1_hex, tc_1_hex = "#000000", "#000000"
                    bc_2_hex, tc_2_hex = "#000000", "#000000"

                gen.generate_code128_svg(
                    self.var_input_text.get(), 
                    "temp_barcode_1.svg", 
                    barcode_height=6.0, 
                    text_pos="bottom",
                    barcode_w_scale=1.338,
                    text_scale=2.5,
                    text_x_off=0.0,
                    text_y_off=0.0,
                    barcode_rot=90,
                    text_rot=270,
                    barcode_color=bc_1_hex,
                    text_color=tc_1_hex,
                    barcode_type="gs1_128",
                    font_name="arial.ttf",
                    text_space=0.0,
                    group=True
                )
                gen.generate_code128_svg(
                    self.var_input_text.get(), 
                    "temp_barcode_2.svg", 
                    barcode_height=5.1, 
                    text_pos="bottom",
                    barcode_w_scale=1.0,
                    text_scale=2.5,
                    text_x_off=0.0,
                    text_y_off=0.0,
                    barcode_rot=180,
                    text_rot=180,
                    barcode_color=bc_2_hex,
                    text_color=tc_2_hex,
                    barcode_type="gs1_128",
                    font_name="arial.ttf",
                    text_space=0.0,
                    group=True
                )
                base_items.append({
                    'id': 'base_1', 'file': 'temp_barcode_1.svg',
                    'ox': self.combined_offsets['base_1'][0], 'oy': self.combined_offsets['base_1'][1],
                    'sx': 1.0, 'sy': 1.0, 'rot': 0.0, 'z': 10, 'color': '',
                    'visible': self.obj_visibility.get("base_1", True), 'preserve_ids': False
                })
                base_items.append({
                    'id': 'base_2', 'file': 'temp_barcode_2.svg',
                    'ox': self.combined_offsets['base_2'][0], 'oy': self.combined_offsets['base_2'][1],
                    'sx': 1.0, 'sy': 1.0, 'rot': 0.0, 'z': 11, 'color': '',
                    'visible': self.obj_visibility.get("base_2", True), 'preserve_ids': False
                })
            else:
                try:
                    bh = float(self.var_barcode_h.get())
                    bw = float(self.var_barcode_w_scale.get())
                    ts = float(self.var_text_scale.get())
                    tx = float(self.var_text_x_off.get())
                    ty = float(self.var_text_y_off.get())
                    br = float(self.var_barcode_rot.get())
                    tr = float(self.var_text_rot.get())
                    font_name = self.var_text_font.get()
                    t_space = float(self.var_text_space.get())
                    b_type = self.var_barcode_type.get()
                    bc_hex = self.pens.get(self.obj_colors.get("barcode", "Preto (#000000)"), {}).get("color_hex", "#000000")
                    tc_hex = self.pens.get(self.obj_colors.get("text", "Preto (#000000)"), {}).get("color_hex", "#000000")
                except Exception as e:
                    print(f"[DEBUG] Error retrieving UI params: {e}")
                    bh, bw, ts, tx, ty, br, tr = 20.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0
                    font_name, t_space, b_type = "arial.ttf", 0.0, "code128"
                    bc_hex, tc_hex = "#000000", "#000000"

                gen.generate_code128_svg(
                    self.var_input_text.get(), 
                    "temp_barcode.svg", 
                    barcode_height=bh, 
                    text_pos=self.var_text_pos.get(),
                    barcode_w_scale=bw,
                    text_scale=ts,
                    text_x_off=tx,
                    text_y_off=ty,
                    barcode_rot=br,
                    text_rot=tr,
                    barcode_color=bc_hex,
                    text_color=tc_hex,
                    barcode_type=b_type,
                    font_name=font_name,
                    text_space=t_space,
                    group=self.var_group_barcode.get()
                )
                
                base_items.append({
                    'id': 'base', 'file': 'temp_barcode.svg',
                    'ox': 0, 'oy': 0, 'sx': 1, 'sy': 1, 'rot': 0, 'z': 10, 'color': '',
                    'visible': self.obj_visibility.get("base", True), 'preserve_ids': True
                })

        if self.var_content_mode.get() == "svg" or (self.var_content_mode.get() == "code128_serial" and (self.custom_scene_items or getattr(self, 'is_combined_mode', False))):
            all_items = base_items + self.custom_scene_items
            for item in self.custom_scene_items:
                c_name = self.obj_colors.get(item['id'])
                if c_name:
                    item['color'] = self.pens.get(c_name, {}).get("color_hex", "")
                print(
                    f"[DEBUG] custom_item id={item['id']} ox={item.get('ox', 0)} oy={item.get('oy', 0)} "
                    f"sx={item.get('sx', 1)} sy={item.get('sy', 1)} rot={item.get('rot', 0)} z={item.get('z', 0)} visible={item.get('visible', True)}"
                )
                    
            composer_module.SceneComposer.compose_workspace(all_items, "temp_workspace.svg")
            self.current_svg = "temp_workspace.svg"
            print("[DEBUG] Workspace Composed.")
        elif self.var_content_mode.get() == "code128_serial":
            self.current_svg = "temp_barcode.svg"
        else:
            self.current_svg = "DUMMY"
            
        if self.current_svg != "DUMMY":
            self.load_svg_preview(reset_fit=from_btn)
            self._populate_treeview(is_custom_svg=(self.var_content_mode.get() == "svg"))
            self.selected_obj.set(current_sel)
            self.preview_manager.draw_selection()
            self.sync_selected_object_controls() # Ensure dimensions don't revert to full bounds
            return
            
        self.svg_bounds = (0, self.svg_raw_width, 0, self.svg_raw_height)
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

    def _populate_treeview(self, is_custom_svg=False):
        # Clear tree
        for i in self.tree_objs.get_children():
            self.tree_objs.delete(i)
            
        if self.current_svg and os.path.exists(self.current_svg):
            # Always show barcode elements if we are generating them
            if self.var_text_type.get() == "Code 128 + Serial" or self.var_content_mode.get() == "code128_serial":
                if getattr(self, 'is_combined_mode', False):
                    if 'base_1' not in self.obj_visibility: self.obj_visibility['base_1'] = True
                    if 'base_2' not in self.obj_visibility: self.obj_visibility['base_2'] = True
                    v_1 = "Sim" if self.obj_visibility['base_1'] else "Não"
                    v_2 = "Sim" if self.obj_visibility['base_2'] else "Não"
                    c_1 = self.obj_colors.get('base_1', 'Preto (#000000)').split(' ')[0]
                    c_2 = self.obj_colors.get('base_2', 'Preto (#000000)').split(' ')[0]
                    self.tree_objs.insert("", "end", iid="base_1", values=("Arte 1 (Frontal)", v_1, c_1))
                    self.tree_objs.insert("", "end", iid="base_2", values=("Arte 2 (Traseira)", v_2, c_2))
                else:
                    if self.var_group_barcode.get():
                        if 'barcode' not in self.obj_visibility: self.obj_visibility['barcode'] = True
                        v_bar = "Sim" if self.obj_visibility['barcode'] else "Não"
                        c_bar = self.obj_colors.get('barcode', 'Preto (#000000)').split(' ')[0]
                        self.tree_objs.insert("", "end", iid="barcode", values=("Código + Serial", v_bar, c_bar))
                    else:
                        if 'barcode' not in self.obj_visibility: self.obj_visibility['barcode'] = True
                        if 'text' not in self.obj_visibility: self.obj_visibility['text'] = True
                        
                        v_bar = "Sim" if self.obj_visibility['barcode'] else "Não"
                        v_txt = "Sim" if self.obj_visibility['text'] else "Não"
                        
                        c_bar = self.obj_colors.get('barcode', 'Preto (#000000)').split(' ')[0]
                        c_txt = self.obj_colors.get('text', 'Preto (#000000)').split(' ')[0]
                        
                        self.tree_objs.insert("", "end", iid="barcode", values=("Código de Barras", v_bar, c_bar))
                        self.tree_objs.insert("", "end", iid="text", values=("Texto Serial", v_txt, c_txt))
            
            # Now show custom composed items
            if is_custom_svg or self.custom_scene_items:
                for item in self.custom_scene_items:
                    tag = item['id']
                    if tag not in self.obj_visibility: self.obj_visibility[tag] = True
                    if tag not in self.obj_colors: self.obj_colors[tag] = "Preto (#000000)"
                    
                    v_tag = "Sim" if self.obj_visibility[tag] else "Não"
                    c_tag = self.obj_colors[tag].split(' ')[0]
                    # Display the filename or a custom name
                    display_name = f"Arte ({os.path.basename(item['file'])})"
                    self.tree_objs.insert("", "end", iid=tag, values=(display_name, v_tag, c_tag))

    def on_tree_select(self, event):
        sel = self.tree_objs.selection()
        if sel:
            self.selected_obj.set(sel[0])
        else:
            self.selected_obj.set("")
        self.sync_selected_object_controls()
        self.preview_manager.draw_selection()

    def on_tree_click(self, event):
        region = self.tree_objs.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree_objs.identify_column(event.x)
            if column == '#2': # Visível column
                item = self.tree_objs.identify_row(event.y)
                if item:
                    # Toggle visibility
                    current = self.obj_visibility.get(item, True)
                    self.obj_visibility[item] = not current
                    # Update Treeview text
                    new_val = "Sim" if self.obj_visibility[item] else "Não"
                    self.tree_objs.set(item, column="visivel", value=new_val)
                    # Update Canvas (Hide/Show)
                    if self.obj_visibility[item]:
                        self.canvas.itemconfig(item, state="normal")
                    else:
                        self.canvas.itemconfig(item, state="hidden")
                        self.canvas.delete("sel_box")
                        self.canvas.delete("handle")
                        self.canvas.delete("dim_label")

    def _on_tab_changed(self, event):
        tab_id = self.notebook.index(self.notebook.select())
        if tab_id == 0: # SVG
            self.var_content_mode.set("svg")
        elif tab_id == 1: # Text/Code
            t = self.var_text_type.get()
            if t == "Texto": self.var_content_mode.set("text")
            elif t == "QR Code": self.var_content_mode.set("barcode")
            else: self.var_content_mode.set("code128_serial")

    def _get_barcode_bounds(self, text, sc):
        # Placeholder for estimating barcode bounds (Code 128)
        # 1 character in Code 128 is approx 11 modules. 
        # Plus quiet zones and padding.
        modules = (len(text) * 11 + 35) 
        w_mm = modules * 0.2 * sc # 0.2 is typical module width
        h_mm = 25 * sc # Typical height
        return (0, w_mm, 0, h_mm)

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
                commands.set_travel_speed(800)
                
                if content_mode == "code128_serial" and (not hasattr(self, 'svg_bounds') or self.svg_bounds == (0, 0, 0, 0)):
                    self.svg_bounds = self._get_barcode_bounds(self.var_input_text.get(), sc)
                
                min_x, max_x, min_y, max_y = self.svg_bounds
                
                # Apply scale globally to the preview frame bounds
                actual_sc = sc
                
                pts = [
                    (min_x * actual_sc + ox, -min_y * actual_sc + oy),
                    (max_x * actual_sc + ox, -min_y * actual_sc + oy),
                    (max_x * actual_sc + ox, -max_y * actual_sc + oy),
                    (min_x * actual_sc + ox, -max_y * actual_sc + oy),
                    (min_x * actual_sc + ox, -min_y * actual_sc + oy)
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
                
                # Generate dynamic pen settings for balor-svg.py
                self._sync_current_pen_settings()
                if content_mode == "code128_serial":
                    self._sync_serial_black_pen_settings()
                settings_csv = "temp_settings.csv"
                with open(settings_csv, "w") as f:
                    for name, p_data in self.pens.items():
                        c_hex = p_data["color_hex"].replace("#", "")
                        # Format: color freq power speed hatch_angle hatch_spacing hatch_pattern repeats (space separated)
                        spc = p_data["hatch_spc"] if p_data["hatch_ena"] else "0"
                        f.write(f"{c_hex} {p_data['freq']} {p_data['power']} {p_data['speed']} {p_data['hatch_ang']} {spc} None 1\n")
                
                settings_arg = ["-s", settings_csv]
                
                # Collect hidden tags
                hidden_tags = []
                for k, v in self.obj_visibility.items():
                    if not v: hidden_tags.append(k)
                hidden_arg = ["--hidden-tags", ",".join(hidden_tags)] if hidden_tags else []
                
                extra_args = ["--repetition", "1", "--travel-speed", "800"] if mode == "light" else []
                ezcad_delay_args = [
                    # Generated SVG hatch uses many short lines; EzCAD native TC values
                    # would eat the beginning/end of each line at 3500 mm/s.
                    "--laser-on-delay", "0",
                    "--laser-off-delay", "0",
                    "--mark-end-delay", "0",
                    "--polygon-delay", "50",
                    "--hatch-power-scale", "0.90",
                    "--hatch-speed-scale", "2.00",
                    "--hatch-overrun", "0.00",
                    "--hatch-serpentine",
                ]
                
                if content_mode == "svg":
                    cmd = [
                        sys.executable, "balor-svg.py", mode,
                        "-f", self.current_svg,
                        "-o", job_file,
                        "--xoff", str(ox),
                        "--yoff", str(oy),
                        "--xscale", str(sc),
                        "--yscale", str(sc)
                    ] + cal_arg + settings_arg + hidden_arg + ezcad_delay_args + extra_args
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
                elif content_mode == "code128_serial":
                    # Use composed workspace if available, otherwise fallback to barcode-only svg.
                    svg_source = self.current_svg if self.current_svg and os.path.exists(self.current_svg) else "temp_barcode.svg"
                    cmd = [
                        sys.executable, "balor-svg.py", mode,
                        "-f", svg_source,
                        "-o", job_file,
                        "--xoff", str(ox),
                        "--yoff", str(oy),
                        "--xscale", str(sc),
                        "--yscale", str(sc)
                    ] + cal_arg + settings_arg + hidden_arg + ezcad_delay_args + extra_args
                
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
                        # Marking Mode
                        self.machine.execute(command_list=commands, loop_count=1)
                        
                        # Auto-Increment if Batch is Active
                        if not self.abort_op and self.var_batch_active.get():
                            # Schedule the UI update safely on the main thread
                            self.root.after(500, self.auto_advance_batch)
                
            if not self.abort_op:
                self.var_status.set("Pronto")
        except Exception as e:
            self.var_status.set("Erro")
            if not self.abort_op:
                messagebox.showerror("Erro", f"Falha na execução:\n{e}")
        finally:
            self.abort_op = False
            self.op_running = False

    def auto_advance_batch(self):
        """Automatically called after a successful mark if batch is active."""
        if not self.var_batch_active.get(): return

        if self.var_db_mode.get():
            # DB MODE: Update Raspberry Pi Database first
            current_record = self.db_serials[self.current_serial_idx]
            log_id = current_record['id']
            
            def _update_task():
                success = self.db_manager.mark_as_engraved(log_id)
                if success:
                    print(f"[AUTO] ID {log_id} marcado no banco.")
                    self.root.after(0, self._finish_auto_advance)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Erro Banco", "Falha ao atualizar status no banco!"))

            threading.Thread(target=_update_task, daemon=True).start()
        else:
            # PDF MODE: Just advance UI
            if self.current_serial_idx < len(self.pdf_serials) - 1:
                self._finish_auto_advance()
            else:
                messagebox.showinfo("Fim do Lote", "Todas as peças do PDF foram gravadas.")
                self.var_batch_active.set(False)
                self.btn_next_serial.config(state="disabled")

    def _finish_auto_advance(self):
        if self.var_db_mode.get():
            self._next_db_serial()
        else:
            self.next_batch_serial()
        self.var_status.set("Pronto para o próximo!")

    def toggle_auto_sync(self):
        if self.var_auto_sync.get():
            self.lbl_db_status.config(text="Auto-Sync: Ativado. Monitorando banco...", foreground="blue")
            threading.Thread(target=self._auto_sync_loop, daemon=True).start()
        else:
            self.lbl_db_status.config(text="Auto-Sync: Desativado.", foreground="black")

    def _auto_sync_loop(self):
        while self.var_auto_sync.get():
            try:
                serials = self.db_manager.get_pending_serials()
                self.root.after(0, lambda s=serials: self._merge_db_results_silently(s))
            except Exception as e:
                print(f"[AUTO-SYNC] Erro no polling: {e}")
            time.sleep(3) # Poll every 3 seconds

    def _merge_db_results_silently(self, new_serials):
        """Appends new database serials and removes absent ones without interrupting selection if possible."""
        existing_ids = {row['id'] for row in self.db_serials}
        new_ids = {row['id'] for row in new_serials}
        
        ids_to_remove = existing_ids - new_ids
        added_count = 0
        removed_count = len(ids_to_remove)
        
        # Add new
        for row in new_serials:
            if row['id'] not in existing_ids:
                self.db_serials.append(row)
                self.tree_db.insert("", "end", iid=str(row['id']), 
                                  values=(row['id'], row['serial'], row['criado_em'].strftime("%d/%m %H:%M")))
                added_count += 1
                
        # Remove absent
        if ids_to_remove:
            self.db_serials = [row for row in self.db_serials if row['id'] not in ids_to_remove]
            for r_id in ids_to_remove:
                if self.tree_db.exists(str(r_id)):
                    self.tree_db.delete(str(r_id))
                    
            if not self.db_serials:
                self.var_batch_active.set(False)
                self.lbl_db_status.config(text="Fila vazia.", foreground="black")
                self.current_serial_idx = -1
            else:
                if self.current_serial_idx >= len(self.db_serials) or self.current_serial_idx < 0:
                    self.current_serial_idx = 0
                
                # Check if current selection is still valid, if not re-select
                sel = self.tree_db.selection()
                if not sel or sel[0] in [str(i) for i in ids_to_remove]:
                    first_row = self.db_serials[self.current_serial_idx]
                    self.var_input_text.set(first_row['serial'])
                    self.tree_db.selection_set(str(first_row['id']))
                    self.update_content_mode()

        if added_count > 0 or removed_count > 0:
            status_text = f"Auto-Sync: {len(self.db_serials)} pendentes."
            if added_count > 0: status_text += f" (+{added_count})"
            if removed_count > 0: status_text += f" (-{removed_count})"
            self.lbl_db_status.config(text=status_text, foreground="blue")
            
            # If the list was empty, automatically select the first new item
            if len(self.db_serials) == added_count and added_count > 0:
                self.current_serial_idx = 0
                self.var_batch_active.set(True)
                self.var_db_mode.set(True)
                
                first_row = self.db_serials[0]
                self.var_input_text.set(first_row['serial'])
                self.tree_db.selection_set(str(first_row['id']))
                self.update_content_mode()

    def load_db_batch(self):
        """Fetch pending serials from Raspberry Pi PostgreSQL database."""
        self.lbl_db_status.config(text="Buscando dados no banco...", foreground="blue")
        self.root.update_idletasks()
        
        def _task():
            serials = self.db_manager.get_pending_serials()
            self.root.after(0, lambda: self._process_db_results(serials))
            
        threading.Thread(target=_task, daemon=True).start()

    def _process_db_results(self, serials):
        if serials:
            self.db_serials = serials
            self.current_serial_idx = 0
            self.var_batch_active.set(True)
            self.var_db_mode.set(True) # Database mode
            
            # Populate Treeview
            for i in self.tree_db.get_children():
                self.tree_db.delete(i)
            
            for row in serials:
                self.tree_db.insert("", "end", iid=str(row['id']), 
                                  values=(row['id'], row['serial'], row['criado_em'].strftime("%d/%m %H:%M")))
            
            self.lbl_db_status.config(text=f"{len(serials)} seriais pendentes no banco.", foreground="green")
            
            # Select first item
            self.var_input_text.set(serials[0]['serial'])
            self.tree_db.selection_set(str(serials[0]['id']))
            self.update_content_mode()
        else:
            self.lbl_db_status.config(text="Nenhum serial pendente (Aprovado + Não Gravado).", foreground="black")
            if not self.var_db_mode.get():
                self.var_batch_active.set(False)

    def clear_db_list(self):
        for i in self.tree_db.get_children():
            self.tree_db.delete(i)
        self.db_serials = []
        self.var_batch_active.set(False)
        self.lbl_db_status.config(text="Lista limpa.")

    def on_db_tree_double_click(self, event):
        item_id = self.tree_db.identify_row(event.y)
        if item_id:
            # Find in db_serials list
            for idx, row in enumerate(self.db_serials):
                if str(row['id']) == item_id:
                    self.current_serial_idx = idx
                    self.var_input_text.set(row['serial'])
                    self.tree_db.selection_set(item_id)
                    self.update_content_mode()
                    break

    def _next_db_serial(self):
        """Advances to the next serial in database mode."""
        if not self.db_serials: return
        
        current_id = str(self.db_serials[self.current_serial_idx]['id'])
        if self.tree_db.exists(current_id):
            self.tree_db.delete(current_id) # Remove from list as it is done
            
        if self.current_serial_idx < len(self.db_serials) - 1:
            self.db_serials.pop(self.current_serial_idx)
            if self.db_serials:
                self.current_serial_idx = 0 # Take the next one in list
                next_row = self.db_serials[0]
                self.var_input_text.set(next_row['serial'])
                self.tree_db.selection_set(str(next_row['id']))
                self.update_content_mode()
                self.lbl_db_status.config(text=f"{len(self.db_serials)} pendentes.")
        else:
            self.db_serials = []
            self.lbl_db_status.config(text="Fim da fila do banco.", foreground="green")
            self.var_batch_active.set(False)

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

