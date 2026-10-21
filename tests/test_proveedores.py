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


class TestProveedoresCartografiaNueva:
    def test_relieve_mdt_wmts(self):
        url = cartografia.CAPAS_BASE["IGN Relieve (MDT sombreado)"]
        assert "servicios.idee.es/wmts/mdt" in url
        assert "LAYER=Relieve" in url
        assert "TILEMATRIXSET=GoogleMapsCompatible" in url
        assert cartografia._PROV_META["IGN Relieve (MDT sombreado)"]["max_zoom"] <= 16

    def test_catastro_wms_base(self):
        info = cartografia.CAPAS_WMS["Catastro (parcelas)"]
        assert "ovc.catastro.meh.es" in info["url"]
        assert "LAYERS=Catastro" in info["url"]
        # El WMS de Catastro solo acepta 1.1.1 (SRS, no CRS)
        assert "VERSION=1.1.1" in info["url"]
        assert "SRS=EPSG:25830" in info["url"]

    def test_nuevos_en_desplegable(self):
        for nombre in ("IGN Relieve (MDT sombreado)", "Catastro (parcelas)"):
            assert nombre in cartografia.PROVIDERS_CTX

    def test_orden_desplegable_agrupado(self):
        claves = list(cartografia.PROVIDERS_CTX)
        assert claves.index("PNOA Ortofoto (IGN)") < claves.index(
            "Topográfico Andalucía (MTA10)") < claves.index(
            "Google Satélite") < claves.index("OpenStreetMap")
        assert set(claves) >= set(cartografia.CAPAS_BASE) | set(cartografia.CAPAS_WMS)

    def test_obtener_atribucion(self):
        assert "Catastro" in cartografia.obtener_atribucion("Catastro (parcelas)")
        assert "IGN" in cartografia.obtener_atribucion("PNOA Ortofoto (IGN)")
        assert "Google" in cartografia.obtener_atribucion("Google Satélite")
        assert "REDIAM" in cartografia.obtener_atribucion(
            "Montes Públicos de Andalucía (REDIAM)")
        assert cartografia.obtener_atribucion("no existe") == ""
        assert cartografia.obtener_atribucion("") == ""


class TestZoomTeselas:
    # Extent cerca de Cazorla en lon/lat
    LON0, LAT0 = -2.98, 37.90

    def _zoom(self, ancho_grados, alto_grados, **kw):
        return cartografia._calcular_zoom_teselas(
            self.LON0, self.LAT0, self.LON0 + ancho_grados,
            self.LAT0 + alto_grados, **kw)

    def _teselas(self, z, ancho, alto):
        tx0, ty0 = cartografia._lat_lon_to_tile(self.LAT0 + alto, self.LON0, z)
        tx1, ty1 = cartografia._lat_lon_to_tile(self.LAT0, self.LON0 + ancho, z)
        return tx1 - tx0 + 1, ty1 - ty0 + 1

    def test_respeta_max_zoom_proveedor(self):
        assert self._zoom(0.01, 0.01, max_zoom=15) <= 15
        assert self._zoom(0.01, 0.01, max_zoom=20) > 15

    def test_acota_teselas_en_x_y_en_y(self):
        # Extent muy alto y estrecho (vertical): antes solo se acotaba X
        for ancho, alto in ((0.02, 0.6), (0.6, 0.02), (0.4, 0.4)):
            z = self._zoom(ancho, alto, max_zoom=20)
            nx, ny = self._teselas(z, ancho, alto)
            assert nx <= 24 and ny <= 24

    def test_resolucion_suficiente(self):
        # ~5 km de lado: debe alcanzar <= 2 m/px
        z = self._zoom(0.055, 0.045, max_zoom=20)
        assert cartografia._resolucion_tesela(self.LAT0, z) <= 2.0
