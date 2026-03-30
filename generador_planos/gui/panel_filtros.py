"""
Panel de filtros avanzados para la tabla de infraestructuras.

Permite filtrar por tipo de trabajo, rango de superficie/longitud,
municipio, monte y texto libre.
"""

import tkinter as tk
from tkinter import ttk

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, FONT_BOLD, FONT_SMALL,
    crear_frame_seccion,
)


class PanelFiltros:
    """Panel lateral de filtros avanzados para la tabla."""

    def __init__(self, parent, motor, callback_filtro):
        """
        motor: GeneradorPlanos
        callback_filtro: callable(indices_filtrados: list) para actualizar la tabla
        """
        self.motor = motor
        self.callback_filtro = callback_filtro
        self._parent = parent
        self._debounce_id = None

        f = crear_frame_seccion(parent, "\U0001f50d  FILTROS")

        # ── Búsqueda por texto ──
        tk.Label(f, text="Buscar texto:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w")
        self._busqueda = tk.StringVar()
        self._busqueda.trace_add("write", lambda *a: self._debounce_filtros())
        tk.Entry(f, textvariable=self._busqueda, font=FONT_SMALL,
                 bg=COLOR_ENTRY, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=1, column=0, sticky="ew", pady=(2, 6))

        # ── Filtro por campo ──
        tk.Label(f, text="Filtrar por campo:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
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
        self._cb_valor.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        self._cb_valor.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtros())

        # ── Rango de superficie ──
        tk.Label(f, text="Superficie (ha):", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=5, column=0, sticky="w")
        rango_sup = tk.Frame(f, bg=COLOR_PANEL)
        rango_sup.grid(row=6, column=0, sticky="ew", pady=(2, 6))

        self._sup_min = tk.Entry(rango_sup, width=8, font=FONT_SMALL,
                                  bg=COLOR_ENTRY, fg=COLOR_TEXTO,
                                  insertbackground="white", relief="flat")
        self._sup_min.pack(side="left")
        tk.Label(rango_sup, text=" - ", bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=FONT_SMALL).pack(side="left")
        self._sup_max = tk.Entry(rango_sup, width=8, font=FONT_SMALL,
                                  bg=COLOR_ENTRY, fg=COLOR_TEXTO,
                                  insertbackground="white", relief="flat")
        self._sup_max.pack(side="left")

        # ── Rango de longitud ──
        tk.Label(f, text="Longitud (m):", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=7, column=0, sticky="w")
        rango_lon = tk.Frame(f, bg=COLOR_PANEL)
        rango_lon.grid(row=8, column=0, sticky="ew", pady=(2, 6))

        self._lon_min = tk.Entry(rango_lon, width=8, font=FONT_SMALL,
                                  bg=COLOR_ENTRY, fg=COLOR_TEXTO,
                                  insertbackground="white", relief="flat")
        self._lon_min.pack(side="left")
        tk.Label(rango_lon, text=" - ", bg=COLOR_PANEL, fg=COLOR_TEXTO,
                 font=FONT_SMALL).pack(side="left")
        self._lon_max = tk.Entry(rango_lon, width=8, font=FONT_SMALL,
                                  bg=COLOR_ENTRY, fg=COLOR_TEXTO,
                                  insertbackground="white", relief="flat")
        self._lon_max.pack(side="left")

        # ── Botones ──
        btn_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_f.grid(row=9, column=0, sticky="ew", pady=(4, 4))
        tk.Button(btn_f, text="Aplicar", command=self._aplicar_filtros,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", padx=6).pack(side="left", padx=(0, 4))
        tk.Button(btn_f, text="Limpiar", command=self._limpiar_filtros,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=6).pack(side="left")

        self._lbl_resultado = tk.Label(f, text="", font=FONT_SMALL,
                                        bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_resultado.grid(row=10, column=0, sticky="w", pady=(2, 0))

        f.columnconfigure(0, weight=1)

    def actualizar_campos(self):
        """Actualiza las opciones de filtro cuando se carga un nuevo SHP."""
        cols = self.motor.obtener_columnas_shapefile()
        self._cb_campo["values"] = ["(todos)"] + cols
        self._campo_filtro.set("(todos)")
        self._cb_valor["values"] = ["(todos)"]
        self._valor_filtro.set("(todos)")
        # Limpiar filtros activos del SHP anterior
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
        """Aplica filtros con retardo de 300ms para evitar recálculos por tecla."""
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

        # Filtro por texto libre (vectorizado)
        texto = self._busqueda.get().strip().lower()
        if texto:
            cols = [c for c in gdf.columns if c != "geometry"]
            text_match = np.zeros(len(gdf), dtype=bool)
            for col in cols:
                text_match |= gdf[col].astype(str).str.lower().str.contains(
                    texto, na=False, regex=False)
            mask &= text_match

        # Filtro por campo/valor (vectorizado)
        campo = self._campo_filtro.get()
        valor = self._valor_filtro.get()
        if campo != "(todos)" and valor != "(todos)":
            if campo in gdf.columns:
                mask &= (gdf[campo].astype(str) == valor).values

        # Filtro por superficie (vectorizado)
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

        # Filtro por longitud (vectorizado)
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
            text=f"{len(indices)}/{len(gdf)} infraestructuras")
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
