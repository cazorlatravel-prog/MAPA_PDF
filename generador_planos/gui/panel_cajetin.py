"""
Panel de configuración del cajetín profesional y plantilla de colores.

Permite configurar: autor, proyecto, número de proyecto, revisión,
firma, organización, subtítulo y colores de la plantilla.
"""

import tkinter as tk
from tkinter import ttk, colorchooser

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE,
    COLOR_ACENTO, FONT_BOLD, FONT_SMALL,
    crear_frame_seccion,
)


class PanelCajetin:
    """Panel de configuración del cajetín y plantilla de colores."""

    def __init__(self, parent, motor, callback_log):
        self.motor = motor
        self.callback_log = callback_log

        f = crear_frame_seccion(parent, "\U0001f4cb  CAJET\u00cdN / PLANTILLA")

        # ── Campos del cajetín ──
        campos = [
            ("Autor:", "autor"),
            ("Proyecto:", "proyecto"),
            ("N\u00ba Proyecto:", "num_proyecto"),
            ("Revisi\u00f3n:", "revision"),
            ("Firma:", "firma"),
        ]
        self._vars = {}
        for i, (label, key) in enumerate(campos):
            tk.Label(f, text=label, font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO).grid(row=i * 2, column=0, sticky="w")
            var = tk.StringVar()
            tk.Entry(f, textvariable=var, font=FONT_SMALL, bg=COLOR_BORDE,
                     fg=COLOR_TEXTO, insertbackground="white",
                     relief="flat").grid(row=i * 2 + 1, column=0,
                                          sticky="ew", pady=(2, 4))
            self._vars[key] = var

        # Valores por defecto
        self._vars["revision"].set("0")

        # ── Organización (multilínea con Entry) ──
        r = len(campos) * 2
        tk.Label(f, text="Organizaci\u00f3n:", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).grid(row=r, column=0, sticky="w")
        self._org = tk.StringVar(
            value="CONSEJER\u00cdA DE SOSTENIBILIDAD - JUNTA DE ANDALUC\u00cdA")
        tk.Entry(f, textvariable=self._org, font=FONT_SMALL, bg=COLOR_BORDE,
                 fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=r + 1, column=0,
                                      sticky="ew", pady=(2, 4))

        tk.Label(f, text="Subt\u00edtulo:", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).grid(row=r + 2, column=0, sticky="w")
        self._subtitulo = tk.StringVar(
            value="PLANO DE INFRAESTRUCTURA FORESTAL")
        tk.Entry(f, textvariable=self._subtitulo, font=FONT_SMALL,
                 bg=COLOR_BORDE, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=r + 3, column=0,
                                      sticky="ew", pady=(2, 6))

        # ── Colores de plantilla ──
        r2 = r + 4
        tk.Label(f, text="Colores plantilla:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=r2, column=0, sticky="w", pady=(4, 2))

        self._colores = {
            "color_cabecera_fondo": "#1C2333",
            "color_cabecera_texto": "#FFFFFF",
            "color_cabecera_acento": "#2ECC71",
            "color_marco_exterior": "#1C2333",
            "color_marco_interior": "#2ECC71",
        }
        self._lbl_colores = {}

        etiquetas = {
            "color_cabecera_fondo": "Fondo cabecera",
            "color_cabecera_texto": "Texto cabecera",
            "color_cabecera_acento": "Acento cabecera",
            "color_marco_exterior": "Marco exterior",
            "color_marco_interior": "Marco interior",
        }

        for i, (key, label) in enumerate(etiquetas.items()):
            row_f = tk.Frame(f, bg=COLOR_PANEL)
            row_f.grid(row=r2 + 1 + i, column=0, sticky="ew", pady=1)

            lbl_c = tk.Label(row_f, bg=self._colores[key], width=3,
                              relief="solid", bd=1)
            lbl_c.pack(side="left", padx=(0, 6))
            self._lbl_colores[key] = lbl_c

            def _elegir(k=key, lbl=lbl_c):
                c = colorchooser.askcolor(color=self._colores[k],
                                          title=f"Color: {k}")[1]
                if c:
                    self._colores[k] = c
                    lbl.configure(bg=c)

            tk.Button(row_f, text=label, command=_elegir,
                      font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                      relief="flat", cursor="hand2").pack(side="left", fill="x",
                                                           expand=True)

        # ── Botón aplicar ──
        r3 = r2 + 1 + len(etiquetas)
        tk.Button(f, text="Aplicar cajet\u00edn y plantilla",
                  command=self._aplicar, font=FONT_SMALL,
                  bg=COLOR_ACENTO, fg="#1A1A2E", relief="flat",
                  cursor="hand2", pady=3).grid(
                  row=r3, column=0, sticky="ew", pady=(6, 4))

        f.columnconfigure(0, weight=1)

    def _aplicar(self):
        cajetin = self.obtener_cajetin()
        plantilla = self.obtener_plantilla()
        self.motor.set_cajetin(cajetin)
        self.motor.set_plantilla(plantilla)
        self.callback_log("Cajet\u00edn y plantilla actualizados.", "info")

    def obtener_cajetin(self) -> dict:
        org = self._org.get().replace(" - ", "\n")
        return {
            "autor": self._vars["autor"].get(),
            "proyecto": self._vars["proyecto"].get(),
            "num_proyecto": self._vars["num_proyecto"].get(),
            "revision": self._vars["revision"].get(),
            "firma": self._vars["firma"].get(),
            "organizacion": org,
            "subtitulo": self._subtitulo.get(),
        }

    def obtener_plantilla(self) -> dict:
        return dict(self._colores)

    def cargar_desde_proyecto(self, cajetin: dict, plantilla: dict):
        """Carga valores desde un proyecto guardado."""
        if cajetin:
            for key, var in self._vars.items():
                var.set(cajetin.get(key, ""))
            org = cajetin.get("organizacion", "")
            self._org.set(org.replace("\n", " - "))
            self._subtitulo.set(cajetin.get("subtitulo", ""))

        if plantilla:
            for key, color in plantilla.items():
                if key in self._colores:
                    self._colores[key] = color
                    if key in self._lbl_colores:
                        self._lbl_colores[key].configure(bg=color)
