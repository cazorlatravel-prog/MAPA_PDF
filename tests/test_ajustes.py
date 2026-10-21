"""Tests del módulo de ajustes persistentes de la GUI (sin tkinter)."""

import importlib.util
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[1] / "generador_planos" / "gui" / "ajustes.py"


@pytest.fixture
def ajustes(tmp_path):
    # Cargar el módulo directamente (el paquete gui importa tkinter) y
    # redirigir el JSON a una carpeta temporal.
    spec = importlib.util.spec_from_file_location("ajustes_test", _RUTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._DIR_CACHE = tmp_path
    mod._RUTA_JSON = tmp_path / "ajustes.json"
    return mod


def test_vacio_si_no_existe(ajustes):
    assert ajustes.cargar_ajustes() == {}


def test_guardar_y_cargar(ajustes):
    assert ajustes.guardar_ajustes({"proveedor": "Google Satélite", "formato": "A3 Horizontal"})
    assert ajustes.cargar_ajustes()["proveedor"] == "Google Satélite"


def test_actualizar_fusiona_e_ignora_none(ajustes):
    ajustes.guardar_ajustes({"a": 1, "b": 2})
    d = ajustes.actualizar_ajustes(b=3, c=None)
    assert d == {"a": 1, "b": 3}
    assert ajustes.cargar_ajustes() == {"a": 1, "b": 3}


def test_corrupto_devuelve_vacio(ajustes):
    ajustes._RUTA_JSON.write_text("{no es json", encoding="utf-8")
    assert ajustes.cargar_ajustes() == {}


def test_guardar_rechaza_no_dict(ajustes):
    assert ajustes.guardar_ajustes(["lista"]) is False
