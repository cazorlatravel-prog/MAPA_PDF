"""
Panel de selección de campos a mostrar en el plano.
Campos dinámicos: se actualizan al cargar un shapefile, mostrando
las columnas reales de la capa + campos calculados automáticamente.
"""

import tkinter as tk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ACENTO,
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

        # Selector de campo encabezado
        enc_f = tk.Frame(self._parent_frame, bg=COLOR_PANEL)
        enc_f.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(enc_f, text="Encabezado:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left")
        self._combo_encabezado = tk.StringVar(value="(automático)")
        self._combo_enc = tk.OptionMenu(enc_f, self._combo_encabezado, "(automático)")
        self._combo_enc.configure(font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                   relief="flat", cursor="hand2", highlightthickness=0)
        self._combo_enc.pack(side="left", padx=(4, 0), fill="x", expand=True)

        # Botones Todos / Ninguno
        btn_f = tk.Frame(self._parent_frame, bg=COLOR_PANEL)
        btn_f.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        tk.Button(btn_f, text="Todos", command=self._sel_todos,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left", padx=(0, 4))
        tk.Button(btn_f, text="Ninguno", command=self._sel_ninguno,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left")
        self._lbl_count = tk.Label(btn_f, text="", font=FONT_SMALL,
                                    bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_count.pack(side="right")

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

        # Actualizar combo de encabezado con los campos disponibles
        self._actualizar_combo_encabezado(campos)

        f = self._parent_frame
        # row 0 = combo encabezado, row 1 = botones, row 2+ = checkboxes
        for i, campo in enumerate(campos):
            var = tk.BooleanVar(value=True)
            # Mostrar etiqueta embellecida si la hay
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            cb = tk.Checkbutton(
                f, text=etiq, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
                command=self._actualizar_count,
            )
            cb.grid(row=i + 2, column=0, sticky="w", pady=1)
            self._check_campos[campo] = var
            self._widgets.append(cb)

        self._actualizar_count()

    def _sel_todos(self):
        for v in self._check_campos.values():
            v.set(True)
        self._actualizar_count()

    def _sel_ninguno(self):
        for v in self._check_campos.values():
            v.set(False)
        self._actualizar_count()

    def _actualizar_count(self):
        n = sum(1 for v in self._check_campos.values() if v.get())
        total = len(self._check_campos)
        self._lbl_count.configure(text=f"{n}/{total}")

    def _actualizar_combo_encabezado(self, campos: list):
        """Actualiza las opciones del combo de encabezado."""
        menu = self._combo_enc["menu"]
        menu.delete(0, "end")
        opciones = ["(automático)"] + list(campos)
        for op in opciones:
            etiq = ETIQUETAS_CAMPOS.get(op, op)
            menu.add_command(label=etiq,
                             command=lambda v=op: self._combo_encabezado.set(v))
        # Si el valor actual no está en la nueva lista, resetear
        if self._combo_encabezado.get() not in opciones:
            self._combo_encabezado.set("(automático)")

    def obtener_campos_activos(self) -> list:
        """Devuelve la lista de campos actualmente seleccionados."""
        return [c for c, v in self._check_campos.items() if v.get()]

    def obtener_campo_encabezado(self) -> str | None:
        """Devuelve el campo elegido como encabezado, o None si es automático."""
        val = self._combo_encabezado.get()
        if val == "(automático)":
            return None
        return val
