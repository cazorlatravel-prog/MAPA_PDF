#!/usr/bin/env python3
"""
EstelaGis - v2.0
Punto de entrada de la aplicación.

Aplicación de escritorio Python para generación de planos cartográficos
profesionales en serie (PDF A3/A4), orientada a infraestructuras forestales
de Andalucía (INFOCA / Junta de Andalucía).
"""

import sys
import tkinter as tk


def verificar_dependencias() -> list:
    """Verifica que todas las dependencias están instaladas."""
    faltantes = []
    for mod, nombre in [
        ("geopandas", "geopandas"),
        ("matplotlib", "matplotlib"),
        ("numpy", "numpy"),
        ("requests", "requests"),
        ("PIL", "Pillow"),
        ("contextily", "contextily"),
        ("pyproj", "pyproj"),
        ("reportlab", "reportlab"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            faltantes.append(nombre)
    return faltantes


def mostrar_error_dependencias(faltantes: list):
    """Muestra ventana de error con instrucciones de instalación."""
    root = tk.Tk()
    root.title("EstelaGis — Dependencias faltantes")
    root.geometry("600x400")
    root.configure(bg="#1a1a2e")

    tk.Label(
        root, text="\u26a0 Faltan librerías necesarias",
        font=("Consolas", 14, "bold"), bg="#1a1a2e", fg="#e94560",
    ).pack(pady=20)

    tk.Label(
        root, text="Ejecuta en tu terminal:",
        font=("Consolas", 11), bg="#1a1a2e", fg="#aaaacc",
    ).pack()

    cmd = "pip install " + " ".join(faltantes)
    txt = tk.Text(root, height=3, font=("Consolas", 10), bg="#0f3460", fg="#e2e2e2")
    txt.insert("1.0", cmd)
    txt.pack(padx=20, pady=10, fill="x")

    tk.Label(
        root, text=f"Faltantes: {', '.join(faltantes)}",
        font=("Consolas", 10), bg="#1a1a2e", fg="#ff6b6b",
    ).pack(pady=5)

    tk.Button(
        root, text="Cerrar", command=root.destroy,
        bg="#e94560", fg="white", font=("Consolas", 11),
    ).pack(pady=10)

    root.mainloop()


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

        # Borde sutil
        borde = tk.Frame(self.root, bg="#10B981", bd=0)
        borde.place(relx=0, rely=0, relwidth=1, relheight=1)
        interior = tk.Frame(borde, bg="#0F1923")
        interior.place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)

        # Nombre prominente estilo GIS
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

        # Subtitulo descriptivo
        tk.Label(
            interior, text="Planos Forestales",
            font=("Segoe UI", 12), bg="#0F1923", fg="#8899AA",
        ).pack(pady=(2, 8))

        # Version
        tk.Label(
            interior, text="v2.0",
            font=("Segoe UI", 9), bg="#0F1923", fg="#506070",
        ).pack(pady=(0, 16))

        # Copyright
        tk.Label(
            interior,
            text="\u00a9 Jose Caballero Sánchez (Cazorla 2026)",
            font=("Segoe UI", 10, "bold"), bg="#0F1923", fg="#10B981",
        ).pack(pady=(0, 4))

        # Licencia
        tk.Label(
            interior,
            text="Licencia de uso gratuita, prohibida su comercialización.",
            font=("Segoe UI", 8), bg="#0F1923", fg="#8899AA",
        ).pack()

        # Texto de estado
        self._estado_var = tk.StringVar(value="Iniciando...")
        tk.Label(
            interior, textvariable=self._estado_var,
            font=("Segoe UI", 8), bg="#0F1923", fg="#506070",
        ).pack(pady=(14, 4))

        # Barra de carga
        barra_bg = tk.Frame(interior, bg="#243447", height=4)
        barra_bg.pack(fill="x", padx=50, pady=(0, 0))
        self._barra = tk.Frame(barra_bg, bg="#10B981", height=4, width=0)
        self._barra.place(x=0, y=0, height=4)
        self._barra_bg = barra_bg

        # Porcentaje
        self._pct_var = tk.StringVar(value="0%")
        tk.Label(
            interior, textvariable=self._pct_var,
            font=("Segoe UI", 8), bg="#0F1923", fg="#506070",
        ).pack(pady=(4, 0))

        self._progreso = 0
        self.root.update()

    def set_progreso(self, porcentaje: int, texto: str = ""):
        """Actualiza la barra de progreso y el texto de estado."""
        self._progreso = porcentaje
        ancho_total = self._barra_bg.winfo_width() or 400
        self._barra.place(x=0, y=0, height=4, width=int(ancho_total * porcentaje / 100))
        self._pct_var.set(f"{porcentaje}%")
        if texto:
            self._estado_var.set(texto)
        self.root.update()

    def cerrar(self):
        """Cierra la ventana splash."""
        self.root.destroy()


def main():
    faltantes = verificar_dependencias()
    if faltantes:
        mostrar_error_dependencias(faltantes)
        sys.exit(1)

    # Mostrar splash ANTES de las importaciones pesadas
    splash = SplashScreen()
    splash.set_progreso(5, "Cargando bibliotecas base...")

    # Importaciones pesadas por pasos con progreso real
    splash.set_progreso(10, "Cargando numpy...")
    import numpy  # noqa: F401

    splash.set_progreso(20, "Cargando matplotlib...")
    import matplotlib  # noqa: F401

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

    splash.set_progreso(70, "Cargando interfaz gráfica...")
    from generador_planos.gui.app import App

    splash.set_progreso(85, "Inicializando aplicación...")

    # Crear ventana principal oculta, reutilizando el Tk del splash no es posible
    # porque splash usa su propio Tk. Cerramos splash y creamos App.
    splash.set_progreso(95, "Preparando ventana principal...")

    # Guardar geometría del splash para transición suave
    splash.set_progreso(100, "¡Listo!")
    splash.root.after(300, splash.cerrar)
    splash.root.mainloop()

    # Ahora crear la aplicación principal (los módulos ya están cacheados)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
