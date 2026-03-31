"""
Panel de generación: modo (todos/seleccionados/rango/agrupado/lotes CSV),
progreso, portada, botón GENERAR.
"""

import os
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, COLOR_ACENTO2, COLOR_ACENTO3, COLOR_ERROR, COLOR_HOVER,
    COLOR_FONDO_APP, COLOR_HEADER,
    FONT_BOLD, FONT_SMALL, FONT_LABEL, FONT_SECCION, FONT_BOTON,
    crear_frame_seccion, crear_boton, crear_entry, crear_label,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS
from ..motor.generador import GeneracionCancelada


class PanelGeneracion:
    """Panel de generación de planos con barra de progreso."""

    def __init__(self, parent, motor, get_config, callback_log,
                 auto_aplicar=None):
        self.motor = motor
        self.get_config = get_config
        self.callback_log = callback_log
        self._auto_aplicar = auto_aplicar
        self._parent_window = parent.winfo_toplevel()

        f = crear_frame_seccion(parent, "\U0001f5a8  GENERACI\u00d3N")

        # ── Modo de seleccion ──
        crear_label(f, "Planos a generar:", tipo="titulo").grid(
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
                selectcolor=COLOR_ENTRY, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
                bd=0, highlightthickness=0,
            ).grid(row=i, column=0, sticky="w", pady=1)

        # Entradas de rango
        rango_f = tk.Frame(f, bg=COLOR_PANEL)
        rango_f.grid(row=3, column=1, sticky="w", padx=(4, 0))

        self._rango_desde = crear_entry(rango_f, width=5)
        self._rango_desde.insert(0, "1")
        self._rango_desde.pack(side="left")

        tk.Label(rango_f, text="\u2013", bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 font=FONT_SMALL).pack(side="left", padx=4)

        self._rango_hasta = crear_entry(rango_f, width=5)
        self._rango_hasta.insert(0, "10")
        self._rango_hasta.pack(side="left")

        # ── Panel de agrupación ──
        self._frame_agrupacion = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_agrupacion.grid(row=6, column=0, columnspan=2,
                                     sticky="ew", pady=(4, 0))

        crear_label(self._frame_agrupacion, "Campo de agrupaci\u00f3n:",
                    tipo="normal").grid(row=0, column=0, sticky="w")

        campos_agrupacion = list(ETIQUETAS_CAMPOS.keys())
        self._campo_agrupacion = tk.StringVar(value="Monte")
        self._cb_campo_agrup = ttk.Combobox(
            self._frame_agrupacion, textvariable=self._campo_agrupacion,
            values=campos_agrupacion, state="readonly", font=FONT_SMALL, width=20,
        )
        self._cb_campo_agrup.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._cb_campo_agrup.bind("<<ComboboxSelected>>", self._on_campo_agrup_changed)

        # Resumen de valores + botón para abrir popup de selección
        self._lbl_valores_resumen = tk.Label(
            self._frame_agrupacion,
            text="Valores a generar: (sin datos)",
            font=FONT_SMALL, bg=COLOR_ENTRY, fg=COLOR_TEXTO,
            anchor="w", padx=8, pady=6, cursor="hand2", relief="flat",
            wraplength=260, justify="left", bd=0,
            highlightthickness=1, highlightbackground=COLOR_BORDE,
        )
        self._lbl_valores_resumen.grid(row=1, column=0, columnspan=2,
                                        sticky="ew", pady=(4, 0))
        self._lbl_valores_resumen.bind("<Button-1>", lambda e: self._abrir_popup_valores())

        btn_sel_f = tk.Frame(self._frame_agrupacion, bg=COLOR_PANEL)
        btn_sel_f.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        crear_boton(btn_sel_f, "Seleccionar valores\u2026",
                    self._abrir_popup_valores,
                    estilo="primario").pack(side="left", padx=(0, 4))
        crear_boton(btn_sel_f, "Detalle\u2026",
                    self._abrir_popup_detalle).pack(side="left", padx=(0, 4))

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
        crear_boton(self._frame_lotes, "Seleccionar CSV",
                    self._seleccionar_csv).pack(anchor="w", pady=(4, 0))
        self._frame_lotes.grid_remove()

        # ── Opciones PDF ──
        self._multipagina = tk.BooleanVar(value=False)
        tk.Checkbutton(
            f, text="PDF multipagina (un solo archivo)",
            variable=self._multipagina, font=FONT_SMALL,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, selectcolor=COLOR_ENTRY,
            activebackground=COLOR_PANEL, activeforeground=COLOR_ACENTO,
            cursor="hand2", bd=0, highlightthickness=0,
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self._incluir_portada = tk.BooleanVar(value=False)
        tk.Checkbutton(
            f, text="Incluir portada e \u00edndice",
            variable=self._incluir_portada, font=FONT_SMALL,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, selectcolor=COLOR_ENTRY,
            activebackground=COLOR_PANEL, activeforeground=COLOR_ACENTO,
            cursor="hand2", bd=0, highlightthickness=0,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # ── Progreso ──
        crear_label(f, "Progreso:", tipo="secundario").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self._progreso = ttk.Progressbar(f, length=240, mode="determinate",
                                          style="Green.Horizontal.TProgressbar")
        self._progreso.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(4, 4))

        self._lbl_progreso = tk.Label(f, text="\u2014", font=FONT_SMALL,
                                       bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_progreso.grid(row=12, column=0, columnspan=2, pady=(0, 8))

        # ── Botones Vista previa y Mapa guia ──
        btn_preview_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_preview_f.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        btn_preview_f.columnconfigure(0, weight=1)
        btn_preview_f.columnconfigure(1, weight=1)

        crear_boton(btn_preview_f, "Vista previa",
                    self._vista_previa, icono="\U0001f50d").grid(
                    row=0, column=0, sticky="ew", padx=(0, 3))
        crear_boton(btn_preview_f, "Mapa gu\u00eda",
                    self._mapa_guia, icono="\U0001f5fa").grid(
                    row=0, column=1, sticky="ew", padx=(3, 0))

        # ── Boton GENERAR ──
        self._btn_generar = crear_boton(
            f, "  GENERAR PLANOS  ", self._iniciar_generacion,
            icono="\U0001f5a8", ancho=30,
            estilo="primario",
        )
        self._btn_generar.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(6, 4))

        # ── Boton PARAR ──
        self._btn_parar = crear_boton(
            f, "  PARAR GENERACI\u00d3N  ", self._parar_generacion,
            icono="\u23f9", ancho=30,
            estilo="peligro",
        )
        self._btn_parar.grid(row=15, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self._btn_parar.configure(state="disabled")

        # ── Boton abrir carpeta ──
        crear_boton(f, "Abrir carpeta de salida",
                    self._abrir_carpeta, icono="\U0001f4c2").grid(
                    row=16, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        # ── Boton vaciar cache ──
        crear_boton(f, "Vaciar cach\u00e9 de teselas",
                    self._vaciar_cache, icono="\U0001f5d1").grid(
                    row=17, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

    def _after_seguro(self, ms, func):
        """Ejecuta func en el hilo principal solo si la ventana sigue viva."""
        try:
            if self._parent_window.winfo_exists():
                self._parent_window.after(ms, func)
        except Exception:
            pass

    # ── Eventos ──

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

    def actualizar_campos_agrupacion(self):
        """Actualiza el combobox de agrupación con las columnas reales del shapefile."""
        campos = list(ETIQUETAS_CAMPOS.keys())
        if self.motor.gdf_infra is not None:
            cols_reales = [c for c in self.motor.gdf_infra.columns
                           if c.lower() != "geometry" and c not in campos]
            campos.extend(cols_reales)
        self._cb_campo_agrup.configure(values=campos)

    def _actualizar_valores_agrupacion(self):
        self._check_valores.clear()
        # Solo limpiar filtro detallado si cambió el campo de agrupación
        campo_actual = self._campo_agrupacion.get()
        if not hasattr(self, "_ultimo_campo_agrup") or self._ultimo_campo_agrup != campo_actual:
            self._indices_filtrados.clear()
            self._ultimo_campo_agrup = campo_actual

        campo = self._campo_agrupacion.get()
        valores = self.motor.obtener_valores_unicos(campo)

        if not valores:
            self._lbl_valores_resumen.configure(
                text="Valores a generar: (sin datos - carga primero el shapefile)")
            return

        for valor in valores:
            self._check_valores[valor] = tk.BooleanVar(value=True)

        self._actualizar_resumen_valores()

    def _actualizar_resumen_valores(self):
        """Actualiza la etiqueta resumen con los valores seleccionados."""
        total = len(self._check_valores)
        sel = sum(1 for v in self._check_valores.values() if v.get())
        if total == 0:
            self._lbl_valores_resumen.configure(
                text="Valores a generar: (sin datos)")
            return
        nombres_sel = [n for n, v in self._check_valores.items() if v.get()]
        preview = ", ".join(nombres_sel[:4])
        if len(nombres_sel) > 4:
            preview += f"... (+{len(nombres_sel) - 4} más)"
        self._lbl_valores_resumen.configure(
            text=f"Valores a generar ({sel}/{total}):  {preview}\n"
                 f"Pulsa aquí para ver/seleccionar todos")

    def _abrir_popup_valores(self):
        """Abre ventana emergente para seleccionar valores de agrupación."""
        if not self._check_valores:
            messagebox.showinfo("Info",
                                "No hay valores. Carga primero el shapefile.")
            return

        campo = self._campo_agrupacion.get()

        popup = tk.Toplevel(self._parent_window)
        popup.title(f"Seleccionar valores de: {campo}")
        popup.geometry("500x450")
        popup.configure(bg=COLOR_PANEL)
        popup.transient(self._parent_window)
        popup.grab_set()

        crear_label(popup, f"Valores a generar (campo: {campo})",
                    tipo="titulo").pack(anchor="w", padx=10, pady=(10, 6))

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

        # Scroll con rueda del ratón
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", _on_mousewheel_linux)
        canvas.bind("<Button-5>", _on_mousewheel_linux)

        # Checkboxes para cada valor
        popup_vars = {}
        for valor, main_var in self._check_valores.items():
            n = len(self.motor.obtener_indices_por_valor(campo, valor))
            texto = f"{valor}  ({n} infra.)"
            var = tk.BooleanVar(value=main_var.get())
            cb = tk.Checkbutton(
                inner, text=texto, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_ENTRY, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
                bd=0, highlightthickness=0,
            )
            cb.pack(anchor="w", padx=8, pady=2)
            popup_vars[valor] = var

        # Botones inferiores
        btn_f = tk.Frame(popup, bg=COLOR_PANEL)
        btn_f.pack(fill="x", padx=8, pady=(4, 8))

        def _sel_todos():
            for v in popup_vars.values():
                v.set(True)

        def _sel_ninguno():
            for v in popup_vars.values():
                v.set(False)

        def _aplicar():
            for valor, var in popup_vars.items():
                self._check_valores[valor].set(var.get())
            self._actualizar_resumen_valores()
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _aplicar)

        crear_boton(btn_f, "Todos", _sel_todos).pack(side="left", padx=(0, 4))
        crear_boton(btn_f, "Ninguno", _sel_ninguno).pack(side="left", padx=(0, 4))
        crear_boton(btn_f, "Aceptar", _aplicar,
                    estilo="primario").pack(side="right")

    def _seleccionar_todos_valores(self):
        for var in self._check_valores.values():
            var.set(True)
        self._actualizar_resumen_valores()

    def _deseleccionar_todos_valores(self):
        for var in self._check_valores.values():
            var.set(False)
        self._actualizar_resumen_valores()

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
        popup.geometry("800x550")
        popup.configure(bg=COLOR_PANEL)
        popup.transient(self._parent_window)
        popup.grab_set()

        crear_label(popup, f"Infraestructuras agrupadas por: {campo}",
                    tipo="titulo").pack(anchor="w", padx=10, pady=(10, 6))

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

        # Determinar columnas útiles para la etiqueta de cada infra
        gdf = self.motor.gdf_infra
        cols_etiqueta = [c for c in gdf.columns
                         if c.lower() != "geometry"][:5]  # máx 5 campos

        for valor in valores_sel:
            indices = self.motor.obtener_indices_por_valor(campo, valor)
            # Cabecera del grupo
            crear_label(inner, f"\u25bc {valor}  ({len(indices)} infra.)",
                        tipo="acento", font=FONT_BOLD).pack(
                anchor="w", padx=4, pady=(8, 2))

            grupo_vars = []
            prev_sel = self._indices_filtrados.get(valor)
            for idx in indices:
                row = gdf.iloc[idx]
                # Construir etiqueta con los campos reales disponibles
                partes = []
                for col in cols_etiqueta:
                    val = str(row.get(col, ""))
                    if val and val != "nan":
                        # Truncar valores largos
                        if len(val) > 25:
                            val = val[:24] + "\u2026"
                        partes.append(val)
                nombre = " | ".join(partes) if partes else f"#{idx}"

                default_on = prev_sel is None or idx in prev_sel
                var = tk.BooleanVar(value=default_on)
                cb = tk.Checkbutton(
                    inner, text=f"  {nombre}", variable=var,
                    font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                    selectcolor=COLOR_ENTRY, activebackground=COLOR_PANEL,
                    activeforeground=COLOR_ACENTO, cursor="hand2",
                    bd=0, highlightthickness=0,
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

        def _guardar_seleccion():
            self._indices_filtrados.clear()
            for valor, gvars in check_vars.items():
                sel = [idx for idx, v in gvars if v.get()]
                todos = [idx for idx, _ in gvars]
                if len(sel) < len(todos):
                    self._indices_filtrados[valor] = sel

        def _aceptar():
            _guardar_seleccion()
            popup.destroy()
            self.callback_log("Selección de infraestructuras actualizada.", "info")

        # Guardar también al cerrar con la X
        popup.protocol("WM_DELETE_WINDOW", lambda: (_guardar_seleccion(), popup.destroy()))

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
                desde = int(self._rango_desde.get())
                hasta = int(self._rango_hasta.get())
            except ValueError:
                messagebox.showwarning("Rango inválido",
                    "Los valores 'Desde' y 'Hasta' deben ser números enteros.")
                return []
            if desde < 1:
                desde = 1
            if hasta > len(gdf):
                hasta = len(gdf)
            if desde > hasta:
                messagebox.showwarning("Rango inválido",
                    f"'Desde' ({desde}) no puede ser mayor que 'Hasta' ({hasta}).")
                return []
            return list(range(desde - 1, hasta))
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

        # Resetear bandera de cancelación
        self.motor._cancelar.clear()

        # Auto-aplicar cajetín, plantilla y simbología antes de generar
        if self._auto_aplicar:
            self._auto_aplicar()

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        if not campos:
            messagebox.showwarning("Aviso", "Selecciona al menos un campo.")
            return
        campo_encabezado = cfg.get("campo_encabezado")

        carpeta = cfg["salida"]
        os.makedirs(carpeta, exist_ok=True)

        multipagina = self._multipagina.get()
        incluir_portada = self._incluir_portada.get()
        escala_manual = cfg.get("escala_manual")
        patron_nombre = cfg.get("patron_nombre", "").strip() or None

        if modo == "agrupado":
            valores_sel = [v for v, var in self._check_valores.items() if var.get()]
            if not valores_sel:
                messagebox.showwarning("Aviso", "Selecciona al menos un valor para agrupar.")
                return

            self._btn_generar.configure(state="disabled", text="\u23f3 Generando...")
            self._btn_parar.configure(state="normal", text="\u23f9  PARAR GENERACI\u00d3N  ")
            self._progreso["value"] = 0
            self._progreso["maximum"] = len(valores_sel)

            campo_grupo = self._campo_agrupacion.get()

            # Preparar filtro de índices por grupo si el usuario
            # ha seleccionado infraestructuras individuales
            indices_filtro = dict(self._indices_filtrados)

            def _worker_agrupado():
                try:
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
                        campo_encabezado=campo_encabezado,
                        patron_nombre=patron_nombre,
                    )

                    self._after_seguro(0, self._fin_generacion)
                except GeneracionCancelada:
                    self._after_seguro(0, self._fin_cancelacion)

            threading.Thread(target=_worker_agrupado, daemon=True).start()
        else:
            indices = self._obtener_indices()
            if not indices:
                messagebox.showwarning("Aviso", "No hay infraestructuras seleccionadas.")
                return

            self._btn_generar.configure(state="disabled", text="\u23f3 Generando...")
            self._btn_parar.configure(state="normal", text="\u23f9  PARAR GENERACI\u00d3N  ")
            self._progreso["value"] = 0
            self._progreso["maximum"] = len(indices)

            def _worker():
                try:
                    self.callback_log(
                        f"\n{'=' * 50}\nIniciando generaci\u00f3n de {len(indices)} planos...",
                        "info")

                    if multipagina:
                        nombre_multi = (patron_nombre or "planos_forestales_completo")
                        # Para multipágina no aplican variables, pero sanear nombre
                        nombre_multi = nombre_multi.replace("{num}", "").replace("{nombre}", "").replace("{campo}", "")
                        nombre_multi = "".join(c for c in nombre_multi if c.isalnum() or c in "_ -.")[:80]
                        nombre_multi = nombre_multi.strip("_- ") or "planos_forestales_completo"
                        ruta_pdf = os.path.join(carpeta, f"{nombre_multi}.pdf")
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
                            campo_encabezado=campo_encabezado,
                            patron_nombre=patron_nombre,
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
                            campo_encabezado=campo_encabezado,
                            patron_nombre=patron_nombre,
                        )

                    self._after_seguro(0, self._fin_generacion)
                except GeneracionCancelada:
                    self._after_seguro(0, self._fin_cancelacion)

            threading.Thread(target=_worker, daemon=True).start()

    def _iniciar_generacion_lotes(self):
        if not hasattr(self, "_ruta_csv_completa"):
            messagebox.showwarning("Aviso", "Selecciona primero un archivo CSV.")
            return

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        escala_manual = cfg.get("escala_manual")
        campo_encabezado = cfg.get("campo_encabezado")

        # Resetear bandera de cancelación
        self.motor._cancelar.clear()

        self._btn_generar.configure(state="disabled", text="\u23f3 Generando lotes...")
        self._btn_parar.configure(state="normal", text="\u23f9  PARAR GENERACI\u00d3N  ")
        self._progreso["value"] = 0

        def _worker_lotes():
            try:
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
                    campo_encabezado=campo_encabezado,
                )

                self._after_seguro(0, self._fin_generacion)
            except GeneracionCancelada:
                self._after_seguro(0, self._fin_cancelacion)

        threading.Thread(target=_worker_lotes, daemon=True).start()

    def _actualizar_progreso(self, actual, total):
        def _update():
            self._progreso.configure(value=actual, maximum=total)
            self._lbl_progreso.configure(
                text=f"{actual}/{total} planos generados")
        self._after_seguro(0, _update)

    def _fin_generacion(self):
        cfg = self.get_config()
        self._btn_generar.configure(state="normal", text="  GENERAR PLANOS  ")
        self._btn_parar.configure(state="disabled", text="\u23f9  PARAR GENERACI\u00d3N  ")
        self.callback_log(
            f"\n\u2713 Proceso finalizado. Planos guardados en:\n{cfg['salida']}", "ok")
        messagebox.showinfo(
            "Completado",
            f"Planos generados correctamente.\n\nCarpeta: {cfg['salida']}",
        )

    def _fin_cancelacion(self):
        self._btn_generar.configure(state="normal", text="  GENERAR PLANOS  ")
        self._btn_parar.configure(state="disabled", text="\u23f9  PARAR GENERACI\u00d3N  ")
        self._lbl_progreso.configure(text="Generaci\u00f3n cancelada")
        self.callback_log(
            "\n\u26a0 Generaci\u00f3n cancelada por el usuario. "
            "Los planos ya generados se han conservado.", "warn")
        messagebox.showinfo(
            "Cancelado",
            "Generaci\u00f3n detenida.\n\n"
            "Los planos generados antes de parar se han conservado.",
        )

    def _parar_generacion(self):
        """Solicita cancelar la generación en curso."""
        self.motor.cancelar_generacion()
        self._btn_parar.configure(state="disabled", text="\u23f9  Parando...")
        self.callback_log("\n\u26a0 Cancelando generaci\u00f3n...", "warn")

    def _vaciar_cache(self):
        """Elimina la caché de teselas descargadas (contextily)."""
        import matplotlib.pyplot as plt
        plt.close("all")

        eliminados = []

        # Caché de contextily
        try:
            import contextily as ctx
            cache_dir = ctx.tile._calculate_cache_dir() if hasattr(ctx.tile, '_calculate_cache_dir') else None
            if cache_dir is None:
                cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "contextily")
            if os.path.isdir(cache_dir):
                shutil.rmtree(cache_dir)
                eliminados.append(f"contextily: {cache_dir}")
        except Exception:
            # Intentar ruta por defecto
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "contextily")
            if os.path.isdir(cache_dir):
                shutil.rmtree(cache_dir)
                eliminados.append(f"contextily: {cache_dir}")

        if eliminados:
            msg = "Cach\u00e9 eliminada:\n" + "\n".join(f"  - {e}" for e in eliminados)
            self.callback_log(f"\n\u2713 {msg}", "ok")
            messagebox.showinfo("Cach\u00e9 vaciada", msg)
        else:
            self.callback_log("\nNo se encontr\u00f3 cach\u00e9 que eliminar.", "info")
            messagebox.showinfo("Cach\u00e9", "No se encontr\u00f3 cach\u00e9 de teselas.")

    # ── Vista previa en miniatura ────────────────────────────────────────

    def _vista_previa(self):
        """Genera una vista previa del primer plano seleccionado y la
        muestra en una ventana emergente."""
        if self.motor.gdf_infra is None:
            messagebox.showwarning("Aviso",
                                    "Carga primero el shapefile.")
            return

        if self._auto_aplicar:
            self._auto_aplicar()

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        if not campos:
            messagebox.showwarning("Aviso", "Selecciona al menos un campo.")
            return

        modo = self._modo_gen.get()
        if modo == "seleccion":
            tabla = cfg.get("tabla")
            sels = tabla.selection() if tabla else ()
            if not sels:
                messagebox.showinfo("Info",
                                     "Selecciona una infraestructura en la tabla.")
                return
            idx = tabla.index(sels[0])
        elif modo == "rango":
            try:
                idx = max(0, int(self._rango_desde.get()) - 1)
            except ValueError:
                idx = 0
        else:
            idx = 0

        self.callback_log("Generando vista previa...", "info")

        def _worker():
            try:
                fig = self.motor.generar_vista_previa(
                    idx_fila=idx,
                    formato_key=cfg["formato"],
                    proveedor=cfg["proveedor"],
                    transparencia_montes=cfg["transparencia"],
                    campos_visibles=campos,
                    color_infra=cfg["color_infra"],
                    escala_manual=cfg.get("escala_manual"),
                    campo_encabezado=cfg.get("campo_encabezado"),
                )
                self._after_seguro(0, lambda: self._mostrar_preview(fig))
            except Exception as e:
                msg = f"Error en vista previa: {e}"
                self._after_seguro(
                    0, lambda: self.callback_log(msg, "error"))

        threading.Thread(target=_worker, daemon=True).start()

    def _mostrar_preview(self, fig):
        """Muestra la figura matplotlib en una ventana emergente."""
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.callback_log("Vista previa generada.", "ok")

        popup = tk.Toplevel(self._parent_window)
        popup.title("Vista previa del plano")
        popup.geometry("900x650")
        popup.configure(bg=COLOR_FONDO_APP)
        popup.transient(self._parent_window)

        canvas = FigureCanvasTkAgg(fig, master=popup)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        import matplotlib.pyplot as _plt

        def _on_close():
            _plt.close(fig)
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", _on_close)

        crear_boton(popup, "Cerrar", _on_close).pack(pady=(0, 10))

    # ── Mapa guía ─────────────────────────────────────────────────────────

    def _mapa_guia(self):
        """Genera un mapa guía con todas las infraestructuras numeradas
        y lo muestra en una ventana emergente."""
        if self.motor.gdf_infra is None:
            messagebox.showwarning("Aviso",
                                    "Carga primero el shapefile.")
            return

        if self._auto_aplicar:
            self._auto_aplicar()

        cfg = self.get_config()

        # Determinar índices según el modo actual
        modo = self._modo_gen.get()
        if modo == "agrupado":
            indices = []
            campo = self._campo_agrupacion.get()
            for valor, var in self._check_valores.items():
                if var.get():
                    indices.extend(
                        self.motor.obtener_indices_por_valor(campo, valor))
        else:
            indices = self._obtener_indices()

        if not indices:
            messagebox.showwarning("Aviso",
                                    "No hay infraestructuras seleccionadas.")
            return

        self.callback_log(
            f"Generando mapa gu\u00eda ({len(indices)} infraestructuras)...",
            "info")

        def _worker():
            try:
                fig = self.motor.generar_mapa_guia(
                    indices=indices,
                    formato_key=cfg["formato"],
                    transparencia_montes=cfg["transparencia"],
                )
                self._after_seguro(0, lambda: self._mostrar_preview(fig))
            except Exception as e:
                msg = f"Error en mapa gu\u00eda: {e}"
                self._after_seguro(
                    0, lambda: self.callback_log(msg, "error"))

        threading.Thread(target=_worker, daemon=True).start()

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
