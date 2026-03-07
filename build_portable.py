#!/usr/bin/env python3
"""
Crea un ejecutable portable (.exe) del Generador de Planos Forestales.

NO requiere instalación. Se genera un único archivo .exe que se puede
copiar a un USB, compartir por email o ejecutar desde cualquier carpeta.

Uso:
    1. pip install pyinstaller
    2. python build_portable.py

Genera:
    dist/GeneradorPlanos_Portable.exe  (~150-300 MB, un solo archivo)
"""

import os
import sys
import subprocess


APP_NAME = "GeneradorPlanos_Portable"
MAIN_SCRIPT = os.path.join("generador_planos", "main.py")
ICON_FILE = os.path.join("assets", "icon.ico")

HIDDEN_IMPORTS = [
    "geopandas",
    "pyproj",
    "pyproj.database",
    "pyproj._crs",
    "shapely",
    "shapely.geometry",
    "fiona",
    "fiona._shim",
    "fiona.schema",
    "contextily",
    "PIL",
    "PIL.Image",
    "numpy",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_pdf",
    "reportlab",
    "requests",
    "certifi",
]

EXCLUDE = [
    "pytest", "test", "unittest", "setuptools", "pip",
    "IPython", "jupyter", "notebook", "sphinx",
    "tkinter.test", "matplotlib.tests",
]


def main():
    print()
    print("=" * 60)
    print("  GENERADOR DE PLANOS FORESTALES")
    print("  Construir ejecutable PORTABLE (un solo .exe)")
    print("=" * 60)
    print()

    # Verificar PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  PyInstaller no encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    if not os.path.exists(MAIN_SCRIPT):
        print(f"  ERROR: No se encuentra {MAIN_SCRIPT}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",            # UN SOLO ARCHIVO
        "--windowed",           # Sin ventana de consola
        "--noconfirm",
        "--clean",
    ]

    # Icono
    if os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        print(f"  Icono: {ICON_FILE}")

    # Hidden imports
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # Exclusiones
    for excl in EXCLUDE:
        cmd.extend(["--exclude-module", excl])

    # Script principal
    cmd.append(MAIN_SCRIPT)

    print()
    print("  Construyendo... (puede tardar varios minutos)")
    print()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        print()
        print("=" * 60)
        print("  COMPLETADO")
        print(f"  Archivo: {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"  Tamano: {size_mb:.1f} MB")
        print()
        print("  Este .exe es 100% portable:")
        print("    - No necesita Python instalado")
        print("    - No necesita instalar nada")
        print("    - Se puede copiar a USB o compartir")
        print("    - Doble clic para ejecutar")
        print("=" * 60)
    else:
        print(f"\n  ERROR: Fallo la construccion (codigo {result.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    main()
