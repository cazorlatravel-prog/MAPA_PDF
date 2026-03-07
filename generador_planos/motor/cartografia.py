"""
Descarga de teselas WMS/WMTS de fondo cartográfico.

Soporta:
  - OpenStreetMap (teselas estándar)
  - PNOA Ortofoto (IGN España) — WMTS
  - IGN Topográfico (MTN) — WMTS
  - Stamen Terrain

Implementa fallback manual para teselas IGN si contextily falla.
"""

import io
import math
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import requests
from PIL import Image

try:
    import contextily as ctx
except ImportError:
    ctx = None


CAPAS_BASE = {
    "OpenStreetMap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "PNOA Ortofoto (IGN)": (
        "https://www.ign.es/wmts/pnoa-ma?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=OI.OrthoimageCoverage&STYLE=default"
        "&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    ),
    "IGN Topográfico": (
        "https://www.ign.es/wmts/mapa-raster?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=MTN&STYLE=default"
        "&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    ),
    "IGN Base": (
        "https://www.ign.es/wmts/ign-base?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=IGNBaseTodo&STYLE=default"
        "&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    ),
    "PNOA Máxima Actualidad": (
        "https://www.ign.es/wmts/pnoa-ma?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=OI.MostRecent&STYLE=default"
        "&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    ),
    "Stamen Terrain": "https://stamen-tiles.a.ssl.fastly.net/terrain/{z}/{x}/{y}.png",
}

# PROVIDERS_CTX se construye siempre para que el desplegable de la GUI
# muestre todos los proveedores disponibles, con o sin contextily.
_PROV_META = {
    "OpenStreetMap": {"max_zoom": 19, "attribution": "© OpenStreetMap"},
    "PNOA Ortofoto (IGN)": {"max_zoom": 20, "attribution": "© IGN España"},
    "IGN Topográfico": {"max_zoom": 18, "attribution": "© IGN España"},
    "IGN Base": {"max_zoom": 18, "attribution": "© IGN España"},
    "PNOA Máxima Actualidad": {"max_zoom": 20, "attribution": "© IGN España"},
    "Stamen Terrain": {"max_zoom": 18, "attribution": "Stamen Design"},
}

if ctx is not None:
    PROVIDERS_CTX = {
        "OpenStreetMap": ctx.providers.OpenStreetMap.Mapnik,
    }
    for name in list(CAPAS_BASE.keys()):
        if name == "OpenStreetMap":
            continue
        meta = _PROV_META.get(name, {})
        PROVIDERS_CTX[name] = {
            "url": CAPAS_BASE[name],
            "max_zoom": meta.get("max_zoom", 18),
            "attribution": meta.get("attribution", ""),
        }
else:
    # Sin contextily: el desplegable sigue mostrando opciones y se usa
    # la descarga manual de teselas como fallback.
    PROVIDERS_CTX = {
        name: {"url": url, **_PROV_META.get(name, {})}
        for name, url in CAPAS_BASE.items()
    }


# ---------------------------------------------------------------------------
# Descarga manual de teselas (fallback si contextily falla con IGN)
# ---------------------------------------------------------------------------

def _lat_lon_to_tile(lat, lon, zoom):
    """Convierte lat/lon a coordenadas de tile XYZ."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _descargar_tesela(url_template, z, x, y, timeout=10):
    """Descarga una tesela individual."""
    url = url_template.format(z=z, x=x, y=y)
    headers = {
        "User-Agent": "GeneradorPlanosForestales/1.0",
        "Referer": "https://www.ign.es/",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content))


def _descargar_teselas_manual(ax, url_template, xmin, xmax, ymin, ymax, crs_epsg=25830):
    """Descarga teselas manualmente y las dibuja en el eje matplotlib.

    Convierte las coordenadas del eje (EPSG:25830) a EPSG:4326 para
    calcular tiles, descarga y compone la imagen de fondo.
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(f"EPSG:{crs_epsg}", "EPSG:4326", always_xy=True)
    lon_min, lat_min = transformer.transform(xmin, ymin)
    lon_max, lat_max = transformer.transform(xmax, ymax)

    # Calcular zoom adecuado
    lon_span = lon_max - lon_min
    for zoom in range(18, 0, -1):
        n_tiles_x = (2 ** zoom) * lon_span / 360.0
        if n_tiles_x <= 12:
            break
    else:
        zoom = 5

    tx_min, ty_min = _lat_lon_to_tile(lat_max, lon_min, zoom)
    tx_max, ty_max = _lat_lon_to_tile(lat_min, lon_max, zoom)

    n = 2 ** zoom
    tiles = []

    # Descargar teselas en paralelo (hasta 8 hilos)
    tile_coords = [
        (tx, ty)
        for tx in range(tx_min, tx_max + 1)
        for ty in range(ty_min, ty_max + 1)
    ]

    def _fetch_tile(coords):
        tx, ty = coords
        img = _descargar_tesela(url_template, zoom, tx, ty)
        tile_lon_min = tx / n * 360.0 - 180.0
        tile_lon_max = (tx + 1) / n * 360.0 - 180.0
        tile_lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
        tile_lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
        return (img, tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max)

    with ThreadPoolExecutor(max_workers=min(8, len(tile_coords) or 1)) as pool:
        futures = {pool.submit(_fetch_tile, tc): tc for tc in tile_coords}
        for fut in as_completed(futures):
            try:
                tiles.append(fut.result())
            except Exception:
                continue

    if not tiles:
        return False

    # Convertir bounds de cada tile de lon/lat a EPSG:25830
    transformer_inv = Transformer.from_crs("EPSG:4326", f"EPSG:{crs_epsg}", always_xy=True)
    for img, tlon_min, tlon_max, tlat_min, tlat_max in tiles:
        txmin_m, tymin_m = transformer_inv.transform(tlon_min, tlat_min)
        txmax_m, tymax_m = transformer_inv.transform(tlon_max, tlat_max)
        ax.imshow(
            np.array(img),
            extent=[txmin_m, txmax_m, tymin_m, tymax_m],
            aspect="auto",
            zorder=0,
            interpolation="bilinear",
        )
    return True


def añadir_fondo_cartografico(ax, gdf_view, proveedor_key: str, xmin=None, xmax=None,
                               ymin=None, ymax=None):
    """Añade capa base de teselas al eje matplotlib.

    Intenta contextily primero; si falla (especialmente con URLs IGN),
    hace fallback a descarga manual de teselas.
    """
    exito_ctx = False

    if ctx is not None:
        proveedor = PROVIDERS_CTX.get(proveedor_key)
        if proveedor is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ctx.add_basemap(
                        ax,
                        crs=gdf_view.crs.to_string(),
                        source=proveedor,
                        zoom="auto",
                        attribution=False,
                    )
                exito_ctx = True
            except Exception:
                pass

    if not exito_ctx:
        # Fallback: descarga manual
        url_template = CAPAS_BASE.get(proveedor_key)
        if url_template and xmin is not None:
            try:
                exito_manual = _descargar_teselas_manual(
                    ax, url_template, xmin, xmax, ymin, ymax
                )
                if not exito_manual:
                    ax.set_facecolor("#E8E8E0")
            except Exception:
                ax.set_facecolor("#E8E8E0")
        else:
            ax.set_facecolor("#E8E8E0")
