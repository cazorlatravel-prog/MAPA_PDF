"""
Gestión de archivos recientes (shapefiles y proyectos).

Persiste las últimas rutas abiertas en un JSON dentro de la carpeta de
caché de la aplicación (~/.mapa_pdf_cache/recientes.json). Es robusto ante
JSON corrupto o ausente: en caso de error devuelve estructuras vacías sin
lanzar excepciones.
"""

import json
from pathlib import Path

# Tipos válidos de recientes
TIPO_SHAPEFILE = "shapefiles"
TIPO_PROYECTO = "proyectos"

_MAX = 8
_DIR_CACHE = Path.home() / ".mapa_pdf_cache"
_RUTA_JSON = _DIR_CACHE / "recientes.json"


def _vacio() -> dict:
    return {TIPO_SHAPEFILE: [], TIPO_PROYECTO: []}


def cargar_recientes() -> dict:
    """Devuelve un dict {'shapefiles': [...], 'proyectos': [...]}.

    Tolerante a archivo inexistente o corrupto.
    """
    datos = _vacio()
    try:
        if not _RUTA_JSON.exists():
            return datos
        with open(_RUTA_JSON, "r", encoding="utf-8") as fh:
            cargado = json.load(fh)
        if isinstance(cargado, dict):
            for clave in (TIPO_SHAPEFILE, TIPO_PROYECTO):
                valor = cargado.get(clave)
                if isinstance(valor, list):
                    # Solo cadenas, sin duplicados, máximo _MAX
                    vistos = []
                    for r in valor:
                        if isinstance(r, str) and r and r not in vistos:
                            vistos.append(r)
                    datos[clave] = vistos[:_MAX]
    except Exception:
        # JSON corrupto u otro error: devolver estructura vacía
        return _vacio()
    return datos


def _guardar(datos: dict) -> None:
    try:
        _DIR_CACHE.mkdir(parents=True, exist_ok=True)
        with open(_RUTA_JSON, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
    except Exception:
        # No interrumpir la app si no se puede escribir la caché
        pass


def agregar_reciente(tipo: str, ruta: str) -> dict:
    """Añade una ruta al principio de la lista del tipo indicado.

    `tipo` debe ser TIPO_SHAPEFILE o TIPO_PROYECTO. Elimina duplicados,
    mantiene como máximo los _MAX más recientes y persiste el resultado.
    Devuelve el dict actualizado.
    """
    if tipo not in (TIPO_SHAPEFILE, TIPO_PROYECTO):
        return cargar_recientes()
    if not ruta or not isinstance(ruta, str):
        return cargar_recientes()

    datos = cargar_recientes()
    lista = datos.get(tipo, [])
    # Mover/insertar al principio sin duplicar
    lista = [r for r in lista if r != ruta]
    lista.insert(0, ruta)
    datos[tipo] = lista[:_MAX]
    _guardar(datos)
    return datos
