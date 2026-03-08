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
        self.escala_manual = None  # None = automática
        self.transparencia_montes = 0.5
        self.color_infra = "#E74C3C"
        self.campos_visibles = []
        self.campo_mapeo = {}
        self.carpeta_salida = ""
        self.patron_nombre = "plano_{num}_{nombre}"

        # Cajetín
        self.cajetin = {
            "autor": "",
            "proyecto": "",
            "num_proyecto": "",
            "revision": "0",
            "firma": "",
            "organizacion": "",
            "subtitulo": "PLANO DE INFRAESTRUCTURA FORESTAL",
        }

        # Plantilla de colores
        self.plantilla = {
            "color_cabecera_fondo": "#1C2333",
            "color_cabecera_texto": "#FFFFFF",
            "color_cabecera_acento": "#2ECC71",
            "color_marco_exterior": "#1C2333",
            "color_marco_interior": "#2ECC71",
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
            "escala_manual": self.escala_manual,
            "transparencia_montes": self.transparencia_montes,
            "color_infra": self.color_infra,
            "campos_visibles": self.campos_visibles,
            "campo_mapeo": self.campo_mapeo,
            "carpeta_salida": self.carpeta_salida,
            "patron_nombre": self.patron_nombre,
            "cajetin": self.cajetin,
            "plantilla": self.plantilla,
            "capas_extra": self.capas_extra,
            "simbologia": self.simbologia,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Proyecto":
        p = cls()
        for key in [
            "nombre", "fecha_creacion", "fecha_modificacion",
            "ruta_infra", "ruta_montes", "formato", "proveedor",
            "escala_manual", "transparencia_montes", "color_infra",
            "campos_visibles", "campo_mapeo", "carpeta_salida", "patron_nombre",
            "cajetin", "plantilla", "capas_extra", "simbologia",
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
