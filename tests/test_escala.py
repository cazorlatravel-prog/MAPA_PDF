"""Tests para el módulo de selección de escala."""

import pytest
from shapely.geometry import box, Point, LineString

from generador_planos.motor.escala import (
    seleccionar_escala, ESCALAS, FORMATOS, INTERVALOS_GRID,
    BARRA_ESCALA_M, MARGENES_MM, DPI_DEFAULT,
)


class TestConstantes:
    """Verifica que las constantes están bien definidas."""

    def test_escalas_ordenadas(self):
        assert ESCALAS == sorted(ESCALAS)

    def test_escalas_positivas(self):
        assert all(e > 0 for e in ESCALAS)

    def test_formatos_existen(self):
        assert "A4 Horizontal" in FORMATOS
        assert "A3 Horizontal" in FORMATOS
        assert "A2 Horizontal" in FORMATOS

    def test_formatos_dimensiones(self):
        for key, (w, h) in FORMATOS.items():
            assert w > h, f"{key}: ancho ({w}) debe ser mayor que alto ({h})"

    def test_intervalos_grid_para_cada_escala(self):
        for escala in ESCALAS:
            assert escala in INTERVALOS_GRID

    def test_barra_escala_para_cada_escala(self):
        for escala in ESCALAS:
            assert escala in BARRA_ESCALA_M

    def test_margenes_completos(self):
        for key in ("izq", "der", "sup", "inf"):
            assert key in MARGENES_MM
            assert MARGENES_MM[key] > 0

    def test_dpi_default(self):
        assert DPI_DEFAULT > 0


class TestSeleccionarEscala:
    """Tests para la función seleccionar_escala."""

    def test_escala_manual_override(self):
        geom = box(500000, 4200000, 501000, 4201000)
        result = seleccionar_escala(geom, "A3 Horizontal", escala_manual=15000)
        assert result == 15000

    def test_escala_manual_cero_usa_auto(self):
        geom = box(500000, 4200000, 501000, 4201000)
        result = seleccionar_escala(geom, "A3 Horizontal", escala_manual=0)
        # Con escala_manual=0 debería usar auto
        assert result in ESCALAS

    def test_geometria_pequena_escala_baja(self):
        # Infraestructura de 500m x 500m → debería dar escala pequeña
        geom = box(500000, 4200000, 500500, 4200500)
        result = seleccionar_escala(geom, "A3 Horizontal")
        assert result <= 10000

    def test_geometria_grande_escala_alta(self):
        # Infraestructura de 20km x 20km → debería dar escala grande
        geom = box(500000, 4200000, 520000, 4220000)
        result = seleccionar_escala(geom, "A3 Horizontal")
        assert result >= 20000

    def test_punto_geometria(self):
        # Un punto debería usar una escala razonable
        geom = Point(500000, 4200000)
        result = seleccionar_escala(geom, "A3 Horizontal")
        assert result in ESCALAS

    def test_linea_geometria(self):
        geom = LineString([(500000, 4200000), (502000, 4202000)])
        result = seleccionar_escala(geom, "A3 Horizontal")
        assert result in ESCALAS

    def test_todos_formatos(self):
        geom = box(500000, 4200000, 501000, 4201000)
        for fmt_key in FORMATOS:
            result = seleccionar_escala(geom, fmt_key)
            assert result in ESCALAS

    def test_resultado_siempre_en_escalas(self):
        geom = box(500000, 4200000, 503000, 4203000)
        result = seleccionar_escala(geom, "A3 Horizontal")
        assert result in ESCALAS

    def test_geometria_enorme_devuelve_max(self):
        # Geometría enorme que no cabe en ninguna escala
        geom = box(0, 0, 500000, 500000)
        result = seleccionar_escala(geom, "A4 Horizontal")
        assert result == ESCALAS[-1]

    def test_es_lateral_cambia_resultado(self):
        geom = box(500000, 4200000, 505000, 4205000)
        normal = seleccionar_escala(geom, "A3 Horizontal", es_lateral=False)
        lateral = seleccionar_escala(geom, "A3 Horizontal", es_lateral=True)
        # Lateral tiene proporciones diferentes, puede dar diferente escala
        assert normal in ESCALAS
        assert lateral in ESCALAS
