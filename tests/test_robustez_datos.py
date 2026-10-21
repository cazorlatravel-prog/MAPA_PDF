"""Tests de robustez de carga de datos (lotes CSV, números en texto,
geometrías nulas) añadidos tras la prueba de extremo a extremo."""

import os

import pytest

pytest.importorskip("geopandas")
pytest.importorskip("pandas")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import LineString, Polygon  # noqa: E402

from generador_planos.motor.proyecto import cargar_lotes_csv  # noqa: E402
from generador_planos.motor._utils_geo import (  # noqa: E402
    _a_numero, _auto_calcular_campos, _calcular_stats_grupo,
)
from generador_planos.motor.simbologia import GestorSimbologia  # noqa: E402
from generador_planos.motor.capas_extra import GestorCapasExtra  # noqa: E402


class TestCargarLotesCsv:
    def test_formato_excel_espanol(self, tmp_path):
        """BOM UTF-8, separador ';', cabecera con espacios/mayúsculas,
        fila corta, ruta relativa al CSV y carpeta vacía."""
        csv = tmp_path / "lotes.csv"
        csv.write_text(
            "Ruta_SHP ;nombre;formato;carpeta_salida\r\n"
            "infra.shp;Lote Ñorte;A4 Horizontal;salida/norte\r\n"
            "C:/datos/otro.shp;Lote corto\r\n",
            encoding="utf-8-sig")
        lotes = cargar_lotes_csv(str(csv))
        assert len(lotes) == 2
        assert lotes[0]["ruta_shp"] == os.path.normpath(str(tmp_path / "infra.shp"))
        assert lotes[0]["nombre"] == "Lote Ñorte"
        assert lotes[0]["carpeta_salida"] == os.path.normpath(
            str(tmp_path / "salida" / "norte"))
        # Fila corta: sin formato ni carpeta, no debe lanzar AttributeError
        assert lotes[1]["formato"] == "A3 Horizontal"
        assert lotes[1]["carpeta_salida"] == ""

    def test_cp1252_y_comas(self, tmp_path):
        csv = tmp_path / "lotes.csv"
        csv.write_bytes("ruta_shp,nombre,formato,carpeta_salida\n"
                        "a.shp,Año Peña,A3 Horizontal,out\n".encode("cp1252"))
        lotes = cargar_lotes_csv(str(csv))
        assert lotes[0]["nombre"] == "Año Peña"

    def test_vacio(self, tmp_path):
        csv = tmp_path / "lotes.csv"
        csv.write_text("", encoding="utf-8")
        assert cargar_lotes_csv(str(csv)) == []


class TestNumerosEnTexto:
    def test_a_numero_formatos_espanoles(self):
        s = pd.Series(["1.234,5", "1,5", "1.5", "7", "", "abc", None, 3])
        r = _a_numero(s)
        assert r.iloc[0] == 1234.5
        assert r.iloc[1] == 1.5
        assert r.iloc[2] == 1.5
        assert r.iloc[3] == 7.0
        assert r.iloc[4] != r.iloc[4]  # NaN
        assert r.iloc[5] != r.iloc[5]  # NaN
        assert r.iloc[6] != r.iloc[6]  # NaN
        assert r.iloc[7] == 3.0

    def test_stats_grupo_con_texto(self):
        g = gpd.GeoDataFrame({
            "Longitud": ["1.234,5", "", "7,5"],
            "Superficie": ["0,5", "abc", None],
            "geometry": [LineString([(0, 0), (1, 0)])] * 3,
        }, crs="EPSG:25830")
        st = _calcular_stats_grupo(g)
        assert abs(st["total_longitud_km"] - 1.242) < 1e-9
        assert abs(st["total_superficie_ha"] - 0.5) < 1e-9


class TestGeometriasNulas:
    def test_auto_calcular_campos_tolera_none(self):
        g = gpd.GeoDataFrame({
            "Nombre_Infra": ["A", "B", "C"],
            "geometry": [LineString([(0, 0), (100, 0)]), None,
                         Polygon([(0, 0), (100, 0), (100, 100)])],
        }, crs="EPSG:25830")
        g = _auto_calcular_campos(g)
        assert list(g["Longitud"]) == [100.0, 0.0, 0.0]
        assert g["Superficie"].iloc[1] == 0.0
        assert g["Superficie"].iloc[2] == 0.5


class TestCapasExtraLayer:
    def test_to_dict_conserva_layer(self, tmp_path):
        ruta = tmp_path / "capa.gpkg"
        gpd.GeoDataFrame({"a": [1], "geometry": [LineString([(0, 0), (1, 1)])]},
                         crs="EPSG:25830").to_file(ruta, layer="hidro",
                                                   driver="GPKG")
        gestor = GestorCapasExtra()
        ok, msg, capa = gestor.cargar_capa(str(ruta), "Hidro", "Hidrografía",
                                           layer="hidro")
        assert ok, msg
        d = gestor.to_dict()
        assert d[0]["layer"] == "hidro"
        g2 = GestorCapasExtra()
        assert g2.cargar_desde_dict(d) == []
        assert g2.capas[0].layer == "hidro"

    def test_eliminar_por_indice(self):
        gestor = GestorCapasExtra()
        from generador_planos.motor.capas_extra import CapaExtra
        gestor.capas = [CapaExtra("Ríos (CHG)", "", None),
                        CapaExtra("Ríos (CHG)", "", None)]
        assert gestor.eliminar_capa_indice(1) == "Ríos (CHG)"
        assert len(gestor.capas) == 1
        assert gestor.eliminar_capa_indice(5) == ""
