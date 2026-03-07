"""
Motor principal de generación de planos cartográficos profesionales.

Orquesta la carga de capas, selección de escala, maquetación y exportación
a PDF individual o multipágina.
"""

import os
import threading

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt

from .escala import seleccionar_escala, FORMATOS, MARGENES_MM
from .cartografia import añadir_fondo_cartografico
from .maquetacion import MaquetadorPlano, ETIQUETAS_CAMPOS

# Campos esperados en el shapefile
CAMPOS_ATRIBUTOS = list(ETIQUETAS_CAMPOS.keys())


class GeneradorPlanos:
    """Motor principal de generación de planos cartográficos profesionales."""

    def __init__(self, config: dict = None):
        self.cfg = config or {}
        self.gdf_infra = None
        self.gdf_montes = None
        self._campo_mapeo = None  # {campo_esperado: campo_real}

    # ── Carga de capas ──────────────────────────────────────────────────

    def cargar_infraestructuras(self, ruta: str) -> tuple:
        """Carga shapefile de infraestructuras y reproyecta a EPSG:25830.

        Valida campos obligatorios y detecta campos con nombres distintos.
        Devuelve (ok, mensaje, campos_faltantes).
        """
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")
            self.gdf_infra = gdf

            # Validar campos
            cols = set(gdf.columns)
            presentes = [c for c in CAMPOS_ATRIBUTOS if c in cols]
            faltantes = [c for c in CAMPOS_ATRIBUTOS if c not in cols]

            self._campo_mapeo = None

            msg = f"\u2713 {len(gdf)} infraestructuras cargadas | CRS: {gdf.crs.name}"
            if faltantes:
                msg += f"\n  \u26a0 Campos no encontrados: {', '.join(faltantes)}"
                msg += f"\n  Campos disponibles: {', '.join(sorted(cols - {'geometry'}))}"

            return True, msg, faltantes
        except Exception as e:
            return False, f"Error al cargar shapefile: {e}", []

    def establecer_mapeo_campos(self, mapeo: dict):
        """Establece un mapeo de campos: {campo_esperado: campo_real_en_shapefile}."""
        self._campo_mapeo = mapeo

    def cargar_montes(self, ruta: str) -> tuple:
        """Carga shapefile de montes (opcional)."""
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")
            self.gdf_montes = gdf
            return True, f"\u2713 Capa montes: {len(gdf)} elementos"
        except Exception as e:
            return False, f"Error al cargar montes: {e}"

    def obtener_columnas_shapefile(self) -> list:
        """Devuelve las columnas disponibles en el shapefile (sin geometry)."""
        if self.gdf_infra is None:
            return []
        return [c for c in self.gdf_infra.columns if c != "geometry"]

    # ── Generación de plano individual ──────────────────────────────────

    def generar_plano(self, idx_fila: int, formato_key: str,
                      proveedor: str, transparencia_montes: float,
                      campos_visibles: list, color_infra: str,
                      salida_dir: str, callback_log=None) -> str:
        """Genera un plano individual para la fila idx_fila."""
        # En hilos separados usar backend Agg (no comparte estado)
        if threading.current_thread() is not threading.main_thread():
            matplotlib.use("Agg")

        def log(msg):
            if callback_log:
                callback_log(msg)

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        # Seleccionar escala automática
        escala = seleccionar_escala(geom, formato_key)
        log(f"  Escala elegida: 1:{escala:,}")

        # Crear maquetador
        maq = MaquetadorPlano(formato_key, escala)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        # Calcular extensión exacta del mapa (escala métrica real)
        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        # Fondo cartográfico (con fallback)
        gdf_view = self.gdf_infra.iloc[[idx_fila]].copy()
        añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)

        # Restaurar límites tras contextily (puede modificarlos)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Capa montes
        if self.gdf_montes is not None:
            montes_clip = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_clip.empty:
                alpha = transparencia_montes
                green = int(34 * alpha)
                montes_clip.plot(
                    ax=ax_map,
                    facecolor=f"#{green:02x}9922",
                    edgecolor="#1a5c10",
                    linewidth=0.8,
                    alpha=alpha,
                )

        # Infraestructuras de fondo (gris)
        infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
        if not infra_fondo.empty:
            infra_fondo.plot(
                ax=ax_map, color="#999999", linewidth=0.6,
                markersize=3, alpha=0.5,
            )

        # Infraestructura seleccionada (resaltada)
        gdf_sel = self.gdf_infra.iloc[[idx_fila]]
        geom_type = str(geom.geom_type).lower()
        if "point" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, markersize=12,
                         marker="o", zorder=5, edgecolor="white", linewidth=0.8)
        elif "line" in geom_type or "string" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, linewidth=2.5, zorder=5)
        else:
            gdf_sel.plot(ax=ax_map, facecolor=color_infra + "55",
                         edgecolor=color_infra, linewidth=1.8, zorder=5)

        # Restaurar límites de nuevo tras dibujar capas
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Grid UTM
        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)

        # Panel de atributos
        maq.dibujar_panel_atributos(row, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)

        # Mapa de posición
        cx, cy = geom.centroid.x, geom.centroid.y
        maq.dibujar_mapa_posicion(cx, cy)

        # Barra de escala + pie
        maq.dibujar_barra_escala(proveedor)

        # Cabecera
        maq.dibujar_cabecera(row)

        # Marcos profesionales
        maq.dibujar_marcos()

        # Guardar
        nombre_infra = str(row.get("Nombre_Infra", f"infra_{idx_fila:04d}"))
        nombre_infra = "".join(c for c in nombre_infra if c.isalnum() or c in "_ -")[:40]
        nombre_arch = f"plano_{idx_fila:04d}_{nombre_infra}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Generación en serie ─────────────────────────────────────────────

    def generar_serie(self, indices: list, formato_key: str, proveedor: str,
                      transparencia: float, campos: list, color_infra: str,
                      salida_dir: str, callback_log=None,
                      callback_progreso=None) -> list:
        """Genera planos en serie para los índices indicados."""
        rutas = []
        total = len(indices)
        for i, idx in enumerate(indices):
            nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx}")
            if callback_log:
                callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
            try:
                ruta = self.generar_plano(
                    idx_fila=idx,
                    formato_key=formato_key,
                    proveedor=proveedor,
                    transparencia_montes=transparencia,
                    campos_visibles=campos,
                    color_infra=color_infra,
                    salida_dir=salida_dir,
                    callback_log=callback_log,
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas

    def generar_pdf_multipagina(self, indices: list, formato_key: str,
                                 proveedor: str, transparencia: float,
                                 campos: list, color_infra: str,
                                 ruta_pdf: str, callback_log=None,
                                 callback_progreso=None) -> str:
        """Genera un único PDF multipágina con todos los planos.

        Usa matplotlib PdfPages para combinar los planos en un solo archivo.
        """
        from matplotlib.backends.backend_pdf import PdfPages

        if threading.current_thread() is not threading.main_thread():
            matplotlib.use("Agg")

        total = len(indices)

        with PdfPages(ruta_pdf) as pdf:
            for i, idx in enumerate(indices):
                nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx}")
                if callback_log:
                    callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
                try:
                    row = self.gdf_infra.iloc[idx]
                    geom = row.geometry

                    escala = seleccionar_escala(geom, formato_key)
                    maq = MaquetadorPlano(formato_key, escala)
                    fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

                    xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
                    maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

                    gdf_view = self.gdf_infra.iloc[[idx]].copy()
                    añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                              xmin=xmin, xmax=xmax,
                                              ymin=ymin, ymax=ymax)
                    ax_map.set_xlim(xmin, xmax)
                    ax_map.set_ylim(ymin, ymax)

                    if self.gdf_montes is not None:
                        montes_clip = self.gdf_montes.cx[xmin:xmax, ymin:ymax]
                        if not montes_clip.empty:
                            alpha = transparencia
                            green = int(34 * alpha)
                            montes_clip.plot(
                                ax=ax_map, facecolor=f"#{green:02x}9922",
                                edgecolor="#1a5c10", linewidth=0.8, alpha=alpha,
                            )

                    infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
                    if not infra_fondo.empty:
                        infra_fondo.plot(ax=ax_map, color="#999999",
                                         linewidth=0.6, markersize=3, alpha=0.5)

                    gdf_sel = self.gdf_infra.iloc[[idx]]
                    geom_type = str(geom.geom_type).lower()
                    if "point" in geom_type:
                        gdf_sel.plot(ax=ax_map, color=color_infra, markersize=12,
                                     marker="o", zorder=5, edgecolor="white", linewidth=0.8)
                    elif "line" in geom_type or "string" in geom_type:
                        gdf_sel.plot(ax=ax_map, color=color_infra, linewidth=2.5, zorder=5)
                    else:
                        gdf_sel.plot(ax=ax_map, facecolor=color_infra + "55",
                                     edgecolor=color_infra, linewidth=1.8, zorder=5)

                    ax_map.set_xlim(xmin, xmax)
                    ax_map.set_ylim(ymin, ymax)

                    maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
                    maq.dibujar_panel_atributos(row, campos,
                                                 campo_mapeo=self._campo_mapeo)

                    cx, cy = geom.centroid.x, geom.centroid.y
                    maq.dibujar_mapa_posicion(cx, cy)
                    maq.dibujar_barra_escala(proveedor)
                    maq.dibujar_cabecera(row)
                    maq.dibujar_marcos()

                    pdf.savefig(fig, dpi=150, facecolor="white")
                    plt.close(fig)

                    if callback_log:
                        callback_log(f"  \u2713 P\u00e1gina {i + 1} a\u00f1adida")
                except Exception as e:
                    if callback_log:
                        callback_log(f"  \u2717 Error: {e}")

                if callback_progreso:
                    callback_progreso(i + 1, total)

        if callback_log:
            callback_log(f"\n\u2713 PDF multipágina guardado: {ruta_pdf}")
        return ruta_pdf
