"""Tests de regresión para el manejo de CRS en el mosaico virtual.

El bug histórico era que ``_construir_vrt_xml_manual`` rechazaba como
"CRS distinto" hojas que en realidad compartían EPSG pero tenían WKTs
ligeramente diferentes (p. ej. porque unas las escribió GDAL 3.4 y otras
GDAL 3.8, o porque eran el resultado de un warp y el original). El
usuario veía un diálogo "Error al crear mosaico: CRS distinto en
h100511.tif, ...". La corrección fue usar el helper robusto
``_crs_iguales`` (comparación por EPSG) en lugar de ``!=``.
"""

import os
import sys
import types
from pathlib import Path

import pytest

# Si el entorno no tiene las dependencias pesadas de cartografia.py
# (numpy, PIL, requests), no podemos importar el módulo y los tests se
# saltan. En CI / entornos de desarrollo reales sí están presentes.
pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("requests")

from generador_planos.motor import cartografia  # noqa: E402


# ---------------------------------------------------------------------------
# Stubs que imitan el API mínimo de un objeto CRS de rasterio
# ---------------------------------------------------------------------------


class _StubCRS:
    """CRS falso con el subconjunto del API de rasterio que usamos.

    ``to_epsg()`` y ``to_wkt()`` son las dos vías por las que
    ``_crs_iguales`` decide igualdad. Permitimos simular un EPSG válido
    con dos WKTs distintos (caso del bug real).
    """

    def __init__(self, epsg=None, wkt="", is_valid=True):
        self._epsg = epsg
        self._wkt = wkt
        self.is_valid = is_valid

    def to_epsg(self):
        return self._epsg

    def to_wkt(self):
        return self._wkt

    def __eq__(self, other):
        # Rasterio compara por WKT estricto: dos CRS con igual EPSG pero
        # distinto WKT se consideran diferentes. Esto reproduce el bug.
        if not isinstance(other, _StubCRS):
            return NotImplemented
        return self._wkt == other._wkt

    def __hash__(self):
        return hash(self._wkt)


# ---------------------------------------------------------------------------
# _crs_iguales: comparación robusta
# ---------------------------------------------------------------------------


class TestCrsIguales:
    def test_mismo_epsg_distinto_wkt_son_iguales(self):
        """Regresión directa del bug: mismo EPSG, distinto WKT → iguales."""
        a = _StubCRS(epsg=25830, wkt="PROJCS[\"ETRS89_UTM_30N\",...]")
        b = _StubCRS(epsg=25830, wkt="PROJCRS[\"ETRS89 / UTM zone 30N\",...]")
        assert a != b  # Python == estricto: distinto (reproduce el bug)
        assert cartografia._crs_iguales(a, b) is True

    def test_epsg_distintos_son_distintos(self):
        a = _StubCRS(epsg=25829, wkt="x")
        b = _StubCRS(epsg=25830, wkt="x")
        assert cartografia._crs_iguales(a, b) is False

    def test_ambos_none(self):
        assert cartografia._crs_iguales(None, None) is True

    def test_uno_none(self):
        a = _StubCRS(epsg=25830, wkt="x")
        assert cartografia._crs_iguales(a, None) is False
        assert cartografia._crs_iguales(None, a) is False

    def test_sin_epsg_fallback_wkt(self):
        """Cuando to_epsg() devuelve None, comparación por WKT."""
        a = _StubCRS(epsg=None, wkt="PROJCRS[custom...]")
        b = _StubCRS(epsg=None, wkt="PROJCRS[custom...]")
        c = _StubCRS(epsg=None, wkt="PROJCRS[otro...]")
        assert cartografia._crs_iguales(a, b) is True
        assert cartografia._crs_iguales(a, c) is False


# ---------------------------------------------------------------------------
# _construir_vrt_xml_manual: regresión del error "CRS distinto en X.tif"
# ---------------------------------------------------------------------------


class _FakeTransform:
    """Imita affine.Affine lo mínimo para el builder manual."""

    def __init__(self, pxw=10.0, pxh=10.0):
        self.a = pxw
        self.e = -pxh  # convenio habitual: píxel Y invertido


class _FakeBounds(tuple):
    """Tupla 4 elementos (xmin, ymin, xmax, ymax) con atributos nombrados."""

    def __new__(cls, xmin, ymin, xmax, ymax):
        return super().__new__(cls, (xmin, ymin, xmax, ymax))


