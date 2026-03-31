"""
Motor principal de generación de planos cartográficos profesionales.

Orquesta la carga de capas, selección de escala, maquetación y exportación
a PDF individual, multipágina o agrupado por campo. Integra capas extra,
simbología, etiquetas, vértices, leyenda, cajetín, portada e índice.
"""

import os
import threading
import traceback

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from shapely.ops import unary_union


class GeneracionCancelada(Exception):
    """Excepción lanzada cuando el usuario cancela la generación."""
    pass

from .escala import seleccionar_escala, FORMATOS, MARGENES_MM
from .cartografia import añadir_fondo_cartografico, añadir_fondo_raster_local
from .maquetacion import MaquetadorPlano, ETIQUETAS_CAMPOS, crear_portada, crear_indice
from .capas_extra import GestorCapasExtra
from .simbologia import GestorSimbologia
from .proyecto import cargar_lotes_csv
from ._utils_geo import (  # noqa: F401
    _asegurar_crs, _detectar_geom_type, _plot_gdf_por_tipo,
    _limpiar_tipos_mixtos, _auto_calcular_campos, _calcular_stats_grupo,
    _leer_geodatos,
)

# Campos esperados en el shapefile
CAMPOS_ATRIBUTOS = list(ETIQUETAS_CAMPOS.keys())


