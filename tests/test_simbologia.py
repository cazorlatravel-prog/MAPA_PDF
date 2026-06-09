"""Tests para el módulo de simbología."""

import pytest

from generador_planos.motor.simbologia import (
    ConfigSimbologia, GestorSimbologia,
    TIPOS_TRAZO, MARCADORES, PALETA_CATEGORIAS,
)


class TestConfigSimbologia:
    def test_valores_por_defecto(self):
        cfg = ConfigSimbologia()
        assert cfg.color is not None
        assert cfg.linewidth > 0
        assert cfg.alpha > 0

    def test_to_dict_roundtrip(self):
        cfg = ConfigSimbologia(color="#FF0000", linewidth=3.0, label="test")
        d = cfg.to_dict()
        cfg2 = ConfigSimbologia.from_dict(d)
        assert cfg2.color == "#FF0000"
        assert cfg2.linewidth == 3.0
        assert cfg2.label == "test"


class TestGestorSimbologia:
    def test_generar_por_categoria(self):
        gestor = GestorSimbologia()
        valores = ["Cortafuegos", "Pista", "Senda"]
        gestor.generar_por_categoria("Tipo", valores)
        assert "Tipo" in gestor.categorias
        assert len(gestor.categorias["Tipo"]) == 3

    def test_obtener_simbologia_infra(self):
        gestor = GestorSimbologia()
        gestor.generar_por_categoria("Campo", ["A", "B"])
        cfg = gestor.obtener_simbologia_infra("Campo", "A")
        assert isinstance(cfg, ConfigSimbologia)

    def test_obtener_simbologia_desconocida(self):
        gestor = GestorSimbologia()
        gestor.generar_por_categoria("Campo", ["A"])
        cfg = gestor.obtener_simbologia_infra("Campo", "Z")
        assert isinstance(cfg, ConfigSimbologia)

    def test_colores_distintos_por_categoria(self):
        gestor = GestorSimbologia()
        gestor.generar_por_categoria("Tipo", ["A", "B", "C"])
        colores = {
            gestor.obtener_simbologia_infra("Tipo", v).color
            for v in ["A", "B", "C"]
        }
        assert len(colores) == 3

    def test_serializar_deserializar(self):
        gestor = GestorSimbologia()
        gestor.generar_por_categoria("Campo", ["X", "Y"])
        d = gestor.to_dict()
        gestor2 = GestorSimbologia.from_dict(d)
        assert "Campo" in gestor2.categorias
        assert len(gestor2.categorias["Campo"]) == 2


class TestConstantes:
    def test_tipos_trazo(self):
        assert len(TIPOS_TRAZO) > 0
        for nombre, estilo in TIPOS_TRAZO.items():
            assert isinstance(nombre, str)
            assert isinstance(estilo, str)

    def test_marcadores(self):
        assert len(MARCADORES) > 0

    def test_paleta_categorias(self):
        assert len(PALETA_CATEGORIAS) >= 10


class TestRegresionesProyecto:
    """Regresiones de carga de proyectos guardados."""

    def test_from_dict_ignora_claves_desconocidas(self):
        """Una clave desconocida en el JSON (de otra versión) no debe
        romper la carga del proyecto entero con TypeError."""
        d = ConfigSimbologia(color="#FF0000").to_dict()
        d["hatch"] = "//"
        d["clave_futura"] = 123
        cfg = ConfigSimbologia.from_dict(d)
        assert cfg.color == "#FF0000"

    def test_generar_por_categoria_conserva_personalizados(self):
        """Al regenerar categorías (p. ej. tras cargar proyecto), los
        colores personalizados de valores ya existentes se conservan."""
        gestor = GestorSimbologia()
        gestor.generar_por_categoria("Tipo", ["A", "B"])
        gestor.categorias["Tipo"]["A"].color = "#ABCDEF"

        gestor.generar_por_categoria("Tipo", ["A", "B", "C"])
        assert gestor.categorias["Tipo"]["A"].color == "#ABCDEF"
        assert "C" in gestor.categorias["Tipo"]

    def test_generar_por_categoria_montes_conserva(self):
        gestor = GestorSimbologia()
        gestor.generar_por_categoria_montes("Prop", ["X"])
        gestor.categorias_montes["Prop"]["X"].color = "#123456"
        gestor.generar_por_categoria_montes("Prop", ["X", "Y"])
        assert gestor.categorias_montes["Prop"]["X"].color == "#123456"
