"""
Panel de configuración: formato de salida, cartografía de fondo,
color de infraestructura, escala manual y carpeta de salida.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
from pathlib import Path

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE,
    FONT_BOLD, FONT_SMALL, FONT_LABEL,
    crear_frame_seccion, crear_boton,
)
from ..motor.escala import FORMATOS, ESCALAS
from ..motor.cartografia import PROVIDERS_CTX


class PanelConfig:
    """Panel de configuración general del plano."""

    def __init__(self, parent):
        f = crear_frame_seccion(parent, "\u2699  CONFIGURACI\u00d3N")

        # ── Formato ──
        tk.Label(f, text="Formato de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=0, column=0, sticky="w")
        self.formato = tk.StringVar(value="A3 Horizontal")
        cb_fmt = ttk.Combobox(f, textvariable=self.formato,
                              values=list(FORMATOS.keys()),
                              state="readonly", font=FONT_LABEL)
        cb_fmt.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        # ── Cartografía ──
        tk.Label(f, text="Cartograf\u00eda de fondo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=2, column=0, sticky="w")
        self.proveedor = tk.StringVar(value="OpenStreetMap")
        cb_prov = ttk.Combobox(f, textvariable=self.proveedor,
                               values=list(PROVIDERS_CTX.keys()),
                               state="readonly", font=FONT_LABEL)
        cb_prov.grid(row=3, column=0, sticky="ew", pady=(2, 8))

        # ── Escala manual ──
        tk.Label(f, text="Escala (0 = autom\u00e1tica):", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=4, column=0, sticky="w")
        escala_f = tk.Frame(f, bg=COLOR_PANEL)
        escala_f.grid(row=5, column=0, sticky="ew", pady=(2, 8))

        tk.Label(escala_f, text="1:", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).pack(side="left")
        self._escala_manual = tk.StringVar(value="0")
        self._cb_escala = ttk.Combobox(
            escala_f, textvariable=self._escala_manual,
            values=["0 (auto)"] + [f"{e:,}" for e in ESCALAS],
            font=FONT_SMALL, width=12,
        )
        self._cb_escala.pack(side="left", padx=(2, 0))

        # ── Color infraestructura ──
        tk.Label(f, text="Color infraestructura:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=6, column=0, sticky="w")
        self._color_infra = "#E74C3C"
        btn_frame = tk.Frame(f, bg=COLOR_PANEL)
        btn_frame.grid(row=7, column=0, sticky="ew", pady=(2, 8))
        self._lbl_color = tk.Label(btn_frame, bg=self._color_infra,
                                    width=4, relief="solid", bd=1)
        self._lbl_color.pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Elegir color", command=self._elegir_color,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2").pack(side="left")

        # ── Carpeta de salida ──
        tk.Label(f, text="Carpeta de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=8, column=0, sticky="w")
        self.salida = tk.StringVar(value=str(Path.home() / "Planos_Forestales"))
        tk.Label(f, textvariable=self.salida, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=9, column=0, sticky="w")
        crear_boton(f, "Seleccionar carpeta", self._elegir_carpeta,
                    icono="\U0001f4c1").grid(row=10, column=0, sticky="ew", pady=(4, 4))

        f.columnconfigure(0, weight=1)

    @property
    def color_infra(self) -> str:
        return self._color_infra

    @property
    def escala_manual(self) -> int:
        """Devuelve la escala manual o None si es automática."""
        txt = self._escala_manual.get().replace(",", "").strip()
        if txt.startswith("0"):
            return None
        try:
            val = int(txt)
            return val if val > 0 else None
        except ValueError:
            return None

    def _elegir_color(self):
        color = colorchooser.askcolor(
            color=self._color_infra,
            title="Color infraestructura",
        )[1]
        if color:
            self._color_infra = color
            self._lbl_color.configure(bg=color)

    def _elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Carpeta de salida")
        if carpeta:
            self.salida.set(carpeta)

    def abrir_carpeta(self):
        carpeta = self.salida.get()
        os.makedirs(carpeta, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(carpeta)
        elif sys.platform == "darwin":
            os.system(f'open "{carpeta}"')
        else:
            os.system(f'xdg-open "{carpeta}"')
