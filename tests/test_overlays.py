"""Tests de las capas WMS superpuestas (overlays)."""

import io

import pytest

pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("requests")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from generador_planos.motor import cartografia  # noqa: E402
from generador_planos.motor.proyecto import Proyecto  # noqa: E402

BBOX = (503000.0, 505000.0, 4196000.0, 4197500.0)  # xmin, xmax, ymin, ymax


class _RespFalsa:
    def __init__(self, contenido, ctype="image/png", status=200):
        self.content = contenido
        self.headers = {"Content-Type": ctype}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _png_rgba():
    arr = np.zeros((8, 8, 4), dtype=np.uint8)
    arr[2:6, 2:6] = (255, 0, 0, 255)  # cuadrado rojo opaco, resto transparente
    buf = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def mock_get(monkeypatch, tmp_path):
    llamadas = []
    monkeypatch.setattr(cartografia, "_TILE_CACHE_DIR", tmp_path)

    def _get(url, params=None, headers=None, timeout=None):
        llamadas.append({"url": url, "params": dict(params or {})})
        return _RespFalsa(_png_rgba())

    monkeypatch.setattr(cartografia.requests, "get", _get)
    return llamadas


class TestPresets:
    def test_presets_bien_formados(self):
        assert cartografia.OVERLAYS_PREDEFINIDOS
        for nombre, p in cartografia.OVERLAYS_PREDEFINIDOS.items():
            assert p["url"].startswith("https://"), nombre
            assert "?" not in p["url"], nombre  # params se construyen aparte
            assert p["capa"], nombre
            assert p["formato"] == "image/png", nombre
            assert 0.0 < p["alpha"] <= 1.0, nombre
            assert p["version"] in ("1.1.1", "1.3.0"), nombre
            assert p["attribution"], nombre

    def test_presets_esperados(self):
        assert "Catastro (parcelas)" in cartografia.OVERLAYS_PREDEFINIDOS
        assert "Límites municipales (IGN)" in cartografia.OVERLAYS_PREDEFINIDOS
        lim = cartografia.OVERLAYS_PREDEFINIDOS["Límites municipales (IGN)"]
        assert lim["capa"] == "AU.AdministrativeBoundary"


class TestAñadirOverlay:
    def test_getmap_params_y_alpha(self, mock_get):
        fig, ax = plt.subplots()
        try:
            llamado = {}
            orig = ax.imshow

            def _imshow(arr, **kw):
                llamado["arr"] = arr
                llamado.update(kw)
                return orig(arr, **kw)

            ax.imshow = _imshow
            cartografia.añadir_overlay_wms(
                ax, "https://servidor.example/wms?map=foo&SERVICE=WMS",
                "mi_capa", *BBOX, alpha=0.45)
        finally:
            plt.close(fig)

        assert len(mock_get) == 1
        p = mock_get[0]["params"]
        assert mock_get[0]["url"] == "https://servidor.example/wms"
        assert p["TRANSPARENT"] == "TRUE"
        assert p["LAYERS"] == "mi_capa"
        assert p["CRS"] == "EPSG:25830"
        assert p["VERSION"] == "1.3.0"
        assert p["REQUEST"] == "GetMap"
        assert p["map"] == "foo"  # parámetro propio del usuario conservado
        assert p["BBOX"] == "503000.0,4196000.0,505000.0,4197500.0"
        assert llamado["alpha"] == pytest.approx(0.45)
        assert llamado["zorder"] == pytest.approx(1.5)
        assert llamado["arr"].shape[-1] == 4  # RGBA conservado
        assert llamado["arr"][0, 0, 3] == 0  # zona transparente

    def test_wms_111_usa_srs(self, mock_get):
        fig, ax = plt.subplots()
        try:
            cartografia.añadir_overlay_wms(
                ax, "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx",
                "Catastro", *BBOX, version="1.1.1")
        finally:
            plt.close(fig)
        p = mock_get[0]["params"]
        assert p["SRS"] == "EPSG:25830"
        assert "CRS" not in p

    def test_cache_en_disco(self, mock_get):
        for _ in range(2):
            fig, ax = plt.subplots()
            cartografia.añadir_overlay_wms(ax, "https://s.example/wms", "c", *BBOX)
            plt.close(fig)
        assert len(mock_get) == 1  # la segunda vez sale de la caché

    def test_respuesta_xml_lanza_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cartografia, "_TILE_CACHE_DIR", tmp_path)
        monkeypatch.setattr(
            cartografia.requests, "get",
            lambda *a, **k: _RespFalsa(b"<ServiceExceptionReport/>", "text/xml"))
        fig, ax = plt.subplots()
        try:
            with pytest.raises(ValueError):
                cartografia.añadir_overlay_wms(ax, "https://s.example/wms",
                                               "c", *BBOX)
        finally:
            plt.close(fig)


