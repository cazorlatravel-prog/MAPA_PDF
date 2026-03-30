"""
Paleta de colores y estilos TTK para la interfaz gráfica.
Diseño moderno, limpio y profesional.
"""

import tkinter as tk
from tkinter import ttk

# ── Paleta de colores ───────────────────────────────────────────────────
# Base: tema oscuro sofisticado con acentos esmeralda
COLOR_FONDO_APP  = "#0F1923"      # Fondo principal (azul noche profundo)
COLOR_PANEL      = "#162230"      # Paneles y secciones
COLOR_PANEL_ALT  = "#1B2B3D"      # Panel alternativo (hover/activo)
COLOR_ACENTO     = "#10B981"      # Esmeralda vibrante (acento principal)
COLOR_ACENTO2    = "#34D399"      # Esmeralda claro (hover)
COLOR_ACENTO3    = "#059669"      # Esmeralda oscuro (pressed)
COLOR_TEXTO      = "#E8ECF1"      # Texto principal (blanco suave)
COLOR_TEXTO_GRIS = "#8899AA"      # Texto secundario
COLOR_BORDE      = "#243447"      # Bordes y separadores
COLOR_ENTRY      = "#0D1620"      # Fondo campos de texto
COLOR_HOVER      = "#1E3348"      # Hover en elementos
COLOR_ERROR      = "#EF4444"      # Rojo error
COLOR_ADVERTENCIA = "#F59E0B"     # Amarillo advertencia
COLOR_EXITO      = "#10B981"      # Verde exito
COLOR_HEADER     = "#0B1219"      # Barra superior

# ── Fuentes ─────────────────────────────────────────────────────────────
FONT_TITULO = ("Segoe UI", 18, "bold")
FONT_SUBTITULO = ("Segoe UI", 12, "bold")
FONT_LABEL  = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_MONO   = ("Consolas", 9)
FONT_SECCION = ("Segoe UI", 9, "bold")
FONT_BOTON  = ("Segoe UI", 9)


def aplicar_estilos(root: tk.Tk):
    """Configura estilos TTK con la paleta moderna."""
    style = ttk.Style(root)
    style.theme_use("clam")

    # ── Combobox ──
    style.configure(
        "TCombobox",
        fieldbackground=COLOR_ENTRY,
        background=COLOR_BORDE,
        foreground=COLOR_TEXTO,
        selectbackground=COLOR_ACENTO,
        selectforeground="#FFFFFF",
        arrowcolor=COLOR_ACENTO,
        padding=(8, 4),
        borderwidth=0,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLOR_ENTRY)],
        foreground=[("readonly", COLOR_TEXTO)],
        bordercolor=[("focus", COLOR_ACENTO)],
    )

    # Popdown (lista desplegable) del Combobox
    root.option_add("*TCombobox*Listbox.background", COLOR_PANEL_ALT)
    root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACENTO)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
    root.option_add("*TCombobox*Listbox.font", FONT_SMALL)

    # ── Progressbar ──
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
        thickness=8,
        borderwidth=0,
    )

    # Progressbar con animación de color
    style.configure(
        "Green.Horizontal.TProgressbar",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
        thickness=8,
        borderwidth=0,
    )

    # ── Treeview ──
    style.configure(
        "Treeview",
        background=COLOR_PANEL,
        foreground=COLOR_TEXTO,
        fieldbackground=COLOR_PANEL,
        rowheight=28,
        borderwidth=0,
        font=FONT_SMALL,
    )
    style.configure(
        "Treeview.Heading",
        background=COLOR_HEADER,
        foreground=COLOR_ACENTO,
        font=FONT_BOLD,
        borderwidth=0,
        padding=(8, 4),
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_ACENTO)],
        foreground=[("selected", "#FFFFFF")],
    )

    # ── Scale ──
    style.configure(
        "TScale",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
        sliderthickness=14,
        borderwidth=0,
    )
    style.configure(
        "Horizontal.TScale",
        troughcolor=COLOR_BORDE,
        background=COLOR_ACENTO,
        sliderthickness=14,
    )

    # ── Notebook (pestanas centrales) ──
    style.configure(
        "TNotebook",
        background=COLOR_FONDO_APP,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_BORDE,
        foreground=COLOR_TEXTO_GRIS,
        font=FONT_SECCION,
        padding=[16, 6],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_PANEL), ("active", COLOR_HOVER)],
        foreground=[("selected", COLOR_ACENTO), ("active", COLOR_TEXTO)],
    )

    # ── Scrollbar moderna ──
    style.configure(
        "Vertical.TScrollbar",
        background=COLOR_BORDE,
        troughcolor=COLOR_PANEL,
        arrowcolor=COLOR_TEXTO_GRIS,
        borderwidth=0,
        width=10,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", COLOR_ACENTO3), ("pressed", COLOR_ACENTO)],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=COLOR_BORDE,
        troughcolor=COLOR_PANEL,
        arrowcolor=COLOR_TEXTO_GRIS,
        borderwidth=0,
        width=10,
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", COLOR_ACENTO3), ("pressed", COLOR_ACENTO)],
    )

    # ── Separator ──
    style.configure("TSeparator", background=COLOR_BORDE)

    # ── Checkbutton ──
    style.configure(
        "TCheckbutton",
        background=COLOR_PANEL,
        foreground=COLOR_TEXTO,
        font=FONT_SMALL,
    )

    # ── Radiobutton ──
    style.configure(
        "TRadiobutton",
        background=COLOR_PANEL,
        foreground=COLOR_TEXTO,
        font=FONT_SMALL,
    )

    # ── LabelFrame ──
    style.configure(
        "TLabelframe",
        background=COLOR_FONDO_APP,
        foreground=COLOR_ACENTO,
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=COLOR_FONDO_APP,
        foreground=COLOR_ACENTO,
        font=FONT_BOLD,
    )


