"""
Descarga de teselas WMS/WMTS de fondo cartográfico.

Soporta:
  - OpenStreetMap (teselas estándar)
  - PNOA Ortofoto (IGN España) — WMTS
  - IGN Topográfico (MTN) — WMTS
  - Stamen Terrain

Implementa fallback manual para teselas IGN si contextily falla.
Incluye caché de teselas en disco para evitar descargas repetidas.
"""

import io
import math
import os
import hashlib
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import requests
from PIL import Image

try:
    import contextily as ctx
except ImportError:
    ctx = None

# Directorio de caché de teselas
_TILE_CACHE_DIR = Path.home() / ".mapa_pdf_cache" / "tiles"

# Caché de Transformers de pyproj (son costosos de crear)
_TRANSFORMER_CACHE = {}


def _get_transformer(from_crs: str, to_crs: str):
    """Devuelve un Transformer cacheado para la combinación de CRS."""
    key = (from_crs, to_crs)
    if key not in _TRANSFORMER_CACHE:
        from pyproj import Transformer
        _TRANSFORMER_CACHE[key] = Transformer.from_crs(
            from_crs, to_crs, always_xy=True)
    return _TRANSFORMER_CACHE[key]


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

# Proveedores WMS directos (imagen completa, no tiles).
# Se usan con _descargar_wms() en lugar de tiles.
CAPAS_WMS = {
    "IGN MTN25 (WMS 1:25.000)": {
        "url": (
            "https://www.ign.es/wms-inspire/mapa-raster?"
            "SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            "&LAYERS=mtn_rasterizado&STYLES="
            "&CRS=EPSG:25830&FORMAT=image/png"
        ),
        "attribution": "© IGN España – MTN25",
    },
    "IGN MTN50 (WMS 1:50.000)": {
        "url": (
            "https://www.ign.es/wms-inspire/mapa-raster?"
            "SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            "&LAYERS=mtn_rasterizado&STYLES="
            "&CRS=EPSG:25830&FORMAT=image/png"
        ),
        "attribution": "© IGN España – MTN50",
    },
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
    "IGN MTN25 (WMS 1:25.000)": {"max_zoom": 18, "attribution": "© IGN España – MTN25"},
    "IGN MTN50 (WMS 1:50.000)": {"max_zoom": 18, "attribution": "© IGN España – MTN50"},
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

# Añadir proveedores WMS al diccionario de proveedores para la GUI
for _wms_name, _wms_info in CAPAS_WMS.items():
    PROVIDERS_CTX[_wms_name] = {
        "url": _wms_info["url"],
        "max_zoom": 18,
        "attribution": _wms_info.get("attribution", ""),
        "wms": True,
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
    """Descarga una tesela individual, con caché en disco."""
    # Generar clave de caché basada en URL + coordenadas
    url = url_template.format(z=z, x=x, y=y)
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_path = _TILE_CACHE_DIR / f"{cache_key}.png"

    # Intentar desde caché
    if cache_path.exists():
        try:
            return Image.open(cache_path).copy()
        except Exception:
            cache_path.unlink(missing_ok=True)

    # Descargar
    headers = {
        "User-Agent": "GeneradorPlanosForestales/1.0",
        "Referer": "https://www.ign.es/",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))

    # Guardar en caché
    try:
        _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cache_path, "PNG")
    except Exception:
        pass

    return img


def _descargar_teselas_manual(ax, url_template, xmin, xmax, ymin, ymax, crs_epsg=25830):
    """Descarga teselas manualmente y las dibuja en el eje matplotlib.

    Convierte las coordenadas del eje (EPSG:25830) a EPSG:4326 para
    calcular tiles, descarga y compone la imagen de fondo.
    """
    transformer = _get_transformer(f"EPSG:{crs_epsg}", "EPSG:4326")
    lon_min, lat_min = transformer.transform(xmin, ymin)
    lon_max, lat_max = transformer.transform(xmax, ymax)

    # Calcular zoom adecuado
    lon_span = lon_max - lon_min
    for zoom in range(18, 0, -1):
        n_tiles_x = (2 ** zoom) * lon_span / 360.0
        if n_tiles_x <= 20:
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
    transformer_inv = _get_transformer("EPSG:4326", f"EPSG:{crs_epsg}")
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


def _descargar_wms(ax, wms_url, xmin, xmax, ymin, ymax, crs_epsg=25830):
    """Descarga una imagen WMS GetMap completa para el bbox y la dibuja en el eje.

    A diferencia de tiles, solicita una sola imagen que cubre todo el extent,
    lo que da mejor calidad a escalas cartográficas específicas (1:25.000, etc.).
    """
    # Calcular tamaño de imagen proporcional al extent del eje
    extent_x = xmax - xmin
    extent_y = ymax - ymin
    aspect = extent_x / max(extent_y, 1)

    # Resolución: ~2 m/pixel para buena calidad impresa (máx 4096 px por lado)
    height = min(4096, max(512, int(extent_y / 2)))
    width = min(4096, max(512, int(height * aspect)))

    # BBOX: en WMS 1.3.0 con EPSG:25830 el orden es (minx,miny,maxx,maxy)
    bbox_str = f"{xmin},{ymin},{xmax},{ymax}"
    url = f"{wms_url}&WIDTH={width}&HEIGHT={height}&BBOX={bbox_str}"

    # Caché
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_path = _TILE_CACHE_DIR / f"wms_{cache_key}.png"

    if cache_path.exists():
        try:
            img = Image.open(cache_path).copy()
        except Exception:
            cache_path.unlink(missing_ok=True)
            img = None
    else:
        img = None

    if img is None:
        headers = {
            "User-Agent": "GeneradorPlanosForestales/1.0",
            "Referer": "https://www.ign.es/",
        }
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))

        try:
            _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
        except Exception:
            pass

    ax.imshow(
        np.array(img),
        extent=[xmin, xmax, ymin, ymax],
        aspect="auto",
        zorder=0,
        interpolation="bilinear",
    )
    return True


def añadir_fondo_cartografico(ax, gdf_view, proveedor_key: str, xmin=None, xmax=None,
                               ymin=None, ymax=None):
    """Añade capa base de teselas o WMS al eje matplotlib.

    Intenta contextily primero; si falla (especialmente con URLs IGN),
    hace fallback a descarga manual de teselas.
    Para proveedores WMS, descarga una imagen GetMap completa.
    """
    # ── Proveedor WMS directo ──
    if proveedor_key in CAPAS_WMS:
        if xmin is not None:
            try:
                wms_url = CAPAS_WMS[proveedor_key]["url"]
                _descargar_wms(ax, wms_url, xmin, xmax, ymin, ymax)
                return
            except Exception:
                ax.set_facecolor("#E8E8E0")
                return
        ax.set_facecolor("#E8E8E0")
        return

    # ── Proveedor de tiles (WMTS / XYZ) ──
    exito_ctx = False

    if ctx is not None:
        proveedor = PROVIDERS_CTX.get(proveedor_key)
        if proveedor is not None and not isinstance(proveedor, dict) or (
                isinstance(proveedor, dict) and not proveedor.get("wms")):
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
