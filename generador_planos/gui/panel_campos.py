"""
Panel de selección de campos a mostrar en el plano.
Cada campo tiene un checkbox que el usuario puede activar/desactivar.
"""

import tkinter as tk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_BORDE, COLOR_ACENTO,
    FONT_SMALL,
    crear_frame_seccion,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS

CAMPOS_ATRIBUTOS = list(ETIQUETAS_CAMPOS.keys())


class PanelCampos:
    """Panel con checkboxes para seleccionar campos visibles en el plano."""

    def __init__(self, parent):
        f = crear_frame_seccion(parent, "\U0001f3f7  CAMPOS EN EL PLANO")

        self._check_campos = {}
        for i, campo in enumerate(CAMPOS_ATRIBUTOS):
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(
                f, text=campo, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
            )
            cb.grid(row=i, column=0, sticky="w", pady=1)
            self._check_campos[campo] = var

        f.columnconfigure(0, weight=1)

    def obtener_campos_activos(self) -> list:
        """Devuelve la lista de campos actualmente seleccionados."""
        return [c for c, v in self._check_campos.items() if v.get()]