class TestMotorOverlays:
    def test_overlay_fallido_no_rompe_y_avisa(self, monkeypatch, tmp_path):
        pytest.importorskip("geopandas")
        from generador_planos.motor.generador import GeneradorPlanos
        monkeypatch.setattr(cartografia, "_TILE_CACHE_DIR", tmp_path)

        def _falla(*a, **k):
            raise ConnectionError("sin red")

        monkeypatch.setattr(cartografia.requests, "get", _falla)
        monkeypatch.setattr("time.sleep", lambda s: None)  # sin esperas de reintento
        motor = GeneradorPlanos()
        motor.overlays_wms = [
            {"nombre": "X", "url": "https://s.example/wms", "capa": "c",
             "alpha": 0.5, "formato": "image/png", "activo": True},
            {"nombre": "Inactiva", "url": "https://s.example/wms", "capa": "d",
             "alpha": 0.5, "formato": "image/png", "activo": False},
        ]
        fig, ax = plt.subplots()
        try:
            with pytest.warns(UserWarning, match="X"):
                motor._añadir_overlays_wms(ax, *BBOX)
        finally:
            plt.close(fig)

    def test_overlay_activo_se_dibuja(self, mock_get):
        pytest.importorskip("geopandas")
        from generador_planos.motor.generador import GeneradorPlanos
        motor = GeneradorPlanos()
        assert motor.overlays_wms == []
        motor.overlays_wms = [
            {"nombre": "Catastro", "activo": True, "alpha": 0.7,
             **{k: v for k, v in cartografia.OVERLAYS_PREDEFINIDOS[
                 "Catastro (parcelas)"].items() if k in ("url", "capa", "formato")}},
        ]
        fig, ax = plt.subplots()
        try:
            motor._añadir_overlays_wms(ax, *BBOX)
            assert len(ax.images) == 1
            assert ax.images[0].get_alpha() == pytest.approx(0.7)
        finally:
            plt.close(fig)
        # Sin 'version' guardada hereda la del preset (Catastro = 1.1.1)
        assert mock_get[0]["params"]["VERSION"] == "1.1.1"


class TestProyectoOverlays:
    def test_round_trip(self, tmp_path):
        p = Proyecto()
        p.overlays_wms = [
            {"nombre": "Catastro (parcelas)",
             "url": "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx",
             "capa": "Catastro", "alpha": 0.8, "formato": "image/png",
             "activo": False, "version": "1.1.1"},
        ]
        ruta = tmp_path / "p.json"
        p.guardar(str(ruta))
        q = Proyecto.cargar(str(ruta))
        assert q.overlays_wms == p.overlays_wms

    def test_proyecto_antiguo_sin_overlays(self):
        q = Proyecto.from_dict({"nombre": "viejo"})
        assert q.overlays_wms == []

    def test_entradas_invalidas_se_descartan(self):
        q = Proyecto.from_dict({"overlays_wms": [
            "basura", {"url": "", "capa": "x"},
            {"url": "https://a.example/wms", "capa": "c", "alpha": "7"},
        ]})
        assert len(q.overlays_wms) == 1
        ov = q.overlays_wms[0]
        assert ov["alpha"] == 1.0 and ov["activo"] is True
        assert ov["nombre"] == "c" and ov["formato"] == "image/png"

        q2 = Proyecto.from_dict({"overlays_wms": None})
        assert q2.overlays_wms == []
