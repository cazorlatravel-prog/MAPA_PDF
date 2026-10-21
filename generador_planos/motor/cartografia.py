"""
Descarga de teselas WMS/WMTS de fondo cartográfico.

Soporta:
  - IGN (WMTS): PNOA Ortofoto, PNOA Máxima Actualidad, IGN Topográfico
    (MTN), IGN Base y IGN Relieve (MDT sombreado, servicios.idee.es/wmts/mdt
    capa ``Relieve``)
  - WMS directos: IGN MTN25/MTN50, Topográfico Andalucía (MTA10) y
    Catastro (parcelas, DG del Catastro, WMS 1.1.1)
  - Google Satélite / Híbrido (teselas XYZ)
  - OpenStreetMap (teselas estándar)

Capas WMS superpuestas (overlays semitransparentes sobre el fondo), con
presets en ``OVERLAYS_PREDEFINIDOS``: Catastro (parcelas), Límites
municipales (IGN) y Montes Públicos de Andalucía (REDIAM).

Implementa fallback manual para teselas IGN si contextily falla.
Incluye caché de teselas en disco para evitar descargas repetidas.
``obtener_atribucion()`` devuelve el texto de atribución de cada proveedor.
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

# Caché de Transformers de pyproj POR HILO. Los Transformer no son seguros
# para compartir entre hilos (la generación corre en workers y la descarga
# de teselas usa un ThreadPoolExecutor): un Transformer compartido puede
# devolver coordenadas erróneas de forma intermitente.
import threading as _threading

_TRANSFORMER_TLS = _threading.local()


def _get_transformer(from_crs: str, to_crs: str):
    """Devuelve un Transformer cacheado para la combinación de CRS.

    La caché es thread-local: cada hilo construye y reutiliza los suyos.
    """
    cache = getattr(_TRANSFORMER_TLS, "cache", None)
    if cache is None:
        cache = _TRANSFORMER_TLS.cache = {}
    key = (from_crs, to_crs)
    if key not in cache:
        from pyproj import Transformer
        cache[key] = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    return cache[key]


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
    # Sombreado del relieve del MDT (IDEE/IGN). El WMS
    # servicios.idee.es/wms-inspire/mdt (EL.ElevationGridCoverage) solo da
    # tintas hipsométricas en gris; el sombreado real es la capa WMTS
    # 'Relieve'. Resolución nativa ~15-20 m: desde z15 ya solo se
    # amplían píxeles, de ahí el max_zoom 14 en _PROV_META.
    "IGN Relieve (MDT sombreado)": (
        "https://servicios.idee.es/wmts/mdt?SERVICE=WMTS&REQUEST=GetTile"
        "&VERSION=1.0.0&LAYER=Relieve&STYLE=default"
        "&FORMAT=image/jpeg&TILEMATRIXSET=GoogleMapsCompatible"
        "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    ),
    # (Stamen Terrain eliminado: el servicio stamen-tiles.*.fastly.net
    #  cerró en 2023 y siempre fallaba.)
    "Google Satélite": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "Google Satélite Híbrido": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
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
    "Topográfico Andalucía (MTA10)": {
        "url": (
            "https://www.ideandalucia.es/wms/mta10r_2001-2013?"
            "SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
            "&LAYERS=mta10r_2001-2013&STYLES="
            "&CRS=EPSG:25830&FORMAT=image/png"
        ),
        "attribution": "© Junta de Andalucía – IECA, MTA10",
    },
    # El WMS de Catastro solo habla 1.1.1 (con 1.3.0 responde HTTP 400) y
    # rechaza el User-Agent por defecto de curl; con el nuestro responde.
    "Catastro (parcelas)": {
        "url": (
            "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx?"
            "SERVICE=WMS&REQUEST=GetMap&VERSION=1.1.1"
            "&LAYERS=Catastro&STYLES="
            "&SRS=EPSG:25830&FORMAT=image/png"
        ),
        "attribution": "© Dirección General del Catastro",
    },
}

# Capas WMS superpuestas predefinidas (se dibujan semitransparentes SOBRE
# el fondo). Todas verificadas con GetCapabilities + GetMap EPSG:25830.
# Claves: url (endpoint base, los parámetros GetMap se construyen en
# añadir_overlay_wms), capa (LAYERS), formato, alpha por defecto, version
# WMS y atribución.
OVERLAYS_PREDEFINIDOS = {
    "Catastro (parcelas)": {
        "url": "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx",
        "capa": "Catastro",
        "formato": "image/png",
        "alpha": 0.8,
        "version": "1.1.1",
        "attribution": "© Dirección General del Catastro",
    },
    "Límites municipales (IGN)": {
        "url": "https://www.ign.es/wms-inspire/unidades-administrativas",
        "capa": "AU.AdministrativeBoundary",
        "formato": "image/png",
        "alpha": 0.9,
        "version": "1.3.0",
        "attribution": "© IGN España – Unidades administrativas",
    },
    "Montes Públicos de Andalucía (REDIAM)": {
        "url": ("https://www.juntadeandalucia.es/medioambiente/mapwms/"
                "REDIAM_Montes_Publicos_Andalucia"),
        "capa": "montes",
        "formato": "image/png",
        "alpha": 0.7,
        "version": "1.3.0",
        "attribution": "© Junta de Andalucía – REDIAM, Montes Públicos",
    },
}

# PROVIDERS_CTX se construye siempre para que el desplegable de la GUI
# muestre todos los proveedores disponibles, con o sin contextily.
_PROV_META = {
    "IGN Relieve (MDT sombreado)": {
        "max_zoom": 14, "attribution": "© IGN España – MDT (IDEE)"},
    "Catastro (parcelas)": {
        "max_zoom": 18, "attribution": "© Dirección General del Catastro"},
    "OpenStreetMap": {"max_zoom": 19, "attribution": "© OpenStreetMap"},
    "PNOA Ortofoto (IGN)": {"max_zoom": 20, "attribution": "© IGN España"},
    "IGN Topográfico": {"max_zoom": 18, "attribution": "© IGN España"},
    "IGN Base": {"max_zoom": 18, "attribution": "© IGN España"},
    "PNOA Máxima Actualidad": {"max_zoom": 20, "attribution": "© IGN España"},
    "Google Satélite": {"max_zoom": 20, "attribution": "© Google"},
    "Google Satélite Híbrido": {"max_zoom": 20, "attribution": "© Google"},
    "IGN MTN25 (WMS 1:25.000)": {"max_zoom": 18, "attribution": "© IGN España – MTN25"},
    "IGN MTN50 (WMS 1:50.000)": {"max_zoom": 18, "attribution": "© IGN España – MTN50"},
    "Topográfico Andalucía (MTA10)": {
        "max_zoom": 18, "attribution": "© Junta de Andalucía – IECA, MTA10"},
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
        "max_zoom": _PROV_META.get(_wms_name, {}).get("max_zoom", 18),
        "attribution": _wms_info.get("attribution", ""),
        "wms": True,
    }

# Orden del desplegable de la GUI: IGN, Andalucía, Catastro, Google, OSM.
# Los proveedores que no figuren aquí se añaden al final en su orden.
_ORDEN_PROVEEDORES = [
    "PNOA Ortofoto (IGN)",
    "PNOA Máxima Actualidad",
    "IGN Topográfico",
    "IGN Base",
    "IGN MTN25 (WMS 1:25.000)",
    "IGN MTN50 (WMS 1:50.000)",
    "IGN Relieve (MDT sombreado)",
    "Topográfico Andalucía (MTA10)",
    "Catastro (parcelas)",
    "Google Satélite",
    "Google Satélite Híbrido",
    "OpenStreetMap",
]
PROVIDERS_CTX = {
    **{k: PROVIDERS_CTX[k] for k in _ORDEN_PROVEEDORES if k in PROVIDERS_CTX},
    **{k: v for k, v in PROVIDERS_CTX.items() if k not in _ORDEN_PROVEEDORES},
}


def obtener_atribucion(proveedor_key: str) -> str:
    """Texto de atribución (copyright) de un proveedor de fondo u overlay.

    Busca en _PROV_META, CAPAS_WMS y OVERLAYS_PREDEFINIDOS. Devuelve ""
    si la clave es desconocida (WMS propio, ráster local...).
    """
    if not proveedor_key:
        return ""
    for fuente in (_PROV_META, CAPAS_WMS, OVERLAYS_PREDEFINIDOS):
        info = fuente.get(proveedor_key)
        if isinstance(info, dict) and info.get("attribution"):
            return info["attribution"]
    return ""


# ---------------------------------------------------------------------------
# Descarga manual de teselas (fallback si contextily falla con IGN)
# ---------------------------------------------------------------------------

def _px_objetivo(ax, minimo: int = 512, maximo: int = 4096) -> int:
    """Píxeles de ancho que necesita un eje al imprimirse.

    = ancho físico del eje (pulgadas) × dpi de salida (``fig.dpi_salida``,
    que fija MaquetadorPlano según la calidad elegida; tope 300). Es la
    resolución justa para pedir/embeber imágenes: el mapa principal de un
    A3 a 300 dpi necesita ~4000 px, pero el minimapa de localización (5 cm)
    solo ~600 px. Antes se pedían 4096 px también para el minimapa.
    """
    try:
        fig = ax.figure
        dpi_salida = float(getattr(fig, "dpi_salida", 300) or 300)
        dpi_salida = min(dpi_salida, 300.0)
        ancho_in = float(fig.get_size_inches()[0]) * float(ax.get_position().width)
        px = int(round(ancho_in * dpi_salida))
    except Exception:
        px = maximo
    return max(minimo, min(maximo, px))


def _reducir_si_excede(img, px_objetivo: int, margen: float = 1.5):
    """Reduce (LANCZOS) una imagen PIL si es mucho mayor que lo necesario.

    Con ``interpolation="none"`` la imagen se embebe en el PDF tal cual;
    si viniera de la caché con más resolución de la que el eje necesita,
    engordaría el PDF sin aportar nada.
    """
    try:
        if img.width > px_objetivo * margen:
            factor = px_objetivo / float(img.width)
            nuevo = (max(1, int(round(img.width * factor))),
                     max(1, int(round(img.height * factor))))
            return img.resize(nuevo, Image.LANCZOS)
    except Exception:
        pass
    return img


def _dimensiones_wms(extent_x: float, extent_y: float,
                     m_por_px: float = 2.0, minimo: int = 512,
                     maximo: int = 4096) -> tuple:
    """Calcula WIDTH/HEIGHT para un GetMap conservando el aspect del BBOX.

    Parte de ~``m_por_px`` metros por píxel y escala AMBOS lados con el
    mismo factor para respetar el mínimo (lado corto >= ``minimo``) y el
    máximo (lado largo <= ``maximo``). Aplicar los límites por separado a
    cada lado, como se hacía antes, deformaba la imagen en formatos
    apaisados a escalas pequeñas (p. ej. A4 a 1:5.000 salía 692x512 para
    un BBOX de proporción 1,95).
    """
    w0 = max(float(extent_x) / m_por_px, 1.0)
    h0 = max(float(extent_y) / m_por_px, 1.0)
    factor = max(1.0, minimo / min(w0, h0))
    factor = min(factor, maximo / max(w0, h0))
    return max(1, int(round(w0 * factor))), max(1, int(round(h0 * factor)))


def _verificar_respuesta_imagen(resp):
    """Lanza un error claro si el servidor devolvió algo que no es imagen.

    Muchos WMS/WMTS responden HTTP 200 con un XML ServiceExceptionReport
    (capa errónea, BBOX inválido...); sin esta comprobación el error real
    se perdía y el usuario solo veía un fondo gris.
    """
    ctype = resp.headers.get("Content-Type", "").lower()
    if (not ctype or ctype.startswith("image/")
            or "octet-stream" in ctype):
        # Sin cabecera o binario genérico (algunos CDN/WMS propios):
        # no se puede juzgar aquí, PIL validará el contenido
        return
    # Extraer un fragmento legible del cuerpo para el diagnóstico
    try:
        detalle = resp.content[:400].decode("utf-8", errors="replace").strip()
    except Exception:
        detalle = f"contenido no decodificable ({ctype or 'tipo desconocido'})"
    raise ValueError(
        f"El servidor devolvió '{ctype or 'desconocido'}' en vez de una "
        f"imagen. Respuesta: {detalle}")


_HEADERS_HTTP = {
    "User-Agent": "GeneradorPlanosForestales/1.0",
    "Referer": "https://www.ign.es/",
}


# Evento de cancelación (lo fija GeneradorPlanos) para que PARAR
# interrumpa también las descargas en curso, no solo entre planos.
_evento_cancelacion = None


class DescargaCancelada(Exception):
    """El usuario canceló mientras se descargaba cartografía."""


# Hosts que no responden: se evitan durante un rato para que un servidor
# caído no bloquee minutos cada plano de una serie.
_HOSTS_CAIDOS = {}
_HOSTS_CAIDOS_SEG = 180.0
_SESION_TLS = _threading.local()
_REQUESTS_GET_ORIGINAL = requests.get


def _sesion_http():
    """requests.Session por hilo: reutiliza conexiones TLS (las teselas
    abrían una conexión nueva por petición)."""
    s = getattr(_SESION_TLS, "sesion", None)
    if s is None:
        s = requests.Session()
        _SESION_TLS.sesion = s
    return s


def _http_get(url, **kwargs):
    """GET vía la sesión del hilo; si ``requests.get`` ha sido sustituido
    (tests con mocks), se respeta esa sustitución."""
    if requests.get is not _REQUESTS_GET_ORIGINAL:
        return requests.get(url, **kwargs)
    return _sesion_http().get(url, **kwargs)


def _get_con_reintentos(url, params=None, headers=None, timeout=60,
                        intentos=3, espera=1.0):
    """GET con reintentos ante cortes de red y errores 5xx.

    - Timeout en dos partes (conexión 5 s / lectura ``timeout``): un
      servidor que no contesta no bloquea el plano un minuto por intento.
    - Reintenta también cortes a mitad de descarga (ChunkedEncodingError).
    - Si el usuario pulsa PARAR, aborta inmediatamente (DescargaCancelada).
    - Un host que ha agotado los reintentos se recuerda y se salta durante
      unos minutos en vez de volver a esperar en cada plano.
    """
    import time
    import urllib.parse
    host = ""
    try:
        host = urllib.parse.urlsplit(url).netloc.lower()
    except Exception:
        pass
    ahora = time.time()
    caido_hasta = _HOSTS_CAIDOS.get(host)
    if caido_hasta and ahora < caido_hasta:
        raise requests.ConnectionError(
            f"El servidor {host} no responde (se reintentará en "
            f"{int(caido_hasta - ahora)} s)")

    if isinstance(timeout, (int, float)):
        timeout = (5.0, float(timeout))
    ultimo = None
    for i in range(max(1, intentos)):
        if _evento_cancelacion is not None and _evento_cancelacion.is_set():
            raise DescargaCancelada("Descarga cancelada por el usuario.")
        try:
            resp = _http_get(url, params=params,
                             headers=headers or _HEADERS_HTTP,
                             timeout=timeout)
            if resp.status_code >= 500 and i < intentos - 1:
                ultimo = requests.HTTPError(
                    f"HTTP {resp.status_code}", response=resp)
            else:
                _HOSTS_CAIDOS.pop(host, None)
                return resp
        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            ultimo = e
        if i < intentos - 1:
            time.sleep(espera * (i + 1))
    if host and isinstance(ultimo, (requests.ConnectionError, requests.Timeout)):
        _HOSTS_CAIDOS[host] = time.time() + _HOSTS_CAIDOS_SEG
    raise ultimo


def _imagen_a_array(img):
    """Convierte una imagen PIL en array RGB/RGBA apto para imshow.

    Las imágenes en paleta ('P', p. ej. Catastro o REDIAM) o escala de
    grises ('L') se convertirían en un array 2D de índices y matplotlib
    las pintaría con un colormap (viridis). La transparencia de la paleta
    se conserva como canal alfa.
    """
    if img.mode in ("RGB", "RGBA"):
        return np.array(img)
    if img.mode in ("P", "LA", "PA") or "transparency" in img.info:
        return np.array(img.convert("RGBA"))
    return np.array(img.convert("RGB"))


def _resolucion_tesela(lat, zoom):
    """Metros por píxel de una tesela WebMercator de 256 px en ``lat``."""
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


def _calcular_zoom_teselas(lon_min, lat_min, lon_max, lat_max,
                           max_zoom=18, m_por_px=2.0,
                           max_teselas_lado=24, teselas_comodas=8):
    """Elige el nivel de zoom de teselas para un extent geográfico.

    Criterios:
      - La resolución de la tesela debe ser al menos la de impresión
        (``m_por_px`` metros/píxel, ~2 m/px como los GetMap WMS).
      - Sin superar ``max_teselas_lado`` teselas en X NI en Y (antes solo
        se acotaba X y en formatos verticales se descargaban de más).
      - Si con pocas teselas (``teselas_comodas`` por lado) se consigue
        todavía más detalle, se usa ese zoom (extents pequeños).
      - Nunca por encima del ``max_zoom`` del proveedor.
    """
    max_zoom = int(max_zoom or 18)
    lat_c = (lat_min + lat_max) / 2.0

    def _n_teselas(z):
        tx0, ty0 = _lat_lon_to_tile(lat_max, lon_min, z)
        tx1, ty1 = _lat_lon_to_tile(lat_min, lon_max, z)
        return abs(tx1 - tx0) + 1, abs(ty1 - ty0) + 1

    def _max_zoom_con(limite):
        mejor = 1
        for z in range(1, max_zoom + 1):
            nx, ny = _n_teselas(z)
            if nx <= limite and ny <= limite:
                mejor = z
            else:
                break
        return mejor

    # Zoom mínimo que alcanza la resolución de impresión
    z_necesario = max_zoom
    for z in range(1, max_zoom + 1):
        if _resolucion_tesela(lat_c, z) <= m_por_px:
            z_necesario = z
            break

    z_tope = _max_zoom_con(max_teselas_lado)
    z_comodo = _max_zoom_con(teselas_comodas) if teselas_comodas else 1
    return max(1, min(max_zoom, z_tope, max(z_necesario, z_comodo)))


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

    # Descargar (con reintento ante cortes de conexión transitorios)
    resp = _get_con_reintentos(url, timeout=timeout, intentos=4, espera=0.5)
    resp.raise_for_status()
    _verificar_respuesta_imagen(resp)
    img = Image.open(io.BytesIO(resp.content))

    # Guardar en caché
    try:
        _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img.save(cache_path, "PNG")
    except Exception:
        pass

    return img


def _descargar_teselas_manual(ax, url_template, xmin, xmax, ymin, ymax,
                              crs_epsg=25830, max_zoom=18, m_por_px=2.0):
    """Descarga teselas manualmente y las dibuja en el eje matplotlib.

    Convierte las coordenadas del eje (EPSG:25830) a EPSG:4326 para
    calcular tiles, descarga y compone UNA sola imagen de fondo (mosaico)
    que se dibuja con un único ``imshow``. El zoom se elige para que el
    mosaico tenga aproximadamente los píxeles que el eje necesita al
    imprimir (``_px_objetivo``), sin bajar de ``m_por_px`` metros/píxel de
    detalle, con como mucho 24 teselas por lado y sin pasar del
    ``max_zoom`` del proveedor.
    """
    transformer = _get_transformer(f"EPSG:{crs_epsg}", "EPSG:4326")
    # Las 4 esquinas: en UTM el rectángulo no es un rectángulo lon/lat
    esquinas = [transformer.transform(x, y)
                for x in (xmin, xmax) for y in (ymin, ymax)]
    lon_min = min(c[0] for c in esquinas)
    lon_max = max(c[0] for c in esquinas)
    lat_min = min(c[1] for c in esquinas)
    lat_max = max(c[1] for c in esquinas)

    # Resolución necesaria según el tamaño físico del eje (nunca más fina
    # que m_por_px: no hace falta más detalle del que el papel muestra)
    px_obj = _px_objetivo(ax)
    m_px_necesario = max(float(m_por_px) * 0.25,
                         float(xmax - xmin) / float(px_obj))
    zoom = _calcular_zoom_teselas(lon_min, lat_min, lon_max, lat_max,
                                  max_zoom=max_zoom,
                                  m_por_px=max(m_px_necesario, 0.3),
                                  teselas_comodas=0)

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
        return (tx, ty, _descargar_tesela(url_template, zoom, tx, ty))

    # Hasta 2 rondas: las teselas que fallan (cortes de conexión de
    # servidores públicos) se reintentan una vez más para no dejar huecos.
    pendientes = tile_coords
    for _ronda in range(2):
        fallidas = []
        with ThreadPoolExecutor(max_workers=min(8, len(pendientes) or 1)) as pool:
            futures = {pool.submit(_fetch_tile, tc): tc for tc in pendientes}
            for fut in as_completed(futures):
                try:
                    tiles.append(fut.result())
                except Exception:
                    fallidas.append(futures[fut])
        if not fallidas:
            break
        pendientes = fallidas

    if not tiles:
        return False

    # ── Componer un único mosaico RGBA (huecos transparentes) ──
    tam = tiles[0][2].width or 256
    n_x = tx_max - tx_min + 1
    n_y = ty_max - ty_min + 1
    mosaico = np.zeros((n_y * tam, n_x * tam, 4), dtype=np.uint8)
    for tx, ty, img in tiles:
        arr = _imagen_a_array(img)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.shape[-1] == 3:
            arr = np.dstack([arr, np.full(arr.shape[:2], 255, dtype=np.uint8)])
        if arr.dtype != np.uint8:
            arr = np.clip(arr * (255 if arr.max() <= 1.0 else 1), 0, 255).astype(np.uint8)
        y0 = (ty - ty_min) * tam
        x0 = (tx - tx_min) * tam
        h, w = min(tam, arr.shape[0]), min(tam, arr.shape[1])
        mosaico[y0:y0 + h, x0:x0 + w] = arr[:h, :w, :4]

    # Reducir a lo que el eje necesita (el zoom se elige por exceso)
    img_mos = Image.fromarray(mosaico, "RGBA")

    # Límites del mosaico en Web Mercator (EPSG:3857), que es el CRS real
    # de las teselas.
    MERC = 20037508.342789244
    mx0 = tx_min / n * 2 * MERC - MERC
    mx1 = (tx_max + 1) / n * 2 * MERC - MERC
    my1 = MERC - ty_min / n * 2 * MERC
    my0 = MERC - (ty_max + 1) / n * 2 * MERC

    # ── Reproyectar el mosaico a EPSG:25830 (alineación exacta) ──
    # Un rectángulo Web Mercator NO es un rectángulo en UTM: colocarlo por
    # sus esquinas ignora la convergencia de meridianos (6 m de error en
    # Cazorla, pero 300-400 m en Huelva). Se warpea con rasterio sobre la
    # malla exacta del plano; si rasterio no está, se cae a las esquinas.
    try:
        from rasterio.warp import reproject, Resampling
        from rasterio.transform import from_bounds as _from_bounds
        h_s, w_s = mosaico.shape[:2]
        w_d = int(px_obj)
        h_d = max(1, int(round(w_d * (ymax - ymin) / max(xmax - xmin, 1e-9))))
        src_tr = _from_bounds(mx0, my0, mx1, my1, w_s, h_s)
        dst_tr = _from_bounds(xmin, ymin, xmax, ymax, w_d, h_d)
        destino = np.zeros((4, h_d, w_d), dtype=np.uint8)
        reproject(
            source=np.ascontiguousarray(np.moveaxis(mosaico, -1, 0)),
            destination=destino,
            src_transform=src_tr, src_crs="EPSG:3857",
            dst_transform=dst_tr, dst_crs=f"EPSG:{crs_epsg}",
            resampling=Resampling.bilinear, dst_nodata=0,
        )
        ax.imshow(
            np.moveaxis(destino, 0, -1),
            extent=[xmin, xmax, ymin, ymax],
            aspect="auto", zorder=0, interpolation="none",
        )
        return True
    except Exception:
        pass

    # Fallback sin rasterio: colocar por las esquinas (aproximado)
    img_mos = _reducir_si_excede(img_mos, px_obj, margen=1.25)
    mos_lon_min = tx_min / n * 360.0 - 180.0
    mos_lon_max = (tx_max + 1) / n * 360.0 - 180.0
    mos_lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty_min / n))))
    mos_lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty_max + 1) / n))))
    transformer_inv = _get_transformer("EPSG:4326", f"EPSG:{crs_epsg}")
    mxmin_m, mymin_m = transformer_inv.transform(mos_lon_min, mos_lat_min)
    mxmax_m, mymax_m = transformer_inv.transform(mos_lon_max, mos_lat_max)
    ax.imshow(
        np.asarray(img_mos),
        extent=[mxmin_m, mxmax_m, mymin_m, mymax_m],
        aspect="auto",
        zorder=0,
        interpolation="none",
    )
    return True


def _descargar_wms(ax, wms_url, xmin, xmax, ymin, ymax, crs_epsg=25830):
    """Descarga una imagen WMS GetMap completa para el bbox y la dibuja en el eje.

    A diferencia de tiles, solicita una sola imagen que cubre todo el extent,
    lo que da mejor calidad a escalas cartográficas específicas (1:25.000, etc.).
    """
    # Tamaño de imagen según el tamaño físico del eje y la calidad de
    # salida (_px_objetivo), con mínimo 512 px. Ambos límites se aplican
    # con UN MISMO factor a los dos lados para conservar el aspect ratio
    # del BBOX: si no, el servidor renderiza la imagen deformada.
    px_obj = _px_objetivo(ax)
    width, height = _dimensiones_wms(xmax - xmin, ymax - ymin,
                                     m_por_px=float(xmax - xmin) / px_obj,
                                     maximo=px_obj)

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
        resp = _get_con_reintentos(url, timeout=60)
        resp.raise_for_status()
        _verificar_respuesta_imagen(resp)
        img = Image.open(io.BytesIO(resp.content))

        try:
            _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
        except Exception:
            pass

    ax.imshow(
        _imagen_a_array(_reducir_si_excede(img, px_obj)),
        extent=[xmin, xmax, ymin, ymax],
        aspect="auto",
        zorder=0,
        interpolation="none",
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
        # Avisar si el CRS del ráster no coincide con el del plano: se
        # dibujaría desplazado en silencio.
        try:
            epsg_src = src.crs.to_epsg() if src.crs else None
        except Exception:
            epsg_src = None
        if epsg_src is not None and epsg_src != 25830:
            warnings.warn(
                f"El ráster '{os.path.basename(ruta_raster)}' está en "
                f"EPSG:{epsg_src}, pero el plano usa EPSG:25830. "
                "Reproyéctalo o el fondo saldrá desplazado.")

        # Recortar al extent del plano, LIMITADO a la extensión del ráster:
        # si el plano sobresale del ráster, rasterio solo devuelve la parte
        # que existe y la imagen se colocaba/estiraba con la ventana pedida
        # completa (fondo desplazado hasta 500 m o estirado 2x en silencio).
        from rasterio.windows import Window
        window = from_bounds(xmin, ymin, xmax, ymax, src.transform)
        try:
            window = window.intersection(Window(0, 0, src.width, src.height))
        except Exception:
            raise ValueError(
                "El ráster no cubre la extensión del plano "
                f"({os.path.basename(ruta_raster)})")
        if window.width <= 0 or window.height <= 0:
            raise ValueError(
                "El ráster no cubre la extensión del plano "
                f"({os.path.basename(ruta_raster)})")
        # Leer bandas visibles (máx 3 para RGB)
        n_bands = min(src.count, 3)

        # Lectura DECIMADA: una ortofoto de 0,25 m/px en un A3 a 1:10.000
        # supondría ~16.000 px de ancho (cientos de MB y minutos de
        # proceso) para acabar impresa a ~4.000 px. Se lee ya reducida con
        # remuestreo 'average' hasta un máximo de 4096 px por lado.
        try:
            from rasterio.enums import Resampling
            w_win = max(1, int(round(window.width)))
            h_win = max(1, int(round(window.height)))
            factor = max(w_win, h_win) / 4096.0
            if factor > 1.0:
                out_shape = (n_bands, max(1, int(h_win / factor)),
                             max(1, int(w_win / factor)))
                data = src.read(list(range(1, n_bands + 1)), window=window,
                                out_shape=out_shape,
                                resampling=Resampling.average)
            else:
                data = src.read(list(range(1, n_bands + 1)), window=window)
        except Exception:
            data = src.read(list(range(1, n_bands + 1)), window=window)

        # Si el plano no intersecta el ráster, la ventana queda vacía.
        # Hay que fallar para que el llamador haga fallback a WMS en vez
        # de dar por bueno un fondo en blanco.
        if data.size == 0 or data.shape[1] == 0 or data.shape[2] == 0:
            raise ValueError(
                "El ráster no cubre la extensión del plano "
                f"({os.path.basename(ruta_raster)})")

        # Calcular extent real de la ventana leída (la ventana, no el
        # array decimado: así el extent es correcto aunque se haya reducido)
        win_transform = src.window_transform(window)
        w_px = window.width
        h_px = window.height
        rx_min = min(win_transform.c, win_transform.c + w_px * win_transform.a)
        rx_max = max(win_transform.c, win_transform.c + w_px * win_transform.a)
        ry_min = min(win_transform.f, win_transform.f + h_px * win_transform.e)
        ry_max = max(win_transform.f, win_transform.f + h_px * win_transform.e)

        # Manejar NODATA: convertir píxeles sin datos en transparentes
        nodata = src.nodata
        cmap_kw = {}
        if n_bands == 1:
            # Una banda: respetar la paleta del ráster (hojas MTN en paleta)
            # o mostrar en gris; antes salía en falso color (viridis).
            try:
                paleta = src.colormap(1)
            except Exception:
                paleta = None
            if paleta:
                lut = np.zeros((256, 4), dtype=np.uint8)
                lut[:, 3] = 255
                for k, v in paleta.items():
                    if 0 <= k < 256:
                        lut[k, :len(v[:4])] = v[:4]
                idx = np.clip(data[0], 0, 255).astype(np.uint8)
                img = lut[idx]
                if nodata is not None:
                    img[data[0] == nodata, 3] = 0
            else:
                img = data[0].astype(float)
                if nodata is not None:
                    img = np.ma.masked_equal(img, nodata)
                cmap_kw = {"cmap": "gray"}
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
        aspect="auto", zorder=0, interpolation="none", **cmap_kw,
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

    # Comprobar si el VRT existente es válido (más reciente que los rásters
    # y con todas sus fuentes referenciadas aún presentes en disco)
    if vrt_path.exists():
        vrt_mtime = vrt_path.stat().st_mtime
        max_raster_mtime = max(os.path.getmtime(f) for f in archivos)
        if vrt_mtime > max_raster_mtime and _vrt_fuentes_existen(vrt_path):
            return str(vrt_path)

    # Homogeneizar CRS: si hay hojas en distintos husos, reproyecta las
    # minoritarias al CRS dominante. Si rasterio no está disponible o todos
    # los rásters ya comparten CRS, devuelve la lista tal cual.
    archivos_mosaico = _homogeneizar_crs_rasters(archivos, carpeta_p)

    # 1) Intentar con gdalbuildvrt (el método más robusto si está disponible).
    #    La lista de entradas va en un fichero auxiliar para no exceder el
    #    límite de longitud de línea de comandos de Windows (~32 KB) con
    #    carpetas que contienen cientos de hojas.
    lista_txt = None
    try:
        import tempfile
        fd, lista_txt = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(archivos_mosaico))
        cmd = ["gdalbuildvrt", "-input_file_list", lista_txt, str(vrt_path)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(vrt_path)
    except (FileNotFoundError, subprocess.CalledProcessError, OSError):
        pass
    finally:
        if lista_txt:
            try:
                os.unlink(lista_txt)
            except OSError:
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

def _vrt_fuentes_existen(vrt_path) -> bool:
    """Comprueba que todas las fuentes referenciadas por un VRT existen.

    Un VRT cacheado puede apuntar a rutas absolutas (p. ej. dentro de
    ``.mosaico_warped*``) que el usuario haya borrado o movido; en ese caso
    hay que regenerarlo en vez de devolver un mosaico roto.
    """
    try:
        from xml.etree import ElementTree as ET
        tree = ET.parse(str(vrt_path))
        for el in tree.iter("SourceFilename"):
            ruta = (el.text or "").strip()
            if not ruta:
                continue
            if el.get("relativeToVRT") == "1":
                ruta = str(Path(vrt_path).parent / ruta)
            if not os.path.exists(ruta):
                return False
        return True
    except Exception:
        return False


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

    # Leer CRS de cada archivo. Distinguimos tres casos:
    #   - CRS válido
    #   - abre pero sin proyección (CRS "vacío")  -> None  (hay que avisar)
    #   - rasterio no puede abrirlo (p. ej. ECW sin driver en la rueda pip)
    #     -> se deja pasar tal cual: gdalbuildvrt/osgeo pueden tener el
    #     driver aunque rasterio no, y antes esto funcionaba así.
    crs_por_archivo = []
    ilegibles = set()
    for fp in archivos:
        try:
            with rasterio.open(fp) as src:
                crs = src.crs
                if not _crs_tiene_definicion(crs):
                    crs = None
                crs_por_archivo.append(crs)
        except Exception:
            crs_por_archivo.append(None)
            ilegibles.add(fp)

    # ¿Son todos iguales? Un CRS None de un ráster legible cuenta como
    # heterogéneo: si lo dejásemos pasar, el builder manual del VRT lo
    # rechazaría más adelante con un mensaje engañoso de "CRS distinto".
    # Al tratarlo aquí, _warpear_fuente produce un error claro y accionable
    # ("el ráster no tiene un CRS definido...").
    primero_valido = next((c for c in crs_por_archivo if c is not None), None)
    if primero_valido is None:
        return list(archivos)
    hay_sin_crs = any(
        c is None and fp not in ilegibles
        for fp, c in zip(archivos, crs_por_archivo))
    if not hay_sin_crs and all(
            _crs_iguales(c, primero_valido)
            for fp, c in zip(archivos, crs_por_archivo)
            if fp not in ilegibles):
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
    etiqueta_destino = f"EPSG:{epsg_destino}" if epsg_destino else "destino"

    resultado = []
    for fp, crs in zip(archivos, crs_por_archivo):
        if fp in ilegibles:
            # rasterio no lo abre: dejarlo pasar sin tocar (ver arriba)
            resultado.append(fp)
            continue
        if crs is not None and _crs_iguales(crs, crs_destino):
            resultado.append(fp)
            continue
        try:
            fp_warpeado = _warpear_fuente(fp, crs_destino, cache_dir)
            resultado.append(fp_warpeado)
        except Exception as e:
            # Si no se puede reproyectar una hoja concreta, abortamos con un
            # mensaje claro que oriente al usuario sobre cómo resolverlo.
            nombre = os.path.basename(fp)
            raise RuntimeError(
                f"No se pudo reproyectar al CRS común ({etiqueta_destino}) "
                f"la hoja '{nombre}'.\n\n"
                f"Detalle: {e}\n\n"
                "Posibles soluciones:\n"
                "  • Comprueba que la hoja tenga un CRS válido "
                "(abrir con QGIS → Propiedades).\n"
                "  • Si falta, asígnalo con "
                f"'gdal_edit.py -a_srs EPSG:<codigo> {nombre}'.\n"
                "  • Si el ráster está corrupto o es incompatible, "
                "muévelo fuera de la carpeta y vuelve a generar el mosaico."
            ) from e

    return resultado


def _crs_tiene_definicion(crs) -> bool:
    """Devuelve True si el CRS de rasterio contiene una definición usable.

    Rasterio devuelve un objeto CRS "vacío" (no None) cuando el ráster no
    tiene metadatos de proyección. Este helper normaliza esas dos formas
    de "no hay CRS".
    """
    if crs is None:
        return False
    # (No se usa crs.is_valid: está obsoleto en rasterio y desaparece en
    #  2.0; un CRS vacío se reconoce porque su WKT es una cadena vacía.)
    try:
        wkt = crs.to_wkt() if hasattr(crs, "to_wkt") else ""
        if not wkt:
            return False
    except Exception:
        return False
    return True


def _warpear_fuente(ruta_origen: str, crs_destino, cache_dir) -> str:
    """Crea una versión reproyectada (warpeada) de un ráster.

    Intenta, por orden, varias estrategias para maximizar las posibilidades
    de éxito cuando un ráster tiene metadatos incómodos (p. ej. hojas MTN
    con geometrías en el borde del huso UTM o datums antiguos):

      1. ``gdalwarp -of VRT`` (CLI) — rápido, sin materializar píxeles.
      2. ``osgeo.gdal.Warp(format='VRT')`` — equivalente con el binding.
      3. ``gdalwarp -of GTiff`` (CLI) — materializa píxeles; es menos
         eficiente pero tolera casos que el VRT rechaza con
         'Chunk and warp failed' porque el pipeline de chunking valida la
         extensión final al escribir.
      4. ``osgeo.gdal.Warp(format='GTiff')`` — equivalente con el binding.
      5. ``rasterio`` → GeoTIFF materializado (pura Python). Reintenta con
         resampleo ``nearest`` y ``bilinear`` para tolerar fuentes cuyas
         características impiden interpolar.

    Si todos los intentos fallan, se lanza ``RuntimeError`` con el detalle
    acumulado de cada tentativa para ayudar al usuario a diagnosticar el
    problema en esa hoja concreta.

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

    def _cache_warp_valida(path_out) -> bool:
        """True si el warpeado cacheado abre bien y tiene el CRS destino.

        Una ejecución anterior interrumpida puede haber dejado un fichero
        parcial/corrupto; si lo devolviéramos, el mosaico fallaría después
        con un error confuso de CRS.
        """
        try:
            import rasterio as _rio
        except ImportError:
            return True  # sin rasterio no podemos validar; asumir válido
        try:
            with _rio.open(str(path_out)) as _ds:
                return (_crs_tiene_definicion(_ds.crs)
                        and _crs_iguales(_ds.crs, crs_destino))
        except Exception:
            return False

    def _limpiar_parcial(path_out):
        try:
            if path_out.exists():
                path_out.unlink()
        except OSError:
            pass

    origen_mtime = origen_p.stat().st_mtime
    if (vrt_out.exists() and vrt_out.stat().st_mtime > origen_mtime
            and _cache_warp_valida(vrt_out)):
        return str(vrt_out)
    if (tif_out.exists() and tif_out.stat().st_mtime > origen_mtime
            and _cache_warp_valida(tif_out)):
        return str(tif_out)

    t_srs = f"EPSG:{epsg}" if epsg else None
    if t_srs is None:
        try:
            t_srs = crs_destino.to_wkt()
        except Exception:
            t_srs = None
    if t_srs is None:
        raise ValueError("CRS de destino inválido")

    # Validación previa: si el ráster no tiene CRS definido, no se puede
    # reproyectar. Lanzamos un error claro antes de gastar tiempo en los
    # fallbacks, porque ninguno de ellos podría inferir la proyección.
    try:
        import rasterio as _rio
        with _rio.open(str(origen_p)) as _src:
            if not _crs_tiene_definicion(_src.crs):
                raise RuntimeError(
                    "el ráster no tiene un CRS definido en sus metadatos. "
                    "Asigna uno con 'gdal_edit.py -a_srs EPSG:<codigo> "
                    f"{origen_p.name}' o exclúyelo de la carpeta"
                )
    except ImportError:
        pass  # sin rasterio no podemos validar, seguimos con los fallbacks

    errores = []

    # 1) gdalwarp CLI → VRT
    try:
        cmd = [
            "gdalwarp", "-overwrite", "-of", "VRT",
            "-t_srs", t_srs,
            "-r", "near",
            str(origen_p), str(vrt_out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(vrt_out)
    except FileNotFoundError:
        errores.append("gdalwarp CLI no disponible en PATH")
    except subprocess.CalledProcessError as e:
        _limpiar_parcial(vrt_out)
        errores.append(
            f"gdalwarp CLI (VRT): {_extraer_mensaje_stderr(e.stderr)}")

    # 2) osgeo.gdal.Warp → VRT
    try:
        from osgeo import gdal  # type: ignore
        try:
            res = gdal.Warp(
                str(vrt_out), str(origen_p),
                format="VRT", dstSRS=t_srs, resampleAlg="near")
            if res is not None:
                res = None  # cerrar dataset
                return str(vrt_out)
            _limpiar_parcial(vrt_out)
            errores.append("osgeo.gdal.Warp (VRT): devolvió None")
        except Exception as e:
            _limpiar_parcial(vrt_out)
            errores.append(f"osgeo.gdal.Warp (VRT): {e}")
    except ImportError:
        errores.append("binding osgeo.gdal no disponible")

    # 3) gdalwarp CLI → GeoTIFF (materializa píxeles; tolera casos que
    #    el modo VRT rechaza con 'Chunk and warp failed')
    try:
        cmd = [
            "gdalwarp", "-overwrite", "-of", "GTiff",
            "-t_srs", t_srs,
            "-r", "near",
            "-co", "COMPRESS=LZW",
            "-co", "TILED=YES",
            "-co", "BIGTIFF=IF_SAFER",
            str(origen_p), str(tif_out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(tif_out)
    except FileNotFoundError:
        pass  # CLI ya registrada como no disponible
    except subprocess.CalledProcessError as e:
        _limpiar_parcial(tif_out)
        errores.append(
            f"gdalwarp CLI (GeoTIFF): {_extraer_mensaje_stderr(e.stderr)}")

    # 4) osgeo.gdal.Warp → GeoTIFF
    try:
        from osgeo import gdal  # type: ignore
        try:
            res = gdal.Warp(
                str(tif_out), str(origen_p),
                format="GTiff", dstSRS=t_srs, resampleAlg="near",
                creationOptions=[
                    "COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_SAFER"])
            if res is not None:
                res = None  # cerrar dataset
                return str(tif_out)
            _limpiar_parcial(tif_out)
            errores.append("osgeo.gdal.Warp (GeoTIFF): devolvió None")
        except Exception as e:
            _limpiar_parcial(tif_out)
            errores.append(f"osgeo.gdal.Warp (GeoTIFF): {e}")
    except ImportError:
        pass  # ya registrado antes

    # 5) rasterio → GeoTIFF (última opción, pura Python). Reintenta con
    #    distintas estrategias de resampleo por si el pipeline interno
    #    falla con una concreta.
    try:
        import rasterio
        from rasterio.warp import (
            calculate_default_transform, reproject, Resampling,
        )
    except ImportError as e:
        errores.append(f"rasterio no disponible: {e}")
        rasterio = None

    if rasterio is not None:
        for resampling in (Resampling.nearest, Resampling.bilinear):
            try:
                with rasterio.open(str(origen_p)) as src:
                    if not _crs_tiene_definicion(src.crs):
                        errores.append(
                            f"rasterio ({resampling.name}): "
                            "el ráster no tiene CRS")
                        break
                    transform, width, height = calculate_default_transform(
                        src.crs, crs_destino,
                        src.width, src.height, *src.bounds)
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
                                resampling=resampling,
                            )
                return str(tif_out)
            except Exception as e:
                errores.append(f"rasterio ({resampling.name}): {e}")
                # Si dejamos un TIFF parcial, lo borramos para no
                # cachear un resultado corrupto
                try:
                    if tif_out.exists():
                        tif_out.unlink()
                except OSError:
                    pass

    detalles = "\n    - ".join(errores) if errores else "sin detalles"
    raise RuntimeError(
        "ningún método de reproyección funcionó para este ráster:\n    - "
        + detalles)


def _extraer_mensaje_stderr(stderr: str) -> str:
    """Extrae la última línea no vacía de la salida de error de GDAL.

    Los mensajes de GDAL por consola suelen incluir varias líneas (avisos
    de PROJ, progreso, etc.) antes del error real. Devolvemos la última
    línea significativa para que el mensaje al usuario sea compacto pero
    informativo.
    """
    if not stderr:
        return "código de salida no-cero (sin stderr)"
    lineas = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
    if not lineas:
        return "código de salida no-cero (sin stderr)"
    return lineas[-1]


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

    # Verificar compatibilidad básica entre rásters. Usamos _crs_iguales
    # (comparación por EPSG cuando sea posible) en lugar de == sobre objetos
    # CRS de rasterio, porque dos hojas con el mismo EPSG pueden tener WKTs
    # distintos (según la versión de PROJ/GDAL que los escribió) y la
    # comparación directa las marcaría erróneamente como incompatibles.
    incompatibles = []
    if not _crs_tiene_definicion(crs):
        incompatibles.append(
            f"{os.path.basename(primera['path'])} no tiene CRS definido")
    for s in fuentes[1:]:
        nombre = os.path.basename(s["path"])
        if not _crs_tiene_definicion(s["crs"]):
            incompatibles.append(f"{nombre} no tiene CRS definido")
        elif not _crs_iguales(s["crs"], crs):
            incompatibles.append(f"CRS distinto en {nombre}")
        if s["count"] != n_bandas:
            incompatibles.append(f"Número de bandas distinto en {nombre}")
    if incompatibles:
        raise ValueError(
            "Los rásters no son compatibles para crear un mosaico:\n"
            + "\n".join(incompatibles[:5])
            + ("\n..." if len(incompatibles) > 5 else "")
            + "\n\nRevisa el CRS de esas hojas (QGIS → Propiedades) o "
            "asígnalo con 'gdal_edit.py -a_srs EPSG:<codigo> hoja.tif'.")

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
    px_obj = _px_objetivo(ax)
    width, height = _dimensiones_wms(xmax - xmin, ymax - ymin,
                                     m_por_px=float(xmax - xmin) / px_obj,
                                     maximo=px_obj)

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
        resp = _get_con_reintentos(
            base_url, params=params, timeout=60,
            headers={"User-Agent": "GeneradorPlanosForestales/1.0"})
        resp.raise_for_status()
        _verificar_respuesta_imagen(resp)
        img = Image.open(io.BytesIO(resp.content))

        try:
            _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
        except Exception:
            pass

    ax.imshow(
        _imagen_a_array(_reducir_si_excede(img, px_obj)),
        extent=[xmin, xmax, ymin, ymax],
        aspect="auto",
        zorder=0,
        interpolation="none",
    )
    return True


def _params_getmap_overlay(url: str, capa: str, xmin, xmax, ymin, ymax,
                           formato: str = "image/png", crs_epsg: int = 25830,
                           version: str = "1.3.0", estilos: str = "",
                           maximo_px: int = 4096):
    """Construye (base_url, params) de un GetMap transparente para overlay.

    Conserva los parámetros no-WMS que traiga la URL del usuario (p. ej.
    ``?language=spa`` o ``map=...`` de MapServer) y sustituye los WMS
    estándar. WMS 1.1.1 usa ``SRS``; 1.3.0 usa ``CRS`` (con EPSG:25830 el
    orden del BBOX es x,y en ambas versiones).
    """
    import urllib.parse
    partes = urllib.parse.urlsplit(url.strip())
    base_url = urllib.parse.urlunsplit(
        (partes.scheme, partes.netloc, partes.path, "", ""))
    claves_wms = {"service", "request", "version", "layers", "styles", "crs",
                  "srs", "format", "transparent", "width", "height", "bbox"}
    params = {k: v for k, v in urllib.parse.parse_qsl(partes.query)
              if k.lower() not in claves_wms}

    width, height = _dimensiones_wms(xmax - xmin, ymax - ymin,
                                     m_por_px=float(xmax - xmin) / max(maximo_px, 1),
                                     maximo=maximo_px)
    version = version or "1.3.0"
    params.update({
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": version,
        "LAYERS": capa,
        "STYLES": estilos or "",
        ("SRS" if version.startswith("1.1") else "CRS"): f"EPSG:{crs_epsg}",
        "FORMAT": formato or "image/png",
        "TRANSPARENT": "TRUE",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "BBOX": f"{xmin},{ymin},{xmax},{ymax}",
    })
    return base_url, params


def añadir_overlay_wms(ax, url: str, capa: str, xmin, xmax, ymin, ymax,
                       alpha: float = 0.6, formato: str = "image/png",
                       crs_epsg: int = 25830, version: str = "1.3.0",
                       estilos: str = ""):
    """Dibuja una capa WMS semitransparente ENCIMA del fondo del mapa.

    Pide un GetMap con TRANSPARENT=TRUE, conserva el canal alfa (RGBA) y lo
    pinta con ``imshow(zorder=1.5, alpha=alpha)``: por encima del fondo
    (zorder 0) y por debajo de montes/infraestructuras. Usa la misma caché
    en disco que ``descargar_wms_custom``.
    """
    import urllib.parse
    px_obj = _px_objetivo(ax)
    base_url, params = _params_getmap_overlay(
        url, capa, xmin, xmax, ymin, ymax, formato=formato,
        crs_epsg=crs_epsg, version=version, estilos=estilos,
        maximo_px=px_obj)

    full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
    cache_key = hashlib.md5(full_url.encode()).hexdigest()
    cache_path = _TILE_CACHE_DIR / f"wms_overlay_{cache_key}.png"

    img = None
    if cache_path.exists():
        try:
            img = Image.open(cache_path).copy()
        except Exception:
            cache_path.unlink(missing_ok=True)
            img = None

    if img is None:
        resp = _get_con_reintentos(
            base_url, params=params, timeout=60,
            headers={"User-Agent": "GeneradorPlanosForestales/1.0"})
        resp.raise_for_status()
        _verificar_respuesta_imagen(resp)
        img = Image.open(io.BytesIO(resp.content))
        img.load()
        try:
            _TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
        except Exception:
            pass

    # Siempre RGBA: las zonas sin datos deben quedar transparentes
    arr = np.array(_reducir_si_excede(img, px_obj).convert("RGBA"))
    try:
        alpha = float(alpha)
    except (TypeError, ValueError):
        alpha = 0.6
    alpha = min(1.0, max(0.0, alpha))
    ax.imshow(
        arr,
        extent=[xmin, xmax, ymin, ymax],
        aspect="auto",
        zorder=1.5,
        alpha=alpha,
        interpolation="none",
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

    # Líneas y puntos deben llevar el color de trazo: con color="none"
    # (pensado para el relleno de polígonos) eran invisibles.
    try:
        tipos = gdf.geometry.geom_type.str.lower()
        es_poligono = tipos.str.contains("polygon").all()
    except Exception:
        es_poligono = True
    if es_poligono:
        gdf.plot(ax=ax, color=facecolor, edgecolor=color,
                 linewidth=linewidth, alpha=alpha, zorder=2)
    else:
        gdf.plot(ax=ax, color=color, linewidth=linewidth, markersize=6,
                 alpha=alpha, zorder=2)


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
        # Usar contextily salvo con entradas WMS (esas no son tiles)
        if (proveedor is not None
                and (not isinstance(proveedor, dict)
                     or not proveedor.get("wms"))):
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
                max_zoom = _PROV_META.get(proveedor_key, {}).get("max_zoom", 18)
                exito_manual = _descargar_teselas_manual(
                    ax, url_template, xmin, xmax, ymin, ymax,
                    max_zoom=max_zoom,
                )
                if not exito_manual:
                    ax.set_facecolor("#E8E8E0")
            except Exception:
                ax.set_facecolor("#E8E8E0")
        else:
            ax.set_facecolor("#E8E8E0")
