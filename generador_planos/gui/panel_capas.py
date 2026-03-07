"""
Panel de carga de capas (Infraestructuras SHP + Montes SHP + Transparencia).

Incluye previsualización rápida de la capa en un mini-canvas al cargarla
y diálogo de mapeo de campos cuando el shapefile no tiene los nombres esperados.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE,
    COLOR_ACENTO, COLOR_ERROR,
    FONT_BOLD, FONT_SMALL,
    crear_frame_seccion, crear_boton,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS

CAMPOS_ESPERADOS = list(ETIQUETAS_CAMPOS.keys())


class PanelCapas:
    """Panel lateral para carga de shapefiles y control de transparencia."""

    def __init__(self, parent, motor, callback_log, callback_tabla):
        self.motor = motor
        self.callback_log = callback_log
        self.callback_tabla = callback_tabla

        f = crear_frame_seccion(parent, "\U0001f4c2  CAPAS")

        # ── Infraestructuras ──
        tk.Label(f, text="Shapefile Infraestructuras *",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w", pady=(0, 2))

        self._ruta_infra = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_infra, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=1, column=0, sticky="w")

        crear_boton(f, "Cargar Shapefile", self._cargar_infra, icono="\U0001f4e5").grid(
            row=2, column=0, sticky="ew", pady=(4, 8))

        # ── Montes ──
        tk.Label(f, text="Capa Montes (opcional)",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=3, column=0, sticky="w", pady=(0, 2))

        self._ruta_montes = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_montes, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=4, column=0, sticky="w")

        crear_boton(f, "Cargar Montes", self._cargar_montes, icono="\U0001f332").grid(
            row=5, column=0, sticky="ew", pady=(4, 2))

        # ── Transparencia ──
        tk.Label(f, text="Transparencia capa montes:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=6, column=0, sticky="w", pady=(6, 0))
        self.transparencia = tk.DoubleVar(value=0.5)
        sl = ttk.Scale(f, from_=0.0, to=1.0, variable=self.transparencia,
                        orient="horizontal")
        sl.grid(row=7, column=0, sticky="ew", pady=(2, 4))

        # ── Mini-canvas de previsualización ──
        self._preview_frame = tk.Frame(f, bg=COLOR_PANEL, height=120)
        self._preview_frame.grid(row=8, column=0, sticky="ew", pady=(4, 8))
        self._preview_frame.grid_propagate(False)
        self._canvas_widget = None

        f.columnconfigure(0, weight=1)

    def _cargar_infra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Infraestructuras",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        ok, msg, faltantes = self.motor.cargar_infraestructuras(ruta)
        if ok:
            self._ruta_infra.set(os.path.basename(ruta))
            self.callback_log(msg, "ok")
            self.callback_tabla()
            self._previsualizar(self.motor.gdf_infra)

            # Si hay campos faltantes, mostrar diálogo de mapeo
            if faltantes:
                self._dialogo_mapeo_campos(faltantes)
        else:
            self._ruta_infra.set("Error al cargar")
            self.callback_log(msg, "error")
            messagebox.showerror("Error", msg)

    def _cargar_montes(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Montes",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        ok, msg = self.motor.cargar_montes(ruta)
        if ok:
            self._ruta_montes.set(os.path.basename(ruta))
            self.callback_log(msg, "ok")
        else:
            self._ruta_montes.set("Error al cargar")
            self.callback_log(msg, "error")

    def _previsualizar(self, gdf):
        """Muestra una previsualización rápida de la capa en un mini-canvas."""
        if self._canvas_widget is not None:
            self._canvas_widget.get_tk_widget().destroy()

        fig, ax = plt.subplots(1, 1, figsize=(3, 1.5), dpi=72)
        fig.patch.set_facecolor(COLOR_PANEL)
        ax.set_facecolor("#0D1117")

        try:
            gdf.plot(ax=ax, color=COLOR_ACENTO, linewidth=0.5, markersize=2, alpha=0.8)
        except Exception:
            pass

        ax.set_axis_off()
        fig.tight_layout(pad=0.1)

        self._canvas_widget = FigureCanvasTkAgg(fig, master=self._preview_frame)
        self._canvas_widget.draw()
        self._canvas_widget.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def _dialogo_mapeo_campos(self, faltantes):
        """Muestra diálogo para mapear campos del shapefile a los esperados."""
        cols_disponibles = self.motor.obtener_columnas_shapefile()
        if not cols_disponibles:
            return

        dialog = tk.Toplevel()
        dialog.title("Mapeo de campos")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("450x500")
        dialog.transient()
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Campos no encontrados en el Shapefile.\n"
                 "Selecciona el campo equivalente para cada uno:",
            font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO,
            justify="left", wraplength=420,
        ).pack(padx=10, pady=(10, 5))

        frame = tk.Frame(dialog, bg=COLOR_PANEL)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        combos = {}
        opciones = ["(ninguno)"] + cols_disponibles

        for i, campo in enumerate(faltantes):
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            tk.Label(frame, text=f"{etiq}:", font=FONT_SMALL,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                     row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            var = tk.StringVar(value="(ninguno)")
            cb = ttk.Combobox(frame, textvariable=var, values=opciones,
                              state="readonly", font=FONT_SMALL, width=25)
            cb.grid(row=i, column=1, sticky="ew", pady=2)
            combos[campo] = var

        frame.columnconfigure(1, weight=1)

        def aplicar():
            mapeo = {}
            for campo, var in combos.items():
                val = var.get()
                if val != "(ninguno)":
                    mapeo[campo] = val
            if mapeo:
                self.motor.establecer_mapeo_campos(mapeo)
                self.callback_log(
                    f"Mapeo de campos aplicado: {mapeo}", "info")
            dialog.destroy()

        crear_boton(dialog, "Aplicar mapeo", aplicar,
                    color_bg=COLOR_ACENTO, color_fg="#1A1A2E").pack(
                    pady=(5, 10), padx=10, fill="x")
