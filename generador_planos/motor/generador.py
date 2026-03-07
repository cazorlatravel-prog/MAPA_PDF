"""
Motor principal de generación de planos cartográficos profesionales.

Orquesta la carga de capas, selección de escala, maquetación y exportación
a PDF individual, multipágina o agrupado por campo. Integra capas extra,
simbología, etiquetas, vértices, leyenda, cajetín, portada e índice.
"""

import os
import threading

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from shapely.ops import unary_union

from .escala import seleccionar_escala, FORMATOS, MARGENES_MM
from .cartografia import añadir_fondo_cartografico
from .maquetacion import MaquetadorPlano, ETIQUETAS_CAMPOS, crear_portada, crear_indice
from .capas_extra import GestorCapasExtra
from .simbologia import GestorSimbologia
from .proyecto import cargar_lotes_csv

# Campos esperados en el shapefile
CAMPOS_ATRIBUTOS = list(ETIQUETAS_CAMPOS.keys())


def _auto_calcular_campos(gdf):
    """Calcula longitud/superficie automáticamente si no existen en el GDF."""
    if "Longitud" not in gdf.columns:
        def _long(g):
            gt = str(g.geom_type).lower()
            if "line" in gt or "string" in gt:
                return round(g.length, 1)
            return 0.0
        gdf["Longitud"] = gdf.geometry.apply(_long)

    if "Superficie" not in gdf.columns:
        def _sup(g):
            gt = str(g.geom_type).lower()
            if "polygon" in gt:
                return round(g.area / 10000, 4)  # m² → ha
            return 0.0
        gdf["Superficie"] = gdf.geometry.apply(_sup)

    return gdf


