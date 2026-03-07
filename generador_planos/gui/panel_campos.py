"""
Panel de selección de campos a mostrar en el plano.
Campos dinámicos: se actualizan al cargar un shapefile, mostrando
las columnas reales de la capa + campos calculados automáticamente.
"""

import tkinter as tk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_BORDE, COLOR_ACENTO,
    FONT_SMALL,
    crear_frame_seccion,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS

# Campos por defecto hasta que se cargue un shapefile
_CAMPOS_DEFECTO = list(ETIQUETAS_CAMPOS.keys())


class PanelCampos:
    """Panel con checkboxes para seleccionar campos visibles en el plano."""

    def __init__(self, parent):
        self._parent_frame = crear_frame_seccion(parent,
                                                  "\U0001f3f7  CAMPOS EN EL PLANO")
        self._check_campos = {}
        self._widgets = []

        # Inicializar con los campos por defecto
        self._construir_checkboxes(_CAMPOS_DEFECTO)

    def actualizar_campos(self, columnas: list):
        """Reconstruye los checkboxes con las columnas reales del shapefile.

        Se llama cuando se carga un nuevo shapefile. Muestra los nombres
        reales de las columnas (excluye 'geometry').
        """
        cols = [c for c in columnas if c.lower() != "geometry"]
        self._construir_checkboxes(cols)

    def _construir_checkboxes(self, campos: list):
        """Destruye los checkboxes anteriores y crea nuevos."""
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()
        self._check_campos.clear()

        f = self._parent_frame
        for i, campo in enumerate(campos):
            var = tk.BooleanVar(value=True)
            # Mostrar etiqueta embellecida si la hay
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            cb = tk.Checkbutton(
                f, text=etiq, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
            )
            cb.grid(row=i, column=0, sticky="w", pady=1)
            self._check_campos[campo] = var
            self._widgets.append(cb)

    def obtener_campos_activos(self) -> list:
        """Devuelve la lista de campos actualmente seleccionados."""
        return [c for c, v in self._check_campos.items() if v.get()]
