"""
Ventana principal de la aplicación Generador de Planos Forestales.

Layout: 1100x780 px mínimo, redimensionable.
┌─────────────────────────────────────────────────────────────┐
│  GENERADOR DE PLANOS FORESTALES            ETRS89·UTM H30N  │
├──────────────────┬──────────────────────────────────────────┤
│  CAPAS           │  TABLA DE INFRAESTRUCTURAS               │
│  CONFIGURACIÓN   │                                          │
│  CAMPOS PLANO    ├──────────────────────────────────────────┤
│  GENERACIÓN      │  LOG DE PROCESO                          │
└──────────────────┴──────────────────────────────────────────┘
"""

import tkinter as tk
from tkinter import ttk

from .estilos import (
    COLOR_FONDO_APP, COLOR_ACENTO, COLOR_TEXTO_GRIS,
    FONT_BOLD, FONT_MONO,
    aplicar_estilos,
)
from .panel_capas import PanelCapas
from .panel_config import PanelConfig
from .panel_campos import PanelCampos
from .panel_generacion import PanelGeneracion
from ..motor.generador import GeneradorPlanos


class App(tk.Tk):
    """Ventana principal de la aplicación."""

    def __init__(self):
        super().__init__()
        self.title("Generador de Planos Forestales v1.0")
        self.geometry("1100x780")
        self.minsize(1100, 780)
        self.configure(bg=COLOR_FONDO_APP)
        self.resizable(True, True)

        self.motor = GeneradorPlanos()

        aplicar_estilos(self)
        self._construir_ui()

    def _construir_ui(self):
        # ── Barra superior ──
        self._barra_superior()

        # ── Contenedor principal ──
        main = tk.Frame(self, bg=COLOR_FONDO_APP)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Columna izquierda (controles) con scroll
        izq_container = tk.Frame(main, bg=COLOR_FONDO_APP)
        izq_container.pack(side="left", fill="y", padx=(0, 8), pady=4)

        izq_canvas = tk.Canvas(izq_container, bg=COLOR_FONDO_APP,
                                highlightthickness=0, width=280)
        izq_scrollbar = ttk.Scrollbar(izq_container, orient="vertical",
                                       command=izq_canvas.yview)

        izq = tk.Frame(izq_canvas, bg="#242D40", bd=0)
        izq.bind("<Configure>",
                 lambda e: izq_canvas.configure(scrollregion=izq_canvas.bbox("all")))
        izq_canvas.create_window((0, 0), window=izq, anchor="nw")
        izq_canvas.configure(yscrollcommand=izq_scrollbar.set)

        izq_canvas.pack(side="left", fill="both", expand=True)
        izq_scrollbar.pack(side="right", fill="y")

        # Columna derecha (tabla + log)
        der = tk.Frame(main, bg=COLOR_FONDO_APP)
        der.pack(side="right", fill="both", expand=True, pady=4)

        # ── Paneles izquierda ──
        self.panel_capas = PanelCapas(
            izq, self.motor,
            callback_log=self._escribir_log,
            callback_tabla=self._poblar_tabla,
        )
        self.panel_config = PanelConfig(izq)
        self.panel_campos = PanelCampos(izq)
        self.panel_generacion = PanelGeneracion(
            izq, self.motor,
            get_config=self._get_config,
            callback_log=self._escribir_log,
        )

        # ── Paneles derecha ──
        self._crear_panel_tabla(der)
        self._crear_panel_log(der)

    def _barra_superior(self):
        barra = tk.Frame(self, bg="#141B2D", height=58)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        tk.Label(
            barra, text="\U0001f5fa  GENERADOR DE PLANOS FORESTALES",
            font=("Helvetica", 16, "bold"), bg="#141B2D", fg=COLOR_ACENTO,
        ).pack(side="left", padx=16, pady=10)

        tk.Label(
            barra, text="ETRS89 \u00b7 UTM H30N \u00b7 INFOCA",
            font=("Helvetica", 9), bg="#141B2D", fg=COLOR_TEXTO_GRIS,
        ).pack(side="right", padx=16)

    def _crear_panel_tabla(self, parent):
        lf = tk.LabelFrame(
            parent, text=" INFRAESTRUCTURAS CARGADAS ",
            font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        lf.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        cols = ["#", "Nombre_Infra", "Municipio", "Monte",
                "Tipo_Trabajos", "Longitud", "Superficie"]
        self._tabla = ttk.Treeview(lf, columns=cols, show="headings",
                                    selectmode="extended")
        for col in cols:
            ancho = 60 if col == "#" else 130
            self._tabla.heading(col, text=col)
            self._tabla.column(col, width=ancho, minwidth=40)

        sb_v = ttk.Scrollbar(lf, orient="vertical", command=self._tabla.yview)
        sb_h = ttk.Scrollbar(lf, orient="horizontal", command=self._tabla.xview)
        self._tabla.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self._tabla.pack(side="left", fill="both", expand=True)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")

    def _crear_panel_log(self, parent):
        lf = tk.LabelFrame(
            parent, text=" LOG DE PROCESO ",
            font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        lf.pack(fill="x", padx=4, pady=(0, 4))

        self._log = tk.Text(
            lf, height=7, font=FONT_MONO,
            bg="#0D1117", fg="#58D68D",
            insertbackground="white", relief="flat", state="disabled",
        )
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Tags de color
        self._log.tag_config("error", foreground="#E74C3C")
        self._log.tag_config("ok", foreground="#2ECC71")
        self._log.tag_config("warn", foreground="#F39C12")
        self._log.tag_config("info", foreground="#85C1E9")

        self._escribir_log("Sistema iniciado. Carga un shapefile para comenzar.", "info")

    def _escribir_log(self, msg: str, tipo: str = ""):
        def _do():
            self._log.configure(state="normal")
            tag = tipo if tipo else ""
            self._log.insert("end", msg + "\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _poblar_tabla(self):
        gdf = self.motor.gdf_infra
        if gdf is None:
            return
        for item in self._tabla.get_children():
            self._tabla.delete(item)

        cols_existentes = list(gdf.columns)

        def _val(row, campo):
            if campo in cols_existentes:
                return str(row[campo])
            return "\u2014"

        for i, (_, row) in enumerate(gdf.iterrows()):
            vals = [
                i + 1,
                _val(row, "Nombre_Infra"),
                _val(row, "Municipio"),
                _val(row, "Monte"),
                _val(row, "Tipo_Trabajos"),
                _val(row, "Longitud"),
                _val(row, "Superficie"),
            ]
            tag = "par" if i % 2 == 0 else "impar"
            self._tabla.insert("", "end", values=vals, tags=(tag,))

        self._tabla.tag_configure("par", background="#1E2A3A")
        self._tabla.tag_configure("impar", background="#172030")
        self._escribir_log(f"Tabla actualizada: {len(gdf)} infraestructuras.", "info")

    def _get_config(self) -> dict:
        """Devuelve la configuración actual para el panel de generación."""
        return {
            "formato": self.panel_config.formato.get(),
            "proveedor": self.panel_config.proveedor.get(),
            "transparencia": self.panel_capas.transparencia.get(),
            "campos": self.panel_campos.obtener_campos_activos(),
            "color_infra": self.panel_config.color_infra,
            "salida": self.panel_config.salida.get(),
            "tabla": self._tabla,
        }
