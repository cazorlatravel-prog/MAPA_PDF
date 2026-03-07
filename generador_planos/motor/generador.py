"""
Motor principal de generación de planos cartográficos profesionales.

Orquesta la carga de capas, selección de escala, maquetación y exportación
a PDF individual, multipágina o agrupado por campo.
"""

import os
import threading

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from shapely.ops import unary_union

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
        """Carga shapefile de infraestructuras y reproyecta a EPSG:25830."""
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")
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

    # ── Consulta para agrupación ────────────────────────────────────────

    def obtener_valores_unicos(self, campo: str) -> list:
        """Devuelve los valores únicos de un campo del shapefile.

        Usa mapeo de campos si está definido.
        """
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
        """Devuelve los índices de filas donde campo == valor."""
        if self.gdf_infra is None:
            return []
        campo_real = campo
        if self._campo_mapeo and campo in self._campo_mapeo:
            campo_real = self._campo_mapeo[campo]
        if campo_real not in self.gdf_infra.columns:
            return []
        mask = self.gdf_infra[campo_real].astype(str) == str(valor)
        return list(self.gdf_infra.index[mask])

    # ── Helpers internos ────────────────────────────────────────────────

    def _ensure_agg(self):
        if threading.current_thread() is not threading.main_thread():
            matplotlib.use("Agg")

    def _dibujar_capas_mapa(self, ax_map, gdf_sel, indices, xmin, xmax,
                             ymin, ymax, transparencia, color_infra):
        """Dibuja fondo de montes, infra de fondo e infra seleccionadas."""
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

        # Infraestructuras de fondo (gris, todas en el viewport)
        infra_fondo = self.gdf_infra.cx[xmin:xmax, ymin:ymax]
        if not infra_fondo.empty:
            infra_fondo.plot(
                ax=ax_map, color="#999999", linewidth=0.6,
                markersize=3, alpha=0.5,
            )

        # Infraestructuras seleccionadas (resaltadas)
        for geom_single in gdf_sel.geometry:
            geom_type = str(geom_single.geom_type).lower()
            break  # detectar tipo del primer elemento

        if "point" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, markersize=12,
                         marker="o", zorder=5, edgecolor="white", linewidth=0.8)
        elif "line" in geom_type or "string" in geom_type:
            gdf_sel.plot(ax=ax_map, color=color_infra, linewidth=2.5, zorder=5)
        else:
            gdf_sel.plot(ax=ax_map, facecolor=color_infra + "55",
                         edgecolor=color_infra, linewidth=1.8, zorder=5)

    # ── Generación de plano individual ──────────────────────────────────

    def generar_plano(self, idx_fila: int, formato_key: str,
                      proveedor: str, transparencia_montes: float,
                      campos_visibles: list, color_infra: str,
                      salida_dir: str, callback_log=None) -> str:
        """Genera un plano individual para la fila idx_fila."""
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        row = self.gdf_infra.iloc[idx_fila]
        geom = row.geometry

        escala = seleccionar_escala(geom, formato_key)
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

        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)
        maq.dibujar_panel_atributos(row, campos_visibles,
                                     campo_mapeo=self._campo_mapeo)

        cx, cy = geom.centroid.x, geom.centroid.y
        maq.dibujar_mapa_posicion(cx, cy)
        maq.dibujar_barra_escala(proveedor)
        maq.dibujar_cabecera(row)
        maq.dibujar_marcos()

        nombre_infra = str(row.get("Nombre_Infra", f"infra_{idx_fila:04d}"))
        nombre_infra = "".join(c for c in nombre_infra if c.isalnum() or c in "_ -")[:40]
        nombre_arch = f"plano_{idx_fila:04d}_{nombre_infra}.pdf"
        ruta_out = os.path.join(salida_dir, nombre_arch)

        maq.guardar(ruta_out)
        log(f"  \u2713 Guardado: {nombre_arch}")
        return ruta_out

    # ── Generación de plano agrupado ────────────────────────────────────

    def generar_plano_agrupado(self, indices: list, campo_grupo: str,
                                valor_grupo: str, formato_key: str,
                                proveedor: str, transparencia_montes: float,
                                campos_visibles: list, color_infra: str,
                                salida_dir: str, num_plano: int = 1,
                                callback_log=None) -> str:
        """Genera un plano con varias infraestructuras agrupadas por un campo.

        Todas las infraestructuras con indices se resaltan en el mapa y
        sus atributos aparecen en la tabla del panel derecho.
        La extensión del mapa se calcula sobre la unión de todas las geometrías.
        """
        self._ensure_agg()

        def log(msg):
            if callback_log:
                callback_log(msg)

        gdf_grupo = self.gdf_infra.iloc[indices]
        rows = [self.gdf_infra.iloc[idx] for idx in indices]

        # Unión de todas las geometrías para calcular extensión
        geom_union = unary_union(gdf_grupo.geometry)
        escala = seleccionar_escala(geom_union, formato_key)
        log(f"  Escala elegida: 1:{escala:,} ({len(indices)} infraestructuras)")

        maq = MaquetadorPlano(formato_key, escala)
        fig, ax_map, ax_info, ax_mini, ax_esc = maq.crear_figura()

        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom_union)
        maq.configurar_mapa_principal(xmin, xmax, ymin, ymax)

        # Fondo cartográfico
        gdf_view = gdf_grupo.copy()
        añadir_fondo_cartografico(ax_map, gdf_view, proveedor,
                                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Capas
        self._dibujar_capas_mapa(ax_map, gdf_grupo, indices,
                                  xmin, xmax, ymin, ymax,
                                  transparencia_montes, color_infra)

        ax_map.set_xlim(xmin, xmax)
        ax_map.set_ylim(ymin, ymax)

        # Grid UTM
        maq.dibujar_grid_utm(xmin, xmax, ymin, ymax)

        # Panel de atributos multi-fila
        maq.dibujar_panel_atributos_multi(rows, campos_visibles,
                                           campo_mapeo=self._campo_mapeo)

        # Mapa de posición
        cx, cy = geom_union.centroid.x, geom_union.centroid.y
        maq.dibujar_mapa_posicion(cx, cy)

        # Barra de escala
        maq.dibujar_barra_escala(proveedor)

        # Cabecera con título de grupo
        etiq_campo = ETIQUETAS_CAMPOS.get(campo_grupo, campo_grupo)
        titulo_grupo = f"{etiq_campo}: {valor_grupo}"
        maq.dibujar_cabecera(rows[0], titulo_grupo=titulo_grupo,
                              num_plano_override=num_plano)

        # Marcos
        maq.dibujar_marcos()

        # Guardar
        nombre_safe = "".join(c for c in valor_grupo if c.isalnum() or c in "_ -")[:40]
        nombre_arch = f"plano_grupo_{num_plano:04d}_{nombre_safe}.pdf"
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
                    idx_fila=idx, formato_key=formato_key,
                    proveedor=proveedor, transparencia_montes=transparencia,
                    campos_visibles=campos, color_infra=color_infra,
                    salida_dir=salida_dir, callback_log=callback_log,
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas

    # ── Generación agrupada en serie ────────────────────────────────────

    def generar_serie_agrupada(self, campo_grupo: str, valores: list,
                                formato_key: str, proveedor: str,
                                transparencia: float, campos: list,
                                color_infra: str, salida_dir: str,
                                callback_log=None,
                                callback_progreso=None) -> list:
        """Genera un plano por cada valor del campo de agrupación.

        Cada plano muestra todas las infraestructuras que comparten ese valor.
        """
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
                    callback_log=callback_log,
                )
                rutas.append(ruta)
            except Exception as e:
                if callback_log:
                    callback_log(f"  \u2717 Error: {e}")
            if callback_progreso:
                callback_progreso(i + 1, total)
        return rutas

    # ── PDF multipágina ─────────────────────────────────────────────────

    def generar_pdf_multipagina(self, indices: list, formato_key: str,
                                 proveedor: str, transparencia: float,
                                 campos: list, color_infra: str,
                                 ruta_pdf: str, callback_log=None,
                                 callback_progreso=None) -> str:
        """Genera un único PDF multipágina con todos los planos."""
        from matplotlib.backends.backend_pdf import PdfPages

        self._ensure_agg()
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

                    gdf_sel = self.gdf_infra.iloc[[idx]]
                    self._dibujar_capas_mapa(ax_map, gdf_sel, [idx],
                                              xmin, xmax, ymin, ymax,
                                              transparencia, color_infra)

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