class GeneradorPlanos:
    """Motor principal de generación de planos cartográficos profesionales."""

    def __init__(self, config: dict = None):
        self.cfg = config or {}
        self.gdf_infra = None
        self.gdf_montes = None
        self._campo_mapeo = None  # {campo_esperado: campo_real}
        self.gestor_capas = GestorCapasExtra()
        self.gestor_simbologia = GestorSimbologia()
        self._cajetin = {}
        self._plantilla = {}
        self.config_infra = {}  # linewidth, alpha, linestyle, marker
        self.layout_key = "Plantilla 1 (Clásica)"
        self.dpi_figura = None   # None = default (400)
        self.dpi_guardado = None  # None = same as dpi_figura
        self.ruta_raster_general = ""       # Ráster local para fondo de mapa
        self.ruta_raster_localizacion = ""  # Ráster local para mapa de localización
        self.ruta_capa_localizacion = ""   # SHP/GDB propio para mapa de localización
        self.wms_custom_general = {}       # {"url":..., "capa":..., "formato":...}
        self.wfs_custom_general = {}       # {"url":..., "capa":...}
        self.wms_custom_localizacion = {}  # {"url":..., "capa":..., "formato":...}
        self.wfs_custom_localizacion = {}  # {"url":..., "capa":...}
        self.escala_localizacion = 250_000  # Escala configurable del mapa localización
        self.prov_localizacion = "WMS IGN (online)"
        self._df_excel = None               # DataFrame con datos de Excel para tabla
        self._campo_enlace_shp = ""
        self._campo_enlace_excel = ""
        self._columnas_excel = None
        self._cancelar = threading.Event()

    def cancelar_generacion(self):
        """Señala que la generación en curso debe detenerse."""
        self._cancelar.set()

    def _check_cancelado(self):
        """Lanza excepción si se ha solicitado cancelar."""
        if self._cancelar.is_set():
            raise GeneracionCancelada("Generación cancelada por el usuario.")

    # ── Configuración ────────────────────────────────────────────────────

    def set_cajetin(self, cajetin: dict):
        self._cajetin = cajetin or {}

    def set_plantilla(self, plantilla: dict):
        self._plantilla = plantilla or {}

    def cargar_excel_tabla(self, ruta: str, hoja: str = None,
                           campo_enlace_shp: str = None,
                           campo_enlace_excel: str = None,
                           columnas_activas: list = None):
        """Carga un archivo Excel para usar sus datos en la tabla lateral.

        Args:
            ruta: Ruta al archivo .xlsx
            hoja: Nombre de la hoja a leer
            campo_enlace_shp: Campo del shapefile para hacer el enlace
            campo_enlace_excel: Campo del Excel para hacer el enlace
            columnas_activas: Lista de columnas del Excel a incluir
        """
        import pandas as pd
        kwargs = {}
        if hoja:
            kwargs["sheet_name"] = hoja
        self._df_excel = pd.read_excel(ruta, engine="openpyxl", **kwargs)
        self._campo_enlace_shp = campo_enlace_shp or ""
        self._campo_enlace_excel = campo_enlace_excel or ""
        self._columnas_excel = columnas_activas  # None = todas

    def limpiar_excel_tabla(self):
        """Elimina los datos Excel cargados (vuelve a usar shapefile)."""
        self._df_excel = None
        self._campo_enlace_shp = ""
        self._campo_enlace_excel = ""
        self._columnas_excel = None

    def _obtener_filas_tabla(self, rows_shp, idx_fila=None):
        """Devuelve las filas para la tabla: de Excel si hay, o del shapefile.

        Si hay campo de enlace configurado, busca en el Excel la fila cuyo
        valor en campo_enlace_excel coincida con el valor de campo_enlace_shp
        de la fila del shapefile. Solo devuelve las columnas seleccionadas.
        """
        if self._df_excel is None:
            return rows_shp

        df = self._df_excel
        # Filtrar columnas seleccionadas
        if self._columnas_excel:
            # Siempre incluir el campo enlace para poder buscar
            cols = list(self._columnas_excel)
            if (self._campo_enlace_excel
                    and self._campo_enlace_excel not in cols):
                cols.insert(0, self._campo_enlace_excel)
            cols_validas = [c for c in cols if c in df.columns]
            df = df[cols_validas]

        # Sin campo enlace: fallback por índice
        if not self._campo_enlace_shp or not self._campo_enlace_excel:
            if idx_fila is not None and idx_fila < len(df):
                return [df.iloc[idx_fila]]
            return [df.iloc[i] for i in range(len(df))]

        # Buscar por campo enlace
        resultado = []
        for row_shp in rows_shp:
            valor_shp = row_shp.get(self._campo_enlace_shp, None)
            if valor_shp is None:
                continue
            # Buscar coincidencia en el Excel
            mask = df[self._campo_enlace_excel].astype(str) == str(valor_shp)
            coincidencias = df[mask]
            for _, fila_excel in coincidencias.iterrows():
                resultado.append(fila_excel)

        return resultado if resultado else rows_shp

    # ── Carga de capas ───────────────────────────────────────────────────

    def cargar_infraestructuras(self, ruta: str, layer: str = None) -> tuple:
        """Carga shapefile/GDB de infraestructuras y reproyecta a EPSG:25830."""
        try:
            gdf = _leer_geodatos(ruta, layer=layer)
            origen = f"capa '{layer}'" if layer else os.path.basename(ruta)
            gdf, aviso_crs = _asegurar_crs(gdf, origen)

            # Limpiar columnas con tipos mixtos (previene str<float TypeError)
            gdf = _limpiar_tipos_mixtos(gdf)

            # Auto-calcular longitud/superficie si no existen
            gdf = _auto_calcular_campos(gdf)

            # Resetear índice y construir índice espacial para .cx[]
            gdf = gdf.reset_index(drop=True)
            gdf.sindex

            self.gdf_infra = gdf

            cols = set(gdf.columns)
            faltantes = [c for c in CAMPOS_ATRIBUTOS if c not in cols]
            self._campo_mapeo = None

            msg = f"\u2713 {len(gdf)} infraestructuras cargadas ({origen}) | CRS: {gdf.crs.name}"
            if aviso_crs:
                msg += f"\n  {aviso_crs}"
            if faltantes:
                msg += f"\n  \u26a0 Campos no encontrados: {', '.join(faltantes)}"
                msg += f"\n  Campos disponibles: {', '.join(sorted(cols - {'geometry'}))}"

            return True, msg, faltantes
        except Exception as e:
            return False, f"Error al cargar capa: {e}", []

    def establecer_mapeo_campos(self, mapeo: dict):
        self._campo_mapeo = mapeo

    def cargar_montes(self, ruta: str, layer: str = None) -> tuple:
        try:
            gdf = _leer_geodatos(ruta, layer=layer)
            origen = f"capa '{layer}'" if layer else os.path.basename(ruta)
            gdf, aviso_crs = _asegurar_crs(gdf, origen)
            # Limpiar columnas con tipos mixtos
            gdf = _limpiar_tipos_mixtos(gdf)
            # Resetear índice y construir índice espacial para .cx[]
            gdf = gdf.reset_index(drop=True)
            gdf.sindex
            self.gdf_montes = gdf
            msg = f"\u2713 Capa montes ({origen}): {len(gdf)} elementos"
            if aviso_crs:
                msg += f"\n  {aviso_crs}"
            return True, msg
        except Exception as e:
            return False, f"Error al cargar montes: {e}"

    def obtener_columnas_shapefile(self) -> list:
        if self.gdf_infra is None:
            return []
        return [c for c in self.gdf_infra.columns if c != "geometry"]

    # ── Consulta para agrupación ─────────────────────────────────────────

    def obtener_valores_unicos(self, campo: str) -> list:
        if self.gdf_infra is None:
            return []
        campo_real = campo
        if self._campo_mapeo and campo in self._campo_mapeo:
            campo_real = self._campo_mapeo[campo]
        if campo_real not in self.gdf_infra.columns:
            return []
        valores = self.gdf_infra[campo_real].dropna().unique().tolist()
        return sorted([str(v) for v in valores])

    def obtener_indices_por_valor(self, campo: str, valor: str) -> list:
        if self.gdf_infra is None:
            return []
        campo_real = campo
        if self._campo_mapeo and campo in self._campo_mapeo:
            campo_real = self._campo_mapeo[campo]
        if campo_real not in self.gdf_infra.columns:
            return []
        mask = self.gdf_infra[campo_real].astype(str) == str(valor)
        return list(self.gdf_infra.index[mask])

    # ── Helpers internos ─────────────────────────────────────────────────

    def _añadir_fondo(self, ax_map, gdf_view, proveedor, xmin, xmax, ymin, ymax):
        """Añade fondo cartográfico usando ráster local, WMS/WFS propio o tiles."""
        # WMS propio
        if self.wms_custom_general:
            try:
                from .cartografia import descargar_wms_custom
                descargar_wms_custom(
                    ax_map, self.wms_custom_general["url"],
                    self.wms_custom_general["capa"],
                    xmin, xmax, ymin, ymax,
                    formato=self.wms_custom_general.get("formato", "image/png"))
                return
            except Exception:
                pass
        # WFS propio
        if self.wfs_custom_general:
            try:
                from .cartografia import descargar_wfs, dibujar_wfs_en_eje
                gdf_wfs = descargar_wfs(
                    self.wfs_custom_general["url"],
                    self.wfs_custom_general["capa"],
                    xmin, ymin, xmax, ymax)
                ax_map.set_facecolor("#E8E8E0")
                dibujar_wfs_en_eje(ax_map, gdf_wfs)
                return
            except Exception:
                pass
        # Ráster local
        if self.ruta_raster_general and os.path.isfile(self.ruta_raster_general):
            try:
                añadir_fondo_raster_local(ax_map, self.ruta_raster_general,
                                           xmin, xmax, ymin, ymax)
                return
            except Exception:
                pass  # Fallback a WMS
        añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)

    def _ensure_agg(self):
        if threading.current_thread() is not threading.main_thread():
            matplotlib.use("Agg")

    def _dibujar_capas_mapa(self, ax_map, gdf_sel, indices, xmin, xmax,
                             ymin, ymax, transparencia, color_infra):
        """Dibuja fondo de montes, capas extra, infra fondo e infra seleccionadas."""
        # Capa montes
        if self.gdf_montes is not None:
            montes_clip = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_clip.empty:
                alpha = transparencia
                campo_cat_montes = self.config_infra.get("campo_categoria_montes")
                if campo_cat_montes and campo_cat_montes in montes_clip.columns:
                    # Colorear por categoría
                    valores_unicos = montes_clip[campo_cat_montes].astype(str).unique()
                    for valor in valores_unicos:
                        simb = self.gestor_simbologia.obtener_simbologia_monte(
                            campo_cat_montes, valor)
                        mask = montes_clip[campo_cat_montes].astype(str) == valor
                        gdf_cat = montes_clip[mask]
                        if gdf_cat.empty:
                            continue
                        gdf_cat.plot(
                            ax=ax_map, facecolor=simb.facecolor,
                            edgecolor=simb.color, linewidth=float(simb.linewidth),
                            alpha=float(alpha), zorder=1,
                        )
                else:
                    # Color fijo
                    montes_clip.plot(
                        ax=ax_map, facecolor="#229922",
                        edgecolor="#1a5c10", linewidth=0.8, alpha=float(alpha),
                        zorder=1,
                    )

        # Capas extra
        self.gestor_capas.dibujar_en_mapa(
            ax_map, xmin, xmax, ymin, ymax, self.gestor_simbologia)

        # Infraestructuras de fondo (gris, todas en el viewport)
        infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
        if not infra_fondo.empty:
            infra_fondo.plot(
                ax=ax_map, color="#999999", linewidth=0.6,
                markersize=3, alpha=0.25, zorder=3,
            )

        # Infraestructuras seleccionadas (resaltadas)
        ci = self.config_infra
        lw = float(ci.get("linewidth", 2.5))
        alpha_infra = max(0.0, min(1.0, float(ci.get("alpha", 0.35))))
        campo_cat = ci.get("campo_categoria")

        # ── Categorización por campo ──
        if campo_cat and campo_cat in gdf_sel.columns:
            # Resolver campo real por mapeo si existe
            campo_real = campo_cat
            if self._campo_mapeo and campo_cat in self._campo_mapeo:
                campo_real = self._campo_mapeo[campo_cat]

            valores_unicos = gdf_sel[campo_real].astype(str).unique()
            for valor in valores_unicos:
                simb = self.gestor_simbologia.obtener_simbologia_infra(
                    campo_cat, valor)
                mask = gdf_sel[campo_real].astype(str) == valor
                gdf_cat = gdf_sel[mask]
                if gdf_cat.empty:
                    continue
                c = simb.color
                ls = simb.linestyle
                _plot_gdf_por_tipo(
                    gdf_cat, ax_map, alpha=alpha_infra, lw=lw, zorder=5,
                    color=c, linestyle=ls, marker=simb.marker,
                    facecolor=simb.facecolor)
        else:
            # Sin categoría: color único
            _plot_gdf_por_tipo(
                gdf_sel, ax_map, alpha=alpha_infra, lw=lw, zorder=5,
                color=color_infra)

    def _construir_items_leyenda(self, gdf_sel, color_infra,
                                  xmin=None, xmax=None, ymin=None, ymax=None):
        """Construye items de leyenda sólo con las infraestructuras seleccionadas."""
        items = []

        geom_type = _detectar_geom_type(gdf_sel)

        # Solo categorías presentes en las infraestructuras seleccionadas
        campo_cat = self.config_infra.get("campo_categoria")
        if campo_cat and campo_cat in gdf_sel.columns:
            campo_real = campo_cat
            if self._campo_mapeo and campo_cat in self._campo_mapeo:
                campo_real = self._campo_mapeo[campo_cat]
            valores_unicos = sorted(
                str(v) for v in gdf_sel[campo_real].dropna().unique()
            )
            for valor in valores_unicos:
                simb = self.gestor_simbologia.obtener_simbologia_infra(
                    campo_cat, valor)
                label = str(valor)[:25]
                items.append((label, simb.color, geom_type, simb.linestyle,
                              simb.marker, simb.facecolor))
        else:
            items.append(("Infraestructuras", color_infra, geom_type, "-", "o",
                           color_infra + "55"))

        # Montes (solo si hay montes visibles en el extent)
        if self.gdf_montes is not None:
            campo_cat_montes = self.config_infra.get("campo_categoria_montes")
            if xmin is not None:
                montes_vis = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            else:
                montes_vis = self.gdf_montes
            if not montes_vis.empty:
                if campo_cat_montes and campo_cat_montes in montes_vis.columns:
                    # Leyenda por categoría de montes
                    valores_visibles = sorted(
                        str(v) for v in montes_vis[campo_cat_montes].dropna().unique()
                    )
                    for valor in valores_visibles:
                        simb = self.gestor_simbologia.obtener_simbologia_monte(
                            campo_cat_montes, valor)
                        label = str(valor)[:25]
                        items.append((label, simb.color, "polygon", "-",
                                      None, simb.facecolor))
                else:
                    items.append(("Montes", "#1a5c10", "polygon", "-", None,
                                  "#22992244"))

        # Capas extra
        items.extend(self.gestor_capas.obtener_items_leyenda(self.gestor_simbologia))

        return items

    def _construir_items_categoria(self, gdf_sel,
                                     xmin=None, xmax=None, ymin=None, ymax=None):
        """Construye items de categoría sólo con las infra seleccionadas."""
        campo_cat = self.config_infra.get("campo_categoria")
        if not campo_cat or campo_cat not in gdf_sel.columns:
            return None

        items = []
        geom_type = _detectar_geom_type(gdf_sel)

        campo_real = campo_cat
        if self._campo_mapeo and campo_cat in self._campo_mapeo:
            campo_real = self._campo_mapeo[campo_cat]

        # Solo categorías de las infraestructuras seleccionadas para el plano
        valores_visibles = sorted(
            str(v) for v in gdf_sel[campo_real].dropna().unique()
        )

        for valor in valores_visibles:
            simb = self.gestor_simbologia.obtener_simbologia_infra(campo_cat, valor)
            label = str(valor)[:25]
            items.append((label, simb.color, geom_type, simb.linestyle,
                          simb.marker, simb.facecolor))
        return items if items else None

    def _construir_items_leyenda_separados(self, gdf_sel, color_infra,
                                              xmin=None, xmax=None,
                                              ymin=None, ymax=None):
        """Construye items de leyenda separados: infraestructuras y montes.

        Usado por Plantilla 2 (panel lateral) donde se muestran en 2 columnas.
        """
        items_infra = []
        items_montes = []

        geom_type = _detectar_geom_type(gdf_sel)

        campo_cat = self.config_infra.get("campo_categoria")
        if campo_cat and campo_cat in gdf_sel.columns:
            campo_real = campo_cat
            if self._campo_mapeo and campo_cat in self._campo_mapeo:
                campo_real = self._campo_mapeo[campo_cat]
            valores_unicos = sorted(
                str(v) for v in gdf_sel[campo_real].dropna().unique()
            )
            for valor in valores_unicos:
                simb = self.gestor_simbologia.obtener_simbologia_infra(
                    campo_cat, valor)
                label = str(valor)[:25]
                items_infra.append((label, simb.color, geom_type, simb.linestyle,
                                    simb.marker, simb.facecolor))
        else:
            items_infra.append(("Infraestructuras", color_infra, geom_type,
                                "-", "o", color_infra + "55"))

        # Montes
        if self.gdf_montes is not None:
            campo_cat_montes = self.config_infra.get("campo_categoria_montes")
            if xmin is not None:
                montes_vis = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            else:
                montes_vis = self.gdf_montes
            if not montes_vis.empty:
                if campo_cat_montes and campo_cat_montes in montes_vis.columns:
                    valores_visibles = sorted(
                        montes_vis[campo_cat_montes].astype(str).unique())
                    for valor in valores_visibles:
                        simb = self.gestor_simbologia.obtener_simbologia_monte(
                            campo_cat_montes, valor)
                        label = str(valor)[:25]
                        items_montes.append((label, simb.color, "polygon", "-",
                                             None, simb.facecolor))
                else:
                    items_montes.append(("Montes", "#1a5c10", "polygon", "-",
                                         None, "#22992244"))

        return items_infra, items_montes

    # ── Generación de plano individual ───────────────────────────────────

    def generar_plano(self, idx_fila: int, formato_key: str,
                      proveedor: str, transparencia_montes: float,
                      campos_visibles: list, color_infra: str,
                      salida_dir: str, escala_manual: int = None,
                      callback_log=None, campo_encabezado: str = None,
                      patron_nombre: str = None) -> str:
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        _es_lateral = self.layout_key == "Plantilla 2 (Panel lateral)"
        escala = seleccionar_escala(geom, formato_key, escala_manual,
                                    es_lateral=_es_lateral)
        log(f"  Escala elegida: 1:{escala:,}")

        maq = MaquetadorPlano(formato_key, escala, layout_key=self.layout_key, dpi=self.dpi_figura)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        gdf_view = self.gdf_infra.iloc[[idx_fila]]
        self._añadir_fondo(ax_map, gdf_view, proveedor, xmin, xmax, ymin, ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        gdf_sel = self.gdf_infra.iloc[[idx_fila]]
        self._dibujar_capas_mapa(ax_map, gdf_sel, [idx_fila],
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Etiquetas infraestructuras
        campo_etiq = self._cajetin.get("campo_etiqueta", "Nombre_Infra")
        if campo_etiq:
            maq.dibujar_etiquetas_infra(gdf_sel, campo_etiqueta=campo_etiq,
                                         campo_mapeo=self._campo_mapeo)
        # Etiquetas montes
        campo_etiq_m = self._cajetin.get("campo_etiqueta_montes", "")
        if campo_etiq_m and self.gdf_montes is not None:
            montes_vis = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_vis.empty:
                maq.dibujar_etiquetas_montes(montes_vis,
                                              campo_etiqueta=campo_etiq_m,
                                              campo_mapeo=self._campo_mapeo)

        # Leyenda y paneles según plantilla
        cx, cy = geom.centroid.x, geom.centroid.y

        # Filas para tabla/panel: Excel si está cargado, si no shapefile
        _filas_tabla = self._obtener_filas_tabla([row], idx_fila=idx_fila)

        if maq.es_lateral:
            # Plantilla 2: localización + tabla datos + leyenda + cajetín
            maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
            maq.dibujar_tabla_infra(_filas_tabla, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)
            items_inf, items_mon = self._construir_items_leyenda_separados(
                gdf_sel, color_infra, xmin, xmax, ymin, ymax)
            maq.dibujar_leyenda_lateral(items_inf, items_mon)
            maq.dibujar_cajetin_lateral(row, cajetin=self._cajetin,
                                         plantilla=self._plantilla,
                                         proveedor=proveedor,
                                         campo_mapeo=self._campo_mapeo)
        else:
            # Plantilla 1: layout clásico
            items_ley = self._construir_items_leyenda(gdf_sel, color_infra,
                                                       xmin, xmax, ymin, ymax)
            maq.dibujar_leyenda(items_ley)
            _fila_panel = _filas_tabla[0] if _filas_tabla else row
            maq.dibujar_panel_atributos(_fila_panel, campos_visibles,
                                         campo_mapeo=self._campo_mapeo,
                                         campo_encabezado=campo_encabezado)
            maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
            items_cat = self._construir_items_categoria(gdf_sel,
                                                         xmin, xmax, ymin, ymax)
            maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                      cajetin=self._cajetin,
                                      items_categoria=items_cat)
            maq.dibujar_cajetin(self._cajetin)

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
        maq.dibujar_escala_grafica_mapa()
        maq.dibujar_norte_en_mapa()
        maq.dibujar_cabecera(row, cajetin=self._cajetin, plantilla=self._plantilla)
        maq.dibujar_marcos(plantilla=self._plantilla, cajetin=self._cajetin)

        num_visible = idx_fila + 1
        nombre_infra = str(row.get("Nombre_Infra", f"infra_{num_visible:04d}"))
        nombre_infra_safe = "".join(c for c in nombre_infra if c.isalnum() or c in "_ -")[:40]

        if patron_nombre:
            nombre_base = patron_nombre.format(
                num=f"{num_visible:04d}", nombre=nombre_infra_safe,
                campo=nombre_infra_safe)
            nombre_base = "".join(c for c in nombre_base if c.isalnum() or c in "_ -.")[:80]
        else:
            nombre_base = f"plano_{num_visible:04d}_{nombre_infra_safe}"
        nombre_arch = f"{nombre_base}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out, dpi_save=self.dpi_guardado)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Generación de plano agrupado ─────────────────────────────────────

    def generar_plano_agrupado(self, indices: list, campo_grupo: str,
                                valor_grupo: str, formato_key: str,
                                proveedor: str, transparencia_montes: float,
                                campos_visibles: list, color_infra: str,
                                salida_dir: str, num_plano: int = 1,
                                escala_manual: int = None,
                                callback_log=None,
                                campo_encabezado: str = None,
                                patron_nombre: str = None) -> str:
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        gdf_grupo = self.gdf_infra.iloc[indices]
        rows = [self.gdf_infra.iloc[idx] for idx in indices]

        geom_union = unary_union(gdf_grupo.geometry)
        _es_lateral = self.layout_key == "Plantilla 2 (Panel lateral)"
        escala = seleccionar_escala(geom_union, formato_key, escala_manual,
                                    es_lateral=_es_lateral)
        log(f"  Escala elegida: 1:{escala:,} ({len(indices)} infraestructuras)")

        maq = MaquetadorPlano(formato_key, escala, layout_key=self.layout_key, dpi=self.dpi_figura)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom_union)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        self._añadir_fondo(ax_map, gdf_grupo, proveedor, xmin, xmax, ymin, ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        self._dibujar_capas_mapa(ax_map, gdf_grupo, indices,
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Etiquetas infraestructuras
        campo_etiq = self._cajetin.get("campo_etiqueta", "Nombre_Infra")
        if campo_etiq:
            maq.dibujar_etiquetas_infra(gdf_grupo, campo_etiqueta=campo_etiq,
                                         campo_mapeo=self._campo_mapeo)
        # Etiquetas montes
        campo_etiq_m = self._cajetin.get("campo_etiqueta_montes", "")
        if campo_etiq_m and self.gdf_montes is not None:
            montes_vis = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_vis.empty:
                maq.dibujar_etiquetas_montes(montes_vis,
                                              campo_etiqueta=campo_etiq_m,
                                              campo_mapeo=self._campo_mapeo)

        # Leyenda y paneles según plantilla
        cx, cy = geom_union.centroid.x, geom_union.centroid.y

        # Filas para tabla/panel: Excel si está cargado, si no shapefile
        _filas_tabla = self._obtener_filas_tabla(rows)

        if maq.es_lateral:
            maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
            maq.dibujar_tabla_infra(_filas_tabla, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)
            items_inf, items_mon = self._construir_items_leyenda_separados(
                gdf_grupo, color_infra, xmin, xmax, ymin, ymax)
            maq.dibujar_leyenda_lateral(items_inf, items_mon)
            maq.dibujar_cajetin_lateral(rows[0], cajetin=self._cajetin,
                                         plantilla=self._plantilla,
                                         num_plano=num_plano,
                                         proveedor=proveedor,
                                         campo_mapeo=self._campo_mapeo)
        else:
            items_ley = self._construir_items_leyenda(gdf_grupo, color_infra,
                                                       xmin, xmax, ymin, ymax)
            stats = _calcular_stats_grupo(gdf_grupo)
            maq.dibujar_leyenda(items_ley, stats_resumen=stats)
            maq.dibujar_panel_atributos_multi(_filas_tabla, campos_visibles,
                                               campo_mapeo=self._campo_mapeo,
                                               campo_encabezado=campo_encabezado)
            maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
            items_cat = self._construir_items_categoria(gdf_grupo,
                                                         xmin, xmax, ymin, ymax)
            maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                      cajetin=self._cajetin,
                                      items_categoria=items_cat)
            maq.dibujar_cajetin(self._cajetin)

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
        maq.dibujar_escala_grafica_mapa()
        maq.dibujar_norte_en_mapa()

        etiq_campo = ETIQUETAS_CAMPOS.get(campo_grupo, campo_grupo)
        titulo_grupo = f"{etiq_campo}: {valor_grupo}"
        maq.dibujar_cabecera(rows[0], titulo_grupo=titulo_grupo,
                              num_plano_override=num_plano,
                              cajetin=self._cajetin, plantilla=self._plantilla)
        maq.dibujar_marcos(plantilla=self._plantilla, cajetin=self._cajetin)

        nombre_safe = "".join(c for c in valor_grupo if c.isalnum() or c in "_ -")[:40]
        if patron_nombre:
            nombre_base = patron_nombre.format(
                num=f"{num_plano:04d}", nombre=nombre_safe,
                campo=nombre_safe)
            nombre_base = "".join(c for c in nombre_base if c.isalnum() or c in "_ -.")[:80]
        else:
            nombre_base = f"plano_grupo_{num_plano:04d}_{nombre_safe}"
        nombre_arch = f"{nombre_base}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out, dpi_save=self.dpi_guardado)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Vista previa en miniatura ────────────────────────────────────────

    def generar_vista_previa(self, idx_fila: int, formato_key: str,
                              proveedor: str, transparencia_montes: float,
                              campos_visibles: list, color_infra: str,
                              escala_manual: int = None,
                              campo_encabezado: str = None):
        """Genera una vista previa (figure matplotlib) a baja resolución.

        Devuelve el objeto ``plt.Figure`` sin guardarlo a disco, para
        mostrarlo en un popup de la GUI.
        """
        self._ensure_agg()

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        _es_lateral = self.layout_key == "Plantilla 2 (Panel lateral)"
        escala = seleccionar_escala(geom, formato_key, escala_manual,
                                    es_lateral=_es_lateral)

        # DPI bajo para preview rápido
        dpi_preview = 72
        maq = MaquetadorPlano(formato_key, escala,
                               layout_key=self.layout_key, dpi=dpi_preview)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        gdf_view = self.gdf_infra.iloc[[idx_fila]]
        self._añadir_fondo(ax_map, gdf_view, proveedor,
                           xmin, xmax, ymin, ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        gdf_sel = self.gdf_infra.iloc[[idx_fila]]
        self._dibujar_capas_mapa(ax_map, gdf_sel, [idx_fila],
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Etiquetas infraestructuras
        campo_etiq = self._cajetin.get("campo_etiqueta", "Nombre_Infra")
        if campo_etiq:
            maq.dibujar_etiquetas_infra(gdf_sel, campo_etiqueta=campo_etiq,
                                         campo_mapeo=self._campo_mapeo)

        cx, cy = geom.centroid.x, geom.centroid.y
        _filas_tabla = self._obtener_filas_tabla([row], idx_fila=idx_fila)

        if maq.es_lateral:
            maq.dibujar_mapa_posicion(
                cx, cy,
                ruta_raster_loc=self.ruta_raster_localizacion,
                escala_loc=self.escala_localizacion,
                prov_localizacion=self.prov_localizacion,
                wms_custom=self.wms_custom_localizacion,
                wfs_custom=self.wfs_custom_localizacion,
                ruta_capa_loc=self.ruta_capa_localizacion)
            maq.dibujar_tabla_infra(_filas_tabla, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)
            items_inf, items_mon = self._construir_items_leyenda_separados(
                gdf_sel, color_infra, xmin, xmax, ymin, ymax)
            maq.dibujar_leyenda_lateral(items_inf, items_mon)
            maq.dibujar_cajetin_lateral(row, cajetin=self._cajetin,
                                         plantilla=self._plantilla,
                                         proveedor=proveedor,
                                         campo_mapeo=self._campo_mapeo)
        else:
            items_ley = self._construir_items_leyenda(gdf_sel, color_infra,
                                                       xmin, xmax, ymin, ymax)
            maq.dibujar_leyenda(items_ley)
            _fila_panel = _filas_tabla[0] if _filas_tabla else row
            maq.dibujar_panel_atributos(_fila_panel, campos_visibles,
                                         campo_mapeo=self._campo_mapeo,
                                         campo_encabezado=campo_encabezado)
            maq.dibujar_mapa_posicion(
                cx, cy,
                ruta_raster_loc=self.ruta_raster_localizacion,
                escala_loc=self.escala_localizacion,
                prov_localizacion=self.prov_localizacion,
                wms_custom=self.wms_custom_localizacion,
                wfs_custom=self.wfs_custom_localizacion,
                ruta_capa_loc=self.ruta_capa_localizacion)
            items_cat = self._construir_items_categoria(gdf_sel,
                                                         xmin, xmax, ymin, ymax)
            maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                      cajetin=self._cajetin,
                                      items_categoria=items_cat)
            maq.dibujar_cajetin(self._cajetin)

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
        maq.dibujar_escala_grafica_mapa()
        maq.dibujar_norte_en_mapa()
        maq.dibujar_cabecera(row, cajetin=self._cajetin,
                              plantilla=self._plantilla)
        maq.dibujar_marcos(plantilla=self._plantilla, cajetin=self._cajetin)

        return fig

    # ── Mapa guía / índice cartográfico ───────────────────────────────────

    def generar_mapa_guia(self, indices: list, formato_key: str,
                           transparencia_montes: float = 0.3,
                           salida_dir: str = None,
                           callback_log=None) -> "plt.Figure | str":
        """Genera un mapa guía que muestra todas las infraestructuras
        numeradas.

        Si *salida_dir* es ``None``, devuelve la figura (para popup).
        Si se proporciona, guarda un PDF y devuelve la ruta.
        """
        from .maquetacion import crear_mapa_guia

        self._ensure_agg()

        campo_nombre = self._cajetin.get("campo_etiqueta", "Nombre_Infra")
        fig = crear_mapa_guia(
            formato_key=formato_key,
            gdf_infra=self.gdf_infra,
            indices=indices,
            gdf_montes=self.gdf_montes,
            transparencia_montes=transparencia_montes,
            plantilla=self._plantilla,
            cajetin=self._cajetin,
            campo_nombre=campo_nombre,
        )

        if salida_dir is not None:
            ruta_out = os.path.join(salida_dir, "mapa_guia.pdf")
            fig.savefig(ruta_out, format="pdf",
                        dpi=self.dpi_guardado or 300, facecolor="white")
            plt.close(fig)
            if callback_log:
                callback_log(f"  \u2713 Mapa guía guardado: mapa_guia.pdf")
            return ruta_out

        return fig

    # ── Generación en serie ──────────────────────────────────────────────

    def generar_serie(self, indices: list, formato_key: str, proveedor: str,
                      transparencia: float, campos: list, color_infra: str,
                      salida_dir: str, escala_manual: int = None,
                      callback_log=None, callback_progreso=None,
                      campo_encabezado: str = None,
                      patron_nombre: str = None) -> list:
        rutas = []
        total = len(indices)
        for i, idx in enumerate(indices):
            self._check_cancelado()
            nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx + 1}")
            if callback_log:
                callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
            try:
                ruta = self.generar_plano(
                    idx_fila=idx, formato_key=formato_key,
                    proveedor=proveedor, transparencia_montes=transparencia,
                    campos_visibles=campos, color_infra=color_infra,
                    salida_dir=salida_dir, escala_manual=escala_manual,
                    callback_log=callback_log,
                    campo_encabezado=campo_encabezado,
                    patron_nombre=patron_nombre,
                )
                rutas.append(ruta)
            except GeneracionCancelada:
                raise
            except Exception as e:
                tb = traceback.format_exc()
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}\n{tb}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas

    # ── Generación agrupada en serie ─────────────────────────────────────

    def generar_serie_agrupada(self, campo_grupo: str, valores: list,
                                formato_key: str, proveedor: str,
                                transparencia: float, campos: list,
                                color_infra: str, salida_dir: str,
                                escala_manual: int = None,
                                callback_log=None,
                                callback_progreso=None,
                                indices_filtro: dict = None,
                                campo_encabezado: str = None,
                                patron_nombre: str = None) -> list:
        rutas = []
        total = len(valores)
        for i, valor in enumerate(valores):
            self._check_cancelado()
            if callback_log:
                callback_log(f"\n[{i + 1}/{total}] Grupo: {campo_grupo} = {valor}")
            indices = self.obtener_indices_por_valor(campo_grupo, valor)
            # Aplicar filtro de infraestructuras individuales si existe
            if indices_filtro and valor in indices_filtro:
                filtro = set(indices_filtro[valor])
                indices = [idx for idx in indices if idx in filtro]
            if not indices:
                if callback_log:
                    callback_log(f"  \u26a0 Sin infraestructuras para {valor}")
                if callback_progreso:
                    callback_progreso(i + 1, total)
                continue
            try:
                ruta = self.generar_plano_agrupado(
                    indices=indices, campo_grupo=campo_grupo,
                    valor_grupo=valor, formato_key=formato_key,
                    proveedor=proveedor, transparencia_montes=transparencia,
                    campos_visibles=campos, color_infra=color_infra,
                    salida_dir=salida_dir, num_plano=i + 1,
                    escala_manual=escala_manual,
                    callback_log=callback_log,
                    campo_encabezado=campo_encabezado,
                    patron_nombre=patron_nombre,
                )
                rutas.append(ruta)
            except GeneracionCancelada:
                raise
            except Exception as e:
                tb = traceback.format_exc()
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}\n{tb}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas

    # ── PDF multipágina ──────────────────────────────────────────────────

    def generar_pdf_multipagina(self, indices: list, formato_key: str,
                                 proveedor: str, transparencia: float,
                                 campos: list, color_infra: str,
                                 ruta_pdf: str, escala_manual: int = None,
                                 incluir_portada: bool = False,
                                 callback_log=None,
                                 callback_progreso=None,
                                 campo_encabezado: str = None,
                                 patron_nombre: str = None) -> str:
        from matplotlib.backends.backend_pdf import PdfPages

        self._ensure_agg()
        total = len(indices)

        with PdfPages(ruta_pdf) as pdf:
            # Portada
            if incluir_portada:
                titulo = self._cajetin.get("proyecto", "PLANOS FORESTALES")
                subtitulo = self._cajetin.get("subtitulo",
                                               "PLANO DE INFRAESTRUCTURA FORESTAL")
                datos = {
                    "N\u00ba de planos": total,
                    "Formato": formato_key,
                    "Cartograf\u00eda": proveedor,
                }
                fig_portada = crear_portada(
                    formato_key, titulo, subtitulo,
                    datos_extra=datos,
                    cajetin=self._cajetin, plantilla=self._plantilla,
                )
                pdf.savefig(fig_portada, dpi=self.dpi_guardado or 300, facecolor="white")
                plt.close(fig_portada)
                if callback_log:
                    callback_log("  \u2713 Portada a\u00f1adida")

                # Índice
                items_idx = []
                for i, idx in enumerate(indices):
                    nombre = str(self.gdf_infra.iloc[idx].get(
                        "Nombre_Infra", f"Infraestructura #{idx + 1}"))
                    items_idx.append((i + 1, nombre, ""))
                fig_indice = crear_indice(formato_key, items_idx,
                                           plantilla=self._plantilla)
                pdf.savefig(fig_indice, dpi=self.dpi_guardado or 300, facecolor="white")
                plt.close(fig_indice)
                if callback_log:
                    callback_log("  \u2713 \u00cdndice a\u00f1adido")

                # Mapa guía cartográfico
                try:
                    from .maquetacion import crear_mapa_guia
                    fig_guia = crear_mapa_guia(
                        formato_key=formato_key,
                        gdf_infra=self.gdf_infra,
                        indices=indices,
                        gdf_montes=self.gdf_montes,
                        transparencia_montes=transparencia,
                        plantilla=self._plantilla,
                        cajetin=self._cajetin,
                    )
                    pdf.savefig(fig_guia, dpi=self.dpi_guardado or 300,
                                facecolor="white")
                    plt.close(fig_guia)
                    if callback_log:
                        callback_log("  \u2713 Mapa gu\u00eda a\u00f1adido")
                except Exception as e:
                    if callback_log:
                        callback_log(f"  \u26a0 No se pudo generar mapa gu\u00eda: {e}")

            # Planos
            for i, idx in enumerate(indices):
                self._check_cancelado()
                nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx + 1}")
                if callback_log:
                    callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
                try:
                    row = self.gdf_infra.iloc[idx]
                    geom = row.geometry

                    _es_lateral = self.layout_key == "Plantilla 2 (Panel lateral)"
                    escala = seleccionar_escala(geom, formato_key, escala_manual,
                                                es_lateral=_es_lateral)
                    maq = MaquetadorPlano(formato_key, escala, layout_key=self.layout_key, dpi=self.dpi_figura)
                    fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

                    xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
                    maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

                    gdf_view = self.gdf_infra.iloc[[idx]]
                    self._añadir_fondo(ax_map, gdf_view, proveedor,
                                       xmin, xmax, ymin, ymax)
                    ax_map.set_xlim(xmin, xmax)
                    ax_map.set_ylim(ymin, ymax)

                    gdf_sel = self.gdf_infra.iloc[[idx]]
                    self._dibujar_capas_mapa(ax_map, gdf_sel, [idx],
                                              xmin, xmax, ymin, ymax,
                                              transparencia, color_infra)

                    ax_map.set_xlim(xmin, xmax)
                    ax_map.set_ylim(ymin, ymax)

                    # Etiquetas infraestructuras
                    campo_etiq = self._cajetin.get("campo_etiqueta", "Nombre_Infra")
                    if campo_etiq:
                        maq.dibujar_etiquetas_infra(
                            gdf_sel, campo_etiqueta=campo_etiq,
                            campo_mapeo=self._campo_mapeo)
                    # Etiquetas montes
                    campo_etiq_m = self._cajetin.get("campo_etiqueta_montes", "")
                    if campo_etiq_m and self.gdf_montes is not None:
                        montes_vis = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
                        if not montes_vis.empty:
                            maq.dibujar_etiquetas_montes(
                                montes_vis, campo_etiqueta=campo_etiq_m,
                                campo_mapeo=self._campo_mapeo)

                    # Leyenda y paneles según plantilla
                    cx, cy = geom.centroid.x, geom.centroid.y

                    # Filas para tabla/panel: Excel si está cargado, si no shapefile
                    _filas_tabla = self._obtener_filas_tabla([row], idx_fila=idx)

                    if maq.es_lateral:
                        maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
                        maq.dibujar_tabla_infra(_filas_tabla, campos,
                                                 campo_mapeo=self._campo_mapeo)
                        items_inf, items_mon = self._construir_items_leyenda_separados(
                            gdf_sel, color_infra, xmin, xmax, ymin, ymax)
                        maq.dibujar_leyenda_lateral(items_inf, items_mon)
                        maq.dibujar_cajetin_lateral(row, cajetin=self._cajetin,
                                                     plantilla=self._plantilla,
                                                     proveedor=proveedor,
                                                     campo_mapeo=self._campo_mapeo)
                    else:
                        items_ley = self._construir_items_leyenda(gdf_sel, color_infra)
                        maq.dibujar_leyenda(items_ley)
                        _fila_panel = _filas_tabla[0] if _filas_tabla else row
                        maq.dibujar_panel_atributos(_fila_panel, campos,
                                                     campo_mapeo=self._campo_mapeo,
                                                     campo_encabezado=campo_encabezado)
                        maq.dibujar_mapa_posicion(
                                cx, cy,
                                ruta_raster_loc=self.ruta_raster_localizacion,
                                escala_loc=self.escala_localizacion,
                                prov_localizacion=self.prov_localizacion,
                                wms_custom=self.wms_custom_localizacion,
                                wfs_custom=self.wfs_custom_localizacion,
                                ruta_capa_loc=self.ruta_capa_localizacion)
                        items_cat = self._construir_items_categoria(gdf_sel)
                        maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                                  cajetin=self._cajetin,
                                                  items_categoria=items_cat)
                        maq.dibujar_cajetin(self._cajetin)

                    maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
                    maq.dibujar_escala_grafica_mapa()
                    maq.dibujar_norte_en_mapa()
                    maq.dibujar_cabecera(row, cajetin=self._cajetin,
                                          plantilla=self._plantilla)
                    maq.dibujar_marcos(plantilla=self._plantilla, cajetin=self._cajetin)

                    pdf.savefig(fig, dpi=self.dpi_guardado or 300, facecolor="white")
                    plt.close(fig)

                    if callback_log:
                        callback_log(f"  \u2713 P\u00e1gina {i + 1} a\u00f1adida")
                except Exception as e:
                    tb = traceback.format_exc()
                    if callback_log:
                        callback_log(f"  \u2717 Error: {e}\n{tb}")

                if callback_progreso:
                    callback_progreso(i + 1, total)

        if callback_log:
            callback_log(f"\n\u2713 PDF multipágina guardado: {ruta_pdf}")
        return ruta_pdf

    # ── Generación por lotes desde CSV ───────────────────────────────────

    def generar_lotes_csv(self, ruta_csv: str, proveedor: str,
                           transparencia: float, campos: list,
                           color_infra: str, escala_manual: int = None,
                           callback_log=None,
                           callback_progreso=None,
                           campo_encabezado: str = None) -> list:
        """Genera planos por lotes a partir de un CSV de configuración."""
        lotes = cargar_lotes_csv(ruta_csv)
        if not lotes:
            if callback_log:
                callback_log("No se encontraron lotes v\u00e1lidos en el CSV.", "warn")
            return []

        rutas = []
        total = len(lotes)
        for i, lote in enumerate(lotes):
            self._check_cancelado()
            if callback_log:
                callback_log(
                    f"\n[{i + 1}/{total}] Lote: {lote.get('nombre', lote['ruta_shp'])}")

            ok, msg, faltantes = self.cargar_infraestructuras(lote["ruta_shp"])
            if not ok:
                if callback_log:
                    callback_log(f"  \u2717 {msg}", "error")
                if callback_progreso:
                    callback_progreso(i + 1, total)
                continue

            formato = lote.get("formato", "A3 Horizontal")
            carpeta = lote.get("carpeta_salida", ".")
            os.makedirs(carpeta, exist_ok=True)

            indices = list(range(len(self.gdf_infra)))
            try:
                resultados = self.generar_serie(
                    indices=indices, formato_key=formato,
                    proveedor=proveedor, transparencia=transparencia,
                    campos=campos, color_infra=color_infra,
                    salida_dir=carpeta, escala_manual=escala_manual,
                    callback_log=callback_log,
                    campo_encabezado=campo_encabezado,
                )
                rutas.extend(resultados)
            except Exception as e:
                tb = traceback.format_exc()
                if callback_log:
                    callback_log(f"  \u2717 Error en lote: {e}\n{tb}", "error")

            if callback_progreso:
                callback_progreso(i + 1, total)

        return rutas
