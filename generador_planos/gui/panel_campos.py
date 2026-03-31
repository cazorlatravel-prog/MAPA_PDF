"""
Panel de seleccion de campos a mostrar en el plano.
Campos dinamicos: se actualizan al cargar un shapefile, mostrando
las columnas reales de la capa + campos calculados automaticamente.
Permite reordenar campos mediante drag-and-drop.
"""

import tkinter as tk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ACENTO,
    COLOR_ENTRY, COLOR_HOVER,
    FONT_SMALL, FONT_BOLD,
    crear_frame_seccion, crear_label,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS

# Campos por defecto hasta que se cargue un shapefile
_CAMPOS_DEFECTO = list(ETIQUETAS_CAMPOS.keys())


class PanelCampos:
    """Panel con checkboxes para seleccionar campos visibles en el plano.
    Soporta reordenación mediante drag-and-drop."""

    def __init__(self, parent):
        self._parent_frame = crear_frame_seccion(parent,
                                                  "\U0001f3f7  CAMPOS EN EL PLANO")
        self._check_campos = {}
        self._widgets = []          # list of row frames
        self._campos_orden = []     # ordered field names
        self._drag_data = None      # drag state

        # Selector de campo encabezado
        enc_f = tk.Frame(self._parent_frame, bg=COLOR_PANEL)
        enc_f.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        crear_label(enc_f, "Encabezado:", tipo="normal").pack(side="left")
        self._combo_encabezado = tk.StringVar(value="(automatico)")
        self._combo_enc = tk.OptionMenu(enc_f, self._combo_encabezado, "(automatico)")
        self._combo_enc.configure(font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                                   relief="flat", cursor="hand2", highlightthickness=0,
                                   activebackground=COLOR_ACENTO,
                                   activeforeground="#FFFFFF", bd=0)
        self._combo_enc.pack(side="left", padx=(6, 0), fill="x", expand=True)

        # Botones Todos / Ninguno
        btn_f = tk.Frame(self._parent_frame, bg=COLOR_PANEL)
        btn_f.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        tk.Button(btn_f, text="Todos", command=self._sel_todos,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=8, bd=0,
                  activebackground=COLOR_ACENTO, activeforeground="#FFFFFF",
                  ).pack(side="left", padx=(0, 4))
        tk.Button(btn_f, text="Ninguno", command=self._sel_ninguno,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=8, bd=0,
                  activebackground=COLOR_ACENTO, activeforeground="#FFFFFF",
                  ).pack(side="left")
        self._lbl_count = tk.Label(btn_f, text="", font=FONT_SMALL,
                                    bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_count.pack(side="right")

        # Inicializar con los campos por defecto
        self._construir_checkboxes(_CAMPOS_DEFECTO)

    def actualizar_campos(self, columnas: list):
        cols = [c for c in columnas if c.lower() != "geometry"]
        self._construir_checkboxes(cols)

    def _construir_checkboxes(self, campos: list):
        for w in self._widgets:
            w.destroy()
        self._widgets.clear()
        self._check_campos.clear()
        self._campos_orden = list(campos)

        self._actualizar_combo_encabezado(campos)

        f = self._parent_frame
        for i, campo in enumerate(campos):
            var = tk.BooleanVar(value=True)
            self._check_campos[campo] = var

            row_frame = tk.Frame(f, bg=COLOR_PANEL)
            row_frame.grid(row=i + 2, column=0, sticky="ew", pady=1)
            row_frame._campo = campo

            # Drag handle
            handle = tk.Label(
                row_frame, text="\u2261", font=("Segoe UI", 11),
                bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS, cursor="fleur",
                padx=2,
            )
            handle.pack(side="left")

            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            cb = tk.Checkbutton(
                row_frame, text=etiq, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_ENTRY, activebackground=COLOR_PANEL,
                activeforeground=COLOR_ACENTO, cursor="hand2",
                command=self._actualizar_count, bd=0,
                highlightthickness=0,
            )
            cb.pack(side="left", fill="x", expand=True)

            # Bind drag events on the handle
            handle.bind("<ButtonPress-1>", lambda e, rf=row_frame: self._drag_start(e, rf))
            handle.bind("<B1-Motion>", self._drag_motion)
            handle.bind("<ButtonRelease-1>", self._drag_end)

            self._widgets.append(row_frame)

        self._actualizar_count()

    # ── Drag-and-drop ──────────────────────────────────────────────────

    def _drag_start(self, event, row_frame):
        """Start dragging a row."""
        self._drag_data = {
            "widget": row_frame,
            "start_y": event.y_root,
            "index": self._widgets.index(row_frame),
        }
        # Highlight the dragged row
        row_frame.configure(bg=COLOR_HOVER)
        for child in row_frame.winfo_children():
            child.configure(bg=COLOR_HOVER)

    def _drag_motion(self, event):
        """Handle mouse motion during drag."""
        if not self._drag_data:
            return

        dragged = self._drag_data["widget"]
        drag_idx = self._widgets.index(dragged)

        # Find which row we're hovering over
        for i, row in enumerate(self._widgets):
            if row is dragged:
                continue
            ry = row.winfo_rooty()
            rh = row.winfo_height()
            mid = ry + rh // 2
            if event.y_root < mid and i < drag_idx:
                self._swap_rows(drag_idx, i)
                break
            elif event.y_root > mid and i > drag_idx:
                self._swap_rows(drag_idx, i)
                break

    def _drag_end(self, event):
        """Finish dragging."""
        if not self._drag_data:
            return
        dragged = self._drag_data["widget"]
        dragged.configure(bg=COLOR_PANEL)
        for child in dragged.winfo_children():
            child.configure(bg=COLOR_PANEL)
        self._drag_data = None

    def _swap_rows(self, from_idx, to_idx):
        """Swap two rows in the list and re-grid them."""
        widgets = self._widgets
        campos = self._campos_orden

        # Swap in lists
        widgets[from_idx], widgets[to_idx] = widgets[to_idx], widgets[from_idx]
        campos[from_idx], campos[to_idx] = campos[to_idx], campos[from_idx]

        # Re-grid all rows
        for i, row in enumerate(widgets):
            row.grid_configure(row=i + 2)

        # Update _check_campos order to match
        new_check = {}
        for campo in campos:
            new_check[campo] = self._check_campos[campo]
        self._check_campos = new_check

    # ── Selection helpers ──────────────────────────────────────────────

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
        menu = self._combo_enc["menu"]
        menu.delete(0, "end")
        opciones = ["(automatico)"] + list(campos)
        for op in opciones:
            etiq = ETIQUETAS_CAMPOS.get(op, op)
            menu.add_command(label=etiq,
                             command=lambda v=op: self._combo_encabezado.set(v))
        if self._combo_encabezado.get() not in opciones:
            self._combo_encabezado.set("(automatico)")

    def restaurar_orden(self, orden: list):
        """Restaura el orden de campos desde un proyecto guardado."""
        # Solo reordenar campos que existen actualmente
        campos_actuales = set(self._campos_orden)
        orden_valido = [c for c in orden if c in campos_actuales]
        # Añadir campos nuevos que no estaban en el orden guardado
        restantes = [c for c in self._campos_orden if c not in orden_valido]
        nuevo_orden = orden_valido + restantes

        if nuevo_orden == self._campos_orden:
            return

        self._campos_orden = nuevo_orden
        # Reordenar check_campos para mantener coherencia
        new_check = {}
        for campo in nuevo_orden:
            new_check[campo] = self._check_campos[campo]
        self._check_campos = new_check

        # Re-grid widgets según nuevo orden
        for i, campo in enumerate(nuevo_orden):
            for w in self._widgets:
                if getattr(w, '_campo', None) == campo:
                    w.grid_configure(row=i + 2)
                    break
        # Reordenar la lista de widgets también
        widget_map = {getattr(w, '_campo', None): w for w in self._widgets}
        self._widgets = [widget_map[c] for c in nuevo_orden if c in widget_map]

    def obtener_campos_activos(self) -> list:
        return [c for c in self._campos_orden
                if self._check_campos.get(c, tk.BooleanVar(value=False)).get()]

    def obtener_campo_encabezado(self) -> str | None:
        val = self._combo_encabezado.get()
        if val == "(automatico)":
            return None
        return val
