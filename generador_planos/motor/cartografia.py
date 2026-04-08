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


def añadir_fondo_raster_local(ax, ruta_raster: str, xmin, xmax, ymin, ymax):
    """Carga un ráster local (GeoTIFF, ECW, JP2…) y lo dibuja como fondo del mapa.

    Lee solo la ventana necesaria (el extent del plano) para no cargar
    todo el archivo en memoria.
    """
    try:
        import rasterio
        from rasterio.windows import from_bounds
    except ImportError:
        raise ImportError(
            "Se necesita la librería 'rasterio' para cargar rásters locales.\n"
            "Instálala con: pip install rasterio")

    with rasterio.open(ruta_raster) as src:
        # Recortar al extent del plano
        window = from_bounds(xmin, ymin, xmax, ymax, src.transform)
        # Leer bandas visibles (máx 3 para RGB)
        n_bands = min(src.count, 3)
        data = src.read(list(range(1, n_bands + 1)), window=window)

        # Calcular extent real de la ventana leída
        win_transform = src.window_transform(window)
        h, w = data.shape[1], data.shape[2]
        rx_min = min(win_transform.c, win_transform.c + w * win_transform.a)
        rx_max = max(win_transform.c, win_transform.c + w * win_transform.a)
        ry_min = min(win_transform.f, win_transform.f + h * win_transform.e)
        ry_max = max(win_transform.f, win_transform.f + h * win_transform.e)

        # Manejar NODATA: convertir píxeles sin datos en transparentes
        nodata = src.nodata
        if n_bands == 1:
            img = data[0].astype(float)
            if nodata is not None:
                img = np.ma.masked_equal(img, nodata)
        else:
            img = np.moveaxis(data, 0, -1)  # (bands, h, w) → (h, w, bands)
            if nodata is not None:
                # Máscara: transparente donde TODAS las bandas == nodata
                mask = np.all(data == nodata, axis=0)
                # Convertir a RGBA para transparencia
                if img.dtype == np.uint8:
                    alpha = np.where(mask, 0, 255).astype(np.uint8)
                else:
                    alpha = np.where(mask, 0.0, 1.0).astype(img.dtype)
                img = np.dstack([img, alpha])

    ax.imshow(
        img, extent=[rx_min, rx_max, ry_min, ry_max],
        aspect="auto", zorder=0, interpolation="bilinear",
    )
    return True


