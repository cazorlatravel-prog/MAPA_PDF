#!/usr/bin/env python3
"""
GENERADOR DE PLANOS FORESTALES - v2.0
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
    root.title("Dependencias faltantes")
    root.geometry("600x400")
    root.configure(bg="#1a1a2e")

    tk.Label(
        root, text="\u26a0 Faltan librer\u00edas necesarias",
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


def main():
    faltantes = verificar_dependencias()
    if faltantes:
        mostrar_error_dependencias(faltantes)
        sys.exit(1)

    # Importar después de verificar dependencias
    from generador_planos.gui.app import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
