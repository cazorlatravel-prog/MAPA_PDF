"""Tests de maquetación (sin red): figura, guardado multi-formato, marca de
agua, utilidades del cajetín y resolución de la fuente."""
import importlib
import os
import warnings

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402
import pytest  # noqa: E402
from matplotlib.text import Text  # noqa: E402

from generador_planos.motor import maquetacion  # noqa: E402
from generador_planos.motor.maquetacion import (  # noqa: E402
    MaquetadorPlano, texto_centro_utm, texto_centro_geo, fecha_cajetin,
    texto_base_cartografica, resolver_fuente, FUENTES_PREFERIDAS,
)
from generador_planos.motor._elementos_mapa import (  # noqa: E402
    formato_distancia, recortar_texto,
)

LAYOUTS = ["Plantilla 1 (Clásica)", "Plantilla 2 (Panel lateral)"]
EXT = (500000, 504000, 4196000, 4198000)


def _maq(layout, dpi=50):
    m = MaquetadorPlano("A4 Horizontal", 10000, layout_key=layout, dpi=dpi)
    m.crear_figura()
    m.configurar_mapa_principal(*EXT)
    return m


@pytest.mark.parametrize("layout", LAYOUTS)
def test_crear_figura_devuelve_5_elementos(layout):
    m = MaquetadorPlano("A4 Horizontal", 10000, layout_key=layout, dpi=50)
    try:
        res = m.crear_figura()
        assert len(res) == 5
        fig, ax_map, ax_info, ax_mini, ax_esc = res
        assert fig is m.fig
        for ax in (ax_map, ax_info, ax_mini, ax_esc):
            assert ax is not None and ax.figure is fig
    finally:
        plt.close(m.fig)


def test_guardar_pdf_y_png(tmp_path):
    m = _maq(LAYOUTS[0])
    fig = m.fig
    ruta = tmp_path / "plano.pdf"
    m.guardar(str(ruta), dpi_save=40, formatos=("pdf", "png"))
    assert ruta.is_file() and ruta.stat().st_size > 0
    png = tmp_path / "plano.png"
    assert png.is_file() and png.stat().st_size > 0
    assert not (tmp_path / "plano.jpg").exists()
    # La figura queda cerrada
    assert not plt.fignum_exists(fig.number)


def test_guardar_jpg(tmp_path):
    m = _maq(LAYOUTS[1])
    m.guardar(str(tmp_path / "p.pdf"), dpi_save=40, formatos=["pdf", "jpg"])
    assert (tmp_path / "p.pdf").is_file()
    assert (tmp_path / "p.jpg").is_file()


def test_guardar_por_defecto_solo_pdf(tmp_path):
    m = _maq(LAYOUTS[0])
    m.guardar(str(tmp_path / "solo.pdf"), dpi_save=40)
    assert sorted(os.listdir(tmp_path)) == ["solo.pdf"]


def test_guardar_cierra_figura_si_falla(tmp_path):
    m = _maq(LAYOUTS[0])
    fig = m.fig
    with pytest.raises(Exception):
        m.guardar(str(tmp_path / "no_existe" / "x.pdf"), dpi_save=40)
    assert not plt.fignum_exists(fig.number)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_marca_agua_anade_texto(layout):
    m = _maq(layout)
    try:
        antes = len(m.ax_map.texts)
        t = m.dibujar_marca_agua("BORRADOR")
        assert isinstance(t, Text)
        assert t in m.ax_map.texts
        assert len(m.ax_map.texts) == antes + 1
        assert t.get_text() == "BORRADOR"
        assert t.get_rotation() == pytest.approx(30)
        assert t.get_alpha() is not None and t.get_alpha() < 0.3
        assert m.dibujar_marca_agua("") is None
        assert len(m.ax_map.texts) == antes + 1
    finally:
        plt.close(m.fig)


def test_texto_centro_utm_separador_miles():
    assert texto_centro_utm(502000, 4196000) == "X 502.000 · Y 4.196.000"
    assert "502.000" in texto_centro_utm(501999.6, 4196000.2)


def test_texto_centro_geo():
    pytest.importorskip("pyproj")
    txt = texto_centro_geo(502000, 4196000)
    # Cerca de Cazorla: lat ~37,9° N, lon ~ -2,98° (5 decimales, coma)
    assert txt.startswith("Lat 37,")
    assert "Lon -2," in txt or "Lon -3," in txt
    lat = txt.split("Lat ")[1].split("°")[0]
    assert len(lat.split(",")[1]) == 5


def test_fecha_cajetin():
    assert fecha_cajetin({"fecha": "10/2026"}) == "10/2026"
    hoy = fecha_cajetin({})
    assert len(hoy) == 10 and hoy[2] == "/" and hoy[5] == "/"


def test_base_cartografica_sin_atribucion_conocida():
    assert texto_base_cartografica("Proveedor inventado") == \
        "Base cartográfica: Proveedor inventado"


def test_formato_distancia_y_recorte():
    assert formato_distancia(500) == "500 m"
    assert formato_distancia(1000) == "1 km"
    assert formato_distancia(2500) == "2,5 km"
    assert formato_distancia(62.5) == "62,5 m"
    assert recortar_texto("abc", 5) == "abc"
    r = recortar_texto("x" * 58, 20)
    assert len(r) == 20 and r.endswith("…")


def test_leyenda_lateral_indica_elementos_ocultos():
    m = _maq(LAYOUTS[1])
    try:
        items = [(f"Cat {i}", "#123456", "linestring", "-", None, None)
                 for i in range(15)]
        m.dibujar_leyenda_lateral(items, [])
        textos = [t.get_text() for t in m.ax_info.texts]
        assert "+3 más" in textos
    finally:
        plt.close(m.fig)


def test_resolver_fuente_sin_avisos():
    instaladas = {f.name for f in fm.fontManager.ttflist}
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        nombre = resolver_fuente()
        importlib.reload(maquetacion)
    assert nombre in instaladas
    assert nombre in FUENTES_PREFERIDAS
    assert not [x for x in w if "fuente" in str(x.message).lower()
                or "font" in str(x.message).lower()]
    # Una lista sin fuentes instaladas cae en DejaVu Sans
    assert resolver_fuente(["Fuente Que No Existe 123"]) == "DejaVu Sans"