def construir_vrt_desde_carpeta(carpeta: str) -> str:
    """Genera un archivo VRT (Virtual Raster) a partir de todos los rásters
    de una carpeta (y subcarpetas), tal como hace QGIS/ArcGIS al añadir
    una carpeta de hojas cartográficas.

    El VRT se guarda junto a la carpeta con nombre '<carpeta>.vrt'.
    Si ya existe y es más reciente que los archivos, lo reutiliza.

    Si las hojas tienen CRS heterogéneos (p. ej. hojas MTN en distintos
    husos UTM), reproyecta sobre la marcha las hojas minoritarias al CRS
    dominante antes de montar el mosaico. Esto evita el error
    'CRS distinto en X.tif' que se producía cuando se mezclaban husos.

    Estrategia de construcción (en orden de preferencia):
      1. Comando ``gdalbuildvrt`` (si está en el PATH).
      2. ``osgeo.gdal.BuildVRT`` (si el binding Python de GDAL está instalado).
      3. Construcción manual del XML VRT usando ``rasterio`` para leer los
         metadatos de cada ráster. No requiere ``gdalbuildvrt`` ni el
         paquete ``osgeo``.

    Returns:
        Ruta al fichero .vrt generado.
    """
    from pathlib import Path
    import subprocess
    import glob

    carpeta_p = Path(carpeta)
    vrt_path = carpeta_p.parent / f"{carpeta_p.name}.vrt"

    # Buscar todos los rásters en la carpeta y subcarpetas
    extensiones = ("*.tif", "*.tiff", "*.ecw", "*.jp2", "*.img")
    archivos = []
    for ext in extensiones:
        archivos.extend(glob.glob(str(carpeta_p / "**" / ext), recursive=True))

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron archivos ráster en: {carpeta}")

    archivos = sorted(archivos)

    # Comprobar si el VRT existente es válido (más reciente que los rásters)
    if vrt_path.exists():
        vrt_mtime = vrt_path.stat().st_mtime
        max_raster_mtime = max(os.path.getmtime(f) for f in archivos)
        if vrt_mtime > max_raster_mtime:
            return str(vrt_path)

    # Homogeneizar CRS: si hay hojas en distintos husos, reproyecta las
    # minoritarias al CRS dominante. Si rasterio no está disponible o todos
    # los rásters ya comparten CRS, devuelve la lista tal cual.
    archivos_mosaico = _homogeneizar_crs_rasters(archivos, carpeta_p)

    # 1) Intentar con gdalbuildvrt (el método más robusto si está disponible)
    try:
        cmd = ["gdalbuildvrt", str(vrt_path)] + archivos_mosaico
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(vrt_path)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # 2) Intentar con el binding Python de GDAL (osgeo.gdal)
    try:
        from osgeo import gdal  # type: ignore
        gdal.BuildVRT(str(vrt_path), archivos_mosaico)
        return str(vrt_path)
    except ImportError:
        pass
    except Exception:
        pass

    # 3) Último recurso: construir el XML del VRT manualmente usando rasterio.
    #    Rasterio viene bundled en el .exe portable y no requiere osgeo.
    try:
        _construir_vrt_xml_manual(vrt_path, archivos_mosaico)
        return str(vrt_path)
    except ImportError as e:
        raise ImportError(
            "Se necesita 'rasterio' o GDAL para generar el mosaico virtual.\n"
            "Instala rasterio con: pip install rasterio\n"
            "O GDAL con: pip install gdal\n"
            "O crea un archivo .vrt manualmente con: "
            "gdalbuildvrt mosaico.vrt carpeta/*.tif") from e


# ---------------------------------------------------------------------------
# Homogeneización de CRS para mosaicos de hojas cartográficas heterogéneas
# ---------------------------------------------------------------------------

def _crs_iguales(a, b) -> bool:
    """Comparación robusta entre dos CRS de rasterio."""
    if a is None or b is None:
        return a is None and b is None
    try:
        ea = a.to_epsg() if hasattr(a, "to_epsg") else None
        eb = b.to_epsg() if hasattr(b, "to_epsg") else None
        if ea is not None and eb is not None:
            return ea == eb
    except Exception:
        pass
    try:
        return a.to_wkt() == b.to_wkt()
    except Exception:
        return a == b


def _elegir_crs_destino(crs_por_archivo):
    """Elige el CRS de destino para un mosaico heterogéneo.

    Estrategia:
      1. El CRS más frecuente entre las hojas.
      2. En caso de empate, prioriza EPSG:25830 (ETRS89/UTM 30N, por defecto
         en España) si alguna hoja lo usa.
      3. Si no, el primer CRS válido encontrado.
    """
    from collections import Counter

    validos = [c for c in crs_por_archivo if c is not None]
    if not validos:
        return None

    # Contar por WKT (único identificador sólido para cualquier CRS)
    counts = Counter()
    wkt_a_crs = {}
    for c in validos:
        try:
            key = c.to_wkt()
        except Exception:
            continue
        counts[key] += 1
        wkt_a_crs.setdefault(key, c)

    if not counts:
        return validos[0]

    # Ordenar por (frecuencia desc, preferencia-25830 desc)
    def _prioridad(item):
        wkt, freq = item
        crs = wkt_a_crs[wkt]
        try:
            prefer_25830 = 1 if crs.to_epsg() == 25830 else 0
        except Exception:
            prefer_25830 = 0
        return (freq, prefer_25830)

    wkt_ganador, _ = max(counts.items(), key=_prioridad)
    return wkt_a_crs[wkt_ganador]


