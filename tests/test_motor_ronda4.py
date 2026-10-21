"""Tests de las correcciones de la revisión profunda del motor (ronda 4)."""

import datetime as dt
import os

import numpy as np
import pytest

pytest.importorskip("geopandas")
pytest.importorskip("rasterio")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import LineString, MultiLineString, Point, Polygon  # noqa: E402

from generador_planos.motor import cartografia, generador  # noqa: E402
from generador_planos.motor.maquetacion import _fmt_valor, MaquetadorPlano  # noqa: E402
from generador_planos.motor._elementos_mapa import _intervalo_grid  # noqa: E402
from generador_planos.motor.paginas_especiales import crear_mapa_guia  # noqa: E402


class TestFmtValor:
    def test_casos(self):
        assert _fmt_valor(None) == "—"
        assert _fmt_valor(float("nan")) == "—"
        assert _fmt_valor(float("inf")) == "—"
        assert _fmt_valor("007") == "007"
        assert _fmt_valor("  ") == "—"
        assert _fmt_valor(12345678901234) == "12345678901234"
        assert _fmt_valor(3.14159) == "3.14"
        assert _fmt_valor(True) == "Sí"
        assert _fmt_valor(dt.date(2024, 3, 5)) == "05/03/2024"
        assert _fmt_valor(pd.Timestamp("2024-03-05 10:00")) == "05/03/2024"
        assert _fmt_valor(pd.NaT) == "—"


class TestClavesYNombres:
    def test_clave_categoria_nulos(self):
        s = pd.Series(["A", None, float("nan"), 3])
        claves = generador._clave_categoria(s)
        assert list(claves) == ["A", generador.SIN_VALOR, generador.SIN_VALOR, "3"]

    def test_normalizar_clave_enlace(self):
        f = generador._normalizar_clave_enlace
        assert f(101.0) == "101"
        assert f("101.0") == "101"
        assert f(" 101 ") == "101"
        assert f(float("nan")) is None
        assert f(None) is None
        assert f("A-7") == "A-7"

    def test_formatear_patron_tolerante(self):
        r = generador._formatear_patron("{num}_{nombre}_{TIPO}", num="0001",
                                        nombre="Pista", campo="x")
        assert r == "0001_Pista_{TIPO}"

    def test_nombre_unico(self):
        m = generador.GeneradorPlanos()
        assert m._nombre_unico("Cortafuegos", 1) == "Cortafuegos"
        assert m._nombre_unico("Cortafuegos", 2) == "Cortafuegos_0002"
        assert m._nombre_unico("cortafuegos", 3) == "cortafuegos_0003"

    def test_valores_unicos_e_indices_fechas(self):
        m = generador.GeneradorPlanos()
        m.gdf_infra = gpd.GeoDataFrame({
            "Fecha": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-02-01"]),
            "geometry": [Point(0, 0)] * 3,
        }, crs="EPSG:25830")
        valores = m.obtener_valores_unicos("Fecha")
        assert len(valores) == 2
        assert m.obtener_indices_por_valor("Fecha", valores[0]) == [0, 1]


class TestIntervaloGrid:
    def test_escalas(self):
        assert _intervalo_grid(10000) == 1000      # estándar
        assert _intervalo_grid(1000) == 100        # manual pequeña
        assert _intervalo_grid(50000) == 5000      # manual grande
        assert _intervalo_grid("x") == 1000


class TestRasterLocalBorde:
    def test_extent_recortado_al_raster(self, tmp_path):
        import rasterio
        from rasterio.transform import from_origin
        ruta = str(tmp_path / "r.tif")
        # Ráster 100x100 px de 10 m: cubre x 0..1000, y 0..1000
        with rasterio.open(ruta, "w", driver="GTiff", width=100, height=100,
                           count=3, dtype="uint8", crs="EPSG:25830",
                           transform=from_origin(0, 1000, 10, 10)) as d:
            d.write(np.full((3, 100, 100), 120, dtype="uint8"))
        fig, ax = plt.subplots()
        try:
            # El plano sobresale 500 m por el oeste: la imagen debe quedar en
            # x 0..600 (no desplazada ni estirada)
            cartografia.añadir_fondo_raster_local(ax, ruta, -500, 600, 200, 800)
            ext = ax.images[0].get_extent()
            assert ext[0] == pytest.approx(0, abs=1)
            assert ext[1] == pytest.approx(600, abs=1)
            assert ext[2] == pytest.approx(200, abs=1)
            assert ext[3] == pytest.approx(800, abs=1)
        finally:
            plt.close(fig)
        # Fuera del ráster: error para que el llamador haga fallback
        fig, ax = plt.subplots()
        try:
            with pytest.raises(ValueError):
                cartografia.añadir_fondo_raster_local(ax, ruta, 5000, 6000, 5000, 6000)
        finally:
            plt.close(fig)


class TestMapaGuiaMultiparte:
    def test_multilinea_y_nulos_con_numeracion(self):
        gdf = gpd.GeoDataFrame({
            "Nombre_Infra": ["A", "B", "C"],
            "geometry": [
                MultiLineString([[(0, 0), (100, 0)], [(0, 50), (100, 50)]]),
                None,
                Polygon([(200, 0), (300, 0), (300, 100)]),
            ],
        }, crs="EPSG:25830")
        fig = crear_mapa_guia("A4 Horizontal", gdf, [0, 1, 2], numeros=[11, 12, 13])
        try:
            textos = [t.get_text() for ax in fig.axes for t in ax.texts]
            assert "11" in textos and "13" in textos
            assert any(t.startswith("11. A") for t in textos)
        finally:
            plt.close(fig)


class TestExtensionMapa:
    def test_centro_en_bbox_y_tamano_real(self):
        maq = MaquetadorPlano("A3 Horizontal", 10000)
        maq.crear_figura()
        geom = LineString([(0, 0), (1000, 0), (1000, 10)])  # centroide ≠ centro bbox
        xmin, xmax, ymin, ymax = maq.calcular_extension_mapa(geom)
        assert (xmin + xmax) / 2 == pytest.approx(500)
        assert (ymin + ymax) / 2 == pytest.approx(5)
        # La anchura en metros corresponde al ancho REAL del eje a 1:10.000
        pos = maq.ax_map.get_position()
        ancho_mm = pos.width * maq.fmt_mm[0]
        assert (xmax - xmin) == pytest.approx(ancho_mm / 1000 * 10000, rel=1e-6)
        plt.close(maq.fig)
