#!/usr/bin/env python3
"""
Crea un ejecutable portable (.exe) de EstelaGis.

NO requiere instalación. Se genera un único archivo .exe que se puede
copiar a un USB, compartir por email o ejecutar desde cualquier carpeta.

Uso:
    1. pip install pyinstaller
    2. python build_portable.py

Genera:
    dist/EstelaGis_Portable.exe  (~150-300 MB, un solo archivo)
    EstelaGis_Portable.exe       (copia en la raíz del proyecto)
    EstelaGis_Portable_v2.0.zip  (ZIP listo para compartir)
"""

import os
import sys
import shutil
import subprocess
import tempfile
import zipfile


APP_NAME = "EstelaGis_Portable"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "EstelaGis — Planos Forestales - \u00a9 Jose Caballero S\u00e1nchez (Cazorla 2026)"
ICON_FILE = os.path.join("assets", "icon.ico")

# Punto de entrada directo que evita la verificación de dependencias
# (en el .exe ya vienen empaquetadas)
LAUNCHER_SCRIPT = "_launcher_portable.py"

LAUNCHER_CODE = '''\
"""Launcher para el ejecutable portable con splash screen."""
import sys
import os
import tkinter as tk

# Asegurar que el paquete se encuentra
if getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    sys.path.insert(0, base)
    os.environ["MPLBACKEND"] = "Agg"


class SplashScreen:
    """Ventana splash con barra de progreso real durante la carga."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)

        ancho, alto = 500, 300
        x = (self.root.winfo_screenwidth() - ancho) // 2
        y = (self.root.winfo_screenheight() - alto) // 2
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.root.configure(bg="#0F1923")
        self.root.attributes("-topmost", True)

        borde = tk.Frame(self.root, bg="#10B981", bd=0)
        borde.place(relx=0, rely=0, relwidth=1, relheight=1)
        interior = tk.Frame(borde, bg="#0F1923")
        interior.place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)

        name_frame = tk.Frame(interior, bg="#0F1923")
        name_frame.pack(pady=(40, 0))

        tk.Label(
            name_frame, text="Estela",
            font=("Segoe UI", 32, "bold"), bg="#0F1923", fg="#10B981",
        ).pack(side="left")

        tk.Label(
            name_frame, text="Gis",
            font=("Segoe UI", 32), bg="#0F1923", fg="#E8ECF1",
        ).pack(side="left")

        tk.Label(
            interior, text="Planos Forestales",
            font=("Segoe UI", 12), bg="#0F1923", fg="#8899AA",
        ).pack(pady=(2, 8))

        tk.Label(
            interior, text="v2.0",
            font=("Segoe UI", 9), bg="#0F1923", fg="#506070",
        ).pack(pady=(0, 16))

        tk.Label(
            interior,
            text="\\u00a9 Jose Caballero S\\u00e1nchez (Cazorla 2026)",
            font=("Segoe UI", 10, "bold"), bg="#0F1923", fg="#10B981",
        ).pack(pady=(0, 4))

        tk.Label(
            interior,
            text="Licencia de uso gratuita, prohibida su comercializaci\\u00f3n.",
            font=("Segoe UI", 8), bg="#0F1923", fg="#8899AA",
        ).pack()

        self._estado_var = tk.StringVar(value="Iniciando...")
        tk.Label(
            interior, textvariable=self._estado_var,
            font=("Segoe UI", 8), bg="#0F1923", fg="#506070",
        ).pack(pady=(14, 4))

        barra_bg = tk.Frame(interior, bg="#243447", height=4)
        barra_bg.pack(fill="x", padx=50, pady=(0, 0))
        self._barra = tk.Frame(barra_bg, bg="#10B981", height=4, width=0)
        self._barra.place(x=0, y=0, height=4)
        self._barra_bg = barra_bg

        self._pct_var = tk.StringVar(value="0%")
        tk.Label(
            interior, textvariable=self._pct_var,
            font=("Segoe UI", 8), bg="#0F1923", fg="#506070",
        ).pack(pady=(4, 0))

        self._progreso = 0
        self.root.update()

    def set_progreso(self, porcentaje, texto=""):
        self._progreso = porcentaje
        ancho_total = self._barra_bg.winfo_width() or 400
        self._barra.place(x=0, y=0, height=4, width=int(ancho_total * porcentaje / 100))
        self._pct_var.set(f"{porcentaje}%")
        if texto:
            self._estado_var.set(texto)
        self.root.update()

    def cerrar(self):
        self.root.destroy()


# Mostrar splash ANTES de las importaciones pesadas
splash = SplashScreen()
splash.set_progreso(5, "Cargando bibliotecas base...")

splash.set_progreso(10, "Cargando numpy...")
import numpy  # noqa: F401

splash.set_progreso(15, "Cargando matplotlib...")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.backends.backend_agg
import matplotlib.backends.backend_pdf
import matplotlib.backends.backend_svg

splash.set_progreso(30, "Cargando geopandas...")
import geopandas  # noqa: F401

splash.set_progreso(40, "Cargando PIL / Pillow...")
import PIL  # noqa: F401

splash.set_progreso(48, "Cargando contextily...")
import contextily  # noqa: F401

splash.set_progreso(55, "Cargando pyproj...")
import pyproj  # noqa: F401

splash.set_progreso(62, "Cargando reportlab...")
import reportlab  # noqa: F401

splash.set_progreso(70, "Cargando interfaz gr\\u00e1fica...")
from generador_planos.gui.app import App

splash.set_progreso(85, "Inicializando aplicaci\\u00f3n...")
splash.set_progreso(95, "Preparando ventana principal...")
splash.set_progreso(100, "\\u00a1Listo!")
splash.root.after(300, splash.cerrar)
splash.root.mainloop()

app = App()
app.mainloop()
'''