def _homogeneizar_crs_rasters(archivos, carpeta_p):
    """Asegura que todos los rásters compartan el mismo CRS para el mosaico.

    Lee los metadatos con rasterio. Si hay CRS heterogéneos:
      - Elige el CRS dominante como destino.
      - Reproyecta las hojas minoritarias a ese CRS creando VRTs warpeados
        (o GeoTIFFs si no hay GDAL) en una carpeta caché oculta dentro de
        ``carpeta_p`` para que se puedan reutilizar entre ejecuciones.

    Si rasterio no está disponible, devuelve la lista de archivos original
    (comportamiento previo: el error de CRS lo lanzará más adelante la
    construcción del VRT).

    Args:
        archivos: lista de rutas a rásters ordenados.
        carpeta_p: Path a la carpeta raíz que contiene los rásters.

    Returns:
        Lista de rutas lista para pasar a ``gdalbuildvrt`` / ``BuildVRT`` /
        ``_construir_vrt_xml_manual``. Contiene rutas originales para los
        rásters que ya estaban en el CRS destino y rutas warpeadas para los
        que había que reproyectar.
    """
    try:
        import rasterio
    except ImportError:
        return list(archivos)

    # Leer CRS de cada archivo
    crs_por_archivo = []
    for fp in archivos:
        try:
            with rasterio.open(fp) as src:
                crs_por_archivo.append(src.crs)
        except Exception:
            crs_por_archivo.append(None)

    # ¿Son todos iguales?
    primero_valido = next((c for c in crs_por_archivo if c is not None), None)
    if primero_valido is None:
        return list(archivos)
    if all(_crs_iguales(c, primero_valido) for c in crs_por_archivo if c is not None):
        return list(archivos)

    # CRS heterogéneos: elegir destino y warpear los que no coincidan
    crs_destino = _elegir_crs_destino(crs_por_archivo)
    if crs_destino is None:
        return list(archivos)

    try:
        epsg_destino = crs_destino.to_epsg()
    except Exception:
        epsg_destino = None
    sufijo_dir = f"_{epsg_destino}" if epsg_destino else ""
    cache_dir = carpeta_p / f".mosaico_warped{sufijo_dir}"

    resultado = []
    for fp, crs in zip(archivos, crs_por_archivo):
        if crs is not None and _crs_iguales(crs, crs_destino):
            resultado.append(fp)
            continue
        try:
            fp_warpeado = _warpear_fuente(fp, crs_destino, cache_dir)
            resultado.append(fp_warpeado)
        except Exception as e:
            # Si no se puede reproyectar una hoja concreta, abortamos con un
            # mensaje claro para el usuario.
            raise RuntimeError(
                "No se pudo reproyectar al CRS común "
                f"({epsg_destino or 'destino'}) la hoja '{os.path.basename(fp)}': {e}"
            ) from e

    return resultado


