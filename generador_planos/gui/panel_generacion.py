"""
Panel de generación: modo (todos/seleccionados/rango), progreso, botón GENERAR.
Incluye opción de PDF multipágina.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ACENTO,
    FONT_BOLD, FONT_SMALL,
    crear_frame_seccion, crear_boton,
)


class PanelGeneracion:
    """Panel de generación de planos con barra de progreso."""

    def __init__(self, parent, motor, get_config, callback_log):
        """
        get_config: callable que devuelve dict con:
            formato, proveedor, transparencia, campos, color_infra, salida, tabla
        """
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

        for i, (val, texto) in enumerate([
            ("todos", "Todos"),
            ("seleccion", "Seleccionados"),
            ("rango", "Rango:"),
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

        # ── PDF multipágina ──
        self._multipagina = tk.BooleanVar(value=False)
        tk.Checkbutton(
            f, text="PDF multipágina (un solo archivo)",
            variable=self._multipagina, font=FONT_SMALL,
            bg=COLOR_PANEL, fg=COLOR_TEXTO, selectcolor=COLOR_BORDE,
            activebackground=COLOR_PANEL, cursor="hand2",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # ── Progreso ──
        tk.Label(f, text="Progreso:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._progreso = ttk.Progressbar(f, length=240, mode="determinate")
        self._progreso.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 8))

        self._lbl_progreso = tk.Label(f, text="\u2014", font=FONT_SMALL,
                                       bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_progreso.grid(row=7, column=0, columnspan=2, pady=(0, 8))

        # ── Botón GENERAR ──
        self._btn_generar = crear_boton(
            f, "  GENERAR PLANOS  ", self._iniciar_generacion,
            icono="\U0001f5a8", ancho=30,
            color_bg=COLOR_ACENTO, color_fg="#1A1A2E",
        )
        self._btn_generar.grid(row=8, column=0, columnspan=2, sticky="ew", pady=4)

        # ── Botón abrir carpeta ──
        crear_boton(f, "Abrir carpeta de salida",
                    self._abrir_carpeta, icono="\U0001f4c2").grid(
                    row=9, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

    def _obtener_indices(self) -> list:
        """Obtiene los índices a generar según el modo seleccionado."""
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
        else:  # rango
            try:
                desde = int(self._rango_desde.get()) - 1
                hasta = int(self._rango_hasta.get())
                return list(range(max(0, desde), min(hasta, len(gdf))))
            except ValueError:
                return []

    def _iniciar_generacion(self):
        if self.motor.gdf_infra is None:
            messagebox.showwarning("Aviso", "Carga primero el shapefile de infraestructuras.")
            return

        indices = self._obtener_indices()
        if not indices:
            messagebox.showwarning("Aviso", "No hay infraestructuras seleccionadas.")
            return

        cfg = self.get_config()
        campos = cfg.get("campos", [])
        if not campos:
            messagebox.showwarning("Aviso", "Selecciona al menos un campo.")
            return

        carpeta = cfg["salida"]
        os.makedirs(carpeta, exist_ok=True)

        self._btn_generar.configure(state="disabled", text="\u23f3 Generando...")
        self._progreso["value"] = 0
        self._progreso["maximum"] = len(indices)

        multipagina = self._multipagina.get()

        def _worker():
            self.callback_log(
                f"\n{'=' * 50}\nIniciando generaci\u00f3n de {len(indices)} planos...", "info")

            def _log(msg):
                self.callback_log(msg)

            def _prog(actual, total):
                self._parent_window.after(
                    0, lambda: self._progreso.__setitem__("value", actual))
                self._parent_window.after(
                    0, lambda: self._lbl_progreso.configure(
                        text=f"{actual}/{total} planos generados"))

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
                    callback_log=_log,
                    callback_progreso=_prog,
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
                    callback_log=_log,
                    callback_progreso=_prog,
                )

            self._parent_window.after(0, self._fin_generacion)

        threading.Thread(target=_worker, daemon=True).start()

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
