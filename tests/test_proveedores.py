"""Tests de los proveedores de cartografía base disponibles en la GUI."""

import pytest

pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("requests")

from generador_planos.motor import cartografia  # noqa: E402


class TestProveedoresNuevos:
    def test_google_satelite_en_capas_base(self):
        assert "Google Satélite" in cartografia.CAPAS_BASE
        url = cartografia.CAPAS_BASE["Google Satélite"]
        assert "{x}" in url and "{y}" in url and "{z}" in url
        assert "lyrs=s" in url

    def test_google_hibrido_en_capas_base(self):
        assert "Google Satélite Híbrido" in cartografia.CAPAS_BASE
        assert "lyrs=y" in cartografia.CAPAS_BASE["Google Satélite Híbrido"]

    def test_topografico_andalucia_en_capas_wms(self):
        assert "Topográfico Andalucía (MTA10)" in cartografia.CAPAS_WMS
        info = cartografia.CAPAS_WMS["Topográfico Andalucía (MTA10)"]
        assert "ideandalucia.es" in info["url"]
        assert "LAYERS=mta10r_2001-2013" in info["url"]
        assert "CRS=EPSG:25830" in info["url"]
        assert "Junta de Andalucía" in info["attribution"]

    def test_todos_en_providers_ctx(self):
        """El desplegable de la GUI se llena con PROVIDERS_CTX: los
        proveedores nuevos deben aparecer en él."""
        for nombre in ("Google Satélite", "Google Satélite Híbrido",
                       "Topográfico Andalucía (MTA10)"):
            assert nombre in cartografia.PROVIDERS_CTX

    def test_url_tesela_google_formatea(self):
        url = cartografia.CAPAS_BASE["Google Satélite"].format(
            z=15, x=15800, y=12700)
        assert url == "https://mt1.google.com/vt/lyrs=s&x=15800&y=12700&z=15"
