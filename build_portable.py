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
ICON_FILE = os.path.join("assets", "icon.ico")

# Punto de entrada directo que evita la verificación de dependencias
# (en el .exe ya vienen empaquetadas)
LAUNCHER_SCRIPT = "_launcher_portable.py"

LAUNCHER_CODE = '''\
"""Launcher para el ejecutable portable."""
import sys
import os

# Asegurar que el paquete se encuentra
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

HIDDEN_IMPORTS = [
    "geopandas",
    "pyproj",
    "pyproj.database",
    "pyproj._crs",
    "shapely",
    "shapely.geometry",
    "contextily",
    "contextily.tile",
    "PIL",
    "PIL.Image",
    "numpy",
    "matplotlib",
    "matplotlib.figure",
    "matplotlib.pyplot",
    "matplotlib.backends",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_pdf",
    "matplotlib.backends.backend_svg",
    "reportlab",
    "reportlab.lib",
    "reportlab.pdfgen",
    "requests",
    "certifi",
    "xyzservices",
    "pyogrio",
    "generador_planos",
    "generador_planos.motor",
    "generador_planos.motor.generador",
    "generador_planos.motor.escala",
    "generador_planos.motor.cartografia",
    "generador_planos.motor.maquetacion",
    "generador_planos.motor.simbologia",
    "generador_planos.motor.capas_extra",
    "generador_planos.motor.perfil",
    "generador_planos.motor.proyecto",
    "generador_planos.gui",
    "generador_planos.gui.app",
    "generador_planos.gui.estilos",
    "generador_planos.gui.panel_capas",
    "generador_planos.gui.panel_config",
    "generador_planos.gui.panel_campos",
    "generador_planos.gui.panel_filtros",
    "generador_planos.gui.panel_simbologia",
    "generador_planos.gui.panel_cajetin",
    "generador_planos.gui.panel_generacion",
]

EXCLUDE = [
    "pytest", "test", "unittest", "pip",
    "IPython", "jupyter", "notebook", "sphinx",
    "tkinter.test",
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

    # Crear launcher temporal
    with open(LAUNCHER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_CODE)
    print(f"  Launcher creado: {LAUNCHER_SCRIPT}")

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

    # Collect-all para paquetes complejos
    for pkg in COLLECT_ALL:
        cmd.extend(["--collect-all", pkg])

    # Hidden imports
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # Exclusiones
    for excl in EXCLUDE:
        cmd.extend(["--exclude-module", excl])

    # Script principal
    cmd.append(LAUNCHER_SCRIPT)

    print()
    print("  Construyendo... (puede tardar 5-15 minutos)")
    print()

    result = subprocess.run(cmd)

    # Limpiar launcher temporal
    if os.path.exists(LAUNCHER_SCRIPT):
        os.remove(LAUNCHER_SCRIPT)

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