def _warpear_fuente(ruta_origen: str, crs_destino, cache_dir) -> str:
    """Crea una versión reproyectada (warpeada) de un ráster.

    Intenta, por orden:
      1. ``gdalwarp -of VRT`` (si está en el PATH) → genera un VRT warpeado
         que no copia los píxeles a disco (sólo metadatos de reproyección).
      2. ``osgeo.gdal.Warp(format='VRT')`` equivalente vía binding Python.
      3. ``rasterio`` reproyectando a un GeoTIFF intermedio (usa más disco,
         pero es pura Python y funciona con la instalación bundled).

    El resultado se cachea en ``cache_dir`` y se reutiliza si es más reciente
    que el fichero de origen.
    """
    import subprocess
    from pathlib import Path as _P

    cache_p = _P(cache_dir)
    cache_p.mkdir(parents=True, exist_ok=True)

    origen_p = _P(ruta_origen)
    try:
        epsg = crs_destino.to_epsg()
    except Exception:
        epsg = None
    sufijo = f"_{epsg}" if epsg else "_warped"

    vrt_out = cache_p / f"{origen_p.stem}{sufijo}.vrt"
    tif_out = cache_p / f"{origen_p.stem}{sufijo}.tif"

    origen_mtime = origen_p.stat().st_mtime
    if vrt_out.exists() and vrt_out.stat().st_mtime > origen_mtime:
        return str(vrt_out)
    if tif_out.exists() and tif_out.stat().st_mtime > origen_mtime:
        return str(tif_out)

    t_srs = f"EPSG:{epsg}" if epsg else None
    if t_srs is None:
        try:
            t_srs = crs_destino.to_wkt()
        except Exception:
            t_srs = None
    if t_srs is None:
        raise ValueError("CRS de destino inválido")

    # 1) gdalwarp CLI
    try:
        cmd = [
            "gdalwarp", "-overwrite", "-of", "VRT",
            "-t_srs", t_srs,
            str(origen_p), str(vrt_out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(vrt_out)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # 2) osgeo.gdal.Warp
    try:
        from osgeo import gdal  # type: ignore
        res = gdal.Warp(str(vrt_out), str(origen_p), format="VRT", dstSRS=t_srs)
        if res is not None:
            res = None  # cerrar dataset
            return str(vrt_out)
    except ImportError:
        pass
    except Exception:
        pass

    # 3) rasterio → GeoTIFF intermedio (más pesado pero pura Python)
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    with rasterio.open(str(origen_p)) as src:
        transform, width, height = calculate_default_transform(
            src.crs, crs_destino, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            "crs": crs_destino,
            "transform": transform,
            "width": width,
            "height": height,
            "driver": "GTiff",
            "compress": "lzw",
            "tiled": True,
        })
        with rasterio.open(str(tif_out), "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=crs_destino,
                    resampling=Resampling.bilinear,
                )
    return str(tif_out)


# Mapeo de dtypes de numpy/rasterio a tipos de datos GDAL (para VRT XML).
_NUMPY_TO_GDAL_DTYPE = {
    "uint8": "Byte",
    "int8": "Int8",
    "uint16": "UInt16",
    "int16": "Int16",
    "uint32": "UInt32",
    "int32": "Int32",
    "uint64": "UInt64",
    "int64": "Int64",
    "float32": "Float32",
    "float64": "Float64",
    "complex64": "CFloat32",
    "complex128": "CFloat64",
}


def _construir_vrt_xml_manual(vrt_path, archivos):
    """Construye un archivo VRT manualmente escribiendo el XML directamente.

    Usa ``rasterio`` para leer los metadatos de cada ráster (transform,
    tamaño, CRS, dtype, número de bandas, nodata). El VRT generado es
    compatible con el formato que produce ``gdalbuildvrt``.

    Requiere que todos los rásters compartan el mismo CRS y número de bandas.
    La resolución de salida se toma como la más fina (píxel más pequeño) del
    conjunto.
    """
    import rasterio
    from xml.etree import ElementTree as ET

    # Leer metadatos de cada ráster
    fuentes = []
    for fp in archivos:
        with rasterio.open(fp) as src:
            fuentes.append({
                "path": str(fp),
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "dtypes": list(src.dtypes),
                "crs": src.crs,
                "transform": src.transform,
                "bounds": tuple(src.bounds),
                "nodata": src.nodata,
                "block_shapes": list(src.block_shapes),
                "colorinterp": [ci.name for ci in src.colorinterp],
            })

    if not fuentes:
        raise RuntimeError("No se pudieron abrir los rásters con rasterio")

    primera = fuentes[0]
    crs = primera["crs"]
    n_bandas = primera["count"]
    dtypes = primera["dtypes"]

    # Verificar compatibilidad básica entre rásters
    incompatibles = []
    for s in fuentes[1:]:
        nombre = os.path.basename(s["path"])
        if s["crs"] != crs:
            incompatibles.append(f"CRS distinto en {nombre}")
        if s["count"] != n_bandas:
            incompatibles.append(f"Número de bandas distinto en {nombre}")
    if incompatibles:
        raise ValueError(
            "Los rásters no son compatibles para crear un mosaico:\n"
            + "\n".join(incompatibles[:5]))

    # Unión de bounds y resolución más fina
    xmins = [s["bounds"][0] for s in fuentes]
    ymins = [s["bounds"][1] for s in fuentes]
    xmaxs = [s["bounds"][2] for s in fuentes]
    ymaxs = [s["bounds"][3] for s in fuentes]
    union_xmin = min(xmins)
    union_ymin = min(ymins)
    union_xmax = max(xmaxs)
    union_ymax = max(ymaxs)

    pxw = min(abs(s["transform"].a) for s in fuentes)
    pxh = min(abs(s["transform"].e) for s in fuentes)
    if pxw <= 0 or pxh <= 0:
        raise ValueError("Resolución de píxel inválida en los rásters fuente")

    out_w = max(1, int(round((union_xmax - union_xmin) / pxw)))
    out_h = max(1, int(round((union_ymax - union_ymin) / pxh)))

    # Construir XML del VRT
    root = ET.Element("VRTDataset", {
        "rasterXSize": str(out_w),
        "rasterYSize": str(out_h),
    })

    if crs is not None:
        try:
            srs_elem = ET.SubElement(root, "SRS")
            srs_elem.text = crs.to_wkt()
        except Exception:
            pass

    geot = ET.SubElement(root, "GeoTransform")
    geot.text = (
        f"  {union_xmin:.16e},  {pxw:.16e},  0.0000000000000000e+00, "
        f" {union_ymax:.16e},  0.0000000000000000e+00, {-pxh:.16e}"
    )

    for banda in range(1, n_bandas + 1):
        gdal_dtype = _NUMPY_TO_GDAL_DTYPE.get(
            str(dtypes[banda - 1]), "Float32")

        vrt_band = ET.SubElement(root, "VRTRasterBand", {
            "dataType": gdal_dtype,
            "band": str(banda),
        })

        # ColorInterp (solo si rasterio lo expone y no es 'undefined')
        try:
            ci_name = primera["colorinterp"][banda - 1]
            if ci_name and ci_name.lower() != "undefined":
                ci_elem = ET.SubElement(vrt_band, "ColorInterp")
                ci_elem.text = ci_name.capitalize()
        except (IndexError, KeyError):
            pass

        # NoDataValue de la banda (si coincide en todas las fuentes)
        nodatas = [s["nodata"] for s in fuentes]
        if nodatas and nodatas[0] is not None and all(
                n == nodatas[0] for n in nodatas):
            nd = ET.SubElement(vrt_band, "NoDataValue")
            nd.text = repr(nodatas[0])

        for s in fuentes:
            src_pxw = abs(s["transform"].a)
            src_pxh = abs(s["transform"].e)
            src_xmin = s["bounds"][0]
            src_ymax = s["bounds"][3]

            dst_x_off = (src_xmin - union_xmin) / pxw
            dst_y_off = (union_ymax - src_ymax) / pxh
            dst_x_size = s["width"] * (src_pxw / pxw)
            dst_y_size = s["height"] * (src_pxh / pxh)

            csrc = ET.SubElement(vrt_band, "ComplexSource")

            fn = ET.SubElement(csrc, "SourceFilename",
                               {"relativeToVRT": "0"})
            fn.text = s["path"]

            sb = ET.SubElement(csrc, "SourceBand")
            sb.text = str(banda)

            try:
                block_h, block_w = s["block_shapes"][banda - 1]
            except (IndexError, TypeError, ValueError):
                block_h, block_w = s["height"], s["width"]
            ET.SubElement(csrc, "SourceProperties", {
                "RasterXSize": str(s["width"]),
                "RasterYSize": str(s["height"]),
                "DataType": _NUMPY_TO_GDAL_DTYPE.get(
                    str(s["dtypes"][banda - 1]), "Float32"),
                "BlockXSize": str(block_w),
                "BlockYSize": str(block_h),
            })

            ET.SubElement(csrc, "SrcRect", {
                "xOff": "0",
                "yOff": "0",
                "xSize": str(s["width"]),
                "ySize": str(s["height"]),
            })

            ET.SubElement(csrc, "DstRect", {
                "xOff": f"{dst_x_off:.6f}",
                "yOff": f"{dst_y_off:.6f}",
                "xSize": f"{dst_x_size:.6f}",
                "ySize": f"{dst_y_size:.6f}",
            })

            if s["nodata"] is not None:
                nd_src = ET.SubElement(csrc, "NODATA")
                nd_src.text = repr(s["nodata"])

    tree = ET.ElementTree(root)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        # Python < 3.9: ET.indent no existe, pero no es crítico
        pass
    tree.write(str(vrt_path), encoding="UTF-8", xml_declaration=False)


def descargar_wfs(url: str, capa: str, xmin, ymin, xmax, ymax,
                  crs_epsg: int = 25830, max_features: int = 50000):
    """Descarga features de un servicio WFS y devuelve un GeoDataFrame.

    Soporta WFS 2.0.0 con filtro BBOX.
    """
    import geopandas as gpd

    # Construir petición GetFeature con BBOX
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "VERSION": "2.0.0",
        "TYPENAMES": capa,
        "SRSNAME": f"EPSG:{crs_epsg}",
        "BBOX": f"{xmin},{ymin},{xmax},{ymax},EPSG:{crs_epsg}",
        "OUTPUTFORMAT": "application/json",
        "COUNT": str(max_features),
    }
    # Construir URL limpiamente
    base_url = url.split("?")[0]
    resp = requests.get(base_url, params=params, timeout=60,
                        headers={"User-Agent": "GeneradorPlanosForestales/1.0"})
    resp.raise_for_status()

    gdf = gpd.read_file(io.BytesIO(resp.content), driver="GeoJSON")
    if gdf.crs is None:
        gdf = gdf.set_crs(f"EPSG:{crs_epsg}")
    elif gdf.crs.to_epsg() != crs_epsg:
        gdf = gdf.to_crs(f"EPSG:{crs_epsg}")
    return gdf


