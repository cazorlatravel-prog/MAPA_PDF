"""Tests para las funciones de utilidad geoespacial."""

import pytest
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiPoint

from generador_planos.motor._utils_geo import (
    _asegurar_crs,
    _detectar_geom_type,
    _plot_gdf_por_tipo,
    _limpiar_tipos_mixtos,
    _auto_calcular_campos,
    _calcular_stats_grupo,
    _leer_geodatos,
)


def _gdf_utm30n():
    """Crea un GeoDataFrame con geometrías en UTM 30N."""
    return gpd.GeoDataFrame(
        {"nombre": ["A", "B"]},
        geometry=[Point(500000, 4200000), Point(501000, 4201000)],
        crs="EPSG:25830",
    )


def _gdf_sin_crs_utm():
    """GeoDataFrame sin CRS con coordenadas que parecen UTM."""
    return gpd.GeoDataFrame(
        {"nombre": ["A"]},
        geometry=[Point(500000, 4200000)],
    )


def _gdf_sin_crs_wgs84():
    """GeoDataFrame sin CRS con coordenadas que parecen WGS84."""
    return gpd.GeoDataFrame(
        {"nombre": ["A"]},
        geometry=[Point(-3.5, 37.5)],
    )


class TestAsegurarCRS:
    def test_ya_tiene_25830(self):
        gdf = _gdf_utm30n()
        result, aviso = _asegurar_crs(gdf, "test")
        assert result.crs.to_epsg() == 25830
        assert aviso == ""

    def test_reproyecta_desde_4326(self):
        gdf = gpd.GeoDataFrame(
            {"nombre": ["A"]},
            geometry=[Point(-3.5, 37.5)],
            crs="EPSG:4326",
        )
        result, aviso = _asegurar_crs(gdf, "test")
        assert result.crs.to_epsg() == 25830
        assert aviso == ""

    def test_sin_crs_detecta_utm(self):
        gdf = _gdf_sin_crs_utm()
        result, aviso = _asegurar_crs(gdf, "test")
        assert result.crs.to_epsg() == 25830
        assert "sin CRS definido" in aviso

    def test_sin_crs_detecta_wgs84(self):
        gdf = _gdf_sin_crs_wgs84()
        result, aviso = _asegurar_crs(gdf, "test")
        assert result.crs.to_epsg() == 25830
        assert "EPSG:4326" in aviso


class TestDetectarGeomType:
    def test_puntos(self):
        gdf = gpd.GeoDataFrame(
            geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:25830"
        )
        assert _detectar_geom_type(gdf) == "point"

    def test_lineas(self):
        gdf = gpd.GeoDataFrame(
            geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:25830"
        )
        assert "line" in _detectar_geom_type(gdf)

    def test_poligonos(self):
        gdf = gpd.GeoDataFrame(
            geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
            crs="EPSG:25830",
        )
        assert "polygon" in _detectar_geom_type(gdf)

    def test_vacio(self):
        gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:25830")
        assert _detectar_geom_type(gdf) == "unknown"


class TestLimpiarTiposMixtos:
    def test_columna_mixta(self):
        gdf = gpd.GeoDataFrame(
            {"mixta": ["texto", 123, None], "num": [1, 2, 3]},
            geometry=[Point(0, 0), Point(1, 1), Point(2, 2)],
            crs="EPSG:25830",
        )
        result = _limpiar_tipos_mixtos(gdf)
        # No debe lanzar excepción
        assert len(result) == 3

    def test_no_modifica_geometry(self):
        gdf = gpd.GeoDataFrame(
            {"a": [1]}, geometry=[Point(0, 0)], crs="EPSG:25830"
        )
        result = _limpiar_tipos_mixtos(gdf)
        assert result.geometry.iloc[0].equals(Point(0, 0))


class TestAutoCalcularCampos:
    def test_calcula_longitud_lineas(self):
        gdf = gpd.GeoDataFrame(
            {"nombre": ["linea"]},
            geometry=[LineString([(0, 0), (1000, 0)])],
            crs="EPSG:25830",
        )
        result = _auto_calcular_campos(gdf)
        assert "Longitud" in result.columns
        assert result["Longitud"].iloc[0] == pytest.approx(1000.0, rel=0.01)

    def test_calcula_superficie_poligonos(self):
        # Polígono de 100m x 100m = 10000 m² = 1 ha
        gdf = gpd.GeoDataFrame(
            {"nombre": ["cuadrado"]},
            geometry=[Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])],
            crs="EPSG:25830",
        )
        result = _auto_calcular_campos(gdf)
        assert "Superficie" in result.columns
        assert result["Superficie"].iloc[0] == pytest.approx(1.0, rel=0.01)

    def test_no_sobreescribe_existente(self):
        gdf = gpd.GeoDataFrame(
            {"nombre": ["linea"], "Longitud": [999]},
            geometry=[LineString([(0, 0), (1000, 0)])],
            crs="EPSG:25830",
        )
        result = _auto_calcular_campos(gdf)
        assert result["Longitud"].iloc[0] == 999  # No modificado


class TestCalcularStatsGrupo:
    def test_stats_basicas(self):
        gdf = gpd.GeoDataFrame(
            {"Longitud": [1000, 2000], "Superficie": [1.0, 2.0]},
            geometry=[Point(0, 0), Point(1, 1)],
            crs="EPSG:25830",
        )
        stats = _calcular_stats_grupo(gdf)
        assert stats["num_infraestructuras"] == 2
        assert stats["total_longitud_km"] == pytest.approx(3.0)
        assert stats["total_superficie_ha"] == pytest.approx(3.0)

    def test_sin_campos_opcionales(self):
        gdf = gpd.GeoDataFrame(
            {"nombre": ["A"]},
            geometry=[Point(0, 0)],
            crs="EPSG:25830",
        )
        stats = _calcular_stats_grupo(gdf)
        assert stats["num_infraestructuras"] == 1
        assert "total_longitud_km" not in stats
