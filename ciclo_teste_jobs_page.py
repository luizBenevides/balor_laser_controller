import threading
import time
import tkinter as tk
import shutil
from tkinter import ttk


DEFAULT_TEST_SERIALS = [
    "4313110010",
    "4313110011",
    "4313110012",
    "4313110013",
    "4313110014",
    "4313110015",
    "4313110016",
    "4313110017",
    "4313110018",
    "4313110019",
]


class CicloTesteJobsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.running = False
        self.worker_thread = None
        self.var_status = tk.StringVar(value="Pronto para teste")
        self.var_execute_laser = tk.BooleanVar(value=False)
        self.var_use_auto_cache = tk.BooleanVar(value=False)
        self.var_simulate_queue = tk.BooleanVar(value=True)
        self.var_simulated_cycle_s = tk.StringVar(value="15.0")
        self.var_queue_lookahead = tk.StringVar(value="4")
        self.var_preheat_s = tk.StringVar(value="120.0")
        self.queue_order_lock = threading.Condition()
        self.queue_next_order = 0
        self.queue_order_counter = 0
        self.serial_vars = [tk.StringVar(value=serial) for serial in DEFAULT_TEST_SERIALS]
        self.build_ui()

    def build_ui(self):
        top = ttk.LabelFrame(self, text="Teste de Ciclo - Geracao de 10 Seriais", padding=10)
        top.pack(fill="x", padx=10, pady=10)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="Status:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        ttk.Label(top, textvariable=self.var_status, foreground="blue", font=("Arial", 10, "bold")).grid(row=0, column=1, sticky="w", padx=5, pady=4)

        buttons = ttk.Frame(top)
        buttons.grid(row=0, column=2, columnspan=3, sticky="e", padx=5, pady=4)
        self.btn_start = ttk.Button(buttons, text="Iniciar Teste 10 Pecas", command=self.start_test)
        self.btn_start.pack(side="left", padx=4)
        ttk.Button(buttons, text="Parar", command=self.stop_test).pack(side="left", padx=4)
        ttk.Button(buttons, text="Limpar Cache", command=self.clear_cache).pack(side="left", padx=4)
        ttk.Button(buttons, text="Gerar Seriais Novos", command=self.fill_unique_serials).pack(side="left", padx=4)
        ttk.Button(buttons, text="Voltar Rotina Automatica", command=self.app.show_auto_page).pack(side="left", padx=4)

        ttk.Checkbutton(
            top,
            text="Usar cache da rotina automatica (nao mede criacao real)",
            variable=self.var_use_auto_cache,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(
            top,
            text="Executar laser fisicamente durante o teste",
            variable=self.var_execute_laser,
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=5, pady=4)
        ttk.Checkbutton(
            top,
            text="Simular fila antecipada",
            variable=self.var_simulate_queue,
        ).grid(row=2, column=0, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Tempo ciclo simulado (s):").grid(row=2, column=1, sticky="e", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_simulated_cycle_s, width=8).grid(row=2, column=2, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Antecipar qtd:").grid(row=2, column=3, sticky="e", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_queue_lookahead, width=5).grid(row=2, column=4, sticky="w", padx=5, pady=4)
        ttk.Label(top, text="Prebuild antes da 1a peca (s):").grid(row=3, column=0, sticky="w", padx=5, pady=4)
        ttk.Entry(top, textvariable=self.var_preheat_s, width=8).grid(row=3, column=1, sticky="w", padx=5, pady=4)
        ttk.Label(
            top,
            text="Sem marcar execucao fisica, este teste NAO conecta na laser: apenas gera Arte 1 + Arte 2 e mede os tempos.",
            foreground="#555555",
        ).grid(row=4, column=0, columnspan=5, sticky="w", padx=5, pady=(2, 4))
        ttk.Label(
            top,
            text="Fila antecipada: simula seriais aprovados no estanque chegando antes da peca entrar na gravacao.",
            foreground="#555555",
        ).grid(row=5, column=0, columnspan=5, sticky="w", padx=5, pady=(2, 4))

        serial_frame = ttk.LabelFrame(self, text="Seriais do Teste", padding=10)
        serial_frame.pack(fill="x", padx=10, pady=5)
        for index, var in enumerate(self.serial_vars):
            row = index // 5
            col = (index % 5) * 2
            ttk.Label(serial_frame, text=f"{index + 1}:").grid(row=row, column=col, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(serial_frame, textvariable=var, width=14).grid(row=row, column=col + 1, sticky="w", padx=(2, 8), pady=3)

        result_frame = ttk.LabelFrame(self, text="Resultado por Peca", padding=10)
        result_frame.pack(fill="both", expand=True, padx=10, pady=5)
        columns = ("idx", "serial", "arte1", "arte2", "total", "status")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=12)
        headings = {
            "idx": "#",
            "serial": "Serial",
            "arte1": "Arte 1 (s)",
            "arte2": "Arte 2 (s)",
            "total": "Total/peca (s)",
            "status": "Status",
        }
        widths = {"idx": 45, "serial": 140, "arte1": 110, "arte2": 110, "total": 120, "status": 430}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center" if col != "status" else "w")
        self.tree.pack(fill="both", expand=True)

        log_frame = ttk.LabelFrame(self, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text = tk.Text(log_frame, height=10, state="disabled", bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        print(f"[CICLO-TESTE] {msg}")

    def set_status(self, msg):
        self.var_status.set(msg)
        self.log(msg)

    def clear_cache(self):
        auto_page = getattr(self.app, "auto_page", None)
        if not auto_page:
            return
        with auto_page.job_cache_lock:
            auto_page.job_cache.clear()
        cache_dir = getattr(auto_page, "job_cache_dir", None)
        if cache_dir:
            shutil.rmtree(cache_dir, ignore_errors=True)
        self.log("Cache em memoria e disco da rotina automatica limpo.")

    def fill_unique_serials(self):
        base = int(time.time()) % 1000000000
        for index, var in enumerate(self.serial_vars):
            var.set(f"9{base + index:09d}")
        self.log("Seriais novos gerados para evitar qualquer HIT de cache antigo.")

    def set_auto_serial_sync(self, auto_page, serial):
        done = threading.Event()

        def _set():
            auto_page.var_serial.set(serial)
            done.set()

        self.after(0, _set)
        done.wait(timeout=2.0)

    def get_test_serials(self):
        return [var.get().strip() for var in self.serial_vars if var.get().strip()]

    def start_test(self):
        if self.running:
            return
        self.running = True
        self.btn_start.config(state="disabled")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.worker_thread = threading.Thread(target=self.run_test, daemon=True)
        self.worker_thread.start()

    def stop_test(self):
        self.running = False
        self.set_status("Parando teste...")

    def finish_test(self):
        self.running = False
        self.btn_start.config(state="normal")
        if self.var_status.get() != "Erro":
            self.var_status.set("Teste finalizado")

    def build_job_pair(self, auto_page, serial, preset_arte1, preset_arte2, use_cache=True):
        jobs = {}
        errors = {}
        elapsed_by_suffix = {}

        def _build_job(suffix, preset_name):
            started = time.perf_counter()
            try:
                jobs[suffix] = auto_page.build_laser_job(preset_name, suffix, serial_override=serial, use_cache=use_cache)
            except Exception as exc:
                errors[suffix] = exc
            finally:
                elapsed_by_suffix[suffix] = time.perf_counter() - started

        self.after(0, lambda s=serial: self.log(f"[FILA-TESTE] Gerando arte1 primeiro para serial {s}."))
        _build_job("arte1", preset_arte1)
        self.after(0, lambda s=serial: self.log(f"[FILA-TESTE] Arte1 pronta; gerando arte2 para serial {s}."))
        _build_job("arte2", preset_arte2)

        if errors:
            suffix, exc = next(iter(errors.items()))
            raise RuntimeError(f"Falha ao gerar {suffix} do serial {serial}: {exc}")

        return jobs, elapsed_by_suffix

    def start_queue_prebuild(self, auto_page, serial, preset_arte1, preset_arte2, queue, use_cache=True):
        if serial in queue:
            return queue[serial]

        with self.queue_order_lock:
            order = self.queue_order_counter
            self.queue_order_counter += 1
        ctx = {
            "serial": serial,
            "ready": threading.Event(),
            "jobs": None,
            "elapsed": None,
            "error": None,
            "started_at": time.perf_counter(),
            "order": order,
        }
        queue[serial] = ctx

        def _worker():
            self.after(0, lambda s=serial, o=order: self.log(f"[FILA-TESTE] Serial {s} aguardando fila FIFO de conversao ordem={o}."))
            try:
                with self.queue_order_lock:
                    while order != self.queue_next_order and self.running:
                        self.queue_order_lock.wait(timeout=0.25)
                if not self.running:
                    return
                self.after(0, lambda s=serial, o=order: self.log(f"[FILA-TESTE] Prebuild iniciado para serial {s} ordem={o}."))
                jobs, elapsed_by_suffix = self.build_job_pair(auto_page, serial, preset_arte1, preset_arte2, use_cache=use_cache)
                with self.queue_order_lock:
                    self.queue_next_order += 1
                    self.queue_order_lock.notify_all()
                ctx["jobs"] = jobs
                ctx["elapsed"] = elapsed_by_suffix
                total = time.perf_counter() - ctx["started_at"]
                a1 = elapsed_by_suffix.get("arte1", 0.0)
                a2 = elapsed_by_suffix.get("arte2", 0.0)
                self.after(
                    0,
                    lambda s=serial, a1=a1, a2=a2, total=total: self.log(
                        f"[FILA-TESTE] Prebuild pronto serial {s}: arte1={a1:.2f}s arte2={a2:.2f}s total={total:.2f}s."
                    ),
                )
            except Exception as exc:
                ctx["error"] = exc
                self.after(0, lambda s=serial, e=exc: self.log(f"[FILA-TESTE] Erro no prebuild serial {s}: {e}"))
                with self.queue_order_lock:
                    if order == self.queue_next_order:
                        self.queue_next_order += 1
                        self.queue_order_lock.notify_all()
            finally:
                ctx["ready"].set()

        threading.Thread(target=_worker, daemon=True).start()
        return ctx

    def run_test(self):
        total_started = time.perf_counter()
        auto_page = getattr(self.app, "auto_page", None)
        if not auto_page:
            self.after(0, lambda: self.set_status("Erro: rotina automatica nao encontrada"))
            self.after(0, self.finish_test)
            return

        old_serial = auto_page.var_serial.get()
        use_cache = self.var_use_auto_cache.get()
        execute_laser = self.var_execute_laser.get()

        self.after(0, lambda: self.set_status("Teste iniciado"))
        try:
            if use_cache:
                self.after(0, lambda: self.log("[ATENCAO] Cache esta ON: este teste mede reaproveitamento de job, nao tempo real de criacao."))
            if not use_cache:
                with auto_page.job_cache_lock:
                    auto_page.job_cache.clear()
                cache_dir = getattr(auto_page, "job_cache_dir", None)
                if cache_dir:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                self.after(0, lambda: self.log("Cache desativado para esta rodada: cache em memoria e disco limpo antes do teste."))

            if self.var_simulate_queue.get():
                self.run_queue_test(auto_page, execute_laser, use_cache)
                return

            for index, serial in enumerate(self.get_test_serials(), start=1):
                if not self.running:
                    break

                piece_started = time.perf_counter()
                self.after(0, lambda i=index, s=serial: self.set_status(f"Peca {i}/10 - serial {s}"))
                self.set_auto_serial_sync(auto_page, serial)

                preset_arte1 = auto_page.resolve_step_preset(auto_page.var_preset_arte1.get(), "arte1")
                preset_arte2 = auto_page.resolve_step_preset(auto_page.var_preset_arte2.get(), "arte2")
                self.after(0, lambda s=serial, c=use_cache: self.log(f"[DIRETO] Gerando arte1+arte2 em paralelo para serial {s}. cache={'ON' if c else 'OFF'}"))
                jobs, elapsed_by_suffix = self.build_job_pair(auto_page, serial, preset_arte1, preset_arte2, use_cache=use_cache)

                arte1_elapsed = elapsed_by_suffix.get("arte1", 0.0)
                arte2_elapsed = elapsed_by_suffix.get("arte2", 0.0)
                job1 = jobs["arte1"]
                job2 = jobs["arte2"]

                if execute_laser and self.running:
                    auto_page.execute_laser_job(job1, preset_arte1, "arte1")
                    auto_page.execute_laser_job(job2, preset_arte2, "arte2")

                piece_elapsed = time.perf_counter() - piece_started
                self.after(0, self.add_result_row, index, serial, arte1_elapsed, arte2_elapsed, piece_elapsed, "OK")

            elapsed = time.perf_counter() - total_started
            self.after(0, lambda: self.log(f"Teste direto finalizado em {elapsed:.2f}s"))
        except Exception as exc:
            self.after(0, lambda: self.set_status(f"Erro: {exc}"))
        finally:
            self.set_auto_serial_sync(auto_page, old_serial)
            self.after(0, self.finish_test)

    def run_queue_test(self, auto_page, execute_laser, use_cache):
        serials = self.get_test_serials()
        if not serials:
            self.after(0, lambda: self.set_status("Erro: informe pelo menos um serial"))
            return

        try:
            simulated_cycle_s = max(0.0, float(self.var_simulated_cycle_s.get().replace(",", ".")))
        except Exception:
            simulated_cycle_s = 15.0
        try:
            queue_lookahead = max(1, int(float(self.var_queue_lookahead.get().replace(",", "."))))
        except Exception:
            queue_lookahead = 4
        try:
            preheat_s = max(0.0, float(self.var_preheat_s.get().replace(",", ".")))
        except Exception:
            preheat_s = 30.0

        preset_arte1 = auto_page.resolve_step_preset(auto_page.var_preset_arte1.get(), "arte1")
        preset_arte2 = auto_page.resolve_step_preset(auto_page.var_preset_arte2.get(), "arte2")
        queue = {}
        with self.queue_order_lock:
            self.queue_next_order = 0
            self.queue_order_counter = 0
        test_started = time.perf_counter()
        self.after(
            0,
            lambda t=simulated_cycle_s, q=queue_lookahead, p=preheat_s: self.log(
                f"[FILA-TESTE] Modo fila ligado. Ciclo simulado={t:.2f}s; antecipar={q}; prebuild antes da 1a={p:.2f}s; cache={'ON' if use_cache else 'OFF'}."
            ),
        )

        for lookahead in range(min(queue_lookahead, len(serials))):
            self.start_queue_prebuild(auto_page, serials[lookahead], preset_arte1, preset_arte2, queue, use_cache=use_cache)

        if preheat_s > 0 and self.running:
            self.after(0, lambda p=preheat_s: self.log(f"[FILA-TESTE] Aguardando {p:.2f}s de prebuild antes da primeira peca."))
            slept = 0.0
            while self.running and slept < preheat_s:
                step = min(0.25, preheat_s - slept)
                time.sleep(step)
                slept += step

        for index, serial in enumerate(serials, start=1):
            if not self.running:
                break

            self.after(0, lambda i=index, total=len(serials), s=serial: self.set_status(f"Fila {i}/{total} - serial {s}"))
            self.set_auto_serial_sync(auto_page, serial)

            current_started = time.perf_counter()
            for future_index in range(index + 1, min(len(serials), index + queue_lookahead) + 1):
                self.start_queue_prebuild(auto_page, serials[future_index - 1], preset_arte1, preset_arte2, queue, use_cache=use_cache)

            ctx = self.start_queue_prebuild(auto_page, serial, preset_arte1, preset_arte2, queue, use_cache=use_cache)
            wait_started = time.perf_counter()
            if not ctx["ready"].is_set():
                self.after(0, lambda s=serial: self.log(f"[FILA-TESTE] Peca aguardando job pronto para serial {s}."))
            ctx["ready"].wait()
            wait_elapsed = time.perf_counter() - wait_started

            if ctx["error"]:
                raise RuntimeError(f"Falha no prebuild do serial {serial}: {ctx['error']}")

            elapsed_by_suffix = ctx["elapsed"] or {}
            jobs = ctx["jobs"] or {}
            arte1_elapsed = elapsed_by_suffix.get("arte1", 0.0)
            arte2_elapsed = elapsed_by_suffix.get("arte2", 0.0)
            prebuild_total = time.perf_counter() - ctx["started_at"]
            self.after(
                0,
                lambda s=serial, w=wait_elapsed, p=prebuild_total: self.log(
                    f"[FILA-TESTE] Peca usando job serial {s}: espera_na_peca={w:.2f}s prebuild_total={p:.2f}s."
                ),
            )

            if execute_laser and self.running:
                auto_page.execute_laser_job(jobs["arte1"], preset_arte1, "arte1")
                auto_page.execute_laser_job(jobs["arte2"], preset_arte2, "arte2")
            elif simulated_cycle_s > 0 and self.running:
                self.after(
                    0,
                    lambda s=serial, t=simulated_cycle_s: self.log(
                        f"[FILA-TESTE] Simulando tempo fisico do ciclo serial {s}: {t:.2f}s."
                    ),
                )
                slept = 0.0
                while self.running and slept < simulated_cycle_s:
                    step = min(0.25, simulated_cycle_s - slept)
                    time.sleep(step)
                    slept += step

            total_elapsed = time.perf_counter() - current_started
            status = f"OK | espera job {wait_elapsed:.2f}s"
            self.after(0, self.add_result_row, index, serial, arte1_elapsed, arte2_elapsed, total_elapsed, status)

        elapsed = time.perf_counter() - test_started
        self.after(0, lambda: self.log(f"[FILA-TESTE] Teste de fila finalizado em {elapsed:.2f}s."))

    def add_result_row(self, index, serial, arte1_elapsed, arte2_elapsed, total_elapsed, status):
        self.tree.insert(
            "",
            "end",
            values=(
                index,
                serial,
                f"{arte1_elapsed:.3f}",
                f"{arte2_elapsed:.3f}",
                f"{total_elapsed:.3f}",
                status,
            ),
        )
