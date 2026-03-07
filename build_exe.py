#!/usr/bin/env python3
"""
Script para construir el ejecutable (.exe) del Generador de Planos Forestales.

Uso:
    1. Instalar PyInstaller:  pip install pyinstaller
    2. Ejecutar:              python build_exe.py

Genera:
    dist/GeneradorPlanos/GeneradorPlanos.exe   (carpeta con dependencias)
    dist/GeneradorPlanos.exe                    (ejecutable único, más lento al abrir)
"""

import os
import sys
import subprocess

# ── Configuración ────────────────────────────────────────────────────────

APP_NAME = "GeneradorPlanos"
ICON_FILE = os.path.join("assets", "icon.ico")

# Punto de entrada directo (sin verificar dependencias, ya van empaquetadas)
LAUNCHER_SCRIPT = "_launcher_exe.py"

LAUNCHER_CODE = '''\
"""Launcher para el ejecutable."""
import sys
import os

if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    sys.path.insert(0, base)

from generador_planos.gui.app import App

app = App()
app.mainloop()
'''

# Paquetes que PyInstaller debe recoger completos
COLLECT_ALL = [
    "matplotlib",
    "contextily",
    "geopandas",
    "pyproj",
    "shapely",
    "numpy",
    "PIL",
    "reportlab",
    "requests",
    "certifi",
    "pyogrio",
    "xyzservices",
]

# Módulos ocultos que PyInstaller puede no detectar automáticamente
HIDDEN_IMPORTS = [
    "geopandas",
    "pyproj", "pyproj.database", "pyproj._crs",
    "shapely", "shapely.geometry",
    "contextily", "contextily.tile",
    "PIL", "PIL.Image",
    "numpy",
    "matplotlib", "matplotlib.figure", "matplotlib.pyplot",
    "matplotlib.backends", "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_pdf",
    "reportlab", "reportlab.lib", "reportlab.pdfgen",
    "requests", "certifi", "xyzservices", "pyogrio",
    "generador_planos",
    "generador_planos.motor", "generador_planos.motor.generador",
    "generador_planos.motor.escala", "generador_planos.motor.cartografia",
    "generador_planos.motor.maquetacion", "generador_planos.motor.simbologia",
    "generador_planos.motor.capas_extra", "generador_planos.motor.perfil",
    "generador_planos.motor.proyecto",
    "generador_planos.gui", "generador_planos.gui.app",
    "generador_planos.gui.estilos", "generador_planos.gui.panel_capas",
    "generador_planos.gui.panel_config", "generador_planos.gui.panel_campos",
    "generador_planos.gui.panel_filtros", "generador_planos.gui.panel_simbologia",
    "generador_planos.gui.panel_cajetin", "generador_planos.gui.panel_generacion",
]


def verificar_pyinstaller():
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__} encontrado.")
        return True
    except ImportError:
        print("  ERROR: PyInstaller no instalado.")
        print("  Ejecuta: pip install pyinstaller")
        return False


def construir_exe(modo_onefile=False):
    """Construye el ejecutable con PyInstaller."""
    print(f"\n{'='*60}")
    print(f"  CONSTRUYENDO: {APP_NAME}")
    print(f"  Modo: {'Un solo archivo' if modo_onefile else 'Carpeta con dependencias'}")
    print(f"{'='*60}\n")

    # Crear launcher temporal
    with open(LAUNCHER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_CODE)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
    ]

    # Icono
    if os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        print(f"  Icono: {ICON_FILE}")

    # Modo un solo archivo o carpeta
    if modo_onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Collect-all para paquetes complejos
    for pkg in COLLECT_ALL:
        cmd.extend(["--collect-all", pkg])

    # Hidden imports
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # Excluir módulos innecesarios para reducir tamaño
    for excl in ["pytest", "pip",
                 "IPython", "jupyter", "notebook", "sphinx"]:
        cmd.extend(["--exclude-module", excl])

    # Script principal
    cmd.append(LAUNCHER_SCRIPT)

    print(f"  Construyendo... (puede tardar 5-15 minutos)")
    print()

    result = subprocess.run(cmd)

    # Limpiar launcher temporal
    if os.path.exists(LAUNCHER_SCRIPT):
        os.remove(LAUNCHER_SCRIPT)

    if result.returncode == 0:
        if modo_onefile:
            exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        else:
            exe_path = os.path.join("dist", APP_NAME, f"{APP_NAME}.exe")

        print(f"\n{'='*60}")
        print(f"  COMPLETADO")
        print(f"  Ejecutable: {exe_path}")

        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"  Tamaño: {size_mb:.1f} MB")

        print(f"{'='*60}")
    else:
        print(f"\n  ERROR: La construcción falló (código {result.returncode})")
        sys.exit(1)


def main():
    print("\n  GENERADOR DE PLANOS FORESTALES - Constructor de ejecutable\n")

    if not verificar_pyinstaller():
        sys.exit(1)

    # Crear carpeta assets si no existe
    os.makedirs("assets", exist_ok=True)

    # Preguntar modo
    print("\n  Modos de construcción:")
    print("    1. Carpeta con dependencias (más rápido al abrir)")
    print("    2. Un solo archivo .exe (más portable, más lento al abrir)")
    print()

    modo = input("  Elige modo [1/2] (por defecto 1): ").strip()
    onefile = modo == "2"

    construir_exe(modo_onefile=onefile)


if __name__ == "__main__":
    main()