def descargar_wms_custom(ax, url: str, capa: str, xmin, xmax, ymin, ymax,
                         crs_epsg: int = 25830, formato: str = "image/png"):
    """Descarga una imagen WMS GetMap de un servicio personalizado del usuario."""
    extent_x = xmax - xmin
    extent_y = ymax - ymin
    aspect = extent_x / max(extent_y, 1)

    height = min(4096, max(512, int(extent_y / 2)))
    width = min(4096, max(512, int(height * aspect)))

    bbox_str = f"{xmin},{ymin},{xmax},{ymax}"
    base_url = url.split("?")[0]
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "LAYERS": capa,
        "STYLES": "",
        "CRS": f"EPSG:{crs_epsg}",
        "FORMAT": formato,
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "BBOX": bbox_str,
    }

    # Caché
    import urllib.parse
    full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    cache_key = hashlib.md5(full_url.encode()).hexdigest()
    cache_path = _TILE_CACHE_DIR / f"wms_custom_{cache_key}.png"

    if cache_path.exists():
        try:
            img = Image.open(cache_path).copy()
        except Exception:
            cache_path.unlink(missing_ok=True)
            img = None
    else:
        img = None

    if img is None:
        resp = requests.get(base_url, params=params, timeout=60,
                            headers={"User-Agent": "GeneradorPlanosForestales/1.0"})
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


def dibujar_wfs_en_eje(ax, gdf, estilo: dict = None):
    """Dibuja un GeoDataFrame WFS en un eje matplotlib."""
    if gdf is None or gdf.empty:
        return
    est = estilo or {}
    color = est.get("color", "#3498DB")
    linewidth = est.get("linewidth", 0.8)
    alpha = est.get("alpha", 0.6)
    facecolor = est.get("facecolor", "none")

    gdf.plot(ax=ax, color=facecolor, edgecolor=color,
             linewidth=linewidth, alpha=alpha, zorder=2)


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
