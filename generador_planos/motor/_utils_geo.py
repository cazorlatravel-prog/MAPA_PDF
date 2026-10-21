"""Funciones de utilidad geoespacial compartidas por el motor."""

from __future__ import annotations

import warnings as _warnings

import geopandas as gpd
from geopandas import GeoDataFrame
from matplotlib.axes import Axes


def _asegurar_crs(gdf: GeoDataFrame, origen: str = "") -> tuple[GeoDataFrame, str]:
    """Asegura que el GeoDataFrame tiene CRS y lo reproyecta a EPSG:25830.

    Si no tiene CRS, intenta detectar si las coordenadas son UTM o
    geográficas (lat/lon) según el rango de valores, y avisa al usuario.
    """
    CRS_DESTINO = "EPSG:25830"

    if gdf.crs is not None:
        if gdf.crs.to_epsg() != 25830:
            gdf = gdf.to_crs(CRS_DESTINO)
        return gdf, ""

    # Sin CRS definido: intentar detectar por rango de coordenadas
    bounds = gdf.total_bounds  # (minx, miny, maxx, maxy)
    minx, miny, maxx, maxy = bounds

    aviso = ""
    if minx > 100_000 and maxx < 900_000 and miny > 3_500_000 and maxy < 5_000_000:
        # Parece UTM zona 30N (coordenadas típicas de España peninsular)
        gdf = gdf.set_crs(CRS_DESTINO)
        aviso = (f"\u26a0 '{origen}' sin CRS definido. "
                 f"Se asume EPSG:25830 (UTM 30N) por el rango de coordenadas.")
    elif minx > -20 and maxx < 10 and miny > 25 and maxy < 50:
        # Parece WGS84 geográficas (lon/lat de España)
        gdf = gdf.set_crs("EPSG:4326")
        gdf = gdf.to_crs(CRS_DESTINO)
        aviso = (f"\u26a0 '{origen}' sin CRS definido. "
                 f"Se asume EPSG:4326 (WGS84) por el rango de coordenadas.")
    else:
        # No se puede determinar: asumir UTM 30N y avisar
        gdf = gdf.set_crs(CRS_DESTINO)
        aviso = (f"\u26a0 '{origen}' sin CRS definido y no se pudo detectar "
                 f"automáticamente. Se asume EPSG:25830. "
                 f"Rango: X[{minx:.0f}-{maxx:.0f}] Y[{miny:.0f}-{maxy:.0f}]")

    _warnings.warn(aviso)
    return gdf, aviso


def _detectar_geom_type(gdf: GeoDataFrame) -> str:
    """Devuelve el tipo de geometría predominante en el GeoDataFrame."""
    if gdf.empty:
        return "unknown"
    tipos = gdf.geometry.geom_type.dropna()
    if tipos.empty:
        return "unknown"
    return tipos.mode().iloc[0].lower()


def _plot_gdf_por_tipo(gdf: GeoDataFrame, ax: Axes, alpha: float, lw: float, zorder: int, color: str,
                       linestyle: str = "-", marker: str = "o", facecolor: str | None = None) -> None:
    """Dibuja un GeoDataFrame separando por tipo de geometría si hay mezcla."""
    if gdf.empty:
        return
    tipos = gdf.geometry.geom_type.str.lower()
    tipos_unicos = tipos.unique()

    for tipo in tipos_unicos:
        sub = gdf[tipos == tipo]
        if sub.empty:
            continue
        if "point" in tipo:
            sub.plot(ax=ax, color=color, markersize=12,
                     marker=marker, zorder=zorder,
                     edgecolor="white", linewidth=0.8, alpha=alpha)
        elif "line" in tipo or "string" in tipo:
            sub.plot(ax=ax, color=color, linewidth=lw,
                     linestyle=linestyle, zorder=zorder, alpha=alpha)
        else:
            fc = facecolor if facecolor else (color + "55")
            sub.plot(ax=ax, facecolor=fc, edgecolor=color,
                     linewidth=lw, linestyle=linestyle,
                     zorder=zorder, alpha=alpha)