class _FakeColorInterp:
    def __init__(self, name):
        self.name = name


class _FakeDataset:
    def __init__(self, crs, xmin=0, ymin=0, xmax=1000, ymax=1000,
                 width=100, height=100, nbands=1):
        self.crs = crs
        self.width = width
        self.height = height
        self.count = nbands
        self.dtypes = ["uint8"] * nbands
        self.transform = _FakeTransform()
        self.bounds = _FakeBounds(xmin, ymin, xmax, ymax)
        self.nodata = None
        self.block_shapes = [(height, width)] * nbands
        self.colorinterp = [_FakeColorInterp("undefined")] * nbands

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _instalar_fake_rasterio(monkeypatch, mapa_path_a_crs):
    """Inyecta un módulo ``rasterio`` falso en sys.modules.

    ``mapa_path_a_crs`` mapea ruta de archivo → _StubCRS que queremos
    que devuelva ``rasterio.open(ruta).crs``.
    """
    fake_rio = types.ModuleType("rasterio")

    # Cada archivo tiene su propia posición en el mosaico para que la
    # unión de bounds sea no trivial.
    _posiciones = {
        ruta: (i * 1000, 0, (i + 1) * 1000, 1000)
        for i, ruta in enumerate(mapa_path_a_crs.keys())
    }

    def _fake_open(fp, *args, **kwargs):
        crs = mapa_path_a_crs[str(fp)]
        xmin, ymin, xmax, ymax = _posiciones[str(fp)]
        return _FakeDataset(crs, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)

    fake_rio.open = _fake_open
    monkeypatch.setitem(sys.modules, "rasterio", fake_rio)


class TestConstruirVrtXmlManual:
    def test_mismo_epsg_distinto_wkt_no_lanza_error(self, tmp_path, monkeypatch):
        """Regresión: hojas con mismo EPSG y WKT distinto deben aceptarse.

        Antes del fix, esto lanzaba
        ``ValueError: Los rásters no son compatibles para crear un mosaico:
        CRS distinto en h100512.tif ...``.
        """
        crs_a = _StubCRS(epsg=25830, wkt="PROJCS[\"ETRS89_UTM_30N_GDAL34\",...]")
        crs_b = _StubCRS(epsg=25830, wkt="PROJCRS[\"ETRS89 / UTM zone 30N\",...]")

        archivos = [
            str(tmp_path / "h100511.tif"),
            str(tmp_path / "h100512.tif"),
            str(tmp_path / "h100513.tif"),
        ]
        # Creamos ficheros vacíos porque _construir_vrt_xml_manual los
        # usa sólo como rutas — el fake rasterio.open() no los lee.
        for fp in archivos:
            Path(fp).touch()

        _instalar_fake_rasterio(
            monkeypatch,
            {
                archivos[0]: crs_a,  # WKT variante 1
                archivos[1]: crs_b,  # WKT variante 2
                archivos[2]: crs_b,  # WKT variante 2
            },
        )

        vrt_path = tmp_path / "mosaico.vrt"
        # No debería lanzar ValueError
        cartografia._construir_vrt_xml_manual(vrt_path, archivos)

        assert vrt_path.exists()
        contenido = vrt_path.read_text()
        assert "<VRTDataset" in contenido
        # Los 3 ficheros deben estar referenciados
        for fp in archivos:
            assert os.path.basename(fp) in contenido

    def test_epsg_realmente_distinto_sigue_fallando(self, tmp_path, monkeypatch):
        """Si los EPSG son distintos de verdad, sí tiene que rechazar."""
        crs_30 = _StubCRS(epsg=25830, wkt="PROJCS[UTM30N]")
        crs_29 = _StubCRS(epsg=25829, wkt="PROJCS[UTM29N]")

        archivos = [
            str(tmp_path / "h_utm30.tif"),
            str(tmp_path / "h_utm29.tif"),
        ]
        for fp in archivos:
            Path(fp).touch()

        _instalar_fake_rasterio(
            monkeypatch,
            {archivos[0]: crs_30, archivos[1]: crs_29},
        )

        vrt_path = tmp_path / "mosaico.vrt"
        with pytest.raises(ValueError, match="CRS distinto"):
            cartografia._construir_vrt_xml_manual(vrt_path, archivos)
