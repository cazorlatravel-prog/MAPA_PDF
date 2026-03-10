"""
Panel de configuración: formato de salida, cartografía de fondo,
color de infraestructura, escala manual y carpeta de salida.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser
from pathlib import Path

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    FONT_BOLD, FONT_SMALL, FONT_LABEL,
    crear_frame_seccion, crear_boton,
)
from ..motor.escala import FORMATOS, ESCALAS
from ..motor.cartografia import PROVIDERS_CTX
from ..motor.maquetacion import CALIDADES_PDF


class PanelConfig:
    """Panel de configuración general del plano."""

    def __init__(self, parent):
        f = crear_frame_seccion(parent, "\u2699  CONFIGURACI\u00d3N")

        # ── Formato ──
        tk.Label(f, text="Formato de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=0, column=0, sticky="w")
        self.formato = tk.StringVar(value="A3 Horizontal")
        cb_fmt = ttk.Combobox(f, textvariable=self.formato,
                              values=list(FORMATOS.keys()),
                              state="readonly", font=FONT_LABEL)
        cb_fmt.grid(row=1, column=0, sticky="ew", pady=(2, 8))

        # ── Cartografía ──
        tk.Label(f, text="Cartografía de fondo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=2, column=0, sticky="w")
        opciones_prov = list(PROVIDERS_CTX.keys()) + ["── Ráster local ──"]
        self.proveedor = tk.StringVar(value="OpenStreetMap")
        self._cb_prov = ttk.Combobox(f, textvariable=self.proveedor,
                               values=opciones_prov,
                               state="readonly", font=FONT_LABEL)
        self._cb_prov.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        self._cb_prov.bind("<<ComboboxSelected>>", self._on_proveedor_changed)

        # Ráster local para mapa general
        self._ruta_raster = tk.StringVar(value="")
        self._frame_raster = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_raster.grid(row=4, column=0, sticky="ew", pady=(0, 4))
        crear_boton(self._frame_raster, "Seleccionar ráster...",
                    self._elegir_raster_general,
                    icono="\U0001f5fa").pack(side="top", fill="x")
        self._lbl_raster = tk.Label(self._frame_raster, text="Sin ráster seleccionado",
                                     font=FONT_SMALL, bg=COLOR_PANEL,
                                     fg=COLOR_TEXTO_GRIS, anchor="w",
                                     wraplength=240)
        self._lbl_raster.pack(side="top", fill="x", pady=(2, 0))
        self._frame_raster.grid_remove()  # Oculto por defecto

        # Ráster local para mapa de localización
        tk.Label(f, text="Cartografía localización:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=5, column=0, sticky="w")
        opciones_loc = ["WMS IGN (online)"] + ["── Ráster local ──"]
        self._prov_localizacion = tk.StringVar(value="WMS IGN (online)")
        self._cb_prov_loc = ttk.Combobox(f, textvariable=self._prov_localizacion,
                                          values=opciones_loc,
                                          state="readonly", font=FONT_LABEL)
        self._cb_prov_loc.grid(row=6, column=0, sticky="ew", pady=(2, 4))
        self._cb_prov_loc.bind("<<ComboboxSelected>>", self._on_prov_loc_changed)

        self._ruta_raster_loc = tk.StringVar(value="")
        self._frame_raster_loc = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_raster_loc.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        crear_boton(self._frame_raster_loc, "Seleccionar ráster...",
                    self._elegir_raster_localizacion,
                    icono="\U0001f5fa").pack(side="top", fill="x")
        self._lbl_raster_loc = tk.Label(self._frame_raster_loc,
                                         text="Sin ráster seleccionado",
                                         font=FONT_SMALL, bg=COLOR_PANEL,
                                         fg=COLOR_TEXTO_GRIS, anchor="w",
                                         wraplength=240)
        self._lbl_raster_loc.pack(side="top", fill="x", pady=(2, 0))
        self._frame_raster_loc.grid_remove()  # Oculto por defecto

        # ── Escala manual ──
        tk.Label(f, text="Escala (0 = automática):", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=8, column=0, sticky="w")
        escala_f = tk.Frame(f, bg=COLOR_PANEL)
        escala_f.grid(row=9, column=0, sticky="ew", pady=(2, 8))

        tk.Label(escala_f, text="1:", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).pack(side="left")
        self._escala_manual = tk.StringVar(value="0")
        self._cb_escala = ttk.Combobox(
            escala_f, textvariable=self._escala_manual,
            values=["0 (auto)"] + [f"{e:,}" for e in ESCALAS],
            font=FONT_SMALL, width=12,
        )
        self._cb_escala.pack(side="left", padx=(2, 0))

        # ── Color infraestructura ──
        tk.Label(f, text="Color infraestructura:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=10, column=0, sticky="w")
        self._color_infra = "#E74C3C"
        btn_frame = tk.Frame(f, bg=COLOR_PANEL)
        btn_frame.grid(row=11, column=0, sticky="ew", pady=(2, 8))
        self._lbl_color = tk.Label(btn_frame, bg=self._color_infra,
                                    width=4, relief="solid", bd=1)
        self._lbl_color.pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Elegir color", command=self._elegir_color,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2").pack(side="left")

        # ── Calidad PDF ──
        tk.Label(f, text="Calidad PDF:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=12, column=0, sticky="w")
        self._calidad_pdf = tk.StringVar(value="Alta (400 DPI)")
        ttk.Combobox(f, textvariable=self._calidad_pdf,
                     values=list(CALIDADES_PDF.keys()),
                     state="readonly", font=FONT_LABEL).grid(
                     row=13, column=0, sticky="ew", pady=(2, 8))

        # ── Origen datos tabla ──
        tk.Label(f, text="Datos de tabla:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=14, column=0, sticky="w")
        self._origen_datos = tk.StringVar(value="Shapefile (capa cargada)")
        cb_origen = ttk.Combobox(
            f, textvariable=self._origen_datos,
            values=["Shapefile (capa cargada)", "Archivo Excel (.xlsx)"],
            state="readonly", font=FONT_LABEL)
        cb_origen.grid(row=15, column=0, sticky="ew", pady=(2, 4))
        cb_origen.bind("<<ComboboxSelected>>", self._on_origen_datos_changed)

        self._ruta_excel = tk.StringVar(value="")
        self._frame_excel = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_excel.grid(row=16, column=0, sticky="ew", pady=(0, 4))
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
        tk.Label(self._frame_hoja, text="Hoja:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left")
        self._hoja_excel = tk.StringVar(value="")
        self._cb_hoja = ttk.Combobox(self._frame_hoja,
                                      textvariable=self._hoja_excel,
                                      state="readonly", font=FONT_SMALL, width=20)
        self._cb_hoja.pack(side="left", padx=(4, 0))
        self._cb_hoja.bind("<<ComboboxSelected>>", self._on_hoja_changed)

        # Campo enlace: SHP ↔ Excel
        self._frame_enlace = tk.Frame(self._frame_excel, bg=COLOR_PANEL)
        self._frame_enlace.pack(side="top", fill="x", pady=(4, 0))

        tk.Label(self._frame_enlace, text="Campo enlace SHP:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO
                 ).grid(row=0, column=0, sticky="w")
        self._campo_enlace_shp = tk.StringVar(value="")
        self._cb_enlace_shp = ttk.Combobox(
            self._frame_enlace, textvariable=self._campo_enlace_shp,
            state="readonly", font=FONT_SMALL, width=18)
        self._cb_enlace_shp.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        tk.Label(self._frame_enlace, text="Campo enlace Excel:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO
                 ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._campo_enlace_excel = tk.StringVar(value="")
        self._cb_enlace_excel = ttk.Combobox(
            self._frame_enlace, textvariable=self._campo_enlace_excel,
            state="readonly", font=FONT_SMALL, width=18)
        self._cb_enlace_excel.grid(row=1, column=1, sticky="ew", padx=(4, 0),
                                    pady=(2, 0))
        self._frame_enlace.columnconfigure(1, weight=1)

        # Checkboxes de columnas Excel a incluir
        tk.Label(self._frame_excel, text="Columnas a incluir:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO
                 ).pack(side="top", anchor="w", pady=(4, 2))

        self._frame_cols_excel = tk.Frame(self._frame_excel, bg=COLOR_PANEL)
        self._frame_cols_excel.pack(side="top", fill="x")
        self._check_cols_excel = {}  # {nombre_col: BooleanVar}
        self._widgets_cols_excel = []

        self._frame_excel.grid_remove()  # Oculto por defecto

        # ── Nombre de archivo ──
        tk.Label(f, text="Nombre de archivo:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=17, column=0, sticky="w")

        # Presets
        self._presets_nombre = {
            "plano_{num}_{nombre}": "Nº + Nombre infraestructura",
            "plano_{num}": "Solo número de plano",
            "{nombre}": "Solo nombre infraestructura",
            "plano_{campo}_{num}": "Campo agrupación + Nº",
        }
        self._preset_nombre = tk.StringVar(value="Nº + Nombre infraestructura")
        cb_preset = ttk.Combobox(
            f, textvariable=self._preset_nombre,
            values=list(self._presets_nombre.values()),
            state="readonly", font=FONT_SMALL,
        )
        cb_preset.grid(row=18, column=0, sticky="ew", pady=(2, 2))
        cb_preset.bind("<<ComboboxSelected>>", self._on_preset_nombre)

        self.patron_nombre = tk.StringVar(value="plano_{num}_{nombre}")
        tk.Entry(f, textvariable=self.patron_nombre, font=FONT_SMALL,
                 bg=COLOR_ENTRY, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=19, column=0, sticky="ew", pady=(2, 0))

        # Preview
        self._lbl_preview_nombre = tk.Label(
            f, text="Ej: plano_0001_CortafuegosNorte.pdf",
            font=("Helvetica", 8), bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_preview_nombre.grid(row=20, column=0, sticky="w", pady=(0, 8))
        self.patron_nombre.trace_add("write", self._actualizar_preview_nombre)

        # ── Carpeta de salida ──
        tk.Label(f, text="Carpeta de salida:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(row=21, column=0, sticky="w")
        self.salida = tk.StringVar(value=str(Path.home() / "Planos_Forestales"))
        tk.Label(f, textvariable=self.salida, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=22, column=0, sticky="w")
        crear_boton(f, "Seleccionar carpeta", self._elegir_carpeta,
                    icono="\U0001f4c1").grid(row=23, column=0, sticky="ew", pady=(4, 4))

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
        """Devuelve la escala manual o None si es automática."""
        txt = self._escala_manual.get().replace(",", "").strip()
        if txt.startswith("0"):
            return None
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
        # Find the pattern key for this label
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
                text="Ej: (patrón inválido)")

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

    # ── Ráster local ──────────────────────────────────────────────────

    _RASTER_FILETYPES = [
        ("Ráster georreferenciado", "*.tif *.tiff *.ecw *.jp2 *.img *.vrt"),
        ("GeoTIFF", "*.tif *.tiff"),
        ("ECW", "*.ecw"),
        ("JPEG2000", "*.jp2"),
        ("Todos", "*.*"),
    ]

    def _on_proveedor_changed(self, event=None):
        if self.proveedor.get() == "── Ráster local ──":
            self._frame_raster.grid()
        else:
            self._frame_raster.grid_remove()

    def _on_prov_loc_changed(self, event=None):
        if self._prov_localizacion.get() == "── Ráster local ──":
            self._frame_raster_loc.grid()
        else:
            self._frame_raster_loc.grid_remove()

    def _elegir_raster_general(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar ráster para mapa general",
            filetypes=self._RASTER_FILETYPES)
        if ruta:
            self._ruta_raster.set(ruta)
            self._lbl_raster.configure(text=Path(ruta).name)

    def _elegir_raster_localizacion(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar ráster para mapa de localización",
            filetypes=self._RASTER_FILETYPES)
        if ruta:
            self._ruta_raster_loc.set(ruta)
            self._lbl_raster_loc.configure(text=Path(ruta).name)

    # ── Origen datos tabla (Excel) ─────────────────────────────────────

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
            # Leer nombres de hojas y poblar combobox
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
        """Al cambiar de hoja, recargar columnas."""
        ruta = self._ruta_excel.get()
        hoja = self._hoja_excel.get()
        if ruta and hoja:
            self._cargar_columnas_excel(ruta, hoja)

    def _cargar_columnas_excel(self, ruta: str, hoja: str):
        """Lee las columnas de la hoja seleccionada y actualiza checkboxes y combos."""
        try:
            import pandas as pd
            df = pd.read_excel(ruta, sheet_name=hoja, engine="openpyxl", nrows=0)
            cols = list(df.columns)
        except Exception:
            cols = []
        self._poblar_columnas_excel(cols)
        # Actualizar combo enlace Excel
        self._cb_enlace_excel.configure(values=cols)
        if cols:
            self._campo_enlace_excel.set(cols[0])
        else:
            self._campo_enlace_excel.set("")

    def _poblar_columnas_excel(self, columnas: list):
        """Crea checkboxes para seleccionar qué columnas del Excel incluir."""
        for w in self._widgets_cols_excel:
            w.destroy()
        self._widgets_cols_excel.clear()
        self._check_cols_excel.clear()

        for col in columnas:
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(
                self._frame_cols_excel, text=col, variable=var,
                font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO,
                selectcolor=COLOR_BORDE, activebackground=COLOR_PANEL,
                cursor="hand2",
            )
            cb.pack(anchor="w", pady=1)
            self._check_cols_excel[col] = var
            self._widgets_cols_excel.append(cb)

    def actualizar_campos_shp_enlace(self, columnas: list):
        """Actualiza el combo de campo enlace SHP con las columnas del shapefile."""
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
        """Devuelve la lista de columnas del Excel seleccionadas por el usuario."""
        return [c for c, v in self._check_cols_excel.items() if v.get()]

    @property
    def ruta_raster_general(self) -> str:
        if self.proveedor.get() == "── Ráster local ──":
            return self._ruta_raster.get()
        return ""

    @property
    def ruta_raster_localizacion(self) -> str:
        if self._prov_localizacion.get() == "── Ráster local ──":
            return self._ruta_raster_loc.get()
        return ""
