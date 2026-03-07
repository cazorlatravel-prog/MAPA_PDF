"""
Panel de generación: modo (todos/seleccionados/rango/agrupado/lotes CSV),
progreso, portada, botón GENERAR.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ACENTO,
    FONT_BOLD, FONT_SMALL, FONT_LABEL,
    crear_frame_seccion, crear_boton,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS


class PanelGeneracion:
    """Panel de generación de planos con barra de progreso."""

    def __init__(self, parent, motor, get_config, callback_log):
        self.motor = motor
        self.get_config = get_config
        self.callback_log = callback_log
        self._parent_window = parent.winfo_toplevel()

        f = crear_frame_seccion(parent, "\U0001f5a8  GENERACI\u00d3N")

        # ── Modo de selección ──
        tk.Label(f, text="Planos a generar:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, columnspan=2, sticky="w")

        self._modo_gen = tk.StringVar(value="todos")
        self._modo_gen.trace_add("write", self._on_modo_changed)

        for i, (val, texto) in enumerate([
            ("todos", "Todos (uno por infraestructura)"),
            ("seleccion", "Seleccionados en tabla"),
            ("rango", "Rango:"),
            ("agrupado", "Agrupar por campo"),
            ("lotes", "Generaci\u00f3n por lotes (CSV)"),
        ], start=1):
            tk.Radiobutton(
                f, text=texto, variable=self._modo_gen, value=val,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                cursor="hand2",
            ).grid(row=i, column=0, sticky="w")

        # Entradas de rango
        rango_f = tk.Frame(f, bg=COLOR_PANEL)
        rango_f.grid(row=3, column=1, sticky="w", padx=(4, 0))

        self._rango_desde = tk.Entry(rango_f, width=5, font=FONT_SMALL,
                                      bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                      insertbackground="white", relief="flat")
        self._rango_desde.insert(0, "1")
        self._rango_desde.pack(side="left")

        tk.Label(rango_f, text="\u2013", bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=FONT_SMALL).pack(side="left", padx=2)

        self._rango_hasta = tk.Entry(rango_f, width=5, font=FONT_SMALL,
                                      bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                      insertbackground="white", relief="flat")
        self._rango_hasta.insert(0, "10")
        self._rango_hasta.pack(side="left")

        # ── Panel de agrupación ──
        self._frame_agrupacion = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_agrupacion.grid(row=6, column=0, columnspan=2,
                                     sticky="ew", pady=(4, 0))

        tk.Label(self._frame_agrupacion, text="Campo de agrupaci\u00f3n:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w")

        campos_agrupacion = list(ETIQUETAS_CAMPOS.keys())
        self._campo_agrupacion = tk.StringVar(value="Monte")
        self._cb_campo_agrup = ttk.Combobox(
            self._frame_agrupacion, textvariable=self._campo_agrupacion,
            values=campos_agrupacion, state="readonly", font=FONT_SMALL, width=20,
        )
        self._cb_campo_agrup.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._cb_campo_agrup.bind("<<ComboboxSelected>>", self._on_campo_agrup_changed)

        tk.Label(self._frame_agrupacion, text="Valores a generar:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self._frame_valores = tk.Frame(self._frame_agrupacion, bg=COLOR_PANEL)
        self._frame_valores.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._canvas_valores = tk.Canvas(self._frame_valores, bg=COLOR_PANEL,
                                          highlightthickness=0, height=100)
        self._sb_valores = ttk.Scrollbar(self._frame_valores, orient="vertical",
                                          command=self._canvas_valores.yview)
        self._inner_valores = tk.Frame(self._canvas_valores, bg=COLOR_PANEL)
        self._inner_valores.bind(
            "<Configure>",
            lambda e: self._canvas_valores.configure(
                scrollregion=self._canvas_valores.bbox("all")),
        )
        self._canvas_valores.create_window((0, 0), window=self._inner_valores,
                                            anchor="nw")
        self._canvas_valores.configure(yscrollcommand=self._sb_valores.set)
        self._canvas_valores.pack(side="left", fill="both", expand=True)
        self._sb_valores.pack(side="right", fill="y")

        btn_sel_f = tk.Frame(self._frame_agrupacion, bg=COLOR_PANEL)
        btn_sel_f.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        tk.Button(btn_sel_f, text="Todos", command=self._seleccionar_todos_valores,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left", padx=(0, 4))
        tk.Button(btn_sel_f, text="Ninguno", command=self._deseleccionar_todos_valores,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left")
        tk.Button(btn_sel_f, text="Detalle\u2026",
                  command=self._abrir_popup_detalle,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", padx=4).pack(side="left", padx=(4, 0))

        self._check_valores = {}
        # {valor_grupo: [indices]} — si no existe la clave, se usan todos
        self._indices_filtrados = {}
        self._frame_agrupacion.columnconfigure(1, weight=1)
        self._frame_agrupacion.grid_remove()

        # ── Panel de lotes CSV ──
        self._frame_lotes = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_lotes.grid(row=7, column=0, columnspan=2,
                                sticky="ew", pady=(4, 0))
        self._ruta_csv = tk.StringVar(value="Sin seleccionar")
        tk.Label(self._frame_lotes, textvariable=self._ruta_csv,
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240).pack(anchor="w")
        tk.Button(self._frame_lotes, text="Seleccionar CSV",
                  command=self._seleccionar_csv, font=FONT_SMALL,
                  bg=COLOR_BORDE, fg=COLOR_TEXTO, relief="flat",
                  cursor="hand2", padx=4).pack(anchor="w", pady=(2, 0))
        self._frame_lotes.grid_remove()

        # ── Opciones PDF ──
        self._multipagina = tk.BooleanVar(value=False)
        tk.Checkbutton(
            f, text="PDF multipágina (un solo archivo)",
            variable=self._multipagina, font=FONT_SMALL,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, selectcolor=COLOR_BORDE,
            activebackground=COLOR_PANEL, cursor="hand2",
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self._incluir_portada = tk.BooleanVar(value=False)
        tk.Checkbutton(
            f, text="Incluir portada e \u00edndice",
            variable=self._incluir_portada, font=FONT_SMALL,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, selectcolor=COLOR_BORDE,
            activebackground=COLOR_PANEL, cursor="hand2",
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # ── Progreso ──
        tk.Label(f, text="Progreso:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._progreso = ttk.Progressbar(f, length=240, mode="determinate")
        self._progreso.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        self._lbl_progreso = tk.Label(f, text="\u2014", font=FONT_SMALL,
                                       bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_progreso.grid(row=12, column=0, columnspan=2, pady=(0, 8))

        # ── Botón GENERAR ──
        self._btn_generar = crear_boton(
            f, "  GENERAR PLANOS  ", self._iniciar_generacion,
            icono="\U0001f5a8", ancho=30,
            color_bg=COLOR_ACENTO, color_fg="#1A1A2E",
        )
        self._btn_generar.grid(row=13, column=0, columnspan=2, sticky="ew", pady=4)

        # ── Botón abrir carpeta ──
        crear_boton(f, "Abrir carpeta de salida",
                    self._abrir_carpeta, icono="\U0001f4c2").grid(
                    row=14, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

    # ── Eventos ──────────────────────────────────────────────────────────

    def _on_modo_changed(self, *args):
        modo = self._modo_gen.get()
        if modo == "agrupado":
            self._frame_agrupacion.grid()
            self._frame_lotes.grid_remove()
            self._actualizar_valores_agrupacion()
        elif modo == "lotes":
            self._frame_agrupacion.grid_remove()
            self._frame_lotes.grid()
        else:
            self._frame_agrupacion.grid_remove()
            self._frame_lotes.grid_remove()

    def _on_campo_agrup_changed(self, event=None):
        self._actualizar_valores_agrupacion()

    def _actualizar_valores_agrupacion(self):
        for widget in self._inner_valores.winfo_children():
            widget.destroy()
        self._check_valores.clear()
        self._indices_filtrados.clear()

        campo = self._campo_agrupacion.get()
        valores = self.motor.obtener_valores_unicos(campo)

        if not valores:
            tk.Label(self._inner_valores,
                     text="(sin datos - carga primero el shapefile)",
                     font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(
                     anchor="w", padx=4)
            return

        for valor in valores:
            var = tk.BooleanVar(value=True)
            n = len(self.motor.obtener_indices_por_valor(campo, valor))
            texto = f"{valor}  ({n} infra.)"
            cb = tk.Checkbutton(
                self._inner_valores, text=texto, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                cursor="hand2",
            )
            cb.pack(anchor="w", padx=4, pady=1)
            self._check_valores[valor] = var

    def _seleccionar_todos_valores(self):
        for var in self._check_valores.values():
            var.set(True)

    def _deseleccionar_todos_valores(self):
        for var in self._check_valores.values():
            var.set(False)

    def _abrir_popup_detalle(self):
        """Abre ventana emergente para seleccionar infraestructuras individuales."""
        campo = self._campo_agrupacion.get()
        valores_sel = [v for v, var in self._check_valores.items() if var.get()]
        if not valores_sel:
            messagebox.showinfo("Info",
                                "Selecciona al menos un valor de agrupación.")
            return

        popup = tk.Toplevel(self._parent_window)
        popup.title("Seleccionar infraestructuras por grupo")
        popup.geometry("620x500")
        popup.configure(bg=COLOR_PANEL)
        popup.transient(self._parent_window)
        popup.grab_set()

        tk.Label(popup, text=f"Infraestructuras agrupadas por: {campo}",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(
                 anchor="w", padx=8, pady=(8, 4))

        # Frame con scroll
        container = tk.Frame(popup, bg=COLOR_PANEL)
        container.pack(fill="both", expand=True, padx=8, pady=4)

        canvas = tk.Canvas(container, bg=COLOR_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COLOR_PANEL)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Construir checkboxes por grupo → infraestructuras
        check_vars = {}  # {valor_grupo: [(idx, BooleanVar), ...]}
        nombre_campo = "Nombre_Infra"
        # Buscar el nombre real del campo en el mapeo
        if self.motor._campo_mapeo and nombre_campo in self.motor._campo_mapeo:
            nombre_campo = self.motor._campo_mapeo[nombre_campo]

        for valor in valores_sel:
            indices = self.motor.obtener_indices_por_valor(campo, valor)
            # Cabecera del grupo
            tk.Label(inner, text=f"\u25bc {valor}  ({len(indices)} infra.)",
                     font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_ACENTO).pack(
                     anchor="w", padx=4, pady=(6, 2))

            grupo_vars = []
            prev_sel = self._indices_filtrados.get(valor)
            for idx in indices:
                row = self.motor.gdf_infra.iloc[idx]
                nombre = str(row.get(nombre_campo,
                             row.get("Nombre_Infra", f"#{idx}")))
                if nombre == "nan":
                    nombre = f"#{idx}"

                default_on = prev_sel is None or idx in prev_sel
                var = tk.BooleanVar(value=default_on)
                cb = tk.Checkbutton(
                    inner, text=f"  {nombre}", variable=var,
                    font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                    selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                    cursor="hand2",
                )
                cb.pack(anchor="w", padx=20, pady=1)
                grupo_vars.append((idx, var))
            check_vars[valor] = grupo_vars

        # Botones inferiores
        btn_f = tk.Frame(popup, bg=COLOR_PANEL)
        btn_f.pack(fill="x", padx=8, pady=(4, 8))

        def _sel_todos():
            for gvars in check_vars.values():
                for _, v in gvars:
                    v.set(True)

        def _sel_ninguno():
            for gvars in check_vars.values():
                for _, v in gvars:
                    v.set(False)

        def _aceptar():
            self._indices_filtrados.clear()
            for valor, gvars in check_vars.items():
                sel = [idx for idx, v in gvars if v.get()]
                # Solo guardar si se han excluido algunos
                todos = [idx for idx, _ in gvars]
                if len(sel) < len(todos):
                    self._indices_filtrados[valor] = sel
            popup.destroy()
            self.callback_log("Selección de infraestructuras actualizada.", "info")

        tk.Button(btn_f, text="Todos", command=_sel_todos,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=6).pack(side="left", padx=(0, 4))
        tk.Button(btn_f, text="Ninguno", command=_sel_ninguno,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=6).pack(side="left", padx=(0, 4))
        tk.Button(btn_f, text="Aceptar", command=_aceptar,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", padx=12).pack(side="right")

    def _seleccionar_csv(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar CSV de lotes",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            self._ruta_csv.set(os.path.basename(ruta))
            self._ruta_csv_completa = ruta

    def actualizar_valores_si_agrupado(self):
        if self._modo_gen.get() == "agrupado":
            self._actualizar_valores_agrupacion()

    # ── Obtener índices ──────────────────────────────────────────────────

    def _obtener_indices(self) -> list:
        gdf = self.motor.gdf_infra
        if gdf is None:
            return []

        modo = self._modo_gen.get()
        cfg = self.get_config()
        tabla = cfg.get("tabla")

        if modo == "todos":
            return list(range(len(gdf)))
        elif modo == "seleccion":
            if tabla is None:
                return []
            sels = tabla.selection()
            if not sels:
                return []
            return [tabla.index(s) for s in sels]
        elif modo == "rango":
            try:
                desde = int(self._rango_desde.get()) - 1
                hasta = int(self._rango_hasta.get())
                return list(range(max(0, desde), min(hasta, len(gdf))))
            except ValueError:
                return []
        else:
            return []

    # ── Generación ───────────────────────────────────────────────────────

    def _iniciar_generacion(self):
        modo = self._modo_gen.get()

        if modo == "lotes":
            self._iniciar_generacion_lotes()
            return

        if self.motor.gdf_infra is None:
            messagebox.showwarning("Aviso", "Carga primero el shapefile de infraestructuras.")
            return

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        if not campos:
            messagebox.showwarning("Aviso", "Selecciona al menos un campo.")
            return

        carpeta = cfg["salida"]
        os.makedirs(carpeta, exist_ok=True)

        multipagina = self._multipagina.get()
        incluir_portada = self._incluir_portada.get()
        escala_manual = cfg.get("escala_manual")

        if modo == "agrupado":
            valores_sel = [v for v, var in self._check_valores.items() if var.get()]
            if not valores_sel:
                messagebox.showwarning("Aviso", "Selecciona al menos un valor para agrupar.")
                return

            self._btn_generar.configure(state="disabled", text="\u23f3 Generando...")
            self._progreso["value"] = 0
            self._progreso["maximum"] = len(valores_sel)

            campo_grupo = self._campo_agrupacion.get()

            # Preparar filtro de índices por grupo si el usuario
            # ha seleccionado infraestructuras individuales
            indices_filtro = dict(self._indices_filtrados)

            def _worker_agrupado():
                self.callback_log(
                    f"\n{'=' * 50}\nGenerando {len(valores_sel)} planos agrupados "
                    f"por {campo_grupo}...", "info")

                self.motor.generar_serie_agrupada(
                    campo_grupo=campo_grupo,
                    valores=valores_sel,
                    formato_key=cfg["formato"],
                    proveedor=cfg["proveedor"],
                    transparencia=cfg["transparencia"],
                    campos=campos,
                    color_infra=cfg["color_infra"],
                    salida_dir=carpeta,
                    escala_manual=escala_manual,
                    callback_log=self.callback_log,
                    callback_progreso=self._actualizar_progreso,
                    indices_filtro=indices_filtro,
                )

                self._parent_window.after(0, self._fin_generacion)

            threading.Thread(target=_worker_agrupado, daemon=True).start()
        else:
            indices = self._obtener_indices()
            if not indices:
                messagebox.showwarning("Aviso", "No hay infraestructuras seleccionadas.")
                return

            self._btn_generar.configure(state="disabled", text="\u23f3 Generando...")
            self._progreso["value"] = 0
            self._progreso["maximum"] = len(indices)

            def _worker():
                self.callback_log(
                    f"\n{'=' * 50}\nIniciando generaci\u00f3n de {len(indices)} planos...",
                    "info")

                if multipagina:
                    ruta_pdf = os.path.join(carpeta, "planos_forestales_completo.pdf")
                    self.motor.generar_pdf_multipagina(
                        indices=indices,
                        formato_key=cfg["formato"],
                        proveedor=cfg["proveedor"],
                        transparencia=cfg["transparencia"],
                        campos=campos,
                        color_infra=cfg["color_infra"],
                        ruta_pdf=ruta_pdf,
                        escala_manual=escala_manual,
                        incluir_portada=incluir_portada,
                        callback_log=self.callback_log,
                        callback_progreso=self._actualizar_progreso,
                    )
                else:
                    self.motor.generar_serie(
                        indices=indices,
                        formato_key=cfg["formato"],
                        proveedor=cfg["proveedor"],
                        transparencia=cfg["transparencia"],
                        campos=campos,
                        color_infra=cfg["color_infra"],
                        salida_dir=carpeta,
                        escala_manual=escala_manual,
                        callback_log=self.callback_log,
                        callback_progreso=self._actualizar_progreso,
                    )

                self._parent_window.after(0, self._fin_generacion)

            threading.Thread(target=_worker, daemon=True).start()

    def _iniciar_generacion_lotes(self):
        if not hasattr(self, "_ruta_csv_completa"):
            messagebox.showwarning("Aviso", "Selecciona primero un archivo CSV.")
            return

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        escala_manual = cfg.get("escala_manual")

        self._btn_generar.configure(state="disabled", text="\u23f3 Generando lotes...")
        self._progreso["value"] = 0

        def _worker_lotes():
            self.callback_log(
                f"\n{'=' * 50}\nIniciando generaci\u00f3n por lotes...", "info")

            self.motor.generar_lotes_csv(
                ruta_csv=self._ruta_csv_completa,
                proveedor=cfg["proveedor"],
                transparencia=cfg["transparencia"],
                campos=campos,
                color_infra=cfg["color_infra"],
                escala_manual=escala_manual,
                callback_log=self.callback_log,
                callback_progreso=self._actualizar_progreso,
            )

            self._parent_window.after(0, self._fin_generacion)

        threading.Thread(target=_worker_lotes, daemon=True).start()

    def _actualizar_progreso(self, actual, total):
        self._parent_window.after(
            0, lambda: self._progreso.__setitem__("value", actual))
        self._parent_window.after(
            0, lambda: self._progreso.__setitem__("maximum", total))
        self._parent_window.after(
            0, lambda: self._lbl_progreso.configure(
                text=f"{actual}/{total} planos generados"))

    def _fin_generacion(self):
        cfg = self.get_config()
        self._btn_generar.configure(state="normal", text="  GENERAR PLANOS  ")
        self.callback_log(
            f"\n\u2713 Proceso finalizado. Planos guardados en:\n{cfg['salida']}", "ok")
        messagebox.showinfo(
            "Completado",
            f"Planos generados correctamente.\n\nCarpeta: {cfg['salida']}",
        )

    def _abrir_carpeta(self):
        cfg = self.get_config()
        carpeta = cfg["salida"]
        os.makedirs(carpeta, exist_ok=True)
        import sys
        if sys.platform == "win32":
            os.startfile(carpeta)
        elif sys.platform == "darwin":
            os.system(f'open "{carpeta}"')
        else:
            os.system(f'xdg-open "{carpeta}"')
