"""
Paleta de colores y estilos TTK para la interfaz gráfica.
"""

import tkinter as tk
from tkinter import ttk

# ── Paleta de colores ───────────────────────────────────────────────────
COLOR_FONDO_APP  = "#1C2333"
COLOR_PANEL      = "#242D40"
COLOR_ACENTO     = "#007932"
COLOR_ACENTO2    = "#368f3f"
COLOR_TEXTO      = "#ECF0F1"
COLOR_TEXTO_GRIS = "#95A5A6"
COLOR_BORDE      = "#2C3E50"
COLOR_ENTRY      = "#1A2636"   # fondo campos de texto (más oscuro → más contraste)
COLOR_HOVER      = "#00793220"
COLOR_ERROR      = "#E74C3C"
COLOR_ADVERTENCIA = "#F39C12"
COLOR_EXITO      = "#368f3f"

# ── Fuentes ─────────────────────────────────────────────────────────────
FONT_TITULO = ("Noto Sans HK", 22, "bold")
FONT_LABEL  = ("Noto Sans HK", 10)
FONT_SMALL  = ("Noto Sans HK", 9)
FONT_BOLD   = ("Noto Sans HK", 10, "bold")
FONT_MONO   = ("Courier", 9)


def aplicar_estilos(root: tk.Tk):
    """Configura estilos TTK con la paleta forestal oscura."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(
        "TCombobox",
        fieldbackground=COLOR_ENTRY,
        background=COLOR_BORDE,
        foreground=COLOR_TEXTO,
        selectbackground=COLOR_ACENTO,
        selectforeground="#1A1A2E",
        arrowcolor=COLOR_ACENTO,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLOR_ENTRY)],
        foreground=[("readonly", COLOR_TEXTO)],
    )

    # Popdown (lista desplegable) del Combobox
    root.option_add("*TCombobox*Listbox.background", COLOR_ENTRY)
    root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACENTO)
    root.option_add("*TCombobox*Listbox.selectForeground", "#1A1A2E")

    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
        thickness=12,
    )

    style.configure(
        "Treeview",
        background="#172030",
        foreground=COLOR_TEXTO,
        fieldbackground="#172030",
        rowheight=22,
    )
    style.configure(
        "Treeview.Heading",
        background="#0D1117",
        foreground=COLOR_ACENTO,
        font=FONT_BOLD,
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_ACENTO)],
        foreground=[("selected", "#1A1A2E")],
    )

    style.configure(
        "TScale",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
    )

    # Notebook (pestañas centrales)
    style.configure(
        "TNotebook",
        background=COLOR_FONDO_APP,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_BORDE,
        foreground=COLOR_TEXTO,
        font=("Noto Sans HK", 9, "bold"),
        padding=[12, 4],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", "#1A2636"), ("active", "#34495E")],
        foreground=[("selected", COLOR_ACENTO), ("active", COLOR_TEXTO)],
    )

    # Scrollbar marrón visible
    style.configure(
        "Vertical.TScrollbar",
        background="#8B5E3C",
        troughcolor=COLOR_BORDE,
        arrowcolor=COLOR_TEXTO,
        borderwidth=0,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", "#A0724B"), ("pressed", "#6B4226")],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background="#8B5E3C",
        troughcolor=COLOR_BORDE,
        arrowcolor=COLOR_TEXTO,
        borderwidth=0,
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", "#A0724B"), ("pressed", "#6B4226")],
    )


def crear_frame_seccion(parent, titulo: str) -> tk.Frame:
    """Crea un frame con título y separador verde."""
    outer = tk.Frame(parent, bg=COLOR_PANEL)
    outer.pack(fill="x", padx=6, pady=(8, 0))

    tk.Label(
        outer, text=titulo, font=("Noto Sans HK", 9, "bold"),
        bg=COLOR_PANEL, fg=COLOR_ACENTO,
    ).pack(anchor="w", pady=(0, 2))

    sep = tk.Frame(outer, bg=COLOR_ACENTO, height=1)
    sep.pack(fill="x", pady=(0, 6))

    inner = tk.Frame(outer, bg=COLOR_PANEL)
    inner.pack(fill="x", padx=4)
    return inner


def crear_boton(parent, texto, comando, icono="", ancho=None,
                color_bg=None, color_fg=None) -> tk.Button:
    """Crea un botón estilizado."""
    if color_bg is None:
        color_bg = COLOR_BORDE
    if color_fg is None:
        color_fg = COLOR_TEXTO
    label = f"{icono} {texto}" if icono else texto
    kwargs = dict(
        text=label, command=comando, font=FONT_LABEL,
        bg=color_bg, fg=color_fg, activebackground=COLOR_ACENTO,
        activeforeground="#1A1A2E", relief="flat", cursor="hand2",
        pady=5,
    )
    if ancho:
        kwargs["width"] = ancho
    return tk.Button(parent, **kwargs)
