"""
Ventana principal de la aplicación Generador de Planos Forestales.

Layout: 1100x780 px mínimo, redimensionable.
┌─────────────────────────────────────────────────────────────┐
│  GENERADOR DE PLANOS FORESTALES            ETRS89·UTM H30N  │
├──────────────────┬──────────────────────────────────────────┤
│  CAPAS           │  TABLA DE INFRAESTRUCTURAS               │
│  CONFIGURACIÓN   │                                          │
│  CAMPOS PLANO    ├──────────────────────────────────────────┤
│  FILTROS         │  LOG DE PROCESO                          │
│  SIMBOLOGÍA      │                                          │
│  CAJETÍN         │                                          │
│  GENERACIÓN      │                                          │
└──────────────────┴──────────────────────────────────────────┘
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from .estilos import (
    COLOR_FONDO_APP, COLOR_ACENTO, COLOR_TEXTO_GRIS, COLOR_PANEL, COLOR_TEXTO,
    FONT_BOLD, FONT_MONO, FONT_SMALL,
    aplicar_estilos,
)
from .panel_capas import PanelCapas
from .panel_config import PanelConfig
from .panel_campos import PanelCampos
from .panel_filtros import PanelFiltros
from .panel_simbologia import PanelSimbologia
from .panel_cajetin import PanelCajetin
from .panel_generacion import PanelGeneracion
from ..motor.generador import GeneradorPlanos
from ..motor.proyecto import Proyecto


class App(tk.Tk):
    """Ventana principal de la aplicación."""

    def __init__(self):
        super().__init__()
        self.title("Generador de Planos Forestales - Jose Caballero Sánchez (Cazorla) - Open Source")
        self.geometry("1100x780")
        self.minsize(1100, 780)
        self.configure(bg=COLOR_FONDO_APP)
        self.resizable(True, True)

        self.motor = GeneradorPlanos()

        aplicar_estilos(self)
        self._construir_ui()

    def _construir_ui(self):
        # ── Barra superior ──
        self._barra_superior()

        # ── Contenedor principal ──
        main = tk.Frame(self, bg=COLOR_FONDO_APP)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Columna izquierda (controles) con scroll
        izq_container = tk.Frame(main, bg=COLOR_FONDO_APP)
        izq_container.pack(side="left", fill="y", padx=(0, 8), pady=4)

        izq_canvas = tk.Canvas(izq_container, bg=COLOR_FONDO_APP,
                                highlightthickness=0, width=280)
        izq_scrollbar = ttk.Scrollbar(izq_container, orient="vertical",
                                       command=izq_canvas.yview)

        izq = tk.Frame(izq_canvas, bg="#242D40", bd=0)
        izq.bind("<Configure>",
                 lambda e: izq_canvas.configure(scrollregion=izq_canvas.bbox("all")))
        izq_canvas.create_window((0, 0), window=izq, anchor="nw")
        izq_canvas.configure(yscrollcommand=izq_scrollbar.set)

        izq_canvas.pack(side="left", fill="both", expand=True)
        izq_scrollbar.pack(side="right", fill="y")

        # Columna derecha (tabla + log)
        der = tk.Frame(main, bg=COLOR_FONDO_APP)
        der.pack(side="right", fill="both", expand=True, pady=4)

        # ── Paneles izquierda ──
        self.panel_capas = PanelCapas(
            izq, self.motor,
            callback_log=self._escribir_log,
            callback_tabla=self._on_tabla_cargada,
        )
        self.panel_config = PanelConfig(izq)
        self.panel_campos = PanelCampos(izq)
        self.panel_filtros = PanelFiltros(
            izq, self.motor,
            callback_filtro=self._on_filtro_aplicado,
        )
        self.panel_simbologia = PanelSimbologia(
            izq, self.motor,
            callback_log=self._escribir_log,
        )
        self.panel_cajetin = PanelCajetin(
            izq, self.motor,
            callback_log=self._escribir_log,
        )
        self.panel_generacion = PanelGeneracion(
            izq, self.motor,
            get_config=self._get_config,
            callback_log=self._escribir_log,
            auto_aplicar=self._auto_aplicar_todo,
        )

        # ── Paneles derecha: Notebook con pestañas + log ──
        self._crear_notebook(der)
        self._crear_panel_log(der)

    def _barra_superior(self):
        barra = tk.Frame(self, bg="#141B2D", height=58)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        tk.Label(
            barra, text="\U0001f5fa  GENERADOR DE PLANOS FORESTALES",
            font=("Helvetica", 14, "bold"), bg="#141B2D", fg=COLOR_ACENTO,
        ).pack(side="left", padx=16, pady=10)

        tk.Label(
            barra,
            text="App creada por Jose Caballero Sánchez (Cazorla) · Open Source · Uso gratuito",
            font=("Helvetica", 8), bg="#141B2D", fg="#7F8C8D",
        ).pack(side="left", padx=(0, 8), pady=10)

        # Botones de proyecto en la barra
        btn_f = tk.Frame(barra, bg="#141B2D")
        btn_f.pack(side="right", padx=8)

        tk.Button(btn_f, text="Guardar proyecto", command=self._guardar_proyecto,
                  font=("Helvetica", 9), bg="#2C3E50", fg="#ECF0F1",
                  relief="flat", cursor="hand2", padx=6).pack(side="left", padx=2)
        tk.Button(btn_f, text="Cargar proyecto", command=self._cargar_proyecto,
                  font=("Helvetica", 9), bg="#2C3E50", fg="#ECF0F1",
                  relief="flat", cursor="hand2", padx=6).pack(side="left", padx=2)

        tk.Label(
            barra, text="ETRS89 \u00b7 UTM H30N",
            font=("Helvetica", 9), bg="#141B2D", fg=COLOR_TEXTO_GRIS,
        ).pack(side="right", padx=16)

    def _crear_notebook(self, parent):
        """Crea el Notebook central con pestañas: Infraestructuras, Mapa General."""
        self._notebook = ttk.Notebook(parent)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        # ── Pestaña 1: Tabla de infraestructuras ──
        tab_tabla = tk.Frame(self._notebook, bg=COLOR_FONDO_APP)
        self._notebook.add(tab_tabla, text=" 📋 Infraestructuras ")
        self._crear_panel_tabla_en(tab_tabla)

        # ── Pestaña 2: Mapa General ──
        tab_mapa = tk.Frame(self._notebook, bg="#0D1117")
        self._notebook.add(tab_mapa, text=" 🗺 Mapa General ")
        self._crear_panel_mapa_general(tab_mapa)

    def _crear_panel_tabla_en(self, parent):
        """Crea la tabla de infraestructuras dentro de un frame."""
        self._tabla_frame = parent
        cols = ["#"]
        self._tabla = ttk.Treeview(parent, columns=cols, show="headings",
                                    selectmode="extended")
        self._tabla.heading("#", text="#")
        self._tabla.column("#", width=60, minwidth=40)

        sb_v = ttk.Scrollbar(parent, orient="vertical", command=self._tabla.yview)
        sb_h = ttk.Scrollbar(parent, orient="horizontal", command=self._tabla.xview)
        self._tabla.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        sb_h.pack(side="bottom", fill="x")
        sb_v.pack(side="right", fill="y")
        self._tabla.pack(side="left", fill="both", expand=True)

    def _reconfigurar_tabla(self, columnas: list):
        """Reconfigura las columnas de la tabla con las columnas reales del shapefile."""
        cols = ["#"] + columnas
        self._tabla.configure(columns=cols)
        for col in cols:
            ancho = 50 if col == "#" else 120
            self._tabla.heading(col, text=col)
            self._tabla.column(col, width=ancho, minwidth=40)

    # ── Mapa General (pestaña 2) ─────────────────────────────────────────

    def _crear_panel_mapa_general(self, parent):
        """Vista previa del mapa general con todas las capas cargadas."""
        from ..motor.cartografia import CAPAS_BASE

        # ── Barra superior: actualizar + proveedor + buscar ──
        toolbar = tk.Frame(parent, bg=COLOR_PANEL, height=32)
        toolbar.pack(fill="x", padx=2, pady=(2, 0))
        toolbar.pack_propagate(False)

        tk.Button(toolbar, text="🔄", command=self._actualizar_mapa_general,
                  font=("Helvetica", 10), bg="#2C3E50", fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left", padx=2, pady=2)

        # Selector de proveedor de fondo
        tk.Label(toolbar, text="Fondo:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(side="left", padx=(4, 2))
        self._mapa_proveedor = ttk.Combobox(
            toolbar, values=list(CAPAS_BASE.keys()), width=18,
            state="readonly", font=("Helvetica", 8))
        self._mapa_proveedor.set(self.panel_config.proveedor.get())
        self._mapa_proveedor.pack(side="left", padx=2, pady=2)
        self._mapa_proveedor.bind("<<ComboboxSelected>>",
                                   lambda _: self._actualizar_mapa_general())

        # Buscador de infraestructura
        tk.Label(toolbar, text="Buscar:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(side="left", padx=(8, 2))
        self._mapa_buscar = tk.Entry(toolbar, width=18, font=("Helvetica", 8),
                                      bg="#1A2636", fg=COLOR_TEXTO,
                                      insertbackground=COLOR_TEXTO, relief="flat")
        self._mapa_buscar.pack(side="left", padx=2, pady=2)
        self._mapa_buscar.bind("<Return>", lambda _: self._buscar_infraestructura())
        tk.Button(toolbar, text="Ir", command=self._buscar_infraestructura,
                  font=("Helvetica", 8), bg="#2C3E50", fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left", padx=1, pady=2)

        # Info
        self._lbl_mapa_info = tk.Label(toolbar, text="Carga capas para ver el mapa",
                                        font=("Helvetica", 7), bg=COLOR_PANEL,
                                        fg=COLOR_TEXTO_GRIS)
        self._lbl_mapa_info.pack(side="right", padx=4)

        # ── Panel lateral: filtro por categoría ──
        self._mapa_body = tk.Frame(parent, bg="#0D1117")
        self._mapa_body.pack(fill="both", expand=True, padx=2, pady=2)

        self._filtro_frame = tk.Frame(self._mapa_body, bg=COLOR_PANEL, width=140)
        self._filtro_frame.pack(side="right", fill="y", padx=(2, 0))
        self._filtro_frame.pack_propagate(False)
        tk.Label(self._filtro_frame, text="Filtro categorías",
                 font=("Helvetica", 8, "bold"), bg=COLOR_PANEL,
                 fg=COLOR_ACENTO).pack(anchor="w", padx=4, pady=(4, 2))
        self._filtro_scroll = tk.Frame(self._filtro_frame, bg=COLOR_PANEL)
        self._filtro_scroll.pack(fill="both", expand=True, padx=2)
        self._filtro_vars = {}  # {valor: BooleanVar}

        # Canvas matplotlib
        self._mapa_frame = tk.Frame(self._mapa_body, bg="#0D1117")
        self._mapa_frame.pack(side="left", fill="both", expand=True)
        self._mapa_canvas = None
        self._mapa_fig = None
        self._mapa_toolbar = None
        self._mapa_click_cid = None
        self._mapa_move_cid = None
        self._marcador_sel = None
        self._mapa_tooltip = None
        self._mapa_artists_cat = {}  # {valor: [artists]}

        # Panel inferior: coordenadas + info de infraestructura clicada
        bottom = tk.Frame(parent, bg="#0D1117")
        bottom.pack(fill="x", padx=2, pady=(0, 2))
        self._lbl_coords = tk.Label(bottom, text="X: — Y: —",
                                     font=FONT_MONO, bg="#0D1117",
                                     fg=COLOR_TEXTO_GRIS, anchor="w")
        self._lbl_coords.pack(side="left", padx=4)
        self._info_frame = tk.Frame(bottom, bg="#0D1117")
        self._info_frame.pack(fill="x", expand=True)
        self._info_tabla = None

    def _actualizar_filtros_categoria(self):
        """Reconstruye los checkboxes de filtro por categoría."""
        for w in self._filtro_scroll.winfo_children():
            w.destroy()
        self._filtro_vars.clear()

        gdf = self.motor.gdf_infra
        if gdf is None:
            return

        ci = self.motor.config_infra
        campo_cat = ci.get("campo_categoria")
        if not campo_cat or campo_cat not in gdf.columns:
            tk.Label(self._filtro_scroll, text="Sin categoría",
                     font=("Helvetica", 7), bg=COLOR_PANEL,
                     fg=COLOR_TEXTO_GRIS).pack(anchor="w", padx=2)
            return

        campo_real = campo_cat
        mapeo = self.motor._campo_mapeo
        if mapeo and campo_cat in mapeo:
            campo_real = mapeo[campo_cat]

        valores = sorted(gdf[campo_real].astype(str).unique())
        for valor in valores:
            simb = self.motor.gestor_simbologia.obtener_simbologia_infra(
                campo_cat, valor)
            var = tk.BooleanVar(value=True)
            self._filtro_vars[valor] = var
            f = tk.Frame(self._filtro_scroll, bg=COLOR_PANEL)
            f.pack(fill="x", pady=1)
            # Color indicator
            ind = tk.Canvas(f, width=12, height=12, bg=COLOR_PANEL,
                            highlightthickness=0)
            ind.pack(side="left", padx=(2, 4))
            ind.create_rectangle(1, 1, 11, 11, fill=simb.color, outline="white",
                                  width=0.5)
            cb = tk.Checkbutton(
                f, text=str(valor)[:18], variable=var,
                font=("Helvetica", 7), bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor="#1A2636", activebackground=COLOR_PANEL,
                activeforeground=COLOR_TEXTO, anchor="w",
                command=self._aplicar_filtro_categoria)
            cb.pack(side="left", fill="x")

        # Botones todo/nada
        bf = tk.Frame(self._filtro_scroll, bg=COLOR_PANEL)
        bf.pack(fill="x", pady=(4, 0))
        tk.Button(bf, text="Todo", font=("Helvetica", 7),
                  bg="#2C3E50", fg=COLOR_TEXTO, relief="flat",
                  command=lambda: self._set_all_filtros(True)).pack(side="left", padx=2)
        tk.Button(bf, text="Nada", font=("Helvetica", 7),
                  bg="#2C3E50", fg=COLOR_TEXTO, relief="flat",
                  command=lambda: self._set_all_filtros(False)).pack(side="left", padx=2)

    def _set_all_filtros(self, estado: bool):
        for var in self._filtro_vars.values():
            var.set(estado)
        self._aplicar_filtro_categoria()

    def _aplicar_filtro_categoria(self):
        """Muestra/oculta artistas del mapa según checkboxes."""
        for valor, artists in self._mapa_artists_cat.items():
            visible = self._filtro_vars.get(valor, tk.BooleanVar(value=True)).get()
            for a in artists:
                a.set_visible(visible)
        if self._mapa_canvas:
            self._mapa_canvas.draw_idle()

    def _actualizar_mapa_general(self):
        """Redibuja el mapa general con capas base + vectoriales + interactividad."""
        gdf = self.motor.gdf_infra
        if gdf is None:
            self._lbl_mapa_info.configure(text="No hay infraestructuras cargadas")
            return

        # Limpiar canvas, toolbar y panel info anteriores
        if self._mapa_toolbar is not None:
            self._mapa_toolbar.destroy()
            self._mapa_toolbar = None
        if self._mapa_canvas is not None:
            self._mapa_canvas.get_tk_widget().destroy()
        if self._mapa_fig is not None:
            plt.close(self._mapa_fig)
        if self._info_tabla is not None:
            self._info_tabla.destroy()
            self._info_tabla = None
        self._mapa_artists_cat.clear()
        self._marcador_sel = None

        fig, ax = plt.subplots(1, 1, figsize=(8, 5), dpi=96)
        fig.patch.set_facecolor("#0D1117")
        ax.set_facecolor("#E8E8E0")
        self._mapa_fig = fig
        self._mapa_ax = ax

        # ── Extensión del mapa basada en todas las infraestructuras ──
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        pad_x = (bounds[2] - bounds[0]) * 0.15 or 1000
        pad_y = (bounds[3] - bounds[1]) * 0.15 or 1000
        xmin, xmax = bounds[0] - pad_x, bounds[2] + pad_x
        ymin, ymax = bounds[1] - pad_y, bounds[3] + pad_y
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

        # ── Fondo cartográfico (proveedor del selector del mapa) ──
        proveedor = self._mapa_proveedor.get()
        try:
            from ..motor.cartografia import añadir_fondo_cartografico
            añadir_fondo_cartografico(ax, gdf, proveedor,
                                       xmin=xmin, xmax=xmax,
                                       ymin=ymin, ymax=ymax)
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
        except Exception:
            pass

        # ── Montes ──
        if self.motor.gdf_montes is not None:
            montes_clip = self.motor.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_clip.empty:
                trans = self.panel_capas.transparencia.get()
                montes_clip.plot(ax=ax, facecolor="#22992244",
                                 edgecolor="#1a5c10", linewidth=0.5,
                                 alpha=trans, zorder=1)

        # ── Capas extra (con simbología) ──
        self.motor.gestor_capas.dibujar_en_mapa(
            ax, xmin, xmax, ymin, ymax, self.motor.gestor_simbologia)

        # ── Infraestructuras (guardando artistas por categoría para filtro) ──
        ci = self.motor.config_infra
        campo_cat = ci.get("campo_categoria")
        lw = ci.get("linewidth", 2.5)
        alpha_infra = ci.get("alpha", 0.65)
        color_infra = "#E74C3C"

        if campo_cat and campo_cat in gdf.columns:
            campo_real = campo_cat
            mapeo = self.motor._campo_mapeo
            if mapeo and campo_cat in mapeo:
                campo_real = mapeo[campo_cat]
            valores = sorted(gdf[campo_real].astype(str).unique())
            for valor in valores:
                simb = self.motor.gestor_simbologia.obtener_simbologia_infra(
                    campo_cat, valor)
                mask = gdf[campo_real].astype(str) == valor
                gdf_cat = gdf[mask]
                if not gdf_cat.empty:
                    n_before = len(ax.collections) + len(ax.lines) + len(ax.patches)
                    gdf_cat.plot(ax=ax, color=simb.color, linewidth=lw,
                                 linestyle=simb.linestyle,
                                 label=str(valor)[:20], alpha=alpha_infra,
                                 zorder=5)
                    # Capturar artistas nuevos
                    all_artists = list(ax.collections) + list(ax.lines) + list(ax.patches)
                    self._mapa_artists_cat[valor] = all_artists[n_before:]
        else:
            gdf.plot(ax=ax, color=color_infra, linewidth=lw,
                     label="Infraestructuras", alpha=alpha_infra, zorder=5)

        ax.legend(loc="upper right", fontsize=6, framealpha=0.85,
                  facecolor="white", edgecolor="#BDC3C7", labelcolor="#333")

        # Estilo
        ax.tick_params(colors="#555", labelsize=6)
        for sp in ax.spines.values():
            sp.set_color("#2C3E50")

        fig.tight_layout(pad=0.5)

        # ── Canvas + toolbar de navegación (zoom, pan, home) ──
        self._mapa_canvas = FigureCanvasTkAgg(fig, master=self._mapa_frame)
        self._mapa_canvas.draw()

        self._mapa_toolbar = NavigationToolbar2Tk(
            self._mapa_canvas, self._mapa_frame)
        self._mapa_toolbar.configure(bg=COLOR_PANEL)
        self._mapa_toolbar.update()
        self._mapa_toolbar.pack(side="bottom", fill="x")
        self._mapa_canvas.get_tk_widget().pack(fill="both", expand=True)

        # ── Tooltip para hover ──
        self._mapa_tooltip = ax.annotate(
            "", xy=(0, 0), xytext=(12, 12),
            textcoords="offset points", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.3", fc="#1C2333", ec=COLOR_ACENTO,
                      alpha=0.92, linewidth=0.6),
            color=COLOR_TEXTO, zorder=20, visible=False)

        # ── Eventos: clic + movimiento ──
        self._mapa_click_cid = fig.canvas.mpl_connect(
            "button_press_event", self._on_mapa_click)
        self._mapa_move_cid = fig.canvas.mpl_connect(
            "motion_notify_event", self._on_mapa_move)

        # ── Filtros categoría ──
        self._actualizar_filtros_categoria()

        n_infra = len(gdf)
        n_capas = len(self.motor.gestor_capas.capas)
        montes = "Sí" if self.motor.gdf_montes is not None else "No"
        self._lbl_mapa_info.configure(
            text=f"{n_infra} infra · {n_capas} capas · Montes: {montes}")

    def _on_mapa_move(self, event):
        """Actualiza coordenadas y tooltip al mover el ratón."""
        if event.inaxes is None or event.xdata is None:
            self._lbl_coords.configure(text="X: — Y: —")
            if self._mapa_tooltip:
                self._mapa_tooltip.set_visible(False)
                self._mapa_canvas.draw_idle()
            return

        # Coordenadas en tiempo real
        self._lbl_coords.configure(
            text=f"X: {event.xdata:.1f}  Y: {event.ydata:.1f}")

        # Tooltip: solo si no estamos en modo zoom/pan
        if self._mapa_toolbar and self._mapa_toolbar.mode:
            return

        gdf = self.motor.gdf_infra
        if gdf is None:
            return

        from shapely.geometry import Point
        pt = Point(event.xdata, event.ydata)
        distancias = gdf.geometry.distance(pt)
        idx = distancias.idxmin()
        dist = distancias[idx]

        ax = self._mapa_ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        umbral = max(xlim[1] - xlim[0], ylim[1] - ylim[0]) * 0.03

        if dist <= umbral:
            row = gdf.loc[idx]
            # Buscar un campo útil para mostrar
            columnas = [c for c in gdf.columns if c != "geometry"]
            nombre = ""
            for campo_nombre in ["Nombre_Infra", "NOMBRE_INF", "COD_INF_1",
                                  "OBJECTID", "nombre", "cod", "Name"]:
                if campo_nombre in columnas:
                    nombre = str(row.get(campo_nombre, ""))
                    if nombre and nombre != "nan":
                        break
            if not nombre or nombre == "nan":
                nombre = str(row.get(columnas[0], "")) if columnas else ""
            # Segundo campo de contexto
            cod = ""
            for campo_cod in ["COD_INF_1", "OBJECTID", "COD_INF"]:
                if campo_cod in columnas and campo_cod not in (nombre,):
                    cod = str(row.get(campo_cod, ""))
                    if cod and cod != "nan":
                        break
            texto = nombre[:30]
            if cod and cod != "nan" and cod != nombre:
                texto += f"\n{cod}"

            self._mapa_tooltip.xy = (event.xdata, event.ydata)
            self._mapa_tooltip.set_text(texto)
            self._mapa_tooltip.set_visible(True)
        else:
            self._mapa_tooltip.set_visible(False)

        self._mapa_canvas.draw_idle()

    def _on_mapa_click(self, event):
        """Al hacer clic en el mapa, busca la infraestructura más cercana y muestra sus datos."""
        if event.inaxes is None or event.xdata is None:
            return
        if self._mapa_toolbar and self._mapa_toolbar.mode:
            return

        gdf = self.motor.gdf_infra
        if gdf is None:
            return

        from shapely.geometry import Point
        click_pt = Point(event.xdata, event.ydata)
        distancias = gdf.geometry.distance(click_pt)
        idx_min = distancias.idxmin()
        dist_min = distancias[idx_min]

        ax = self._mapa_ax
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        umbral = max(xlim[1] - xlim[0], ylim[1] - ylim[0]) * 0.05
        if dist_min > umbral:
            return

        row = gdf.loc[idx_min]
        columnas = [c for c in gdf.columns if c != "geometry"]

        # Crear tabla de info
        if self._info_tabla is not None:
            self._info_tabla.destroy()

        info_lf = tk.LabelFrame(
            self._info_frame,
            text=f" Infraestructura #{idx_min + 1} ",
            font=FONT_BOLD, bg="#0D1117", fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        info_lf.pack(fill="x", padx=2, pady=2)
        self._info_tabla = info_lf

        tree = ttk.Treeview(info_lf, columns=columnas, show="headings",
                             height=2, selectmode="browse")
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, width=100, minwidth=40)

        vals = []
        for col in columnas:
            v = str(row.get(col, "—"))
            if v == "nan":
                v = "—"
            vals.append(v)
        tree.insert("", "end", values=vals, tags=("sel",))
        tree.tag_configure("sel", background="#1E3A5F")

        sb_h = ttk.Scrollbar(info_lf, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=sb_h.set)
        sb_h.pack(side="bottom", fill="x")
        tree.pack(fill="x", expand=True)

        # Resaltar la infraestructura seleccionada
        geom = row.geometry
        if geom is not None:
            cx, cy = geom.centroid.x, geom.centroid.y
            if self._marcador_sel:
                for m in self._marcador_sel:
                    m.remove()
            self._marcador_sel = ax.plot(
                cx, cy, "o", color="#FFFF00", markersize=12,
                markeredgecolor="#E74C3C", markeredgewidth=2,
                zorder=10, alpha=0.9)
            self._mapa_canvas.draw_idle()

    def _buscar_infraestructura(self):
        """Busca infraestructura por texto y hace zoom a ella."""
        texto = self._mapa_buscar.get().strip()
        if not texto:
            return
        gdf = self.motor.gdf_infra
        if gdf is None:
            return

        columnas = [c for c in gdf.columns if c != "geometry"]
        texto_lower = texto.lower()

        # Buscar en todas las columnas de texto
        encontrado = None
        for _, row in gdf.iterrows():
            for col in columnas:
                val = str(row.get(col, "")).lower()
                if texto_lower in val:
                    encontrado = row
                    break
            if encontrado is not None:
                break

        if encontrado is None:
            self._lbl_mapa_info.configure(text=f"No encontrado: '{texto}'")
            return

        geom = encontrado.geometry
        if geom is None:
            return

        # Hacer zoom a la infraestructura
        ax = self._mapa_ax
        cx, cy = geom.centroid.x, geom.centroid.y
        # Ventana de 2km alrededor
        semi = 1000
        ax.set_xlim(cx - semi, cx + semi)
        ax.set_ylim(cy - semi, cy + semi)

        # Marcar
        if self._marcador_sel:
            for m in self._marcador_sel:
                m.remove()
        self._marcador_sel = ax.plot(
            cx, cy, "o", color="#FFFF00", markersize=14,
            markeredgecolor="#E74C3C", markeredgewidth=2.5,
            zorder=10, alpha=0.9)

        self._mapa_canvas.draw_idle()

        # Mostrar nombre encontrado
        nombre = ""
        for col in columnas:
            val = str(encontrado.get(col, ""))
            if texto_lower in val.lower():
                nombre = val
                break
        self._lbl_mapa_info.configure(text=f"Encontrado: {nombre[:50]}")

    def _crear_panel_log(self, parent):
        lf = tk.LabelFrame(
            parent, text=" LOG DE PROCESO ",
            font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        lf.pack(fill="x", padx=4, pady=(0, 4))

        self._log = tk.Text(
            lf, height=7, font=FONT_MONO,
            bg="#0D1117", fg="#58D68D",
            insertbackground="white", relief="flat", state="disabled",
        )
        sb = ttk.Scrollbar(lf, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        self._log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Tags de color
        self._log.tag_config("error", foreground="#E74C3C")
        self._log.tag_config("ok", foreground="#2ECC71")
        self._log.tag_config("warn", foreground="#F39C12")
        self._log.tag_config("info", foreground="#85C1E9")

        self._escribir_log("Sistema iniciado. Carga un shapefile para comenzar.", "info")

    def _escribir_log(self, msg: str, tipo: str = ""):
        def _do():
            self._log.configure(state="normal")
            tag = tipo if tipo else ""
            self._log.insert("end", msg + "\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _poblar_tabla(self, indices=None):
        gdf = self.motor.gdf_infra
        if gdf is None:
            return
        for item in self._tabla.get_children():
            self._tabla.delete(item)

        # Columnas reales del shapefile (sin geometry)
        columnas = [c for c in gdf.columns if c != "geometry"]

        if indices is None:
            indices = range(len(gdf))

        for i in indices:
            row = gdf.iloc[i]
            vals = [i + 1]
            for col in columnas:
                v = str(row.get(col, "\u2014"))
                if v == "nan":
                    v = "\u2014"
                vals.append(v)
            tag = "par" if i % 2 == 0 else "impar"
            self._tabla.insert("", "end", values=vals, tags=(tag,))

        self._tabla.tag_configure("par", background="#1E2A3A")
        self._tabla.tag_configure("impar", background="#172030")
        n = len(list(indices)) if not isinstance(indices, range) else len(indices)
        self._escribir_log(f"Tabla actualizada: {n} infraestructuras.", "info")

    def _on_tabla_cargada(self):
        # Obtener columnas reales y reconfigurar tabla
        columnas = self.motor.obtener_columnas_shapefile()
        self._reconfigurar_tabla(columnas)
        self._poblar_tabla()
        self.panel_generacion.actualizar_campos_agrupacion()
        self.panel_generacion.actualizar_valores_si_agrupado()
        self.panel_filtros.actualizar_campos()
        self.panel_simbologia.actualizar_capas_extra()
        self.panel_simbologia.actualizar_campo_categoria()
        # Actualizar checkboxes de campos con las columnas reales del shapefile
        self.panel_campos.actualizar_campos(columnas)
        self.panel_cajetin.actualizar_campos_subtitulo(columnas)
        # Actualizar mapa de previsualización
        self._actualizar_mapa_general()

    def _on_filtro_aplicado(self, indices: list):
        self._poblar_tabla(indices)

    def _auto_aplicar_todo(self):
        """Aplica cajetín, plantilla y simbología al motor antes de generar."""
        cajetin = self.panel_cajetin.obtener_cajetin()
        plantilla = self.panel_cajetin.obtener_plantilla()
        self.motor.set_cajetin(cajetin)
        self.motor.set_plantilla(plantilla)
        self.motor.config_infra = self.panel_simbologia.obtener_config_infra()
        self.panel_simbologia._aplicar()

    def _get_config(self) -> dict:
        return {
            "formato": self.panel_config.formato.get(),
            "proveedor": self.panel_config.proveedor.get(),
            "transparencia": self.panel_capas.transparencia.get(),
            "campos": self.panel_campos.obtener_campos_activos(),
            "campo_encabezado": self.panel_campos.obtener_campo_encabezado(),
            "color_infra": self.panel_config.color_infra,
            "salida": self.panel_config.salida.get(),
            "escala_manual": self.panel_config.escala_manual,
            "tabla": self._tabla,
        }

    # ── Guardar/Cargar proyecto ──────────────────────────────────────────

    def _guardar_proyecto(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar proyecto",
            defaultextension=".json",
            filetypes=[("Proyecto JSON", "*.json")],
        )
        if not ruta:
            return

        p = Proyecto()
        p.nombre = os.path.splitext(os.path.basename(ruta))[0]
        p.formato = self.panel_config.formato.get()
        p.proveedor = self.panel_config.proveedor.get()
        p.escala_manual = self.panel_config.escala_manual
        p.transparencia_montes = self.panel_capas.transparencia.get()
        p.color_infra = self.panel_config.color_infra
        p.campos_visibles = self.panel_campos.obtener_campos_activos()
        p.carpeta_salida = self.panel_config.salida.get()
        p.cajetin = self.panel_cajetin.obtener_cajetin()
        p.plantilla = self.panel_cajetin.obtener_plantilla()
        p.simbologia = self.motor.gestor_simbologia.to_dict()
        p.capas_extra = self.motor.gestor_capas.to_dict()

        try:
            p.guardar(ruta)
            self._escribir_log(f"Proyecto guardado: {ruta}", "ok")
        except Exception as e:
            self._escribir_log(f"Error al guardar proyecto: {e}", "error")
            messagebox.showerror("Error", str(e))

    def _cargar_proyecto(self):
        ruta = filedialog.askopenfilename(
            title="Cargar proyecto",
            filetypes=[("Proyecto JSON", "*.json")],
        )
        if not ruta:
            return

        try:
            p = Proyecto.cargar(ruta)
            self.panel_config.formato.set(p.formato)
            self.panel_config.proveedor.set(p.proveedor)
            self.panel_capas.transparencia.set(p.transparencia_montes)
            self.panel_config.salida.set(p.carpeta_salida)
            self.panel_cajetin.cargar_desde_proyecto(p.cajetin, p.plantilla)

            # Aplicar cajetín y plantilla al motor
            self.motor.set_cajetin(p.cajetin)
            self.motor.set_plantilla(p.plantilla)

            # Simbología
            if p.simbologia:
                from ..motor.simbologia import GestorSimbologia
                self.motor.gestor_simbologia = GestorSimbologia.from_dict(p.simbologia)

            self._escribir_log(f"Proyecto cargado: {p.nombre}", "ok")
        except Exception as e:
            self._escribir_log(f"Error al cargar proyecto: {e}", "error")
            messagebox.showerror("Error", str(e))
