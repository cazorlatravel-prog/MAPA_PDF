"""
Panel editor de simbología: colores, grosores, trazos y marcadores
para infraestructuras, montes y capas extra.
Incluye categorización por campo: color/trazo diferente según valor.
"""

import tkinter as tk
from tkinter import ttk, colorchooser

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE,
    COLOR_ACENTO, FONT_BOLD, FONT_SMALL,
    crear_frame_seccion,
)
from ..motor.simbologia import TIPOS_TRAZO, MARCADORES, TRAMAS, PALETA_CATEGORIAS


class PanelSimbologia:
    """Panel de configuración de simbología para capas."""

    def __init__(self, parent, motor, callback_log):
        self.motor = motor
        self.callback_log = callback_log
        self._widgets_capas = []
        # [(valor, color_var, lbl_color, trazo_var, trama_var, marcador_var)]
        self._widgets_categorias = []

        f = crear_frame_seccion(parent, "\U0001f3a8  SIMBOLOG\u00cdA")

        # ── Categorización por campo ──
        tk.Label(f, text="Colorear por campo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w")

        cat_f = tk.Frame(f, bg=COLOR_PANEL)
        cat_f.grid(row=1, column=0, sticky="ew", pady=(2, 2))

        self._campo_categoria = tk.StringVar(value="(ninguno)")
        self._cb_campo_cat = ttk.Combobox(
            cat_f, textvariable=self._campo_categoria,
            values=["(ninguno)"], state="readonly", font=FONT_SMALL, width=20,
        )
        self._cb_campo_cat.pack(side="left", fill="x", expand=True)
        self._cb_campo_cat.bind("<<ComboboxSelected>>", self._on_campo_cat_changed)

        self._frame_categorias = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_categorias.grid(row=2, column=0, sticky="ew", pady=(2, 6))

        # Separador
        ttk.Separator(f, orient="horizontal").grid(
            row=3, column=0, sticky="ew", pady=(2, 6))

        # ── Simbología de infraestructuras ──
        grosor_header = tk.Frame(f, bg=COLOR_PANEL)
        grosor_header.grid(row=4, column=0, sticky="ew")
        tk.Label(grosor_header, text="Grosor l\u00ednea infra:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left")
        self._lbl_grosor = tk.Label(grosor_header, text="2.5", font=FONT_SMALL,
                                     bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_grosor.pack(side="right")

        self._grosor_infra = tk.DoubleVar(value=2.5)
        self._grosor_infra.trace_add("write", lambda *_: self._lbl_grosor.configure(
            text=f"{self._grosor_infra.get():.1f}"))
        ttk.Scale(f, from_=0.5, to=15.0, variable=self._grosor_infra,
                  orient="horizontal").grid(row=5, column=0, sticky="ew", pady=(2, 6))

        alpha_header = tk.Frame(f, bg=COLOR_PANEL)
        alpha_header.grid(row=6, column=0, sticky="ew")
        tk.Label(alpha_header, text="Transparencia infra:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left")
        self._lbl_alpha = tk.Label(alpha_header, text="0.35", font=FONT_SMALL,
                                    bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_alpha.pack(side="right")

        self._alpha_infra = tk.DoubleVar(value=0.35)
        self._alpha_infra.trace_add("write", lambda *_: self._lbl_alpha.configure(
            text=f"{self._alpha_infra.get():.2f}"))
        ttk.Scale(f, from_=0.1, to=1.0, variable=self._alpha_infra,
                  orient="horizontal").grid(row=7, column=0, sticky="ew", pady=(2, 6))

        tk.Label(f, text="Trazo l\u00ednea infra:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=8, column=0, sticky="w")
        self._trazo_infra = tk.StringVar(value="Continuo")
        ttk.Combobox(f, textvariable=self._trazo_infra,
                     values=list(TIPOS_TRAZO.keys()),
                     state="readonly", font=FONT_SMALL).grid(
                     row=9, column=0, sticky="ew", pady=(2, 6))

        tk.Label(f, text="Marcador puntos:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=10, column=0, sticky="w")
        self._marcador = tk.StringVar(value="C\u00edrculo")
        ttk.Combobox(f, textvariable=self._marcador,
                     values=list(MARCADORES.keys()),
                     state="readonly", font=FONT_SMALL).grid(
                     row=11, column=0, sticky="ew", pady=(2, 6))

        # ── Color de montes ──
        tk.Label(f, text="Color montes:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=12, column=0, sticky="w")
        col_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        col_montes_f.grid(row=13, column=0, sticky="ew", pady=(2, 6))
        self._color_montes = "#1a5c10"
        self._lbl_col_montes = tk.Label(col_montes_f, bg=self._color_montes,
                                         width=4, relief="solid", bd=1)
        self._lbl_col_montes.pack(side="left", padx=(0, 6))
        tk.Button(col_montes_f, text="Cambiar", command=self._elegir_color_montes,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2").pack(side="left")

        # ── Categorización de montes por campo ──
        ttk.Separator(f, orient="horizontal").grid(
            row=14, column=0, sticky="ew", pady=(2, 4))

        tk.Label(f, text="Colorear montes por campo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=15, column=0, sticky="w")

        cat_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        cat_montes_f.grid(row=16, column=0, sticky="ew", pady=(2, 2))

        self._campo_cat_montes = tk.StringVar(value="(ninguno)")
        self._cb_campo_cat_montes = ttk.Combobox(
            cat_montes_f, textvariable=self._campo_cat_montes,
            values=["(ninguno)"], state="readonly", font=FONT_SMALL, width=20,
        )
        self._cb_campo_cat_montes.pack(side="left", fill="x", expand=True)
        self._cb_campo_cat_montes.bind("<<ComboboxSelected>>",
                                        self._on_campo_cat_montes_changed)

        self._frame_cat_montes = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_cat_montes.grid(row=17, column=0, sticky="ew", pady=(2, 6))
        self._widgets_cat_montes = []  # [(valor, color_var, lbl_color), ...]

        # ── Capas extra ──
        ttk.Separator(f, orient="horizontal").grid(
            row=18, column=0, sticky="ew", pady=(2, 4))

        tk.Label(f, text="Capas adicionales:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=19, column=0, sticky="w", pady=(2, 0))

        self._frame_capas = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_capas.grid(row=20, column=0, sticky="ew", pady=(2, 4))

        # ── Botón aplicar ──
        tk.Button(f, text="Aplicar simbolog\u00eda", command=self._aplicar,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", pady=3).grid(
                  row=21, column=0, sticky="ew", pady=(4, 4))

        f.columnconfigure(0, weight=1)

    def actualizar_capas_extra(self):
        """Actualiza la lista de capas extra disponibles."""
        for w in self._frame_capas.winfo_children():
            w.destroy()
        self._widgets_capas.clear()

        capas = self.motor.gestor_capas.capas
        if not capas:
            tk.Label(self._frame_capas, text="(sin capas adicionales)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")
            return

        for capa in capas:
            row_f = tk.Frame(self._frame_capas, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=1)

            simb = self.motor.gestor_simbologia.obtener_simbologia_capa(capa.tipo)
            color_var = {"color": simb.color}

            lbl_color = tk.Label(row_f, bg=simb.color, width=3,
                                  relief="solid", bd=1)
            lbl_color.pack(side="left", padx=(0, 4))

            def _elegir(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de capa")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            tk.Button(row_f, text=capa.nombre, command=_elegir,
                      font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                      relief="flat", cursor="hand2").pack(side="left", fill="x",
                                                           expand=True)

            self._widgets_capas.append((capa.nombre, capa.tipo, color_var))

    def _on_campo_cat_changed(self, event=None):
        """Cuando cambia el campo de categorización, genera colores/estilos por valor."""
        from ..motor.simbologia import _TRAMAS_CICLO
        self._widgets_categorias.clear()
        for w in self._frame_categorias.winfo_children():
            w.destroy()

        campo = self._campo_categoria.get()
        if campo == "(ninguno)" or self.motor.gdf_infra is None:
            return

        valores = self.motor.obtener_valores_unicos(campo)
        if not valores:
            tk.Label(self._frame_categorias, text="(sin valores)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")
            return

        # Generar simbología automática
        self.motor.gestor_simbologia.generar_por_categoria(campo, valores)

        nombres_tramas = list(TRAMAS.keys())
        nombres_trazos = list(TIPOS_TRAZO.keys())
        nombres_marcadores = list(MARCADORES.keys())
        trazos_inv = {v: k for k, v in TIPOS_TRAZO.items()}
        tramas_inv = {v: k for k, v in TRAMAS.items()}
        marcadores_inv = {v: k for k, v in MARCADORES.items()}

        for i, valor in enumerate(valores[:20]):
            color = PALETA_CATEGORIAS[i % len(PALETA_CATEGORIAS)]
            hatch_code = _TRAMAS_CICLO[i % len(_TRAMAS_CICLO)]

            # Fila principal: color + nombre
            row_f = tk.Frame(self._frame_categorias, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=1)

            color_var = {"color": color}
            lbl_color = tk.Label(row_f, bg=color, width=3,
                                  relief="solid", bd=1)
            lbl_color.pack(side="left", padx=(0, 4))

            def _elegir_cat(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de categor\u00eda")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            tk.Button(row_f, text=str(valor)[:22], command=_elegir_cat,
                      font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                      relief="flat", cursor="hand2", anchor="w").pack(
                      side="left", fill="x", expand=True)

            # Fila de estilo: trazo + trama + marcador
            style_f = tk.Frame(self._frame_categorias, bg=COLOR_PANEL)
            style_f.pack(fill="x", pady=(0, 2), padx=(14, 0))

            # Trazo
            trazo_var = tk.StringVar(value=trazos_inv.get("-", "Continuo"))
            ttk.Combobox(style_f, textvariable=trazo_var,
                         values=nombres_trazos, state="readonly",
                         font=FONT_SMALL, width=8).pack(side="left", padx=(0, 2))

            # Trama
            trama_var = tk.StringVar(
                value=tramas_inv.get(hatch_code, "Sin trama"))
            ttk.Combobox(style_f, textvariable=trama_var,
                         values=nombres_tramas, state="readonly",
                         font=FONT_SMALL, width=9).pack(side="left", padx=(0, 2))

            # Marcador
            marcador_var = tk.StringVar(value="C\u00edrculo")
            ttk.Combobox(style_f, textvariable=marcador_var,
                         values=nombres_marcadores, state="readonly",
                         font=FONT_SMALL, width=7).pack(side="left")

            self._widgets_categorias.append(
                (str(valor), color_var, lbl_color,
                 trazo_var, trama_var, marcador_var))

        if len(valores) > 20:
            tk.Label(self._frame_categorias,
                     text=f"... +{len(valores) - 20} valores m\u00e1s (estilos auto)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")

        self.callback_log(
            f"Categor\u00eda por '{campo}': {len(valores)} valores \u00fanicos.", "info")

    def _on_campo_cat_montes_changed(self, event=None):
        """Cuando cambia el campo de categorización de montes, genera estilos por valor."""
        from ..motor.simbologia import _TRAMAS_CICLO
        self._widgets_cat_montes.clear()
        for w in self._frame_cat_montes.winfo_children():
            w.destroy()

        campo = self._campo_cat_montes.get()
        if campo == "(ninguno)" or self.motor.gdf_montes is None:
            return

        if campo not in self.motor.gdf_montes.columns:
            tk.Label(self._frame_cat_montes, text="(campo no encontrado)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")
            return

        valores = sorted(self.motor.gdf_montes[campo].dropna().astype(str).unique().tolist())
        if not valores:
            tk.Label(self._frame_cat_montes, text="(sin valores)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")
            return

        # Generar simbología automática
        self.motor.gestor_simbologia.generar_por_categoria_montes(campo, valores)

        paleta_montes = [
            "#1a5c10", "#2E7D32", "#388E3C", "#43A047", "#4CAF50",
            "#66BB6A", "#81C784", "#A5D6A7", "#558B2F", "#33691E",
            "#827717", "#9E9D24", "#AFB42B", "#C0CA33", "#D4E157",
        ]

        nombres_tramas = list(TRAMAS.keys())
        tramas_inv = {v: k for k, v in TRAMAS.items()}

        for i, valor in enumerate(valores[:20]):
            color = paleta_montes[i % len(paleta_montes)]
            hatch_code = _TRAMAS_CICLO[i % len(_TRAMAS_CICLO)]

            row_f = tk.Frame(self._frame_cat_montes, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=1)

            color_var = {"color": color}
            lbl_color = tk.Label(row_f, bg=color, width=3,
                                  relief="solid", bd=1)
            lbl_color.pack(side="left", padx=(0, 4))

            def _elegir_cat(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de categor\u00eda monte")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            tk.Button(row_f, text=str(valor)[:22], command=_elegir_cat,
                      font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                      relief="flat", cursor="hand2", anchor="w").pack(
                      side="left", fill="x", expand=True)

            # Selector de trama para polígonos de montes
            style_f = tk.Frame(self._frame_cat_montes, bg=COLOR_PANEL)
            style_f.pack(fill="x", pady=(0, 2), padx=(14, 0))

            tk.Label(style_f, text="Trama:", font=FONT_SMALL,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(side="left")
            trama_var = tk.StringVar(
                value=tramas_inv.get(hatch_code, "Sin trama"))
            ttk.Combobox(style_f, textvariable=trama_var,
                         values=nombres_tramas, state="readonly",
                         font=FONT_SMALL, width=10).pack(side="left", padx=(2, 0))

            self._widgets_cat_montes.append(
                (str(valor), color_var, lbl_color, trama_var))

        if len(valores) > 20:
            tk.Label(self._frame_cat_montes,
                     text=f"... +{len(valores) - 20} valores m\u00e1s (estilos auto)",
                     font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w")

        self.callback_log(
            f"Categor\u00eda montes por '{campo}': {len(valores)} valores \u00fanicos.", "info")

    def actualizar_campo_categoria(self):
        """Actualiza las opciones del combobox de categorización con columnas del shapefile."""
        campos = ["(ninguno)"]
        if self.motor.gdf_infra is not None:
            campos += [c for c in self.motor.gdf_infra.columns
                       if c.lower() != "geometry"]
        self._cb_campo_cat.configure(values=campos)

    def actualizar_campo_categoria_montes(self):
        """Actualiza las opciones del combobox de categorización de montes."""
        campos = ["(ninguno)"]
        if self.motor.gdf_montes is not None:
            campos += [c for c in self.motor.gdf_montes.columns
                       if c.lower() != "geometry"]
        self._cb_campo_cat_montes.configure(values=campos)

    def _elegir_color_montes(self):
        c = colorchooser.askcolor(color=self._color_montes,
                                  title="Color montes")[1]
        if c:
            self._color_montes = c
            self._lbl_col_montes.configure(bg=c)

    def _aplicar(self):
        """Aplica la simbología configurada al gestor del motor."""
        from ..motor.simbologia import ConfigSimbologia

        gs = self.motor.gestor_simbologia

        # Montes
        gs.montes.color = self._color_montes
        gs.montes.facecolor = self._color_montes

        # Capas extra
        for nombre, tipo, color_var in self._widgets_capas:
            simb = gs.obtener_simbologia_capa(tipo)
            simb.color = color_var["color"]
            simb.facecolor = color_var["color"] + "44"
            gs.set_simbologia_capa(tipo, simb)

        # Categorización por campo: actualizar colores y estilos editados
        campo_cat = self._campo_categoria.get()
        if campo_cat != "(ninguno)" and self._widgets_categorias:
            for entry in self._widgets_categorias:
                valor, color_var, _, trazo_var, trama_var, marcador_var = entry
                if campo_cat in gs.categorias and valor in gs.categorias[campo_cat]:
                    simb = gs.categorias[campo_cat][valor]
                    simb.color = color_var["color"]
                    simb.facecolor = color_var["color"] + "55"
                    simb.linestyle = TIPOS_TRAZO.get(trazo_var.get(), "-")
                    simb.hatch = TRAMAS.get(trama_var.get(), "")
                    simb.marker = MARCADORES.get(marcador_var.get(), "o")

        # Categorización de montes por campo
        campo_cat_montes = self._campo_cat_montes.get()
        if campo_cat_montes != "(ninguno)" and self._widgets_cat_montes:
            for entry in self._widgets_cat_montes:
                valor, color_var, _, trama_var = entry
                if (campo_cat_montes in gs.categorias_montes and
                        valor in gs.categorias_montes[campo_cat_montes]):
                    simb = gs.categorias_montes[campo_cat_montes][valor]
                    simb.color = color_var["color"]
                    simb.facecolor = color_var["color"]
                    simb.hatch = TRAMAS.get(trama_var.get(), "")

        # Configuración infraestructuras (grosor, transparencia, trazo, marcador)
        self.motor.config_infra = self.obtener_config_infra()

        self.callback_log("Simbolog\u00eda actualizada.", "info")

    def obtener_config_infra(self) -> dict:
        """Devuelve configuración de simbología de infraestructuras."""
        campo_cat = self._campo_categoria.get()
        campo_cat_montes = self._campo_cat_montes.get()
        return {
            "linewidth": self._grosor_infra.get(),
            "alpha": self._alpha_infra.get(),
            "linestyle": TIPOS_TRAZO.get(self._trazo_infra.get(), "-"),
            "marker": MARCADORES.get(self._marcador.get(), "o"),
            "campo_categoria": campo_cat if campo_cat != "(ninguno)" else None,
            "campo_categoria_montes": campo_cat_montes if campo_cat_montes != "(ninguno)" else None,
        }
