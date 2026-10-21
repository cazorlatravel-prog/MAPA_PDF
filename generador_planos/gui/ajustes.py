"""
Ajustes de usuario persistentes entre sesiones.

Guarda en ~/.mapa_pdf_cache/ajustes.json las últimas opciones elegidas en la
interfaz (proveedor de cartografía, formato, calidad, plantilla, carpeta de
salida, opciones de salida...) para que al abrir la aplicación de nuevo no
haya que volver a configurarlas. Es tolerante a archivo ausente o corrupto.
"""

import json
from pathlib import Path

_DIR_CACHE = Path.home() / ".mapa_pdf_cache"
_RUTA_JSON = _DIR_CACHE / "ajustes.json"


def cargar_ajustes() -> dict:
    """Devuelve el dict de ajustes guardados ({} si no hay o está corrupto)."""
    try:
        if not _RUTA_JSON.exists():
            return {}
        with open(_RUTA_JSON, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def guardar_ajustes(datos: dict) -> bool:
    """Persiste los ajustes. Devuelve False si no se pudo escribir."""
    if not isinstance(datos, dict):
        return False
    try:
        _DIR_CACHE.mkdir(parents=True, exist_ok=True)
        with open(_RUTA_JSON, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def actualizar_ajustes(**cambios) -> dict:
    """Fusiona `cambios` con los ajustes existentes y los guarda."""
    datos = cargar_ajustes()
    datos.update({k: v for k, v in cambios.items() if v is not None})
    guardar_ajustes(datos)
    return datos
