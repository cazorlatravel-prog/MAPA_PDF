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

from .estilos import (
    COLOR_FONDO_APP, COLOR_ACENTO, COLOR_TEXTO_GRIS,
    FONT_BOLD, FONT_MONO,
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

        # ── Paneles derecha ──
        self._crear_panel_tabla(der)
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

    def _crear_panel_tabla(self, parent):
        lf = tk.LabelFrame(
            parent, text=" INFRAESTRUCTURAS CARGADAS ",
            font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        lf.pack(fill="both", expand=True, padx=4, pady=(4, 4))

        # Tabla con columna placeholder; se reconfigura al cargar shapefile
        self._tabla_frame = lf
        cols = ["#"]
        self._tabla = ttk.Treeview(lf, columns=cols, show="headings",
                                    selectmode="extended")
        self._tabla.heading("#", text="#")
        self._tabla.column("#", width=60, minwidth=40)

        sb_v = ttk.Scrollbar(lf, orient="vertical", command=self._tabla.yview)
        sb_h = ttk.Scrollbar(lf, orient="horizontal", command=self._tabla.xview)
        self._tabla.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        self._tabla.pack(side="left", fill="both", expand=True)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")

    def _reconfigurar_tabla(self, columnas: list):
        """Reconfigura las columnas de la tabla con las columnas reales del shapefile."""
        cols = ["#"] + columnas
        self._tabla.configure(columns=cols)
        for col in cols:
            ancho = 50 if col == "#" else 120
            self._tabla.heading(col, text=col)
            self._tabla.column(col, width=ancho, minwidth=40)

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
        # Actualizar checkboxes de campos con las columnas reales del shapefile
        self.panel_campos.actualizar_campos(columnas)
        self.panel_cajetin.actualizar_campos_subtitulo(columnas)

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