def crear_frame_seccion(parent, titulo: str, colapsable: bool = False) -> tk.Frame:
    """Crea un frame con titulo estilizado y linea de acento sutil."""
    outer = tk.Frame(parent, bg=COLOR_PANEL)
    outer.pack(fill="x", padx=8, pady=(6, 0))

    # Cabecera de seccion
    header = tk.Frame(outer, bg=COLOR_PANEL)
    header.pack(fill="x", pady=(6, 0))

    tk.Label(
        header, text=titulo, font=FONT_SECCION,
        bg=COLOR_PANEL, fg=COLOR_ACENTO,
    ).pack(side="left", padx=(4, 0))

    # Linea de acento sutil
    sep_container = tk.Frame(outer, bg=COLOR_PANEL)
    sep_container.pack(fill="x", pady=(4, 6))

    # Gradiente visual: linea fina con color acento
    sep = tk.Frame(sep_container, bg=COLOR_ACENTO, height=1)
    sep.pack(fill="x", padx=4)

    # Contenido interior con padding
    inner = tk.Frame(outer, bg=COLOR_PANEL)
    inner.pack(fill="x", padx=8, pady=(0, 6))
    return inner


def crear_boton(parent, texto, comando, icono="", ancho=None,
                color_bg=None, color_fg=None, estilo="normal") -> tk.Button:
    """Crea un boton estilizado con hover effects."""
    if estilo == "primario":
        color_bg = color_bg or COLOR_ACENTO
        color_fg = color_fg or "#FFFFFF"
        hover_bg = COLOR_ACENTO2
        active_bg = COLOR_ACENTO3
    elif estilo == "peligro":
        color_bg = color_bg or COLOR_ERROR
        color_fg = color_fg or "#FFFFFF"
        hover_bg = "#DC2626"
        active_bg = "#B91C1C"
    else:
        color_bg = color_bg or COLOR_BORDE
        color_fg = color_fg or COLOR_TEXTO
        hover_bg = COLOR_HOVER
        active_bg = COLOR_ACENTO3

    label = f"{icono}  {texto}" if icono else texto

    kwargs = dict(
        text=label, command=comando, font=FONT_BOTON,
        bg=color_bg, fg=color_fg,
        activebackground=active_bg, activeforeground="#FFFFFF",
        relief="flat", cursor="hand2",
        pady=6, padx=10,
        bd=0, highlightthickness=0,
    )
    if ancho:
        kwargs["width"] = ancho

    btn = tk.Button(parent, **kwargs)

    # Hover effects
    def _on_enter(e):
        btn.configure(bg=hover_bg)

    def _on_leave(e):
        btn.configure(bg=color_bg)

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)

    return btn


def crear_entry(parent, textvariable=None, width=None, **kwargs) -> tk.Entry:
    """Crea un campo de entrada estilizado."""
    opts = dict(
        font=FONT_SMALL,
        bg=COLOR_ENTRY, fg=COLOR_TEXTO,
        insertbackground=COLOR_ACENTO,
        relief="flat",
        highlightthickness=1,
        highlightcolor=COLOR_ACENTO,
        highlightbackground=COLOR_BORDE,
        bd=0,
    )
    if textvariable:
        opts["textvariable"] = textvariable
    if width:
        opts["width"] = width
    opts.update(kwargs)
    entry = tk.Entry(parent, **opts)
    return entry


def crear_label(parent, text, tipo="normal", **kwargs) -> tk.Label:
    """Crea una etiqueta estilizada."""
    if tipo == "titulo":
        font = FONT_BOLD
        fg = COLOR_TEXTO
    elif tipo == "secundario":
        font = FONT_SMALL
        fg = COLOR_TEXTO_GRIS
    elif tipo == "acento":
        font = FONT_SMALL
        fg = COLOR_ACENTO
    else:
        font = FONT_SMALL
        fg = COLOR_TEXTO

    opts = dict(text=text, font=font, bg=COLOR_PANEL, fg=fg)
    opts.update(kwargs)
    return tk.Label(parent, **opts)
