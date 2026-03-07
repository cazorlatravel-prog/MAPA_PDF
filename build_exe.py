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
import shutil

# ── Configuración ────────────────────────────────────────────────────────

APP_NAME = "GeneradorPlanos"
MAIN_SCRIPT = os.path.join("generador_planos", "main.py")
ICON_FILE = os.path.join("assets", "icon.ico")

# Datos adicionales que PyInstaller debe incluir
DATAS = [
    # Si hubiera archivos de datos, se añadirían aquí:
    # ("ruta_origen", "ruta_destino_en_exe"),
]

# Módulos ocultos que PyInstaller puede no detectar automáticamente
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

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",           # Sin consola (GUI)
        "--noconfirm",          # Sobreescribir sin preguntar
        "--clean",              # Limpiar caché
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

    # Datos adicionales
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in DATAS:
        cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    # Hidden imports
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # Excluir módulos innecesarios para reducir tamaño
    for excl in ["pytest", "test", "unittest", "setuptools", "pip"]:
        cmd.extend(["--exclude-module", excl])

    # Script principal
    cmd.append(MAIN_SCRIPT)

    print(f"  Comando: {' '.join(cmd[:6])}...")
    print()

    result = subprocess.run(cmd)

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

    if not os.path.exists(MAIN_SCRIPT):
        print(f"  ERROR: No se encuentra {MAIN_SCRIPT}")
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
