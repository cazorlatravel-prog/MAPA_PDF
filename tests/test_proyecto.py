"""Tests para el módulo de gestión de proyectos."""

import json
import os
import tempfile

import pytest

from generador_planos.motor.proyecto import Proyecto


class TestProyecto:
    def test_crear_vacio(self):
        p = Proyecto()
        assert p.formato == "A3 Horizontal"

    def test_to_dict(self):
        p = Proyecto()
        d = p.to_dict()
        assert isinstance(d, dict)
        assert "formato" in d

    def test_from_dict_roundtrip(self):
        p = Proyecto()
        p.formato = "A2 Horizontal"
        p.cajetin["autor"] = "Test Author"
        d = p.to_dict()
        p2 = Proyecto.from_dict(d)
        assert p2.formato == "A2 Horizontal"
        assert p2.cajetin["autor"] == "Test Author"

    def test_guardar_y_cargar(self):
        p = Proyecto()
        p.formato = "A4 Horizontal"
        p.cajetin["proyecto"] = "Proyecto Test"

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            ruta = f.name

        try:
            p.guardar(ruta)
            assert os.path.isfile(ruta)

            p2 = Proyecto.cargar(ruta)
            assert p2.formato == "A4 Horizontal"
            assert p2.cajetin["proyecto"] == "Proyecto Test"
        finally:
            os.unlink(ruta)

    def test_guardar_json_valido(self):
        p = Proyecto()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            ruta = f.name

        try:
            p.guardar(ruta)
            with open(ruta) as f:
                data = json.load(f)
            assert isinstance(data, dict)
        finally:
            os.unlink(ruta)
