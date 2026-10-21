"""
Panel de configuracion: formato de salida, cartografia de fondo,
color de infraestructura, escala manual y carpeta de salida.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from pathlib import Path

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, COLOR_HOVER,
    FONT_BOLD, FONT_SMALL, FONT_LABEL,
    crear_frame_seccion, crear_boton, crear_entry, crear_label,
    crear_tooltip,
)
from ..motor.escala import FORMATOS, ESCALAS
from ..motor.cartografia import PROVIDERS_CTX
from ..motor.maquetacion import CALIDADES_PDF


class PanelConfig:
    """Panel de configuracion general del plano."""

    def __init__(self, parent):
        f = crear_frame_seccion(parent, "\u2699  CONFIGURACI\u00d3N")

        # ── Formato ──
        crear_label(f, "Formato de salida:", tipo="titulo").grid(
            row=0, column=0, sticky="w")
        self.formato = tk.StringVar(value="A3 Horizontal")
        cb_fmt = ttk.Combobox(f, textvariable=self.formato,
                              values=list(FORMATOS.keys()),
                              state="readonly", font=FONT_LABEL)
        cb_fmt.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        # ── Cartografia ──
        crear_label(f, "Cartografia de fondo:", tipo="titulo").grid(
            row=2, column=0, sticky="w")
        opciones_prov = (list(PROVIDERS_CTX.keys())
                         + ["\u2500\u2500 WMS propio \u2500\u2500",
                            "\u2500\u2500 WFS propio \u2500\u2500",
                            "\u2500\u2500 R\u00e1ster local \u2500\u2500"])
        self.proveedor = tk.StringVar(value="OpenStreetMap")
        self._cb_prov = ttk.Combobox(f, textvariable=self.proveedor,
                               values=opciones_prov,
                               state="readonly", font=FONT_LABEL)
        self._cb_prov.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        self._cb_prov.bind("<<ComboboxSelected>>", self._on_proveedor_changed)
        crear_tooltip(
            self._cb_prov,
            "Cartografía de fondo del mapa principal:\n"
            "· Proveedores online (OSM, IGN…): descarga teselas (necesita internet).\n"
            "· Ráster local: usa un GeoTIFF/ECW/VRT o carpeta de hojas tuya.\n"
            "· WMS/WFS propio: conecta a tu servidor de mapas.")

        # Raster local para mapa general
        self._ruta_raster = tk.StringVar(value="")
        self._frame_raster = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_raster.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        crear_boton(self._frame_raster, "Seleccionar r\u00e1ster...",
                    self._elegir_raster_general,
                    icono="\U0001f5fa").pack(side="top", fill="x")
        crear_boton(self._frame_raster, "Carpeta de hojas...",
                    self._elegir_carpeta_raster_general,
                    icono="\U0001f4c2").pack(side="top", fill="x", pady=(2, 0))
        self._lbl_raster = tk.Label(self._frame_raster, text="Sin r\u00e1ster seleccionado",
                                     font=FONT_SMALL, bg=COLOR_PANEL,
                                     fg=COLOR_TEXTO_GRIS, anchor="w",
                                     wraplength=240)
        self._lbl_raster.pack(side="top", fill="x", pady=(2, 0))
        self._frame_raster.grid_remove()

        # WMS propio para mapa general
        self._frame_wms_custom = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_wms_custom.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        crear_label(self._frame_wms_custom, "URL del servicio WMS:",
                    tipo="normal").pack(anchor="w")
        self._wms_url = tk.StringVar(value="")
        crear_entry(self._frame_wms_custom, textvariable=self._wms_url).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wms_custom, "Nombre de capa (LAYERS):",
                    tipo="normal").pack(anchor="w")
        self._wms_capa = tk.StringVar(value="")
        crear_entry(self._frame_wms_custom, textvariable=self._wms_capa).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wms_custom, "Formato:",
                    tipo="normal").pack(anchor="w")
        self._wms_formato = tk.StringVar(value="image/png")
        ttk.Combobox(self._frame_wms_custom, textvariable=self._wms_formato,
                     values=["image/png", "image/jpeg"],
                     state="readonly", font=FONT_SMALL, width=14
                     ).pack(anchor="w", pady=(2, 2))
        self._frame_wms_custom.grid_remove()

        # WFS propio para mapa general
        self._frame_wfs_custom = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_wfs_custom.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        crear_label(self._frame_wfs_custom, "URL del servicio WFS:",
                    tipo="normal").pack(anchor="w")
        self._wfs_url = tk.StringVar(value="")
        crear_entry(self._frame_wfs_custom, textvariable=self._wfs_url).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wfs_custom, "Nombre de capa (TYPENAMES):",
                    tipo="normal").pack(anchor="w")
        self._wfs_capa = tk.StringVar(value="")
        crear_entry(self._frame_wfs_custom, textvariable=self._wfs_capa).pack(
            fill="x", pady=(2, 2))
        self._frame_wfs_custom.grid_remove()

        # ── Cartografia localizacion ──
        crear_label(f, "Cartografia localizacion:", tipo="titulo").grid(
            row=5, column=0, sticky="w")
        opciones_loc = (["WMS IGN (online)"]
                        + list(PROVIDERS_CTX.keys())
                        + ["\u2500\u2500 WMS propio \u2500\u2500",
                           "\u2500\u2500 WFS propio \u2500\u2500",
                           "\u2500\u2500 R\u00e1ster local \u2500\u2500",
                           "\u2500\u2500 Capa SHP/GDB \u2500\u2500"])
        self._prov_localizacion = tk.StringVar(value="WMS IGN (online)")
        self._cb_prov_loc = ttk.Combobox(f, textvariable=self._prov_localizacion,
                                          values=opciones_loc,
                                          state="readonly", font=FONT_LABEL)
        self._cb_prov_loc.grid(row=6, column=0, sticky="ew", pady=(2, 4))
        self._cb_prov_loc.bind("<<ComboboxSelected>>", self._on_prov_loc_changed)

        self._ruta_raster_loc = tk.StringVar(value="")
        self._frame_raster_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_raster_loc.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        crear_boton(self._frame_raster_loc, "Seleccionar r\u00e1ster...",
                    self._elegir_raster_localizacion,
                    icono="\U0001f5fa").pack(side="top", fill="x")
        crear_boton(self._frame_raster_loc, "Carpeta de hojas...",
                    self._elegir_carpeta_raster_localizacion,
                    icono="\U0001f4c2").pack(side="top", fill="x", pady=(2, 0))
        self._lbl_raster_loc = tk.Label(self._frame_raster_loc,
                                         text="Sin r\u00e1ster seleccionado",
                                         font=FONT_SMALL, bg=COLOR_PANEL,
                                         fg=COLOR_TEXTO_GRIS, anchor="w",
                                         wraplength=240)
        self._lbl_raster_loc.pack(side="top", fill="x", pady=(2, 0))
        self._frame_raster_loc.grid_remove()

        # WMS propio para localizacion
        self._frame_wms_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_wms_loc.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        crear_label(self._frame_wms_loc, "URL del servicio WMS:",
                    tipo="normal").pack(anchor="w")
        self._wms_loc_url = tk.StringVar(value="")
        crear_entry(self._frame_wms_loc, textvariable=self._wms_loc_url).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wms_loc, "Nombre de capa (LAYERS):",
                    tipo="normal").pack(anchor="w")
        self._wms_loc_capa = tk.StringVar(value="")
        crear_entry(self._frame_wms_loc, textvariable=self._wms_loc_capa).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wms_loc, "Formato:",
                    tipo="normal").pack(anchor="w")
        self._wms_loc_formato = tk.StringVar(value="image/png")
        ttk.Combobox(self._frame_wms_loc, textvariable=self._wms_loc_formato,
                     values=["image/png", "image/jpeg"],
                     state="readonly", font=FONT_SMALL, width=14
                     ).pack(anchor="w", pady=(2, 2))
        self._frame_wms_loc.grid_remove()

        # WFS propio para localizacion
        self._frame_wfs_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_wfs_loc.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        crear_label(self._frame_wfs_loc, "URL del servicio WFS:",
                    tipo="normal").pack(anchor="w")
        self._wfs_loc_url = tk.StringVar(value="")
        crear_entry(self._frame_wfs_loc, textvariable=self._wfs_loc_url).pack(
            fill="x", pady=(2, 2))
        crear_label(self._frame_wfs_loc, "Nombre de capa (TYPENAMES):",
                    tipo="normal").pack(anchor="w")
        self._wfs_loc_capa = tk.StringVar(value="")
        crear_entry(self._frame_wfs_loc, textvariable=self._wfs_loc_capa).pack(
            fill="x", pady=(2, 2))
        self._frame_wfs_loc.grid_remove()

        # Capa SHP/GDB propia para localizacion
        self._ruta_capa_loc = tk.StringVar(value="")
        self._frame_capa_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_capa_loc.grid(row=7, column=0, sticky="ew", pady=(0, 4))
        crear_boton(self._frame_capa_loc, "Seleccionar SHP / GDB...",
                    self._elegir_capa_localizacion,
                    icono="\U0001f5fa").pack(side="top", fill="x")
        self._lbl_capa_loc = tk.Label(self._frame_capa_loc,
                                       text="Sin capa seleccionada",
                                       font=FONT_SMALL, bg=COLOR_PANEL,
                                       fg=COLOR_TEXTO_GRIS, anchor="w",
                                       wraplength=240)
        self._lbl_capa_loc.pack(side="top", fill="x", pady=(2, 0))
        self._frame_capa_loc.grid_remove()

        # ── Escala mapa de localizacion ──
        escala_loc_f = tk.Frame(f, bg=COLOR_PANEL)
        escala_loc_f.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        self._frame_escala_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_escala_loc.grid(row=8, column=0, sticky="ew", pady=(0, 8))
        escala_loc_f.grid_remove()

        crear_label(self._frame_escala_loc, "Escala localizacion:",
                    tipo="titulo").pack(anchor="w")
        esc_loc_inner = tk.Frame(self._frame_escala_loc, bg=COLOR_PANEL)
        esc_loc_inner.pack(fill="x", pady=(2, 0))
        crear_label(esc_loc_inner, "1:", tipo="normal").pack(side="left")
        self._escala_localizacion = tk.StringVar(value="250,000")
        _ESCALAS_LOC = ["50,000", "100,000", "150,000", "200,000",
                        "250,000", "500,000", "1,000,000", "2,000,000"]
        self._cb_escala_loc = ttk.Combobox(
            esc_loc_inner, textvariable=self._escala_localizacion,
            values=_ESCALAS_LOC,
            font=FONT_SMALL, width=12)
        self._cb_escala_loc.pack(side="left", padx=(2, 0))
        crear_tooltip(
            self._cb_escala_loc,
            "Escala del mapa de localización (recuadro de situación).\n"
            "Valores mayores abarcan más territorio alrededor de la zona.")

        # ── Escala manual ──
        crear_label(f, "Escala (0 = automatica):", tipo="titulo").grid(
            row=9, column=0, sticky="w")
        escala_f = tk.Frame(f, bg=COLOR_PANEL)
        escala_f.grid(row=10, column=0, sticky="ew", pady=(2, 8))

        crear_label(escala_f, "1:", tipo="normal").pack(side="left")
        self._escala_manual = tk.StringVar(value="0")
        self._cb_escala = ttk.Combobox(
            escala_f, textvariable=self._escala_manual,
            values=["0 (auto)"] + [f"{e:,}" for e in ESCALAS],
            font=FONT_SMALL, width=12,
        )
        self._cb_escala.pack(side="left", padx=(2, 0))
        crear_tooltip(
            self._cb_escala,
            "Escala del mapa principal (1:N).\n"
            "0 = automática: se ajusta a cada infraestructura.\n"
            "Un valor fijo usa la misma escala en todos los planos.")

        # ── Color infraestructura ──
        crear_label(f, "Color infraestructura:", tipo="titulo").grid(
            row=11, column=0, sticky="w")
        self._color_infra = "#E74C3C"
        btn_frame = tk.Frame(f, bg=COLOR_PANEL)
        btn_frame.grid(row=12, column=0, sticky="ew", pady=(2, 8))
        self._lbl_color = tk.Label(btn_frame, bg=self._color_infra,
                                    width=4, relief="flat", bd=0,
                                    highlightthickness=1,
                                    highlightbackground=COLOR_BORDE)
        self._lbl_color.pack(side="left", padx=(0, 8))
        crear_boton(btn_frame, "Elegir color", self._elegir_color).pack(
            side="left")

        # ── Calidad PDF ──
        crear_label(f, "Calidad PDF:", tipo="titulo").grid(
            row=13, column=0, sticky="w")
        self._calidad_pdf = tk.StringVar(value="Alta (400 DPI)")
        cb_calidad = ttk.Combobox(f, textvariable=self._calidad_pdf,
                     values=list(CALIDADES_PDF.keys()),
                     state="readonly", font=FONT_LABEL)
        cb_calidad.grid(row=14, column=0, sticky="ew", pady=(2, 8))
        crear_tooltip(
            cb_calidad,
            "Resolución de salida del PDF (DPI).\n"
            "Mayor calidad = más nitidez pero archivos más grandes "
            "y generación más lenta.")

        # ── Origen datos tabla ──
        crear_label(f, "Datos de tabla:", tipo="titulo").grid(
            row=15, column=0, sticky="w")
        self._origen_datos = tk.StringVar(value="Shapefile (capa cargada)")
        cb_origen = ttk.Combobox(
            f, textvariable=self._origen_datos,
            values=["Shapefile (capa cargada)", "Archivo Excel (.xlsx)"],
            state="readonly", font=FONT_LABEL)
        cb_origen.grid(row=16, column=0, sticky="ew", pady=(2, 4))
        cb_origen.bind("<<ComboboxSelected>>", self._on_origen_datos_changed)

        self._ruta_excel = tk.StringVar(value="")
        self._frame_excel = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_excel.grid(row=17, column=0, sticky="ew", pady=(0, 4))
        crear_boton(self._frame_excel, "Seleccionar Excel...",
                    self._elegir_excel,
                    icono="\U0001f4ca").pack(side="top", fill="x")
        self._lbl_excel = tk.Label(self._frame_excel, text="Sin archivo seleccionado",
                                    font=FONT_SMALL, bg=COLOR_PANEL,
                                    fg=COLOR_TEXTO_GRIS, anchor="w",
                                    wraplength=240)
        self._lbl_excel.pack(side="top", fill="x", pady=(2, 0))

        # Selector de hoja del Excel
        self._frame_hoja = tk.Frame(self._frame_excel, bg=COLOR_PANEL)
        self._frame_hoja.pack(side="top", fill="x", pady=(2, 0))
        crear_label(self._frame_hoja, "Hoja:", tipo="normal").pack(side="left")
        self._hoja_excel = tk.StringVar(value="")
        self._cb_hoja = ttk.Combobox(self._frame_hoja,
                                      textvariable=self._hoja_excel,
                                      state="readonly", font=FONT_SMALL, width=20)
        self._cb_hoja.pack(side="left", padx=(4, 0))
        self._cb_hoja.bind("<<ComboboxSelected>>", self._on_hoja_changed)

        # Campo enlace: SHP <-> Excel
        self._frame_enlace = tk.Frame(self._frame_excel, bg=COLOR_PANEL)
        self._frame_enlace.pack(side="top", fill="x", pady=(4, 0))

        crear_label(self._frame_enlace, "Campo enlace SHP:",
                    tipo="normal").grid(row=0, column=0, sticky="w")
        self._campo_enlace_shp = tk.StringVar(value="")
        self._cb_enlace_shp = ttk.Combobox(
            self._frame_enlace, textvariable=self._campo_enlace_shp,
            state="readonly", font=FONT_SMALL, width=18)
        self._cb_enlace_shp.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        crear_label(self._frame_enlace, "Campo enlace Excel:",
                    tipo="normal").grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._campo_enlace_excel = tk.StringVar(value="")
        self._cb_enlace_excel = ttk.Combobox(
            self._frame_enlace, textvariable=self._campo_enlace_excel,
            state="readonly", font=FONT_SMALL, width=18)
        self._cb_enlace_excel.grid(row=1, column=1, sticky="ew", padx=(4, 0),
                                    pady=(2, 0))
        self._frame_enlace.columnconfigure(1, weight=1)

        # Checkboxes de columnas Excel a incluir
        crear_label(self._frame_excel, "Columnas a incluir:",
                    tipo="normal").pack(side="top", anchor="w", pady=(4, 2))

        self._frame_cols_excel = tk.Frame(self._frame_excel, bg=COLOR_PANEL)
        self._frame_cols_excel.pack(side="top", fill="x")
        self._check_cols_excel = {}
        self._widgets_cols_excel = []

        self._frame_excel.grid_remove()

        # ── Nombre de archivo ──
        crear_label(f, "Nombre de archivo:", tipo="titulo").grid(
            row=18, column=0, sticky="w")

        self._presets_nombre = {
            "plano_{num}_{nombre}": "N\u00ba + Nombre infraestructura",
            "plano_{num}": "Solo numero de plano",
            "{nombre}": "Solo nombre infraestructura",
            "plano_{campo}_{num}": "Campo agrupacion + N\u00ba",
        }
        self._preset_nombre = tk.StringVar(value="N\u00ba + Nombre infraestructura")
        cb_preset = ttk.Combobox(
            f, textvariable=self._preset_nombre,
            values=list(self._presets_nombre.values()),
            state="readonly", font=FONT_SMALL,
        )
        cb_preset.grid(row=19, column=0, sticky="ew", pady=(2, 2))
        cb_preset.bind("<<ComboboxSelected>>", self._on_preset_nombre)

        self.patron_nombre = tk.StringVar(value="plano_{num}_{nombre}")
        entry_patron = crear_entry(f, textvariable=self.patron_nombre)
        entry_patron.grid(row=20, column=0, sticky="ew", pady=(2, 0))
        crear_tooltip(
            entry_patron,
            "Patrón del nombre de cada archivo PDF. Variables disponibles:\n"
            "{num} = número de plano · {nombre} = nombre de la "
            "infraestructura · {campo} = valor del campo de agrupación.")

        self._lbl_preview_nombre = tk.Label(
            f, text="Ej: plano_0001_CortafuegosNorte.pdf",
            font=("Segoe UI", 8), bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_preview_nombre.grid(row=21, column=0, sticky="w", pady=(2, 8))
        self.patron_nombre.trace_add("write", self._actualizar_preview_nombre)

        # ── Carpeta de salida ──
        crear_label(f, "Carpeta de salida:", tipo="titulo").grid(
            row=22, column=0, sticky="w")
        self.salida = tk.StringVar(value=str(Path.home() / "Planos_Forestales"))
        tk.Label(f, textvariable=self.salida, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=23, column=0, sticky="w")
        crear_boton(f, "Seleccionar carpeta", self._elegir_carpeta,
                    icono="\U0001f4c1").grid(row=24, column=0, sticky="ew", pady=(4, 4))

        # ── Capas WMS superpuestas (overlays) ──
        self._parent = parent
        self._overlays = []  # lista de dicts (ver motor.overlays_wms)
        self._crear_seccion_overlays(f, fila=25)

        f.columnconfigure(0, weight=1)

    @property
    def calidad_pdf(self) -> str:
        return self._calidad_pdf.get()

    @property
    def dpi_figura(self) -> int:
        return CALIDADES_PDF.get(self._calidad_pdf.get(), (400, 300))[0]

    @property
    def dpi_guardado(self) -> int:
        return CALIDADES_PDF.get(self._calidad_pdf.get(), (400, 300))[1]

    @property
    def color_infra(self) -> str:
        return self._color_infra

    @property
    def escala_manual(self) -> int:
        # No descartar por empezar en "0": un "0500" tecleado debe ser 500,
        # no escala automática. "0" y "0 (Automática)" siguen dando None
        # (val<=0 y ValueError respectivamente).
        txt = self._escala_manual.get().replace(",", "").replace(".", "").strip()
        try:
            val = int(txt)
            return val if val > 0 else None
        except ValueError:
            return None

    def _elegir_color(self):
        color = colorchooser.askcolor(
            color=self._color_infra,
            title="Color infraestructura",
        )[1]
        if color:
            self._color_infra = color
            self._lbl_color.configure(bg=color)

    def _on_preset_nombre(self, event=None):
        label = self._preset_nombre.get()
        for pattern, lbl in self._presets_nombre.items():
            if lbl == label:
                self.patron_nombre.set(pattern)
                break

    def _actualizar_preview_nombre(self, *args):
        patron = self.patron_nombre.get()
        try:
            ejemplo = patron.format(
                num="0001", nombre="CortafuegosNorte", campo="Municipio")
            self._lbl_preview_nombre.configure(
                text=f"Ej: {ejemplo}.pdf")
        except (KeyError, IndexError, ValueError):
            self._lbl_preview_nombre.configure(
                text="Ej: (patron invalido)")

    def _elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Carpeta de salida")
        if carpeta:
            self.salida.set(carpeta)

    def abrir_carpeta(self):
        carpeta = self.salida.get()
        os.makedirs(carpeta, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(carpeta)
        elif sys.platform == "darwin":
            os.system(f'open "{carpeta}"')
        else:
            os.system(f'xdg-open "{carpeta}"')

    # ── Raster local ──

    _RASTER_FILETYPES = [
        ("R\u00e1ster georreferenciado", "*.tif *.tiff *.ecw *.jp2 *.img *.vrt"),
        ("GeoTIFF", "*.tif *.tiff"),
        ("ECW", "*.ecw"),
        ("JPEG2000", "*.jp2"),
        ("Todos", "*.*"),
    ]

    def _on_proveedor_changed(self, event=None):
        prov = self.proveedor.get()
        self._frame_raster.grid_remove()
        self._frame_wms_custom.grid_remove()
        self._frame_wfs_custom.grid_remove()
        if prov == "\u2500\u2500 R\u00e1ster local \u2500\u2500":
            self._frame_raster.grid()
        elif prov == "\u2500\u2500 WMS propio \u2500\u2500":
            self._frame_wms_custom.grid()
        elif prov == "\u2500\u2500 WFS propio \u2500\u2500":
            self._frame_wfs_custom.grid()

    def _on_prov_loc_changed(self, event=None):
        prov = self._prov_localizacion.get()
        self._frame_raster_loc.grid_remove()
        self._frame_wms_loc.grid_remove()
        self._frame_wfs_loc.grid_remove()
        self._frame_capa_loc.grid_remove()
        if prov == "\u2500\u2500 R\u00e1ster local \u2500\u2500":
            self._frame_raster_loc.grid()
        elif prov == "\u2500\u2500 WMS propio \u2500\u2500":
            self._frame_wms_loc.grid()
        elif prov == "\u2500\u2500 WFS propio \u2500\u2500":
            self._frame_wfs_loc.grid()
        elif prov == "\u2500\u2500 Capa SHP/GDB \u2500\u2500":
            self._frame_capa_loc.grid()

    def _elegir_raster_general(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar r\u00e1ster para mapa general",
            filetypes=self._RASTER_FILETYPES)
        if ruta:
            self._ruta_raster.set(ruta)
            self._lbl_raster.configure(text=Path(ruta).name)

    def _elegir_raster_localizacion(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar r\u00e1ster para mapa de localizacion",
            filetypes=self._RASTER_FILETYPES)
        if ruta:
            self._ruta_raster_loc.set(ruta)
            self._lbl_raster_loc.configure(text=Path(ruta).name)

    def _elegir_carpeta_raster_general(self):
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta con hojas cartograficas (mapa general)")
        if not carpeta:
            return
        self._generar_vrt_y_asignar(carpeta, self._ruta_raster, self._lbl_raster)

    def _elegir_carpeta_raster_localizacion(self):
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta con hojas cartograficas (localizacion)")
        if not carpeta:
            return
        self._generar_vrt_y_asignar(carpeta, self._ruta_raster_loc, self._lbl_raster_loc)

    def _generar_vrt_y_asignar(self, carpeta, var_ruta, lbl):
        """Construye el mosaico VRT de una carpeta de hojas EN SEGUNDO PLANO.

        Antes se hac\u00eda en el hilo principal: con decenas de hojas MTN (y
        m\u00e1s si hay que reproyectar las de otro huso) la interfaz quedaba
        congelada varios minutos sin ninguna indicaci\u00f3n.
        """
        import threading
        from ..motor.cartografia import construir_vrt_desde_carpeta

        if getattr(self, "_vrt_en_curso", False):
            messagebox.showinfo(
                "Mosaico en curso",
                "Ya se est\u00e1 creando un mosaico; espera a que termine.")
            return
        self._vrt_en_curso = True
        lbl.configure(text=f"\u23f3 Creando mosaico de '{Path(carpeta).name}'... "
                           "(puede tardar varios minutos)")

        def _en_hilo():
            try:
                vrt = construir_vrt_desde_carpeta(carpeta)
                resultado = ("ok", vrt)
            except FileNotFoundError as e:
                resultado = ("sin_rasters", str(e))
            except Exception as e:
                resultado = ("error", str(e))
            try:
                self._parent.after(0, lambda: _al_terminar(resultado))
            except Exception:
                pass

        def _al_terminar(resultado):
            self._vrt_en_curso = False
            try:
                if not self._parent.winfo_exists():
                    return
            except Exception:
                return
            tipo, valor = resultado
            if tipo == "ok":
                var_ruta.set(valor)
                lbl.configure(
                    text=f"VRT: {Path(carpeta).name} ({Path(valor).name})")
            elif tipo == "sin_rasters":
                lbl.configure(text="Sin r\u00e1ster seleccionado")
                messagebox.showwarning("Sin r\u00e1sters", valor)
            else:
                lbl.configure(text="Error al crear el mosaico")
                messagebox.showerror("Error al crear mosaico", valor)

        threading.Thread(target=_en_hilo, daemon=True).start()

    _CAPA_FILETYPES = [
        ("Shapefile", "*.shp"),
        ("Geodatabase", "*.gdb"),
        ("GeoJSON", "*.geojson *.json"),
        ("Todos", "*.*"),
    ]

    def _elegir_capa_localizacion(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar capa para mapa de localizacion",
            filetypes=self._CAPA_FILETYPES)
        if ruta:
            self._ruta_capa_loc.set(ruta)
            self._lbl_capa_loc.configure(text=Path(ruta).name)

    # ── Origen datos tabla (Excel) ──

    def _on_origen_datos_changed(self, event=None):
        if self._origen_datos.get() == "Archivo Excel (.xlsx)":
            self._frame_excel.grid()
        else:
            self._frame_excel.grid_remove()

    def _elegir_excel(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")])
        if ruta:
            self._ruta_excel.set(ruta)
            self._lbl_excel.configure(text=Path(ruta).name)
            try:
                import openpyxl
                wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
                hojas = wb.sheetnames
                wb.close()
                self._cb_hoja.configure(values=hojas)
                if hojas:
                    self._hoja_excel.set(hojas[0])
                    self._cargar_columnas_excel(ruta, hojas[0])
            except Exception:
                self._cb_hoja.configure(values=[])
                self._hoja_excel.set("")
                self._poblar_columnas_excel([])

    def _on_hoja_changed(self, event=None):
        ruta = self._ruta_excel.get()
        hoja = self._hoja_excel.get()
        if ruta and hoja:
            self._cargar_columnas_excel(ruta, hoja)

    def _cargar_columnas_excel(self, ruta: str, hoja: str):
        try:
            import pandas as pd
            df = pd.read_excel(ruta, sheet_name=hoja, engine="openpyxl", nrows=0)
            cols = list(df.columns)
        except Exception:
            cols = []
        self._poblar_columnas_excel(cols)
        self._cb_enlace_excel.configure(values=cols)
        if cols:
            self._campo_enlace_excel.set(cols[0])
        else:
            self._campo_enlace_excel.set("")

    def _poblar_columnas_excel(self, columnas: list):
        for w in self._widgets_cols_excel:
            w.destroy()
        self._widgets_cols_excel.clear()
        self._check_cols_excel.clear()

        for col in columnas:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(
                self._frame_cols_excel, text=col, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_ENTRY, activebackground=COLOR_PANEL,
                cursor="hand2", bd=0, highlightthickness=0,
            )
            cb.pack(anchor="w", pady=1)
            self._check_cols_excel[col] = var
            self._widgets_cols_excel.append(cb)

    def actualizar_campos_shp_enlace(self, columnas: list):
        cols = [c for c in columnas if c.lower() != "geometry"]
        self._cb_enlace_shp.configure(values=cols)
        if cols and not self._campo_enlace_shp.get():
            self._campo_enlace_shp.set(cols[0])

    @property
    def usa_excel(self) -> bool:
        return self._origen_datos.get() == "Archivo Excel (.xlsx)"

    @property
    def ruta_excel(self) -> str:
        if self.usa_excel:
            return self._ruta_excel.get()
        return ""

    @property
    def hoja_excel(self) -> str:
        return self._hoja_excel.get()

    @property
    def campo_enlace_shp(self) -> str:
        return self._campo_enlace_shp.get()

    @property
    def campo_enlace_excel(self) -> str:
        return self._campo_enlace_excel.get()

    @property
    def columnas_excel_activas(self) -> list:
        return [c for c, v in self._check_cols_excel.items() if v.get()]

    @property
    def ruta_raster_general(self) -> str:
        if self.proveedor.get() == "\u2500\u2500 R\u00e1ster local \u2500\u2500":
            return self._ruta_raster.get()
        return ""

    @property
    def ruta_raster_localizacion(self) -> str:
        if self._prov_localizacion.get() == "\u2500\u2500 R\u00e1ster local \u2500\u2500":
            return self._ruta_raster_loc.get()
        return ""

    @property
    def ruta_capa_localizacion(self) -> str:
        if self._prov_localizacion.get() == "\u2500\u2500 Capa SHP/GDB \u2500\u2500":
            return self._ruta_capa_loc.get()
        return ""

    @property
    def wms_custom_general(self) -> dict:
        if self.proveedor.get() == "\u2500\u2500 WMS propio \u2500\u2500":
            url = self._wms_url.get().strip()
            capa = self._wms_capa.get().strip()
            if url and capa:
                return {"url": url, "capa": capa,
                        "formato": self._wms_formato.get()}
        return {}

    @property
    def wfs_custom_general(self) -> dict:
        if self.proveedor.get() == "\u2500\u2500 WFS propio \u2500\u2500":
            url = self._wfs_url.get().strip()
            capa = self._wfs_capa.get().strip()
            if url and capa:
                return {"url": url, "capa": capa}
        return {}

    @property
    def wms_custom_localizacion(self) -> dict:
        if self._prov_localizacion.get() == "\u2500\u2500 WMS propio \u2500\u2500":
            url = self._wms_loc_url.get().strip()
            capa = self._wms_loc_capa.get().strip()
            if url and capa:
                return {"url": url, "capa": capa,
                        "formato": self._wms_loc_formato.get()}
        return {}

    @property
    def wfs_custom_localizacion(self) -> dict:
        if self._prov_localizacion.get() == "\u2500\u2500 WFS propio \u2500\u2500":
            url = self._wfs_loc_url.get().strip()
            capa = self._wfs_loc_capa.get().strip()
            if url and capa:
                return {"url": url, "capa": capa}
        return {}

    @property
    def escala_localizacion(self) -> int:
        txt = self._escala_localizacion.get().replace(",", "").strip()
        try:
            val = int(txt)
            return val if val > 0 else 250_000
        except ValueError:
            return 250_000

    # ── Capas WMS superpuestas ──

    def _crear_seccion_overlays(self, f, fila: int):
        """Sección plegable 'CAPAS WMS SUPERPUESTAS'."""
        self._overlays_visible = tk.BooleanVar(value=False)
        self._btn_toggle_overlays = tk.Button(
            f, text="▸  CAPAS WMS SUPERPUESTAS (0)",
            command=self._toggle_overlays, font=FONT_BOLD,
            bg=COLOR_PANEL, fg=COLOR_ACENTO, activebackground=COLOR_PANEL,
            activeforeground=COLOR_ACENTO, relief="flat", bd=0,
            highlightthickness=0, cursor="hand2", anchor="w")
        self._btn_toggle_overlays.grid(row=fila, column=0, sticky="ew",
                                       pady=(6, 2))
        crear_tooltip(
            self._btn_toggle_overlays,
            "Capas WMS semitransparentes dibujadas ENCIMA del fondo del\n"
            "mapa principal (no en el de localización): p. ej. parcelas de\n"
            "Catastro sobre la ortofoto PNOA, límites municipales o montes\n"
            "públicos. Cada capa tiene su propia transparencia y se puede\n"
            "activar/desactivar sin borrarla. Requiere internet.")

        body = tk.Frame(f, bg=COLOR_PANEL)
        body.grid(row=fila + 1, column=0, sticky="ew", pady=(0, 6))
        self._frame_overlays = body

        self._lb_overlays = tk.Listbox(
            body, height=4, font=FONT_SMALL, bg=COLOR_ENTRY, fg=COLOR_TEXTO,
            selectbackground=COLOR_ACENTO, relief="flat",
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            activestyle="none", exportselection=False)
        self._lb_overlays.pack(fill="x", pady=(0, 4))
        self._lb_overlays.bind("<Double-Button-1>",
                               lambda e: self._toggle_overlay_activo())

        fila1 = tk.Frame(body, bg=COLOR_PANEL)
        fila1.pack(fill="x")
        self._btn_overlay_preset = crear_boton(
            fila1, "Añadir predefinida ▾",
            self._menu_overlays_predefinidos)
        self._btn_overlay_preset.pack(side="left", fill="x", expand=True)
        crear_boton(fila1, "Añadir WMS propio…",
                    self._dialogo_overlay_wms).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        fila2 = tk.Frame(body, bg=COLOR_PANEL)
        fila2.pack(fill="x", pady=(4, 0))
        crear_boton(fila2, "Quitar", self._quitar_overlay).pack(
            side="left", fill="x", expand=True)
        crear_boton(fila2, "Activar/Desactivar",
                    self._toggle_overlay_activo).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        body.grid_remove()

    def _toggle_overlays(self):
        if self._overlays_visible.get():
            self._frame_overlays.grid_remove()
            self._overlays_visible.set(False)
        else:
            self._frame_overlays.grid()
            self._overlays_visible.set(True)
        self._refrescar_overlays()

    def _refrescar_overlays(self):
        """Repinta la lista y sincroniza con el motor."""
        sel = self._lb_overlays.curselection()
        self._lb_overlays.delete(0, "end")
        for ov in self._overlays:
            marca = "✓" if ov.get("activo", True) else "✗"
            pct = int(round(float(ov.get("alpha", 0.6)) * 100))
            self._lb_overlays.insert(
                "end", f"{marca}  {ov.get('nombre', ov.get('capa', ''))}"
                       f"  ({pct}%)")
        if sel and sel[0] < len(self._overlays):
            self._lb_overlays.selection_set(sel[0])
        flecha = "▾" if self._overlays_visible.get() else "▸"
        n_act = sum(1 for o in self._overlays if o.get("activo", True))
        self._btn_toggle_overlays.configure(
            text=f"{flecha}  CAPAS WMS SUPERPUESTAS ({n_act}/{len(self._overlays)})")
        self._sincronizar_overlays_motor()

    def _sincronizar_overlays_motor(self):
        """Empuja la lista a ``motor.overlays_wms``.

        La ventana principal (App) expone ``self.motor``; se localiza a
        través de la ventana raíz para no depender de cambios en app.py.
        """
        try:
            motor = getattr(self._parent.winfo_toplevel(), "motor", None)
        except Exception:
            motor = None
        if motor is not None:
            motor.overlays_wms = self.obtener_overlays()

    def _menu_overlays_predefinidos(self):
        from ..motor.cartografia import OVERLAYS_PREDEFINIDOS
        menu = tk.Menu(self._btn_overlay_preset, tearoff=0)
        for nombre in OVERLAYS_PREDEFINIDOS:
            menu.add_command(
                label=nombre,
                command=lambda n=nombre: self._añadir_overlay_predefinido(n))
        btn = self._btn_overlay_preset
        try:
            menu.tk_popup(btn.winfo_rootx(),
                          btn.winfo_rooty() + btn.winfo_height())
        finally:
            menu.grab_release()

    def _añadir_overlay_predefinido(self, nombre: str):
        from ..motor.cartografia import OVERLAYS_PREDEFINIDOS
        p = OVERLAYS_PREDEFINIDOS.get(nombre)
        if not p:
            return
        if any(o.get("nombre") == nombre for o in self._overlays):
            messagebox.showinfo("Capa ya añadida",
                                f"'{nombre}' ya está en la lista.")
            return
        self._overlays.append({
            "nombre": nombre, "url": p["url"], "capa": p["capa"],
            "alpha": float(p.get("alpha", 0.6)),
            "formato": p.get("formato", "image/png"),
            "activo": True, "version": p.get("version", "1.3.0"),
        })
        self._refrescar_overlays()

    def _dialogo_overlay_wms(self):
        """Diálogo para añadir un WMS propio como capa superpuesta."""
        dlg = tk.Toplevel(self._parent.winfo_toplevel())
        dlg.title("Añadir capa WMS superpuesta")
        dlg.configure(bg=COLOR_PANEL)
        dlg.transient(self._parent.winfo_toplevel())
        dlg.resizable(False, False)

        v_nombre = tk.StringVar(value="")
        v_url = tk.StringVar(value="")
        v_capa = tk.StringVar(value="")
        v_formato = tk.StringVar(value="image/png")
        v_version = tk.StringVar(value="1.3.0")
        v_alpha = tk.DoubleVar(value=60)

        cont = tk.Frame(dlg, bg=COLOR_PANEL, padx=12, pady=10)
        cont.pack(fill="both", expand=True)
        for txt, var in (("Nombre:", v_nombre),
                         ("URL del servicio WMS:", v_url),
                         ("Nombre de capa (LAYERS):", v_capa)):
            crear_label(cont, txt).pack(anchor="w")
            crear_entry(cont, textvariable=var, width=48).pack(
                fill="x", pady=(2, 6))
        fila = tk.Frame(cont, bg=COLOR_PANEL)
        fila.pack(fill="x", pady=(0, 6))
        crear_label(fila, "Formato:").pack(side="left")
        ttk.Combobox(fila, textvariable=v_formato,
                     values=["image/png", "image/gif"],
                     state="readonly", font=FONT_SMALL, width=11
                     ).pack(side="left", padx=(4, 12))
        crear_label(fila, "Versión WMS:").pack(side="left")
        ttk.Combobox(fila, textvariable=v_version,
                     values=["1.3.0", "1.1.1"],
                     state="readonly", font=FONT_SMALL, width=7
                     ).pack(side="left", padx=(4, 0))
        crear_label(cont, "Opacidad (%):").pack(anchor="w")
        tk.Scale(cont, from_=10, to=100, orient="horizontal",
                 variable=v_alpha, resolution=5, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO, highlightthickness=0,
                 troughcolor=COLOR_ENTRY).pack(fill="x")

        def _aceptar():
            url, capa = v_url.get().strip(), v_capa.get().strip()
            if not url or not capa:
                messagebox.showwarning(
                    "Datos incompletos",
                    "Indica la URL del servicio y el nombre de la capa.",
                    parent=dlg)
                return
            self._overlays.append({
                "nombre": v_nombre.get().strip() or capa,
                "url": url, "capa": capa,
                "alpha": round(v_alpha.get() / 100.0, 2),
                "formato": v_formato.get(),
                "activo": True, "version": v_version.get(),
            })
            dlg.destroy()
            self._refrescar_overlays()

        botones = tk.Frame(cont, bg=COLOR_PANEL)
        botones.pack(fill="x", pady=(8, 0))
        crear_boton(botones, "Cancelar", dlg.destroy).pack(side="right")
        crear_boton(botones, "Añadir", _aceptar,
                    estilo="primario").pack(side="right", padx=(0, 6))
        dlg.grab_set()

    def _indice_overlay_sel(self):
        sel = self._lb_overlays.curselection()
        if not sel or sel[0] >= len(self._overlays):
            return None
        return sel[0]

    def _quitar_overlay(self):
        i = self._indice_overlay_sel()
        if i is None:
            return
        del self._overlays[i]
        self._refrescar_overlays()

    def _toggle_overlay_activo(self):
        i = self._indice_overlay_sel()
        if i is None:
            return
        self._overlays[i]["activo"] = not self._overlays[i].get("activo", True)
        self._refrescar_overlays()

    def obtener_overlays(self) -> list:
        """Copia de la lista de capas WMS superpuestas configuradas."""
        return [dict(o) for o in self._overlays]

    def cargar_overlays(self, lista):
        """Sustituye la lista de overlays (p. ej. al cargar un proyecto)."""
        self._overlays = [
            dict(o) for o in (lista or [])
            if isinstance(o, dict) and o.get("url") and o.get("capa")]
        if self._overlays and not self._overlays_visible.get():
            self._toggle_overlays()  # mostrar la sección si hay capas
        else:
            self._refrescar_overlays()

    @property
    def overlays_wms(self) -> list:
        """Overlays configurados (para get_config / motor.overlays_wms)."""
        return self.obtener_overlays()