def _calcular_stats_grupo(gdf_grupo):
    """Calcula estadísticas resumen para un grupo de infraestructuras."""
    stats = {"num_infraestructuras": len(gdf_grupo)}

    if "Longitud" in gdf_grupo.columns:
        total_m = gdf_grupo["Longitud"].astype(float).sum()
        stats["total_longitud_km"] = total_m / 1000.0

    if "Superficie" in gdf_grupo.columns:
        total_ha = gdf_grupo["Superficie"].astype(float).sum()
        stats["total_superficie_ha"] = total_ha

    return stats


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

    # ── Configuración ────────────────────────────────────────────────────

    def set_cajetin(self, cajetin: dict):
        self._cajetin = cajetin or {}

    def set_plantilla(self, plantilla: dict):
        self._plantilla = plantilla or {}

    # ── Carga de capas ───────────────────────────────────────────────────

    def cargar_infraestructuras(self, ruta: str) -> tuple:
        """Carga shapefile de infraestructuras y reproyecta a EPSG:25830."""
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")

            # Auto-calcular longitud/superficie si no existen
            gdf = _auto_calcular_campos(gdf)

            self.gdf_infra = gdf

            cols = set(gdf.columns)
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
        self._campo_mapeo = mapeo

    def cargar_montes(self, ruta: str) -> tuple:
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
                green = int(34 * alpha)
                montes_clip.plot(
                    ax=ax_map, facecolor=f"#{green:02x}9922",
                    edgecolor="#1a5c10", linewidth=0.8, alpha=alpha,
                )

        # Capas extra
        self.gestor_capas.dibujar_en_mapa(
            ax_map, xmin, xmax, ymin, ymax, self.gestor_simbologia)

        # Infraestructuras de fondo (gris, todas en el viewport)
        infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
        if not infra_fondo.empty:
            infra_fondo.plot(
                ax=ax_map, color="#999999", linewidth=0.6,
                markersize=3, alpha=0.5,
            )

        # Infraestructuras seleccionadas (resaltadas)
        geom_type = ""
        for geom_single in gdf_sel.geometry:
            geom_type = str(geom_single.geom_type).lower()
            break

        if "point" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, markersize=12,
                         marker="o", zorder=5, edgecolor="white", linewidth=0.8)
        elif "line" in geom_type or "string" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, linewidth=2.5, zorder=5)
        else:
            gdf_sel.plot(ax=ax_map, facecolor=color_infra + "55",
                         edgecolor=color_infra, linewidth=1.8, zorder=5)

    def _construir_items_leyenda(self, gdf_sel, color_infra):
        """Construye items de leyenda para infra + capas extra."""
        items = []

        # Infraestructuras
        geom_type = ""
        for g in gdf_sel.geometry:
            if g is not None:
                geom_type = str(g.geom_type).lower()
                break
        items.append(("Infraestructuras", color_infra, geom_type, "-", "o",
                       color_infra + "55"))

        # Montes
        if self.gdf_montes is not None:
            items.append(("Montes", "#1a5c10", "polygon", "-", None, "#22992244"))

        # Capas extra
        items.extend(self.gestor_capas.obtener_items_leyenda(self.gestor_simbologia))

        return items

    # ── Generación de plano individual ───────────────────────────────────

    def generar_plano(self, idx_fila: int, formato_key: str,
                      proveedor: str, transparencia_montes: float,
                      campos_visibles: list, color_infra: str,
                      salida_dir: str, escala_manual: int = None,
                      callback_log=None) -> str:
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        escala = seleccionar_escala(geom, formato_key, escala_manual)
        log(f"  Escala elegida: 1:{escala:,}")

        maq = MaquetadorPlano(formato_key, escala)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        gdf_view = self.gdf_infra.iloc[[idx_fila]].copy()
        añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        gdf_sel = self.gdf_infra.iloc[[idx_fila]]
        self._dibujar_capas_mapa(ax_map, gdf_sel, [idx_fila],
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Etiquetas
        maq.dibujar_etiquetas_infra(gdf_sel, campo_mapeo=self._campo_mapeo)

        # Leyenda
        items_ley = self._construir_items_leyenda(gdf_sel, color_infra)
        maq.dibujar_leyenda(items_ley)

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
        maq.dibujar_panel_atributos(row, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)

        cx, cy = geom.centroid.x, geom.centroid.y
        maq.dibujar_mapa_posicion(cx, cy)
        maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                  cajetin=self._cajetin)
        maq.dibujar_cabecera(row, cajetin=self._cajetin, plantilla=self._plantilla)
        maq.dibujar_cajetin(self._cajetin)
        maq.dibujar_marcos(plantilla=self._plantilla)

        nombre_infra = str(row.get("Nombre_Infra", f"infra_{idx_fila:04d}"))
        nombre_infra = "".join(c for c in nombre_infra if c.isalnum() or c in "_ -")[:40]
        nombre_arch = f"plano_{idx_fila:04d}_{nombre_infra}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Generación de plano agrupado ─────────────────────────────────────

    def generar_plano_agrupado(self, indices: list, campo_grupo: str,
                                valor_grupo: str, formato_key: str,
                                proveedor: str, transparencia_montes: float,
                                campos_visibles: list, color_infra: str,
                                salida_dir: str, num_plano: int = 1,
                                escala_manual: int = None,
                                callback_log=None) -> str:
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        gdf_grupo = self.gdf_infra.iloc[indices]
        rows = [self.gdf_infra.iloc[idx] for idx in indices]

        geom_union = unary_union(gdf_grupo.geometry)
        escala = seleccionar_escala(geom_union, formato_key, escala_manual)
        log(f"  Escala elegida: 1:{escala:,} ({len(indices)} infraestructuras)")

        maq = MaquetadorPlano(formato_key, escala)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom_union)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        gdf_view = gdf_grupo.copy()
        añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        self._dibujar_capas_mapa(ax_map, gdf_grupo, indices,
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Etiquetas
        maq.dibujar_etiquetas_infra(gdf_grupo, campo_mapeo=self._campo_mapeo)

        # Leyenda con estadísticas
        items_ley = self._construir_items_leyenda(gdf_grupo, color_infra)
        stats = _calcular_stats_grupo(gdf_grupo)
        maq.dibujar_leyenda(items_ley, stats_resumen=stats)

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)

        maq.dibujar_panel_atributos_multi(rows, campos_visibles,
                                           campo_mapeo=self._campo_mapeo)

        cx, cy = geom_union.centroid.x, geom_union.centroid.y
        maq.dibujar_mapa_posicion(cx, cy)
        maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                  cajetin=self._cajetin)

        etiq_campo = ETIQUETAS_CAMPOS.get(campo_grupo, campo_grupo)
        titulo_grupo = f"{etiq_campo}: {valor_grupo}"
        maq.dibujar_cabecera(rows[0], titulo_grupo=titulo_grupo,
                              num_plano_override=num_plano,
                              cajetin=self._cajetin, plantilla=self._plantilla)

        maq.dibujar_cajetin(self._cajetin)
        maq.dibujar_marcos(plantilla=self._plantilla)

        nombre_safe = "".join(c for c in valor_grupo if c.isalnum() or c in "_ -")[:40]
        nombre_arch = f"plano_grupo_{num_plano:04d}_{nombre_safe}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Generación en serie ──────────────────────────────────────────────

    def generar_serie(self, indices: list, formato_key: str, proveedor: str,
                      transparencia: float, campos: list, color_infra: str,
                      salida_dir: str, escala_manual: int = None,
                      callback_log=None, callback_progreso=None) -> list:
        rutas = []
        total = len(indices)
        for i, idx in enumerate(indices):
            nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx}")
            if callback_log:
                callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
            try:
                ruta = self.generar_plano(
                    idx_fila=idx, formato_key=formato_key,
                    proveedor=proveedor, transparencia_montes=transparencia,
                    campos_visibles=campos, color_infra=color_infra,
                    salida_dir=salida_dir, escala_manual=escala_manual,
                    callback_log=callback_log,
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}")
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
                                callback_progreso=None) -> list:
        rutas = []
        total = len(valores)
        for i, valor in enumerate(valores):
            if callback_log:
                callback_log(f"\n[{i + 1}/{total}] Grupo: {campo_grupo} = {valor}")
            indices = self.obtener_indices_por_valor(campo_grupo, valor)
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
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}")
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
                                 callback_progreso=None) -> str:
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
                pdf.savefig(fig_portada, dpi=300, facecolor="white")
                plt.close(fig_portada)
                if callback_log:
                    callback_log("  \u2713 Portada a\u00f1adida")

                # Índice
                items_idx = []
                for i, idx in enumerate(indices):
                    nombre = str(self.gdf_infra.iloc[idx].get(
                        "Nombre_Infra", f"Infraestructura #{idx}"))
                    items_idx.append((i + 1, nombre, ""))
                fig_indice = crear_indice(formato_key, items_idx,
                                           plantilla=self._plantilla)
                pdf.savefig(fig_indice, dpi=300, facecolor="white")
                plt.close(fig_indice)
                if callback_log:
                    callback_log("  \u2713 \u00cdndice a\u00f1adido")

            # Planos
            for i, idx in enumerate(indices):
                nombre = self.gdf_infra.iloc[idx].get("Nombre_Infra", f"#{idx}")
                if callback_log:
                    callback_log(f"\n[{i + 1}/{total}] Generando: {nombre}")
                try:
                    row = self.gdf_infra.iloc[idx]
                    geom = row.geometry

                    escala = seleccionar_escala(geom, formato_key, escala_manual)
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

                    gdf_sel = self.gdf_infra.iloc[[idx]]
                    self._dibujar_capas_mapa(ax_map, gdf_sel, [idx],
                                              xmin, xmax, ymin, ymax,
                                              transparencia, color_infra)

                    ax_map.set_xlim(xmin, xmax)
                    ax_map.set_ylim(ymin, ymax)

                    # Etiquetas y vértices
                    maq.dibujar_etiquetas_infra(gdf_sel,
                                                 campo_mapeo=self._campo_mapeo)

                    # Leyenda
                    items_ley = self._construir_items_leyenda(gdf_sel, color_infra)
                    maq.dibujar_leyenda(items_ley)

                    maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
                    maq.dibujar_panel_atributos(row, campos,
                                                 campo_mapeo=self._campo_mapeo)

                    cx, cy = geom.centroid.x, geom.centroid.y
                    maq.dibujar_mapa_posicion(cx, cy)
                    maq.dibujar_barra_escala(proveedor, cx_utm=cx, cy_utm=cy,
                                              cajetin=self._cajetin)
                    maq.dibujar_cabecera(row, cajetin=self._cajetin,
                                          plantilla=self._plantilla)
                    maq.dibujar_cajetin(self._cajetin)
                    maq.dibujar_marcos(plantilla=self._plantilla)

                    pdf.savefig(fig, dpi=300, facecolor="white")
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

    # ── Generación por lotes desde CSV ───────────────────────────────────

    def generar_lotes_csv(self, ruta_csv: str, proveedor: str,
                           transparencia: float, campos: list,
                           color_infra: str, escala_manual: int = None,
                           callback_log=None,
                           callback_progreso=None) -> list:
        """Genera planos por lotes a partir de un CSV de configuración."""
        lotes = cargar_lotes_csv(ruta_csv)
        if not lotes:
            if callback_log:
                callback_log("No se encontraron lotes v\u00e1lidos en el CSV.", "warn")
            return []

        rutas = []
        total = len(lotes)
        for i, lote in enumerate(lotes):
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
                )
                rutas.extend(resultados)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error en lote: {e}", "error")

            if callback_progreso:
                callback_progreso(i + 1, total)

        return rutas