# Paquetes que PyInstaller debe recoger completos
COLLECT_ALL = [
    "matplotlib",
    "contextily",
    "rasterio",
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
    "adjustText",
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
    "rasterio",
    "rasterio.sample",
    "rasterio._io",
    "rasterio.crs",
    "rasterio.enums",
    "rasterio.errors",
    "rasterio.transform",
    "rasterio.vrt",
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
    "adjustText",
]

EXCLUDE = [
    "pytest", "pip",
    "IPython", "jupyter", "notebook", "sphinx",
    "tkinter.test",
]


def crear_version_info():
    """Crea archivo de metadatos Windows (visible en Propiedades del .exe)."""
    parts = APP_VERSION.split(".")
    major = int(parts[0]) if len(parts) > 0 else 2
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0

    version_info = f"""\
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040A04B0',
          [
            StringStruct(u'CompanyName', u'Jose Caballero S\u00e1nchez (Cazorla)'),
            StringStruct(u'FileDescription',
                         u'EstelaGis — Planos Forestales'),
            StringStruct(u'FileVersion', u'{APP_VERSION}'),
            StringStruct(u'InternalName', u'{APP_NAME}'),
            StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
            StringStruct(u'ProductName',
                         u'EstelaGis — Planos Forestales'),
            StringStruct(u'ProductVersion', u'{APP_VERSION}'),
            StringStruct(u'LegalCopyright',
                         u'\u00a9 Jose Caballero S\u00e1nchez (Cazorla 2026) Todos los derechos reservados'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1034, 1200])])
  ]
)
"""
    path = os.path.join(tempfile.gettempdir(), "version_info.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(version_info)
    return path


def crear_zip(exe_path):
    """Crea un ZIP listo para compartir con el .exe dentro."""
    version_short = APP_VERSION.replace(".", "_")
    zip_name = f"EstelaGis_Portable_v{version_short}.zip"
    zip_path = os.path.join(os.path.dirname(exe_path), zip_name)

    print(f"  Creando ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, os.path.basename(exe_path))

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  ZIP creado: {size_mb:.1f} MB")
    return zip_path


def main():
    print()
    print("=" * 60)
    print("  EstelaGis — Planos Forestales")
    print("  Construir ejecutable PORTABLE (un solo .exe)")
    print("=" * 60)
    print()

    # Verificar dependencias principales
    print("  Verificando dependencias...")
    faltantes = []
    for mod_name in ["matplotlib", "geopandas", "numpy", "pyproj",
                     "shapely", "contextily", "rasterio", "PIL", "reportlab"]:
        try:
            __import__(mod_name)
        except ImportError:
            faltantes.append(mod_name)
    if faltantes:
        print(f"  FALTAN módulos: {', '.join(faltantes)}")
        print("  Ejecuta: pip install -r requirements.txt")
        sys.exit(1)

    import matplotlib
    print(f"  matplotlib {matplotlib.__version__} en: {os.path.dirname(matplotlib.__file__)}")

    # Verificar PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  PyInstaller no encontrado. Instalando...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"]
        )

    # Crear launcher temporal
    with open(LAUNCHER_SCRIPT, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_CODE)
    print(f"  Launcher creado: {LAUNCHER_SCRIPT}")

    # Crear archivo de metadatos Windows
    version_file = crear_version_info()
    print(f"  Metadatos Windows: v{APP_VERSION} - Jose Caballero")

    # Detectar rutas de site-packages para que PyInstaller encuentre todo
    import site
    site_dirs = []
    try:
        site_dirs += site.getsitepackages()
    except AttributeError:
        pass
    try:
        usp = site.getusersitepackages()
        if isinstance(usp, str):
            site_dirs.append(usp)
    except AttributeError:
        pass
    # Añadir directorio padre de matplotlib como ruta extra
    mpl_dir = os.path.dirname(matplotlib.__file__)
    mpl_parent = os.path.dirname(mpl_dir)
    if mpl_parent not in site_dirs:
        site_dirs.append(mpl_parent)
    site_dirs = [d for d in site_dirs if os.path.isdir(d)]
    print(f"  Rutas de búsqueda para PyInstaller: {len(site_dirs)}")
    for d in site_dirs:
        print(f"    - {d}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",            # UN SOLO ARCHIVO
        "--windowed",           # Sin ventana de consola
        "--noconfirm",
        "--clean",
        "--version-file", version_file,
    ]

    # Añadir rutas de site-packages explícitamente
    for sp in site_dirs:
        cmd.extend(["--paths", sp])

    # Icono
    if os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        print(f"  Icono: {ICON_FILE}")

    # Collect-all para paquetes complejos
    for pkg in COLLECT_ALL:
        cmd.extend(["--collect-all", pkg])

    # Collect-submodules para paquetes que fallan con solo collect-all
    for pkg in ["matplotlib", "matplotlib.backends", "geopandas",
                "pyproj", "shapely", "contextily", "rasterio"]:
        cmd.extend(["--collect-submodules", pkg])

    # Collect-data para paquetes con archivos de datos necesarios
    for pkg in ["matplotlib", "pyproj", "certifi"]:
        cmd.extend(["--collect-data", pkg])

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

    # Limpiar archivo de metadatos temporal
    if os.path.exists(version_file):
        os.remove(version_file)

    if result.returncode == 0:
        exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        print()
        print("=" * 60)
        print("  COMPLETADO")
        print(f"  Archivo: {exe_path}")

        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"  Tamano: {size_mb:.1f} MB")

            # Copiar el .exe a la raíz del proyecto para fácil acceso
            root_exe = f"{APP_NAME}.exe"
            shutil.copy2(exe_path, root_exe)
            print()
            print(f"  Copiado a raiz: {root_exe}")

            # Crear ZIP listo para compartir
            crear_zip(exe_path)

        print()
        print("  Este .exe es 100% portable:")
        print("    - No necesita Python instalado")
        print("    - No necesita instalar nada")
        print("    - Se puede copiar a USB o compartir")
        print("    - Doble clic para ejecutar")
        print()
        print("  Propiedades visibles en Windows Explorer:")
        print("    - Nombre: EstelaGis")
        print(f"    - Version: {APP_VERSION}")
        print("    - Autor: Jose Caballero")
        print("=" * 60)
    else:
        print(f"\n  ERROR: Fallo la construccion (codigo {result.returncode})")
        sys.exit(1)


if __name__ == "__main__":
    main()