def _limpiar_tipos_mixtos(gdf: GeoDataFrame) -> GeoDataFrame:
    """Convierte columnas con tipos mixtos (str + float) a str para evitar TypeError."""
    col_geom = gdf.geometry.name if hasattr(gdf, "geometry") else "geometry"
    for col in gdf.columns:
        if col == col_geom:
            continue
        if gdf[col].dtype == object:
            # Columna con tipo 'object' puede tener mezcla de str, float, int, None
            # Forzar a str (manteniendo los nulos como NaN)
            try:
                gdf[col] = gdf[col].where(gdf[col].isna(), gdf[col].astype(str))
            except Exception:
                pass
    return gdf


def _auto_calcular_campos(gdf: GeoDataFrame) -> GeoDataFrame:
    """Calcula longitud/superficie automáticamente si no existen en el GDF.

    Tolera geometrías nulas o vacías (frecuentes en exportaciones de
    ArcGIS): antes una sola geometría None abortaba la carga de la capa.
    """
    if "Longitud" not in gdf.columns:
        def _long(g):
            if g is None or g.is_empty:
                return 0.0
            gt = str(g.geom_type).lower()
            if "line" in gt or "string" in gt:
                return round(g.length, 1)
            return 0.0
        gdf["Longitud"] = gdf.geometry.apply(_long)

    if "Superficie" not in gdf.columns:
        def _sup(g):
            if g is None or g.is_empty:
                return 0.0
            gt = str(g.geom_type).lower()
            if "polygon" in gt:
                return round(g.area / 10000, 4)  # m² → ha
            return 0.0
        gdf["Superficie"] = gdf.geometry.apply(_sup)

    return gdf


def _a_numero(serie):
    """Convierte una Serie a float tolerando texto con formato español.

    Acepta "1.234,5" (miles con punto, decimal con coma), "1,5" y "1.5".
    Los valores no convertibles pasan a NaN en vez de lanzar ValueError.
    """
    import pandas as pd

    def _conv(v):
        if v is None:
            return float("nan")
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "null", "—"):
            return float("nan")
        if "," in s:
            # Coma decimal (convención española): los puntos son de miles
            s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return float("nan")

    return pd.to_numeric(serie.map(_conv), errors="coerce")


def _calcular_stats_grupo(gdf_grupo: GeoDataFrame) -> dict[str, float]:
    """Calcula estadísticas resumen para un grupo de infraestructuras."""
    stats = {"num_infraestructuras": len(gdf_grupo)}

    # Longitud/Superficie pueden venir como texto en el shapefile
    # ("1.234,5"); astype(float) rompía el plano agrupado entero.
    if "Longitud" in gdf_grupo.columns:
        total_m = _a_numero(gdf_grupo["Longitud"]).fillna(0).sum()
        stats["total_longitud_km"] = float(total_m) / 1000.0

    if "Superficie" in gdf_grupo.columns:
        total_ha = _a_numero(gdf_grupo["Superficie"]).fillna(0).sum()
        stats["total_superficie_ha"] = float(total_ha)

    return stats


def _leer_geodatos(ruta: str, layer: str | None = None) -> GeoDataFrame:
    """Lee un shapefile o geodatabase con fallback al driver OpenFileGDB.

    Si el .dbf está en latin-1/cp1252 pero un .cpg erróneo declara UTF-8
    (habitual en shapefiles españoles antiguos), la lectura lanza
    UnicodeDecodeError; se reintenta forzando cp1252 en vez de fallar.
    """
    kwargs = {}
    if layer:
        kwargs["layer"] = layer
    if ruta.lower().rstrip("/\\").endswith(".gdb"):
        # Intentar primero con OpenFileGDB (más compatible con ArcGIS)
        try:
            return gpd.read_file(ruta, driver="OpenFileGDB", **kwargs)
        except Exception:
            pass
    try:
        return gpd.read_file(ruta, **kwargs)
    except UnicodeDecodeError:
        return gpd.read_file(ruta, encoding="cp1252", **kwargs)
