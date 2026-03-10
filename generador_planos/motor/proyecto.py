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

import json
import os
from datetime import datetime


class Proyecto:
    """Configuración completa de un proyecto de planos."""

    def __init__(self):
        self.nombre = "Proyecto sin nombre"
        self.fecha_creacion = datetime.now().isoformat()
        self.fecha_modificacion = datetime.now().isoformat()

        # Rutas de datos
        self.ruta_infra = ""
        self.ruta_montes = ""

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
        self.escala_manual = None  # None = automática
        self.transparencia_montes = 0.3
        self.color_infra = "#E74C3C"
        self.campos_visibles = []
        self.campo_mapeo = {}
        self.carpeta_salida = ""
        self.patron_nombre = "plano_{num}_{nombre}"
        self.layout_key = "Plantilla 1 (Clásica)"

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

    def to_dict(self) -> dict:
        self.fecha_modificacion = datetime.now().isoformat()
        return {
            "nombre": self.nombre,
            "fecha_creacion": self.fecha_creacion,
            "fecha_modificacion": self.fecha_modificacion,
            "ruta_infra": self.ruta_infra,
            "ruta_montes": self.ruta_montes,
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
            "origen_datos_tabla": self.origen_datos_tabla,
            "ruta_excel_tabla": self.ruta_excel_tabla,
            "hoja_excel_tabla": self.hoja_excel_tabla,
            "campo_enlace_shp": self.campo_enlace_shp,
            "campo_enlace_excel": self.campo_enlace_excel,
            "columnas_excel_activas": self.columnas_excel_activas,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Proyecto":
        p = cls()
        for key in [
            "nombre", "fecha_creacion", "fecha_modificacion",
            "ruta_infra", "ruta_montes", "formato", "proveedor",
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
            "origen_datos_tabla", "ruta_excel_tabla", "hoja_excel_tabla",
            "campo_enlace_shp", "campo_enlace_excel", "columnas_excel_activas",
        ]:
            if key in d:
                setattr(p, key, d[key])
        return p

    def guardar(self, ruta: str):
        """Guarda el proyecto a un archivo JSON."""
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def cargar(cls, ruta: str) -> "Proyecto":
        """Carga un proyecto desde un archivo JSON."""
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def cargar_lotes_csv(ruta_csv: str) -> list:
    """Carga un CSV con rutas a múltiples shapefiles para generación por lotes.

    Formato CSV esperado:
        ruta_shp,nombre,formato,carpeta_salida
        /ruta/a/infra1.shp,Proyecto Norte,A3 Horizontal,/salida/norte
        /ruta/a/infra2.shp,Proyecto Sur,A4 Vertical,/salida/sur

    Devuelve lista de dicts con la configuración de cada lote.
    """
    import csv

    lotes = []
    with open(ruta_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lote = {
                "ruta_shp": row.get("ruta_shp", "").strip(),
                "nombre": row.get("nombre", "").strip(),
                "formato": row.get("formato", "A3 Horizontal").strip(),
                "carpeta_salida": row.get("carpeta_salida", "").strip(),
            }
            if lote["ruta_shp"]:
                lotes.append(lote)

    return lotes
