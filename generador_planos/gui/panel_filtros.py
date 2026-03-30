"""
Panel de filtros avanzados para la tabla de infraestructuras.
"""

import tkinter as tk
from tkinter import ttk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO,
    FONT_BOLD, FONT_SMALL,
    crear_frame_seccion, crear_boton, crear_entry, crear_label,
)


class PanelFiltros:
    """Panel lateral de filtros avanzados para la tabla."""

    def __init__(self, parent, motor, callback_filtro):
        self.motor = motor
        self.callback_filtro = callback_filtro
        self._parent = parent
        self._debounce_id = None

        f = crear_frame_seccion(parent, "\U0001f50d  FILTROS")

        # ── Busqueda por texto ──
        crear_label(f, "Buscar texto:", tipo="normal").grid(
            row=0, column=0, sticky="w")
        self._busqueda = tk.StringVar()
        self._busqueda.trace_add("write", lambda *a: self._debounce_filtros())
        crear_entry(f, textvariable=self._busqueda).grid(
            row=1, column=0, sticky="ew", pady=(2, 8))

        # ── Filtro por campo ──
        crear_label(f, "Filtrar por campo:", tipo="normal").grid(
            row=2, column=0, sticky="w")
        self._campo_filtro = tk.StringVar(value="(todos)")
        self._cb_campo = ttk.Combobox(f, textvariable=self._campo_filtro,
                                       values=["(todos)"], state="readonly",
                                       font=FONT_SMALL)
        self._cb_campo.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        self._cb_campo.bind("<<ComboboxSelected>>", self._on_campo_changed)

        # ── Filtro por valor del campo ──
        self._valor_filtro = tk.StringVar(value="(todos)")
        self._cb_valor = ttk.Combobox(f, textvariable=self._valor_filtro,
                                       values=["(todos)"], state="readonly",
                                       font=FONT_SMALL)
        self._cb_valor.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self._cb_valor.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtros())

        # ── Rango de superficie ──
        crear_label(f, "Superficie (ha):", tipo="secundario").grid(
            row=5, column=0, sticky="w")
        rango_sup = tk.Frame(f, bg=COLOR_PANEL)
        rango_sup.grid(row=6, column=0, sticky="ew", pady=(2, 8))

        self._sup_min = crear_entry(rango_sup, width=8)
        self._sup_min.pack(side="left")
        tk.Label(rango_sup, text=" \u2013 ", bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 font=FONT_SMALL).pack(side="left")
        self._sup_max = crear_entry(rango_sup, width=8)
        self._sup_max.pack(side="left")

        # ── Rango de longitud ──
        crear_label(f, "Longitud (m):", tipo="secundario").grid(
            row=7, column=0, sticky="w")
        rango_lon = tk.Frame(f, bg=COLOR_PANEL)
        rango_lon.grid(row=8, column=0, sticky="ew", pady=(2, 8))

        self._lon_min = crear_entry(rango_lon, width=8)
        self._lon_min.pack(side="left")
        tk.Label(rango_lon, text=" \u2013 ", bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 font=FONT_SMALL).pack(side="left")
        self._lon_max = crear_entry(rango_lon, width=8)
        self._lon_max.pack(side="left")

        # ── Botones ──
        btn_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_f.grid(row=9, column=0, sticky="ew", pady=(4, 4))
        btn_f.columnconfigure(0, weight=1)
        btn_f.columnconfigure(1, weight=1)
        crear_boton(btn_f, "Aplicar", self._aplicar_filtros,
                    estilo="primario").grid(row=0, column=0, sticky="ew", padx=(0, 3))
        crear_boton(btn_f, "Limpiar", self._limpiar_filtros).grid(
            row=0, column=1, sticky="ew", padx=(3, 0))

        self._lbl_resultado = tk.Label(f, text="", font=FONT_SMALL,
                                        bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_resultado.grid(row=10, column=0, sticky="w", pady=(4, 0))

        f.columnconfigure(0, weight=1)

    def actualizar_campos(self):
        cols = self.motor.obtener_columnas_shapefile()
        self._cb_campo["values"] = ["(todos)"] + cols
        self._campo_filtro.set("(todos)")
        self._cb_valor["values"] = ["(todos)"]
        self._valor_filtro.set("(todos)")
        self._limpiar_filtros()

    def _on_campo_changed(self, event=None):
        campo = self._campo_filtro.get()
        if campo == "(todos)":
            self._cb_valor["values"] = ["(todos)"]
            self._valor_filtro.set("(todos)")
            return

        valores = self.motor.obtener_valores_unicos(campo)
        self._cb_valor["values"] = ["(todos)"] + valores
        self._valor_filtro.set("(todos)")

    def _debounce_filtros(self):
        if self._debounce_id is not None:
            self._parent.after_cancel(self._debounce_id)
        self._debounce_id = self._parent.after(300, self._aplicar_filtros)

    def _aplicar_filtros(self):
        self._debounce_id = None
        gdf = self.motor.gdf_infra
        if gdf is None:
            self._lbl_resultado.configure(text="")
            return

        import numpy as np
        mask = np.ones(len(gdf), dtype=bool)

        texto = self._busqueda.get().strip().lower()
        if texto:
            cols = [c for c in gdf.columns if c != "geometry"]
            text_match = np.zeros(len(gdf), dtype=bool)
            for col in cols:
                text_match |= gdf[col].astype(str).str.lower().str.contains(
                    texto, na=False, regex=False)
            mask &= text_match

        campo = self._campo_filtro.get()
        valor = self._valor_filtro.get()
        if campo != "(todos)" and valor != "(todos)":
            if campo in gdf.columns:
                mask &= (gdf[campo].astype(str) == valor).values

        sup_min_txt = self._sup_min.get().strip()
        sup_max_txt = self._sup_max.get().strip()
        if (sup_min_txt or sup_max_txt) and "Superficie" in gdf.columns:
            try:
                sup_vals = gdf["Superficie"].astype(float)
                if sup_min_txt:
                    mask &= (sup_vals >= float(sup_min_txt)).values
                if sup_max_txt:
                    mask &= (sup_vals <= float(sup_max_txt)).values
            except (ValueError, TypeError):
                pass

        lon_min_txt = self._lon_min.get().strip()
        lon_max_txt = self._lon_max.get().strip()
        if (lon_min_txt or lon_max_txt) and "Longitud" in gdf.columns:
            try:
                lon_vals = gdf["Longitud"].astype(float)
                if lon_min_txt:
                    mask &= (lon_vals >= float(lon_min_txt)).values
                if lon_max_txt:
                    mask &= (lon_vals <= float(lon_max_txt)).values
            except (ValueError, TypeError):
                pass

        indices = list(np.where(mask)[0])
        self._lbl_resultado.configure(
            text=f"{len(indices)} / {len(gdf)} infraestructuras")
        self.callback_filtro(indices)

    def _limpiar_filtros(self):
        self._busqueda.set("")
        self._campo_filtro.set("(todos)")
        self._valor_filtro.set("(todos)")
        self._sup_min.delete(0, "end")
        self._sup_max.delete(0, "end")
        self._lon_min.delete(0, "end")
        self._lon_max.delete(0, "end")
        self._lbl_resultado.configure(text="")

        gdf = self.motor.gdf_infra
        if gdf is not None:
            self.callback_filtro(list(range(len(gdf))))
