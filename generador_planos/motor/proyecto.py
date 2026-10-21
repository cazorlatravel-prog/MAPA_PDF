"""
Gestión de proyectos: guardar/cargar configuración completa a JSON.

Un proyecto almacena:
  - Ruta del shapefile de infraestructuras
  - Ruta del shapefile de montes
  - Capas extra (nombre, ruta, tipo, visibilidad)
  - Simbología
  - Configuración del cajetín
  - Formato, proveedor, escala manual, campos visibles
  - Carpeta de salida
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


class Proyecto:
    """Configuración completa de un proyecto de planos."""

    nombre: str
    fecha_creacion: str
    fecha_modificacion: str
    ruta_infra: str
    ruta_montes: str
    layer_infra: str
    layer_montes: str
    formato: str
    proveedor: str
    ruta_raster_general: str
    ruta_raster_localizacion: str
    prov_localizacion: str
    escala_localizacion: int
    ruta_capa_localizacion: str
    wms_custom_general: dict[str, str]
    wfs_custom_general: dict[str, str]
    wms_custom_localizacion: dict[str, str]
    wfs_custom_localizacion: dict[str, str]
    overlays_wms: list[dict[str, Any]]
    escala_manual: int | None
    transparencia_montes: float
    color_infra: str
    campos_visibles: list[str]
    campo_mapeo: dict[str, str]
    carpeta_salida: str
    patron_nombre: str
    layout_key: str
    transparencia_infra: float
    calidad_pdf: str
    campo_encabezado: str
    modo_gen: str
    rango_desde: int
    rango_hasta: int
    campo_agrupacion: str
    multipagina: bool
    incluir_portada: bool
    origen_datos_tabla: str
    ruta_excel_tabla: str
    hoja_excel_tabla: str
    campo_enlace_shp: str
    campo_enlace_excel: str
    columnas_excel_activas: list[str]
    cajetin: dict[str, str]
    plantilla: dict[str, str]
    capas_extra: list[dict[str, Any]]
    simbologia: dict[str, Any]
    # Simbología UI
    simbologia_ui: dict[str, Any]
    # Filtros
    filtros: dict[str, Any]
    # Orden de campos
    campos_orden: list[str]

    def __init__(self) -> None:
        self.nombre = "Proyecto sin nombre"
        self.fecha_creacion = datetime.now().isoformat()
        self.fecha_modificacion = datetime.now().isoformat()

        # Rutas de datos
        self.ruta_infra = ""
        self.ruta_montes = ""
        self.layer_infra = ""   # Nombre de capa dentro de GDB (vacío si SHP)
        self.layer_montes = ""  # Nombre de capa dentro de GDB (vacío si SHP)

        # Configuración de generación
        self.formato = "A3 Horizontal"
        self.proveedor = "OpenStreetMap"
        self.ruta_raster_general = ""       # Ráster local para fondo de mapa
        self.ruta_raster_localizacion = ""  # Ráster local para mapa de localización
        self.prov_localizacion = "WMS IGN (online)"
        self.escala_localizacion = 250_000
        self.ruta_capa_localizacion = ""   # SHP/GDB propio para localización
        self.wms_custom_general = {}       # {"url":..., "capa":..., "formato":...}
        self.wfs_custom_general = {}       # {"url":..., "capa":...}
        self.wms_custom_localizacion = {}
        self.wfs_custom_localizacion = {}
        # Capas WMS superpuestas al fondo (lista de dicts: nombre, url,
        # capa, alpha, formato, activo, version)
        self.overlays_wms = []
        # Opciones de salida de la GUI: formato (PDF / PDF + PNG / PDF + JPG)
        # y marca de agua
        self.opciones_salida = {}
        self.escala_manual = None  # None = automática
        self.transparencia_montes = 0.3
        self.color_infra = "#E74C3C"
        self.campos_visibles = []
        self.campo_mapeo = {}
        self.carpeta_salida = ""
        self.patron_nombre = "plano_{num}_{nombre}"
        self.layout_key = "Plantilla 2 (Panel lateral)"

        # Campos adicionales
        self.transparencia_infra = 0.35
        self.calidad_pdf = "Alta (400 DPI)"
        self.campo_encabezado = ""

        # Generación
        self.modo_gen = "todos"
        self.rango_desde = 1
        self.rango_hasta = 10
        self.campo_agrupacion = "Monte"
        self.multipagina = False
        self.incluir_portada = False

        # Origen datos tabla
        self.origen_datos_tabla = "Shapefile (capa cargada)"
        self.ruta_excel_tabla = ""
        self.hoja_excel_tabla = ""
        self.campo_enlace_shp = ""
        self.campo_enlace_excel = ""
        self.columnas_excel_activas = []

        # Cajetín
        self.cajetin = {
            "autor": "",
            "cargo_autor": "",
            "proyecto": "",
            "num_proyecto": "",
            "revision": "",
            "cargo_revision": "",
            "firma": "",
            "cargo_firma": "",
            "organizacion": "",
            "subtitulo": "PLANO DE INFRAESTRUCTURA FORESTAL",
        }

        # Plantilla de colores
        self.plantilla = {
            "color_cabecera_fondo": "#1C2333",
            "color_cabecera_texto": "#FFFFFF",
            "color_cabecera_acento": "#007932",
            "color_marco_exterior": "#1C2333",
            "color_marco_interior": "#007932",
        }

        # Capas extra (se serializan como lista de dicts)
        self.capas_extra = []

        # Simbología (dict serializable)
        self.simbologia = {}

        # Estado UI de simbología (grosor, alpha, trazo, marcador, etc.)
        self.simbologia_ui = {}

        # Filtros activos
        self.filtros = {}

        # Orden de campos personalizado
        self.campos_orden = []

    def to_dict(self) -> dict[str, Any]:
        self.fecha_modificacion = datetime.now().isoformat()
        return {
            "nombre": self.nombre,
            "fecha_creacion": self.fecha_creacion,
            "fecha_modificacion": self.fecha_modificacion,
            "ruta_infra": self.ruta_infra,
            "ruta_montes": self.ruta_montes,
            "layer_infra": self.layer_infra,
            "layer_montes": self.layer_montes,
            "formato": self.formato,
            "proveedor": self.proveedor,
            "ruta_raster_general": self.ruta_raster_general,
            "ruta_raster_localizacion": self.ruta_raster_localizacion,
            "prov_localizacion": self.prov_localizacion,
            "escala_localizacion": self.escala_localizacion,
            "ruta_capa_localizacion": self.ruta_capa_localizacion,
            "wms_custom_general": self.wms_custom_general,
            "wfs_custom_general": self.wfs_custom_general,
            "wms_custom_localizacion": self.wms_custom_localizacion,
            "wfs_custom_localizacion": self.wfs_custom_localizacion,
            "overlays_wms": self.overlays_wms,
            "opciones_salida": self.opciones_salida,
            "escala_manual": self.escala_manual,
            "transparencia_montes": self.transparencia_montes,
            "color_infra": self.color_infra,
            "campos_visibles": self.campos_visibles,
            "campo_mapeo": self.campo_mapeo,
            "carpeta_salida": self.carpeta_salida,
            "patron_nombre": self.patron_nombre,
            "layout_key": self.layout_key,
            "transparencia_infra": self.transparencia_infra,
            "calidad_pdf": self.calidad_pdf,
            "campo_encabezado": self.campo_encabezado,
            "modo_gen": self.modo_gen,
            "rango_desde": self.rango_desde,
            "rango_hasta": self.rango_hasta,
            "campo_agrupacion": self.campo_agrupacion,
            "multipagina": self.multipagina,
            "incluir_portada": self.incluir_portada,
            "cajetin": self.cajetin,
            "plantilla": self.plantilla,
            "capas_extra": self.capas_extra,
            "simbologia": self.simbologia,
            "simbologia_ui": self.simbologia_ui,
            "filtros": self.filtros,
            "campos_orden": self.campos_orden,
            "origen_datos_tabla": self.origen_datos_tabla,
            "ruta_excel_tabla": self.ruta_excel_tabla,
            "hoja_excel_tabla": self.hoja_excel_tabla,
            "campo_enlace_shp": self.campo_enlace_shp,
            "campo_enlace_excel": self.campo_enlace_excel,
            "columnas_excel_activas": self.columnas_excel_activas,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Proyecto:
        p = cls()
        for key in [
            "nombre", "fecha_creacion", "fecha_modificacion",
            "ruta_infra", "ruta_montes", "layer_infra", "layer_montes",
            "formato", "proveedor",
            "ruta_raster_general", "ruta_raster_localizacion", "prov_localizacion",
            "escala_localizacion", "ruta_capa_localizacion",
            "wms_custom_general", "wfs_custom_general",
            "wms_custom_localizacion", "wfs_custom_localizacion",
            "escala_manual", "transparencia_montes", "color_infra",
            "campos_visibles", "campo_mapeo", "carpeta_salida", "patron_nombre",
            "layout_key",
            "transparencia_infra", "calidad_pdf", "campo_encabezado",
            "modo_gen", "rango_desde", "rango_hasta", "campo_agrupacion",
            "multipagina", "incluir_portada",
            "cajetin", "plantilla", "capas_extra", "simbologia",
            "simbologia_ui", "filtros", "campos_orden",
            "origen_datos_tabla", "ruta_excel_tabla", "hoja_excel_tabla",
            "campo_enlace_shp", "campo_enlace_excel", "columnas_excel_activas",
        ]:
            if key in d:
                setattr(p, key, d[key])
        # Overlays WMS (proyectos antiguos no los tienen): solo dicts
        # con url y capa; el resto de claves con valores por defecto.
        p.overlays_wms = _normalizar_overlays(d.get("overlays_wms"))
        op = d.get("opciones_salida")
        p.opciones_salida = op if isinstance(op, dict) else {}
        return p

    def guardar(self, ruta: str) -> None:
        """Guarda el proyecto a un archivo JSON."""
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def cargar(cls, ruta: str) -> Proyecto:
        """Carga un proyecto desde un archivo JSON."""
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def _normalizar_overlays(valor: Any) -> list[dict[str, Any]]:
    """Valida la lista de overlays WMS leída de un proyecto JSON."""
    if not isinstance(valor, list):
        return []
    resultado = []
    for ov in valor:
        if not isinstance(ov, dict):
            continue
        url = str(ov.get("url") or "").strip()
        capa = str(ov.get("capa") or "").strip()
        if not url or not capa:
            continue
        try:
            alpha = min(1.0, max(0.0, float(ov.get("alpha", 0.6))))
        except (TypeError, ValueError):
            alpha = 0.6
        norm = {
            "nombre": str(ov.get("nombre") or capa),
            "url": url,
            "capa": capa,
            "alpha": alpha,
            "formato": str(ov.get("formato") or "image/png"),
            "activo": bool(ov.get("activo", True)),
        }
        if ov.get("version"):
            norm["version"] = str(ov["version"])
        resultado.append(norm)
    return resultado


def cargar_lotes_csv(ruta_csv: str) -> list[dict[str, str]]:
    """Carga un CSV con rutas a múltiples shapefiles para generación por lotes.

    Formato CSV esperado (cabecera obligatoria):
        ruta_shp,nombre,formato,carpeta_salida
        C:/datos/infra1.shp,Proyecto Norte,A3 Horizontal,C:/salida/norte
        C:/datos/infra2.shp,Proyecto Sur,A4 Horizontal,C:/salida/sur

    Tolera lo que produce Excel en español: separador ``;``, BOM UTF-8,
    codificación cp1252, filas cortas y espacios en las cabeceras. Las
    rutas relativas se resuelven respecto a la carpeta del CSV.

    Devuelve lista de dicts con la configuración de cada lote.
    """
    import csv
    import os

    # 1) Leer el texto tolerando BOM y cp1252 (Excel "CSV UTF-8" añade BOM;
    #    "CSV (delimitado por comas)" en Windows español guarda cp1252).
    try:
        with open(ruta_csv, "r", encoding="utf-8-sig", newline="") as f:
            texto = f.read()
    except UnicodeDecodeError:
        with open(ruta_csv, "r", encoding="cp1252", newline="") as f:
            texto = f.read()

    if not texto.strip():
        return []

    # 2) Detectar separador (; o ,) a partir de la cabecera
    primera_linea = texto.splitlines()[0]
    delimitador = ";" if primera_linea.count(";") > primera_linea.count(",") else ","

    base_dir = os.path.dirname(os.path.abspath(ruta_csv))

    def _abs(p: str) -> str:
        if not p:
            return ""
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))

    lotes = []
    reader = csv.DictReader(texto.splitlines(), delimiter=delimitador)
    # Normalizar cabeceras: " Ruta_SHP " -> "ruta_shp"
    if reader.fieldnames:
        reader.fieldnames = [
            (c or "").strip().lower().lstrip("\ufeff") for c in reader.fieldnames]
    for row in reader:
        # DictReader rellena con None las columnas ausentes en filas cortas
        def _get(k, default=""):
            v = row.get(k)
            return (v if isinstance(v, str) else default).strip()

        lote = {
            "ruta_shp": _abs(_get("ruta_shp")),
            "nombre": _get("nombre"),
            "formato": _get("formato") or "A3 Horizontal",
            "carpeta_salida": _abs(_get("carpeta_salida")),
        }
        if lote["ruta_shp"]:
            lotes.append(lote)

    return lotes
