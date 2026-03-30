"""
Panel editor de simbologia: colores, grosores, trazos y marcadores
para infraestructuras, montes y capas extra.
"""

import tkinter as tk
from tkinter import ttk, colorchooser

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, COLOR_HOVER,
    FONT_BOLD, FONT_SMALL,
    crear_frame_seccion, crear_boton, crear_label,
)
from ..motor.simbologia import TIPOS_TRAZO, MARCADORES, PALETA_CATEGORIAS


class PanelSimbologia:
    """Panel de configuracion de simbologia para capas."""

    def __init__(self, parent, motor, callback_log):
        self.motor = motor
        self.callback_log = callback_log
        self._widgets_capas = []
        self._widgets_categorias = []

        f = crear_frame_seccion(parent, "\U0001f3a8  SIMBOLOG\u00cdA")

        # ── Categorizacion por campo ──
        crear_label(f, "Colorear por campo:", tipo="titulo").grid(
            row=0, column=0, sticky="w")

        cat_f = tk.Frame(f, bg=COLOR_PANEL)
        cat_f.grid(row=1, column=0, sticky="ew", pady=(2, 4))

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
        tk.Frame(f, bg=COLOR_BORDE, height=1).grid(
            row=3, column=0, sticky="ew", pady=(2, 8))

        # ── Simbologia de infraestructuras ──
        grosor_header = tk.Frame(f, bg=COLOR_PANEL)
        grosor_header.grid(row=4, column=0, sticky="ew")
        crear_label(grosor_header, "Grosor l\u00ednea infra:", tipo="normal").pack(
            side="left")
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
        crear_label(alpha_header, "Transparencia infra:", tipo="normal").pack(
            side="left")
        self._lbl_alpha = tk.Label(alpha_header, text="0.35", font=FONT_SMALL,
                                    bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_alpha.pack(side="right")

        self._alpha_infra = tk.DoubleVar(value=0.35)
        self._alpha_infra.trace_add("write", lambda *_: self._lbl_alpha.configure(
            text=f"{self._alpha_infra.get():.2f}"))
        ttk.Scale(f, from_=0.1, to=1.0, variable=self._alpha_infra,
                  orient="horizontal").grid(row=7, column=0, sticky="ew", pady=(2, 6))

        crear_label(f, "Trazo l\u00ednea infra:", tipo="normal").grid(
            row=8, column=0, sticky="w")
        self._trazo_infra = tk.StringVar(value="Continuo")
        ttk.Combobox(f, textvariable=self._trazo_infra,
                     values=list(TIPOS_TRAZO.keys()),
                     state="readonly", font=FONT_SMALL).grid(
                     row=9, column=0, sticky="ew", pady=(2, 6))

        crear_label(f, "Marcador puntos:", tipo="normal").grid(
            row=10, column=0, sticky="w")
        self._marcador = tk.StringVar(value="C\u00edrculo")
        ttk.Combobox(f, textvariable=self._marcador,
                     values=list(MARCADORES.keys()),
                     state="readonly", font=FONT_SMALL).grid(
                     row=11, column=0, sticky="ew", pady=(2, 6))

        # ── Color de montes ──
        crear_label(f, "Color montes:", tipo="normal").grid(
            row=12, column=0, sticky="w")
        col_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        col_montes_f.grid(row=13, column=0, sticky="ew", pady=(2, 6))
        self._color_montes = "#1a5c10"
        self._lbl_col_montes = tk.Label(col_montes_f, bg=self._color_montes,
                                         width=4, relief="flat", bd=0,
                                         highlightthickness=1,
                                         highlightbackground=COLOR_BORDE)
        self._lbl_col_montes.pack(side="left", padx=(0, 8))
        crear_boton(col_montes_f, "Cambiar", self._elegir_color_montes).pack(
            side="left")

        # ── Categorizacion de montes por campo ──
        tk.Frame(f, bg=COLOR_BORDE, height=1).grid(
            row=14, column=0, sticky="ew", pady=(2, 6))

        crear_label(f, "Colorear montes por campo:", tipo="titulo").grid(
            row=15, column=0, sticky="w")

        cat_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        cat_montes_f.grid(row=16, column=0, sticky="ew", pady=(2, 4))

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
        self._widgets_cat_montes = []

        # ── Capas extra ──
        tk.Frame(f, bg=COLOR_BORDE, height=1).grid(
            row=18, column=0, sticky="ew", pady=(2, 6))

        crear_label(f, "Capas adicionales:", tipo="titulo").grid(
            row=19, column=0, sticky="w", pady=(2, 0))

        self._frame_capas = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_capas.grid(row=20, column=0, sticky="ew", pady=(2, 4))

        # ── Boton aplicar ──
        crear_boton(f, "Aplicar simbolog\u00eda", self._aplicar,
                    estilo="primario").grid(
            row=21, column=0, sticky="ew", pady=(6, 4))

        f.columnconfigure(0, weight=1)

    def actualizar_capas_extra(self):
        for w in self._frame_capas.winfo_children():
            w.destroy()
        self._widgets_capas.clear()

        capas = self.motor.gestor_capas.capas
        if not capas:
            crear_label(self._frame_capas, "(sin capas adicionales)",
                        tipo="secundario").pack(anchor="w")
            return

        for capa in capas:
            row_f = tk.Frame(self._frame_capas, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=2)

            simb = self.motor.gestor_simbologia.obtener_simbologia_capa(capa.tipo)
            color_var = {"color": simb.color}

            lbl_color = tk.Label(row_f, bg=simb.color, width=3,
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=COLOR_BORDE)
            lbl_color.pack(side="left", padx=(0, 6))

            def _elegir(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de capa")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            crear_boton(row_f, capa.nombre, _elegir).pack(
                side="left", fill="x", expand=True)

            self._widgets_capas.append((capa.nombre, capa.tipo, color_var))

    def _on_campo_cat_changed(self, event=None):
        self._widgets_categorias.clear()
        for w in self._frame_categorias.winfo_children():
            w.destroy()

        campo = self._campo_categoria.get()
        if campo == "(ninguno)" or self.motor.gdf_infra is None:
            return

        valores = self.motor.obtener_valores_unicos(campo)
        if not valores:
            crear_label(self._frame_categorias, "(sin valores)",
                        tipo="secundario").pack(anchor="w")
            return

        self.motor.gestor_simbologia.generar_por_categoria(campo, valores)

        for i, valor in enumerate(valores[:20]):
            color = PALETA_CATEGORIAS[i % len(PALETA_CATEGORIAS)]

            row_f = tk.Frame(self._frame_categorias, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=2)

            color_var = {"color": color}
            lbl_color = tk.Label(row_f, bg=color, width=3,
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=COLOR_BORDE)
            lbl_color.pack(side="left", padx=(0, 6))

            def _elegir_cat(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de categor\u00eda")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            crear_boton(row_f, str(valor)[:22], _elegir_cat).pack(
                side="left", fill="x", expand=True)

            self._widgets_categorias.append(
                (str(valor), color_var, lbl_color))

        if len(valores) > 20:
            crear_label(self._frame_categorias,
                        f"... +{len(valores) - 20} valores m\u00e1s",
                        tipo="secundario").pack(anchor="w")

        self.callback_log(
            f"Categor\u00eda por '{campo}': {len(valores)} valores \u00fanicos.", "info")

    def _on_campo_cat_montes_changed(self, event=None):
        self._widgets_cat_montes.clear()
        for w in self._frame_cat_montes.winfo_children():
            w.destroy()

        campo = self._campo_cat_montes.get()
        if campo == "(ninguno)" or self.motor.gdf_montes is None:
            return

        if campo not in self.motor.gdf_montes.columns:
            crear_label(self._frame_cat_montes, "(campo no encontrado)",
                        tipo="secundario").pack(anchor="w")
            return

        valores = sorted(self.motor.gdf_montes[campo].dropna().astype(str).unique().tolist())
        if not valores:
            crear_label(self._frame_cat_montes, "(sin valores)",
                        tipo="secundario").pack(anchor="w")
            return

        self.motor.gestor_simbologia.generar_por_categoria_montes(campo, valores)

        paleta_montes = [
            "#1a5c10", "#2E7D32", "#388E3C", "#43A047", "#4CAF50",
            "#66BB6A", "#81C784", "#A5D6A7", "#558B2F", "#33691E",
            "#827717", "#9E9D24", "#AFB42B", "#C0CA33", "#D4E157",
        ]

        for i, valor in enumerate(valores[:20]):
            color = paleta_montes[i % len(paleta_montes)]

            row_f = tk.Frame(self._frame_cat_montes, bg=COLOR_PANEL)
            row_f.pack(fill="x", pady=2)

            color_var = {"color": color}
            lbl_color = tk.Label(row_f, bg=color, width=3,
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=COLOR_BORDE)
            lbl_color.pack(side="left", padx=(0, 6))

            def _elegir_cat(lbl=lbl_color, cv=color_var):
                c = colorchooser.askcolor(color=cv["color"],
                                          title="Color de categor\u00eda monte")[1]
                if c:
                    cv["color"] = c
                    lbl.configure(bg=c)

            crear_boton(row_f, str(valor)[:22], _elegir_cat).pack(
                side="left", fill="x", expand=True)

            self._widgets_cat_montes.append(
                (str(valor), color_var, lbl_color))

        if len(valores) > 20:
            crear_label(self._frame_cat_montes,
                        f"... +{len(valores) - 20} valores m\u00e1s",
                        tipo="secundario").pack(anchor="w")

        self.callback_log(
            f"Categor\u00eda montes por '{campo}': {len(valores)} valores \u00fanicos.", "info")

    def actualizar_campo_categoria(self):
        campos = ["(ninguno)"]
        if self.motor.gdf_infra is not None:
            campos += [c for c in self.motor.gdf_infra.columns
                       if c.lower() != "geometry"]
        self._cb_campo_cat.configure(values=campos)

    def actualizar_campo_categoria_montes(self):
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
        from ..motor.simbologia import ConfigSimbologia

        gs = self.motor.gestor_simbologia

        gs.montes.color = self._color_montes
        gs.montes.facecolor = self._color_montes

        for nombre, tipo, color_var in self._widgets_capas:
            simb = gs.obtener_simbologia_capa(tipo)
            simb.color = color_var["color"]
            simb.facecolor = color_var["color"] + "44"
            gs.set_simbologia_capa(tipo, simb)

        campo_cat = self._campo_categoria.get()
        if campo_cat != "(ninguno)" and self._widgets_categorias:
            for entry in self._widgets_categorias:
                valor, color_var, _ = entry
                if campo_cat in gs.categorias and valor in gs.categorias[campo_cat]:
                    simb = gs.categorias[campo_cat][valor]
                    simb.color = color_var["color"]
                    simb.facecolor = color_var["color"] + "55"

        campo_cat_montes = self._campo_cat_montes.get()
        if campo_cat_montes != "(ninguno)" and self._widgets_cat_montes:
            for entry in self._widgets_cat_montes:
                valor, color_var, _ = entry
                if (campo_cat_montes in gs.categorias_montes and
                        valor in gs.categorias_montes[campo_cat_montes]):
                    simb = gs.categorias_montes[campo_cat_montes][valor]
                    simb.color = color_var["color"]
                    simb.facecolor = color_var["color"]

        self.motor.config_infra = self.obtener_config_infra()

        self.callback_log("Simbolog\u00eda actualizada.", "info")

    def obtener_config_infra(self) -> dict:
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
