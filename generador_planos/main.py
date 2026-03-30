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


def mostrar_splash(root):
    """Muestra una ventana splash de bienvenida mientras carga la app."""
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)

    ancho, alto = 480, 260
    x = (splash.winfo_screenwidth() - ancho) // 2
    y = (splash.winfo_screenheight() - alto) // 2
    splash.geometry(f"{ancho}x{alto}+{x}+{y}")
    splash.configure(bg="#0F1923")
    splash.attributes("-topmost", True)

    # Borde sutil
    borde = tk.Frame(splash, bg="#10B981", bd=0)
    borde.place(relx=0, rely=0, relwidth=1, relheight=1)
    interior = tk.Frame(borde, bg="#0F1923")
    interior.place(x=1, y=1, relwidth=1, relheight=1, width=-2, height=-2)

    # Icono
    tk.Label(
        interior, text="\U0001f5fa", font=("Segoe UI", 36),
        bg="#0F1923", fg="#10B981",
    ).pack(pady=(28, 4))

    # Titulo
    tk.Label(
        interior, text="Generador de Planos Forestales",
        font=("Segoe UI", 15, "bold"), bg="#0F1923", fg="#E8ECF1",
    ).pack(pady=(0, 12))

    # Descripcion
    tk.Label(
        interior, text="Aplicaci\u00f3n para generar planos",
        font=("Segoe UI", 10), bg="#0F1923", fg="#8899AA",
    ).pack()

    # Copyright
    tk.Label(
        interior,
        text="\u00a9 Jose Caballero S\u00e1nchez (Cazorla 2026)",
        font=("Segoe UI", 10, "bold"), bg="#0F1923", fg="#10B981",
    ).pack(pady=(2, 4))

    # Licencia
    tk.Label(
        interior,
        text="Licencia de uso gratuita, prohibida su comercializaci\u00f3n.",
        font=("Segoe UI", 8), bg="#0F1923", fg="#8899AA",
    ).pack()

    # Barra de carga
    barra_bg = tk.Frame(interior, bg="#243447", height=3)
    barra_bg.pack(fill="x", padx=40, pady=(18, 0))
    barra = tk.Frame(barra_bg, bg="#10B981", height=3, width=0)
    barra.place(x=0, y=0, height=3)

    # Animacion de la barra
    def animar(step=0):
        if step <= 100:
            ancho_total = barra_bg.winfo_width() or (480 - 80)
            barra.place(x=0, y=0, height=3, width=int(ancho_total * step / 100))
            splash.after(20, animar, step + 2)

    splash.after(100, animar)
    return splash


def main():
    faltantes = verificar_dependencias()
    if faltantes:
        mostrar_error_dependencias(faltantes)
        sys.exit(1)

    # Importar despues de verificar dependencias
    from generador_planos.gui.app import App

    app = App()

    # Mostrar splash
    splash = mostrar_splash(app)
    app.withdraw()

    def cerrar_splash():
        splash.destroy()
        app.deiconify()

    app.after(2500, cerrar_splash)
    app.mainloop()


if __name__ == "__main__":
    main()
