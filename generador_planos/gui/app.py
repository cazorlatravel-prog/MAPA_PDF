"""
Ventana principal de la aplicación Generador de Planos Forestales.

Layout: 1100x780 px mínimo, redimensionable.
┌─────────────────────────────────────────────────────────────┐
│  GENERADOR DE PLANOS FORESTALES            ETRS89·UTM H30N  │
├──────────────────┬──────────────────────────────────────────┤
│  CAPAS           │  TABLA DE INFRAESTRUCTURAS               │
│  FILTROS         │                                          │
│  SIMBOLOGÍA      ├──────────────────────────────────────────┤
│  CAMPOS PLANO    │  LOG DE PROCESO                          │
│  CAJETÍN         │                                          │
│  CONFIGURACIÓN   │                                          │
│  GENERACIÓN      │                                          │
└──────────────────┴──────────────────────────────────────────┘
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
        self.title("Generador de Planos Forestales - \u00a9 Jose Caballero S\u00e1nchez (Cazorla 2026)")
        self.geometry("1100x780")
        self.minsize(1100, 780)
        self.configure(bg=COLOR_FONDO_APP)
        self.resizable(True, True)

        self.motor = GeneradorPlanos()
        self._ultimo_dir_proyecto = os.path.expanduser("~")

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

        # ── Paneles izquierda (orden de flujo de trabajo) ──

        # 1. Carga de datos
        self.panel_capas = PanelCapas(
            izq, self.motor,
            callback_log=self._escribir_log,
            callback_tabla=self._on_tabla_cargada,
            callback_montes_cargados=self._on_montes_cargados,
        )

        # 2. Filtrado de datos
        self.panel_filtros = PanelFiltros(
            izq, self.motor,
            callback_filtro=self._on_filtro_aplicado,
        )

        # 3. Estilo visual
        self.panel_simbologia = PanelSimbologia(
            izq, self.motor,
            callback_log=self._escribir_log,
        )

        # 4. Campos a mostrar en el plano
        self.panel_campos = PanelCampos(izq)

        # 5. Cajetín y plantilla
        self.panel_cajetin = PanelCajetin(
            izq, self.motor,
            callback_log=self._escribir_log,
        )

        # 6. Configuración de salida
        self.panel_config = PanelConfig(izq)

        # 7. Generación final
        self.panel_generacion = PanelGeneracion(
            izq, self.motor,
            get_config=self._get_config,
            callback_log=self._escribir_log,
            auto_aplicar=self._auto_aplicar_todo,
        )

        # ── Panel derecho: tabla + log ──
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
            text="\u00a9 Jose Caballero S\u00e1nchez (Cazorla 2026) \u00b7 Todos los derechos reservados",
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
        """Crea la tabla de infraestructuras directamente en el panel derecho."""
        lf = tk.LabelFrame(
            parent, text=" INFRAESTRUCTURAS ",
            font=FONT_BOLD, bg=COLOR_FONDO_APP, fg=COLOR_ACENTO,
            bd=1, relief="solid",
        )
        lf.pack(fill="both", expand=True, padx=4, pady=(4, 4))
        self._tabla_frame = lf
        cols = ["#"]
        self._tabla = ttk.Treeview(lf, columns=cols, show="headings",
                                    selectmode="extended")
        self._tabla.heading("#", text="#")
        self._tabla.column("#", width=60, minwidth=40)

        sb_v = ttk.Scrollbar(lf, orient="vertical", command=self._tabla.yview)
        sb_h = ttk.Scrollbar(lf, orient="horizontal", command=self._tabla.xview)
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
        self._log.tag_config("ok", foreground="#007932")
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

        # Borrar todo de golpe (más rápido que uno a uno)
        children = self._tabla.get_children()
        if children:
            self._tabla.delete(*children)

        # Configurar tags UNA VEZ antes del bucle
        self._tabla.tag_configure("par", background="#1E2A3A")
        self._tabla.tag_configure("impar", background="#172030")

        # Columnas reales del shapefile (sin geometry)
        columnas = [c for c in gdf.columns if c != "geometry"]

        if indices is None:
            indices = range(len(gdf))

        for i in indices:
            row = gdf.iloc[i]
            vals = [i + 1]
            for col in columnas:
                v = row.get(col)
                vals.append("\u2014" if v is None or str(v) == "nan" else str(v))
            tag = "par" if i % 2 == 0 else "impar"
            self._tabla.insert("", "end", values=vals, tags=(tag,))

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
        self.panel_simbologia.actualizar_campo_categoria_montes()
        # Actualizar checkboxes de campos con las columnas reales del shapefile
        self.panel_campos.actualizar_campos(columnas)
        self.panel_cajetin.actualizar_campos_subtitulo(columnas)
        # Actualizar combo de campo enlace SHP para Excel
        self.panel_config.actualizar_campos_shp_enlace(columnas)

        # Restaurar campos visibles del proyecto si se acaba de cargar uno
        if hasattr(self, "_campos_visibles_proyecto") and self._campos_visibles_proyecto:
            campos_proy = self._campos_visibles_proyecto
            for campo, var in self.panel_campos._check_campos.items():
                var.set(campo in campos_proy)
            self.panel_campos._actualizar_count()
            self._campos_visibles_proyecto = []

    def _on_montes_cargados(self):
        """Actualiza comboboxes de categorización y etiquetas de montes."""
        self.panel_simbologia.actualizar_campo_categoria_montes()
        if self.motor.gdf_montes is not None:
            cols = [c for c in self.motor.gdf_montes.columns
                    if c.lower() != "geometry"]
            self.panel_cajetin.actualizar_campos_montes(cols)

    def _on_filtro_aplicado(self, indices: list):
        self._poblar_tabla(indices)

    def _auto_aplicar_todo(self):
        """Aplica cajetín, plantilla, layout y simbología al motor antes de generar."""
        cajetin = self.panel_cajetin.obtener_cajetin()
        plantilla = self.panel_cajetin.obtener_plantilla()
        self.motor.set_cajetin(cajetin)
        self.motor.set_plantilla(plantilla)
        # Plantilla de layout
        self.motor.layout_key = self.panel_cajetin.obtener_layout_key()
        # Calidad PDF (DPI)
        self.motor.dpi_figura = self.panel_config.dpi_figura
        self.motor.dpi_guardado = self.panel_config.dpi_guardado
        # Primero aplicar simbología (colores de categorías, montes, capas extra)
        self.panel_simbologia._aplicar()
        # Después sobreescribir alpha con el valor del panel Capas (tiene prioridad)
        self.motor.config_infra["alpha"] = self.panel_capas.transparencia_infra.get()
        # Rutas de ráster local
        self.motor.ruta_raster_general = self.panel_config.ruta_raster_general
        self.motor.ruta_raster_localizacion = self.panel_config.ruta_raster_localizacion
        self.motor.ruta_capa_localizacion = self.panel_config.ruta_capa_localizacion
        # WMS/WFS personalizados
        self.motor.wms_custom_general = self.panel_config.wms_custom_general
        self.motor.wfs_custom_general = self.panel_config.wfs_custom_general
        self.motor.wms_custom_localizacion = self.panel_config.wms_custom_localizacion
        self.motor.wfs_custom_localizacion = self.panel_config.wfs_custom_localizacion
        # Escala y proveedor localización
        self.motor.escala_localizacion = self.panel_config.escala_localizacion
        self.motor.prov_localizacion = self.panel_config._prov_localizacion.get()
        # Datos de tabla desde Excel
        if self.panel_config.usa_excel and self.panel_config.ruta_excel:
            try:
                self.motor.cargar_excel_tabla(
                    self.panel_config.ruta_excel,
                    hoja=self.panel_config.hoja_excel or None,
                    campo_enlace_shp=self.panel_config.campo_enlace_shp,
                    campo_enlace_excel=self.panel_config.campo_enlace_excel,
                    columnas_activas=self.panel_config.columnas_excel_activas)
            except Exception as e:
                self._escribir_log(f"Error al cargar Excel: {e}", "error")
                self.motor.limpiar_excel_tabla()
        else:
            self.motor.limpiar_excel_tabla()

    def _get_config(self) -> dict:
        return {
            "formato": self.panel_config.formato.get(),
            "proveedor": self.panel_config.proveedor.get(),
            "ruta_raster_general": self.panel_config.ruta_raster_general,
            "ruta_raster_localizacion": self.panel_config.ruta_raster_localizacion,
            "transparencia": self.panel_capas.transparencia.get(),
            "campos": self.panel_campos.obtener_campos_activos(),
            "campo_encabezado": self.panel_campos.obtener_campo_encabezado(),
            "color_infra": self.panel_config.color_infra,
            "salida": self.panel_config.salida.get(),
            "patron_nombre": self.panel_config.patron_nombre.get(),
            "escala_manual": self.panel_config.escala_manual,
            "tabla": self._tabla,
        }

    # ── Guardar/Cargar proyecto ──────────────────────────────────────────

    def _guardar_proyecto(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar proyecto",
            defaultextension=".json",
            filetypes=[("Proyecto JSON", "*.json")],
            initialdir=self._ultimo_dir_proyecto,
        )
        if not ruta:
            return
        self._ultimo_dir_proyecto = os.path.dirname(ruta)

        p = Proyecto()
        p.nombre = os.path.splitext(os.path.basename(ruta))[0]
        p.formato = self.panel_config.formato.get()
        p.proveedor = self.panel_config.proveedor.get()
        p.ruta_raster_general = self.panel_config.ruta_raster_general
        p.ruta_raster_localizacion = self.panel_config.ruta_raster_localizacion
        p.prov_localizacion = self.panel_config._prov_localizacion.get()
        p.escala_localizacion = self.panel_config.escala_localizacion
        p.ruta_capa_localizacion = self.panel_config.ruta_capa_localizacion
        p.wms_custom_general = self.panel_config.wms_custom_general
        p.wfs_custom_general = self.panel_config.wfs_custom_general
        p.wms_custom_localizacion = self.panel_config.wms_custom_localizacion
        p.wfs_custom_localizacion = self.panel_config.wfs_custom_localizacion
        p.escala_manual = self.panel_config.escala_manual
        p.transparencia_montes = self.panel_capas.transparencia.get()
        p.transparencia_infra = self.panel_capas.transparencia_infra.get()
        p.color_infra = self.panel_config.color_infra
        p.calidad_pdf = self.panel_config.calidad_pdf
        p.campos_visibles = self.panel_campos.obtener_campos_activos()
        p.campo_encabezado = self.panel_campos.obtener_campo_encabezado() or ""
        p.carpeta_salida = self.panel_config.salida.get()
        p.patron_nombre = self.panel_config.patron_nombre.get()
        p.layout_key = self.panel_cajetin.obtener_layout_key()
        p.cajetin = self.panel_cajetin.obtener_cajetin()
        p.plantilla = self.panel_cajetin.obtener_plantilla()
        p.simbologia = self.motor.gestor_simbologia.to_dict()
        p.capas_extra = self.motor.gestor_capas.to_dict()
        # Origen datos tabla
        p.origen_datos_tabla = self.panel_config._origen_datos.get()
        p.ruta_excel_tabla = self.panel_config.ruta_excel
        p.hoja_excel_tabla = self.panel_config.hoja_excel
        p.campo_enlace_shp = self.panel_config.campo_enlace_shp
        p.campo_enlace_excel = self.panel_config.campo_enlace_excel
        p.columnas_excel_activas = self.panel_config.columnas_excel_activas

        # Generación
        p.modo_gen = self.panel_gen._modo_gen.get()
        try:
            p.rango_desde = int(self.panel_gen._rango_desde.get())
        except ValueError:
            p.rango_desde = 1
        try:
            p.rango_hasta = int(self.panel_gen._rango_hasta.get())
        except ValueError:
            p.rango_hasta = 10
        p.campo_agrupacion = self.panel_gen._campo_agrupacion.get()
        p.multipagina = self.panel_gen._multipagina.get()
        p.incluir_portada = self.panel_gen._incluir_portada.get()

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
            initialdir=self._ultimo_dir_proyecto,
        )
        if not ruta:
            return
        self._ultimo_dir_proyecto = os.path.dirname(ruta)

        try:
            p = Proyecto.cargar(ruta)

            # ── Configuración general ──
            self.panel_config.formato.set(p.formato)
            self.panel_config.proveedor.set(p.proveedor)
            # Ráster local
            if p.ruta_raster_general:
                self.panel_config._ruta_raster.set(p.ruta_raster_general)
                self.panel_config._lbl_raster.configure(
                    text=os.path.basename(p.ruta_raster_general))
            if p.ruta_raster_localizacion:
                self.panel_config._ruta_raster_loc.set(p.ruta_raster_localizacion)
                self.panel_config._lbl_raster_loc.configure(
                    text=os.path.basename(p.ruta_raster_localizacion))
            if hasattr(p, "prov_localizacion") and p.prov_localizacion:
                self.panel_config._prov_localizacion.set(p.prov_localizacion)
            # Escala localización
            if hasattr(p, "escala_localizacion") and p.escala_localizacion:
                self.panel_config._escala_localizacion.set(
                    f"{p.escala_localizacion:,}")
            # Capa propia localización
            if hasattr(p, "ruta_capa_localizacion") and p.ruta_capa_localizacion:
                self.panel_config._ruta_capa_loc.set(p.ruta_capa_localizacion)
                self.panel_config._lbl_capa_loc.configure(
                    text=os.path.basename(p.ruta_capa_localizacion))
            # WMS/WFS personalizados mapa general
            if hasattr(p, "wms_custom_general") and p.wms_custom_general:
                self.panel_config._wms_url.set(p.wms_custom_general.get("url", ""))
                self.panel_config._wms_capa.set(p.wms_custom_general.get("capa", ""))
                self.panel_config._wms_formato.set(
                    p.wms_custom_general.get("formato", "image/png"))
            if hasattr(p, "wfs_custom_general") and p.wfs_custom_general:
                self.panel_config._wfs_url.set(p.wfs_custom_general.get("url", ""))
                self.panel_config._wfs_capa.set(p.wfs_custom_general.get("capa", ""))
            # WMS/WFS personalizados localización
            if hasattr(p, "wms_custom_localizacion") and p.wms_custom_localizacion:
                self.panel_config._wms_loc_url.set(
                    p.wms_custom_localizacion.get("url", ""))
                self.panel_config._wms_loc_capa.set(
                    p.wms_custom_localizacion.get("capa", ""))
                self.panel_config._wms_loc_formato.set(
                    p.wms_custom_localizacion.get("formato", "image/png"))
            if hasattr(p, "wfs_custom_localizacion") and p.wfs_custom_localizacion:
                self.panel_config._wfs_loc_url.set(
                    p.wfs_custom_localizacion.get("url", ""))
                self.panel_config._wfs_loc_capa.set(
                    p.wfs_custom_localizacion.get("capa", ""))
            # Mostrar/ocultar frames según proveedor
            self.panel_config._on_proveedor_changed()
            self.panel_config._on_prov_loc_changed()
            self.panel_config.salida.set(p.carpeta_salida)
            if p.patron_nombre:
                self.panel_config.patron_nombre.set(p.patron_nombre)

            # Escala manual
            if p.escala_manual:
                self.panel_config._escala_manual.set(f"{p.escala_manual:,}")
            else:
                self.panel_config._escala_manual.set("0 (auto)")

            # Color infraestructura
            if p.color_infra:
                self.panel_config._color_infra = p.color_infra
                self.panel_config._lbl_color.configure(bg=p.color_infra)

            # Calidad PDF
            if hasattr(p, "calidad_pdf") and p.calidad_pdf:
                self.panel_config._calidad_pdf.set(p.calidad_pdf)

            # ── Transparencias ──
            self.panel_capas.transparencia.set(p.transparencia_montes)
            if hasattr(p, "transparencia_infra"):
                self.panel_capas.transparencia_infra.set(p.transparencia_infra)

            # ── Campos ──
            if hasattr(p, "campo_encabezado") and p.campo_encabezado:
                self.panel_campos._combo_encabezado.set(p.campo_encabezado)

            # campos_visibles se restauran después de cargar el SHP
            # (se guardan para restaurar cuando se recargue la capa)

            # ── Layout y cajetín ──
            if p.layout_key:
                self.panel_cajetin._layout_key.set(p.layout_key)
                self.motor.layout_key = p.layout_key
            self.panel_cajetin.cargar_desde_proyecto(p.cajetin, p.plantilla)

            # Aplicar cajetín y plantilla al motor
            self.motor.set_cajetin(p.cajetin)
            self.motor.set_plantilla(p.plantilla)

            # ── Origen datos tabla ──
            if hasattr(p, "origen_datos_tabla") and p.origen_datos_tabla:
                self.panel_config._origen_datos.set(p.origen_datos_tabla)
                self.panel_config._on_origen_datos_changed()
            if hasattr(p, "ruta_excel_tabla") and p.ruta_excel_tabla:
                self.panel_config._ruta_excel.set(p.ruta_excel_tabla)
                self.panel_config._lbl_excel.configure(
                    text=os.path.basename(p.ruta_excel_tabla))
                # Recargar hojas y columnas del Excel
                hoja = getattr(p, "hoja_excel_tabla", "") or ""
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(
                        p.ruta_excel_tabla, read_only=True, data_only=True)
                    self.panel_config._cb_hoja.configure(values=wb.sheetnames)
                    wb.close()
                    if hoja:
                        self.panel_config._hoja_excel.set(hoja)
                    self.panel_config._cargar_columnas_excel(
                        p.ruta_excel_tabla, hoja or wb.sheetnames[0])
                except Exception:
                    pass
            if hasattr(p, "hoja_excel_tabla") and p.hoja_excel_tabla:
                self.panel_config._hoja_excel.set(p.hoja_excel_tabla)
            if hasattr(p, "campo_enlace_shp") and p.campo_enlace_shp:
                self.panel_config._campo_enlace_shp.set(p.campo_enlace_shp)
            if hasattr(p, "campo_enlace_excel") and p.campo_enlace_excel:
                self.panel_config._campo_enlace_excel.set(p.campo_enlace_excel)
            # Restaurar columnas Excel seleccionadas
            if hasattr(p, "columnas_excel_activas") and p.columnas_excel_activas:
                cols_proy = p.columnas_excel_activas
                for col, var in self.panel_config._check_cols_excel.items():
                    var.set(col in cols_proy)

            # ── Simbología ──
            if p.simbologia:
                from ..motor.simbologia import GestorSimbologia
                self.motor.gestor_simbologia = GestorSimbologia.from_dict(p.simbologia)

            # ── Generación ──
            if hasattr(p, "modo_gen") and p.modo_gen:
                self.panel_gen._modo_gen.set(p.modo_gen)
            if hasattr(p, "rango_desde"):
                self.panel_gen._rango_desde.delete(0, "end")
                self.panel_gen._rango_desde.insert(0, str(p.rango_desde))
            if hasattr(p, "rango_hasta"):
                self.panel_gen._rango_hasta.delete(0, "end")
                self.panel_gen._rango_hasta.insert(0, str(p.rango_hasta))
            if hasattr(p, "campo_agrupacion") and p.campo_agrupacion:
                self.panel_gen._campo_agrupacion.set(p.campo_agrupacion)
            if hasattr(p, "multipagina"):
                self.panel_gen._multipagina.set(p.multipagina)
            if hasattr(p, "incluir_portada"):
                self.panel_gen._incluir_portada.set(p.incluir_portada)

            # Guardar campos visibles para restaurar tras cargar SHP
            self._campos_visibles_proyecto = p.campos_visibles or []

            self._escribir_log(f"Proyecto cargado: {p.nombre}", "ok")
        except Exception as e:
            self._escribir_log(f"Error al cargar proyecto: {e}", "error")
            messagebox.showerror("Error", str(e))
