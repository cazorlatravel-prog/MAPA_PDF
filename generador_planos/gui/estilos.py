"""
Paleta de colores y estilos TTK para la interfaz gráfica.

Dos temas disponibles:

- ``PALETA_CLARA`` (por defecto): aspecto de escritorio SIG tipo QGIS /
  ArcGIS Pro (fondo gris claro, paneles casi blancos, acento azul).
- ``PALETA_OSCURA``: el tema oscuro original (azul noche + esmeralda).

El tema se elige al importar el módulo a partir de
``ajustes.cargar_ajustes().get("tema", "claro")``; cambiarlo requiere
reiniciar la aplicación (los widgets Tk leen los colores al crearse).
Los nombres de las constantes ``COLOR_*`` se mantienen para que el resto
de módulos no tenga que cambiar.
"""

import sys
import tkinter as tk
from tkinter import ttk

from . import ajustes as _ajustes

# ── Paletas ─────────────────────────────────────────────────────────────

PALETA_CLARA = {
    "FONDO_APP": "#f0f0f0",     # Fondo de la ventana
    "PANEL": "#f7f7f7",         # Paneles y secciones
    "PANEL_ALT": "#ffffff",     # Menús / panel alternativo
    "ACENTO": "#2f7fd6",        # Azul primario (botones principales, selección)
    "ACENTO2": "#2a72c0",       # Hover del acento (algo más oscuro)
    "ACENTO3": "#2364ab",       # Pulsado
    "TEXTO": "#1e1e1e",         # Texto principal
    "TEXTO_GRIS": "#5a5a5a",    # Texto secundario
    "BORDE": "#c9c9c9",         # Bordes y separadores
    "ENTRY": "#ffffff",         # Campos de texto
    "HOVER": "#e3ecf7",         # Hover en elementos neutros
    "ERROR": "#c0392b",         # Peligro (PARAR)
    "ADVERTENCIA": "#b7791f",   # Aviso
    "EXITO": "#3f9a3f",         # Éxito (GENERAR)
    "HEADER": "#e8e8e8",        # Barra de herramientas / cabeceras
    "BOTON": "#e6e6e6",         # Botón neutro
    "BOTON_TEXTO": "#1e1e1e",
    "TITULO_SECCION": "#1f5fa8",
    "FILA_PAR": "#ffffff",      # Filas de la tabla de atributos
    "FILA_IMPAR": "#f3f6fa",
    "LOG_FONDO": "#ffffff",
    "LOG_TEXTO": "#1e1e1e",
    "LOG_OK": "#2e7d32",
    "LOG_ERROR": "#c0392b",
    "LOG_WARN": "#9a6700",
    "LOG_INFO": "#1f5fa8",
    "SELECCION_MAPA": "#ffe100",
    "MAPA_FONDO": "#ffffff",
    "FACTOR_HOVER": 0.92,       # hover = color * factor (más oscuro)
}

PALETA_OSCURA = {
    "FONDO_APP": "#0F1923",
    "PANEL": "#162230",
    "PANEL_ALT": "#1B2B3D",
    "ACENTO": "#10B981",
    "ACENTO2": "#34D399",
    "ACENTO3": "#059669",
    "TEXTO": "#E8ECF1",
    "TEXTO_GRIS": "#8899AA",
    "BORDE": "#243447",
    "ENTRY": "#0D1620",
    "HOVER": "#1E3348",
    "ERROR": "#EF4444",
    "ADVERTENCIA": "#F59E0B",
    "EXITO": "#10B981",
    "HEADER": "#0B1219",
    "BOTON": "#243447",
    "BOTON_TEXTO": "#E8ECF1",
    "TITULO_SECCION": "#10B981",
    "FILA_PAR": "#162230",
    "FILA_IMPAR": "#0F1923",
    "LOG_FONDO": "#0D1620",
    "LOG_TEXTO": "#6EE7B7",
    "LOG_OK": "#6EE7B7",
    "LOG_ERROR": "#FCA5A5",
    "LOG_WARN": "#FCD34D",
    "LOG_INFO": "#93C5FD",
    "SELECCION_MAPA": "#ffe100",
    "MAPA_FONDO": "#ffffff",
    "FACTOR_HOVER": 1.18,       # hover = color * factor (más claro)
}

TEMAS = {"claro": PALETA_CLARA, "oscuro": PALETA_OSCURA}


def _tema_configurado() -> str:
    try:
        tema = str(_ajustes.cargar_ajustes().get("tema", "claro")).lower()
    except Exception:
        tema = "claro"
    return tema if tema in TEMAS else "claro"


TEMA = _tema_configurado()
PALETA = TEMAS[TEMA]

# ── Constantes (mismos nombres de siempre) ──────────────────────────────
COLOR_FONDO_APP   = PALETA["FONDO_APP"]
COLOR_PANEL       = PALETA["PANEL"]
COLOR_PANEL_ALT   = PALETA["PANEL_ALT"]
COLOR_ACENTO      = PALETA["ACENTO"]
COLOR_ACENTO2     = PALETA["ACENTO2"]
COLOR_ACENTO3     = PALETA["ACENTO3"]
COLOR_TEXTO       = PALETA["TEXTO"]
COLOR_TEXTO_GRIS  = PALETA["TEXTO_GRIS"]
COLOR_BORDE       = PALETA["BORDE"]
COLOR_ENTRY       = PALETA["ENTRY"]
COLOR_HOVER       = PALETA["HOVER"]
COLOR_ERROR       = PALETA["ERROR"]
COLOR_ADVERTENCIA = PALETA["ADVERTENCIA"]
COLOR_EXITO       = PALETA["EXITO"]
COLOR_HEADER      = PALETA["HEADER"]
# Nuevas
COLOR_BOTON          = PALETA["BOTON"]
COLOR_BOTON_TEXTO    = PALETA["BOTON_TEXTO"]
COLOR_TITULO_SECCION = PALETA["TITULO_SECCION"]
COLOR_FILA_PAR       = PALETA["FILA_PAR"]
COLOR_FILA_IMPAR     = PALETA["FILA_IMPAR"]
COLOR_LOG_FONDO      = PALETA["LOG_FONDO"]
COLOR_LOG_TEXTO      = PALETA["LOG_TEXTO"]
COLOR_LOG_OK         = PALETA["LOG_OK"]
COLOR_LOG_ERROR      = PALETA["LOG_ERROR"]
COLOR_LOG_WARN       = PALETA["LOG_WARN"]
COLOR_LOG_INFO       = PALETA["LOG_INFO"]
COLOR_SELECCION_MAPA = PALETA["SELECCION_MAPA"]
COLOR_MAPA_FONDO     = PALETA["MAPA_FONDO"]
FACTOR_HOVER         = PALETA["FACTOR_HOVER"]

# ── Fuentes ─────────────────────────────────────────────────────────────
_FAMILIA = "Segoe UI"
_FAMILIA_MONO = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"

FONT_TITULO    = (_FAMILIA, 18, "bold")
FONT_SUBTITULO = (_FAMILIA, 12, "bold")
FONT_LABEL     = (_FAMILIA, 10)
FONT_SMALL     = (_FAMILIA, 9)
FONT_BOLD      = (_FAMILIA, 10, "bold")
FONT_MONO      = (_FAMILIA_MONO, 9)
FONT_SECCION   = (_FAMILIA, 9, "bold")
FONT_BOTON     = (_FAMILIA, 9)
FONT_MINI      = (_FAMILIA, 8)
FONT_ICONO     = (_FAMILIA, 11)


def aplicar_estilos(root: tk.Tk):
    """Configura estilos TTK con la paleta activa."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=COLOR_PANEL, foreground=COLOR_TEXTO,
                    bordercolor=COLOR_BORDE, lightcolor=COLOR_PANEL,
                    darkcolor=COLOR_BORDE, troughcolor=COLOR_FONDO_APP,
                    focuscolor=COLOR_ACENTO, selectbackground=COLOR_ACENTO,
                    selectforeground="#FFFFFF", font=FONT_SMALL)
    style.configure("TFrame", background=COLOR_PANEL)

    # ── Combobox ──
    style.configure(
        "TCombobox",
        fieldbackground=COLOR_ENTRY,
        background=COLOR_BOTON,
        foreground=COLOR_TEXTO,
        selectbackground=COLOR_ENTRY,
        selectforeground=COLOR_TEXTO,
        arrowcolor=COLOR_TEXTO_GRIS,
        bordercolor=COLOR_BORDE,
        lightcolor=COLOR_ENTRY,
        darkcolor=COLOR_ENTRY,
        padding=(6, 3),
        borderwidth=1,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLOR_ENTRY), ("disabled", COLOR_PANEL)],
        foreground=[("readonly", COLOR_TEXTO), ("disabled", COLOR_TEXTO_GRIS)],
        selectbackground=[("readonly", COLOR_ENTRY)],
        selectforeground=[("readonly", COLOR_TEXTO)],
        bordercolor=[("focus", COLOR_ACENTO), ("hover", COLOR_ACENTO2)],
        arrowcolor=[("hover", COLOR_ACENTO)],
        background=[("active", COLOR_HOVER), ("pressed", COLOR_HOVER)],
    )

    # Popdown (lista desplegable) del Combobox
    root.option_add("*TCombobox*Listbox.background", COLOR_ENTRY)
    root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACENTO)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
    root.option_add("*TCombobox*Listbox.font", FONT_SMALL)

    # ── Entry ttk ──
    style.configure("TEntry", fieldbackground=COLOR_ENTRY,
                    foreground=COLOR_TEXTO, bordercolor=COLOR_BORDE)

    # ── Progressbar ──
    for nombre in ("Horizontal.TProgressbar", "Green.Horizontal.TProgressbar"):
        style.configure(
            nombre,
            troughcolor=COLOR_FONDO_APP if TEMA == "claro" else COLOR_BORDE,
            background=COLOR_ACENTO if nombre.startswith("Horizontal")
            else COLOR_EXITO,
            bordercolor=COLOR_BORDE,
            lightcolor=COLOR_ACENTO,
            darkcolor=COLOR_ACENTO,
            thickness=8,
            borderwidth=1,
        )
    style.configure("Green.Horizontal.TProgressbar",
                    lightcolor=COLOR_EXITO, darkcolor=COLOR_EXITO)
    style.configure("Estado.Horizontal.TProgressbar",
                    troughcolor=COLOR_PANEL, background=COLOR_ACENTO,
                    bordercolor=COLOR_BORDE, lightcolor=COLOR_ACENTO,
                    darkcolor=COLOR_ACENTO, thickness=6, borderwidth=1)

    # ── Treeview (tabla de atributos) ──
    style.configure(
        "Treeview",
        background=COLOR_FILA_PAR,
        foreground=COLOR_TEXTO,
        fieldbackground=COLOR_FILA_PAR,
        rowheight=22,
        borderwidth=0,
        font=FONT_SMALL,
    )
    style.configure(
        "Treeview.Heading",
        background=COLOR_HEADER,
        foreground=COLOR_TEXTO,
        font=FONT_SECCION,
        borderwidth=1,
        bordercolor=COLOR_BORDE,
        lightcolor=COLOR_HEADER,
        darkcolor=COLOR_BORDE,
        relief="flat",
        padding=(6, 3),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLOR_HOVER)],
        foreground=[("active", COLOR_TEXTO)],
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_ACENTO)],
        foreground=[("selected", "#FFFFFF")],
    )

    # ── Scale ──
    for nombre in ("TScale", "Horizontal.TScale"):
        style.configure(
            nombre,
            troughcolor=COLOR_BORDE if TEMA == "claro" else COLOR_BORDE,
            background=COLOR_ACENTO,
            bordercolor=COLOR_BORDE,
            lightcolor=COLOR_ACENTO,
            darkcolor=COLOR_ACENTO2,
            sliderthickness=14,
            gripcount=0,
            borderwidth=0,
        )
    style.map("Horizontal.TScale",
              background=[("active", COLOR_ACENTO2), ("pressed", COLOR_ACENTO3)])

    # ── Notebook ──
    style.configure(
        "TNotebook",
        background=COLOR_FONDO_APP,
        bordercolor=COLOR_BORDE,
        lightcolor=COLOR_PANEL,
        darkcolor=COLOR_BORDE,
        tabmargins=(2, 4, 2, 0),
        borderwidth=1,
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_HEADER if TEMA == "claro" else COLOR_BORDE,
        foreground=COLOR_TEXTO_GRIS,
        bordercolor=COLOR_BORDE,
        lightcolor=COLOR_PANEL,
        darkcolor=COLOR_BORDE,
        font=FONT_SECCION,
        padding=(12, 4),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_PANEL), ("active", COLOR_HOVER)],
        foreground=[("selected", COLOR_TEXTO), ("active", COLOR_TEXTO)],
        expand=[("selected", (0, 2, 0, 0))],
    )
    # Notebook sin pestañas propias (la barra de pestañas la dibuja la app
    # en varias filas para que nunca se recorten)
    style.configure("Dock.TNotebook", background=COLOR_PANEL,
                    borderwidth=0, tabmargins=0)
    style.layout("Dock.TNotebook.Tab", [])

    # ── PanedWindow (separadores) ──
    style.configure("TPanedwindow", background=COLOR_FONDO_APP)
    style.configure("Sash", sashthickness=6, gripcount=0,
                    background=COLOR_FONDO_APP, bordercolor=COLOR_FONDO_APP,
                    lightcolor=COLOR_FONDO_APP, darkcolor=COLOR_FONDO_APP)

    # ── Scrollbars ──
    for nombre in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(
            nombre,
            background=COLOR_BOTON if TEMA == "claro" else COLOR_BORDE,
            troughcolor=COLOR_PANEL,
            bordercolor=COLOR_BORDE if TEMA == "claro" else COLOR_PANEL,
            lightcolor=COLOR_BOTON if TEMA == "claro" else COLOR_BORDE,
            darkcolor=COLOR_BORDE,
            arrowcolor=COLOR_TEXTO_GRIS,
            gripcount=0,
            borderwidth=1,
            width=12,
            arrowsize=12,
        )
        style.map(
            nombre,
            background=[("pressed", COLOR_ACENTO), ("active", COLOR_HOVER)],
            arrowcolor=[("active", COLOR_ACENTO)],
        )

    # ── Separator ──
    style.configure("TSeparator", background=COLOR_BORDE)

    # ── Check / Radio ttk ──
    for nombre in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            nombre,
            background=COLOR_PANEL,
            foreground=COLOR_TEXTO,
            indicatorbackground=COLOR_ENTRY,
            indicatorforeground=COLOR_ACENTO,
            font=FONT_SMALL,
        )
        style.map(nombre,
                  background=[("active", COLOR_PANEL)],
                  indicatorbackground=[("selected", COLOR_ENTRY)])
    style.configure("TOC.TCheckbutton", background=COLOR_ENTRY)
    style.map("TOC.TCheckbutton", background=[("active", COLOR_HOVER)])

    # ── LabelFrame ──
    style.configure(
        "TLabelframe",
        background=COLOR_PANEL,
        foreground=COLOR_TEXTO,
        bordercolor=COLOR_BORDE,
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=COLOR_PANEL,
        foreground=COLOR_TITULO_SECCION,
        font=FONT_BOLD,
    )

    # Menús Tk clásicos (menubuttons de Recientes, etc.)
    root.option_add("*Menu.background", COLOR_PANEL_ALT)
    root.option_add("*Menu.foreground", COLOR_TEXTO)
    root.option_add("*Menu.activeBackground", COLOR_ACENTO)
    root.option_add("*Menu.activeForeground", "#FFFFFF")
    root.option_add("*Menu.relief", "flat")


def crear_frame_seccion(parent, titulo: str, colapsable: bool = False) -> tk.Frame:
    """Crea un frame con título estilizado y línea separadora sutil."""
    outer = tk.Frame(parent, bg=COLOR_PANEL)
    outer.pack(fill="x", padx=8, pady=(4, 0))

    # Cabecera de sección
    header = tk.Frame(outer, bg=COLOR_PANEL)
    header.pack(fill="x", pady=(6, 0))

    tk.Label(
        header, text=titulo, font=FONT_SECCION,
        bg=COLOR_PANEL, fg=COLOR_TITULO_SECCION,
    ).pack(side="left", padx=(4, 0))

    # Línea separadora
    sep_container = tk.Frame(outer, bg=COLOR_PANEL)
    sep_container.pack(fill="x", pady=(4, 6))
    tk.Frame(sep_container, bg=COLOR_BORDE, height=1).pack(fill="x", padx=4)

    # Contenido interior con padding
    inner = tk.Frame(outer, bg=COLOR_PANEL)
    inner.pack(fill="x", padx=8, pady=(0, 6))
    return inner


def _ajustar_brillo(color_hex: str, factor: float) -> str:
    """Aclara (factor>1) u oscurece (factor<1) un color hexadecimal.

    Devuelve el mismo color si no se puede interpretar (p.ej. nombres).
    """
    try:
        c = color_hex.strip()
        if not c.startswith("#") or len(c) != 7:
            return color_hex
        r = int(c[1:3], 16)
        g = int(c[3:5], 16)
        b = int(c[5:7], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return color_hex


def crear_boton(parent, texto, comando, icono="", ancho=None,
                color_bg=None, color_fg=None, estilo="normal") -> tk.Button:
    """Crea un botón estilizado con efecto hover.

    estilo: "normal" (neutro), "primario" (azul), "exito" (verde),
    "peligro" (rojo).
    """
    if estilo == "primario":
        color_bg = color_bg or COLOR_ACENTO
        color_fg = color_fg or "#FFFFFF"
        active_bg = COLOR_ACENTO3
    elif estilo == "exito":
        color_bg = color_bg or COLOR_EXITO
        color_fg = color_fg or "#FFFFFF"
        active_bg = _ajustar_brillo(color_bg, 0.8)
    elif estilo == "peligro":
        color_bg = color_bg or COLOR_ERROR
        color_fg = color_fg or "#FFFFFF"
        active_bg = _ajustar_brillo(color_bg, 0.8)
    else:
        color_bg = color_bg or COLOR_BOTON
        color_fg = color_fg or COLOR_BOTON_TEXTO
        active_bg = COLOR_HOVER

    label = f"{icono}  {texto}" if icono else texto

    neutro = estilo not in ("primario", "exito", "peligro")
    kwargs = dict(
        text=label, command=comando, font=FONT_BOTON,
        bg=color_bg, fg=color_fg,
        activebackground=active_bg,
        activeforeground=COLOR_TEXTO if neutro else "#FFFFFF",
        disabledforeground=(COLOR_TEXTO_GRIS if neutro
                            else _ajustar_brillo(color_fg, 0.85)),
        relief="flat", cursor="hand2",
        pady=4, padx=10,
        bd=0,
        highlightthickness=1 if (neutro and TEMA == "claro") else 0,
        highlightbackground=COLOR_BORDE,
        highlightcolor=COLOR_ACENTO,
    )
    if ancho:
        kwargs["width"] = ancho

    btn = tk.Button(parent, **kwargs)

    # Hover: un toque más oscuro (tema claro) o más claro (tema oscuro).
    # El leave restaura siempre el color exacto.
    hover_calc = _ajustar_brillo(color_bg, FACTOR_HOVER)

    def _on_enter(e):
        try:
            if str(btn["state"]) == "disabled":
                return
        except Exception:
            return
        btn.configure(bg=hover_calc)

    # Color "apagado" para botones de color deshabilitados (si no, un
    # PARAR deshabilitado seguía pareciendo activo)
    btn._bg_normal = color_bg
    btn._bg_deshabilitado = (color_bg if neutro
                             else _mezclar(color_bg, COLOR_PANEL, 0.55))

    def _on_leave(e):
        try:
            deshab = str(btn["state"]) == "disabled"
            btn.configure(bg=btn._bg_deshabilitado if deshab else color_bg)
        except Exception:
            pass

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)

    return btn


def actualizar_color_estado(btn):
    """Ajusta el fondo de un botón de crear_boton a su estado actual."""
    try:
        deshab = str(btn["state"]) == "disabled"
        bg = btn._bg_deshabilitado if deshab else btn._bg_normal
        if btn.cget("bg") != bg:
            btn.configure(bg=bg)
    except Exception:
        pass


def _mezclar(c1: str, c2: str, t: float) -> str:
    """Mezcla lineal de dos colores #rrggbb (t=0 → c1, t=1 → c2)."""
    try:
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#%02X%02X%02X" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))
    except Exception:
        return c1


def crear_entry(parent, textvariable=None, width=None, **kwargs) -> tk.Entry:
    """Crea un campo de entrada estilizado."""
    opts = dict(
        font=FONT_SMALL,
        bg=COLOR_ENTRY, fg=COLOR_TEXTO,
        insertbackground=COLOR_TEXTO,
        disabledbackground=COLOR_PANEL,
        relief="flat",
        highlightthickness=1,
        highlightcolor=COLOR_ACENTO,
        highlightbackground=COLOR_BORDE,
        selectbackground=COLOR_ACENTO,
        selectforeground="#FFFFFF",
        bd=2,
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
        fg = COLOR_TITULO_SECCION
    else:
        font = FONT_SMALL
        fg = COLOR_TEXTO

    opts = dict(text=text, font=font, bg=COLOR_PANEL, fg=fg)
    opts.update(kwargs)
    return tk.Label(parent, **opts)


# ── Botón de barra de herramientas ──────────────────────────────────────

class BotonHerramienta(tk.Frame):
    """Botón plano de barra de herramientas (icono + texto corto).

    - ``conmutable=True``: se queda "hundido" mientras está activo
      (``set_activo``), como las herramientas Desplazar / Seleccionar de
      QGIS.
    - ``estilo``: "normal", "primario", "exito" o "peligro" (botones
      destacados con color de fondo).
    """

    def __init__(self, parent, icono, texto, comando, tooltip="",
                 conmutable=False, estilo="normal", bg=None):
        self._bg_barra = bg or COLOR_HEADER
        super().__init__(parent, bg=self._bg_barra, bd=0,
                         highlightthickness=1,
                         highlightbackground=self._bg_barra)
        self._comando = comando
        self._activo = False
        self._habilitado = True
        self._conmutable = conmutable
        self._estilo = estilo

        if estilo == "exito":
            self._c_bg, self._c_fg = COLOR_EXITO, "#FFFFFF"
        elif estilo == "peligro":
            self._c_bg, self._c_fg = COLOR_ERROR, "#FFFFFF"
        elif estilo == "primario":
            self._c_bg, self._c_fg = COLOR_ACENTO, "#FFFFFF"
        else:
            self._c_bg, self._c_fg = self._bg_barra, COLOR_TEXTO
        self._c_hover = (_ajustar_brillo(self._c_bg, FACTOR_HOVER)
                         if estilo != "normal" else COLOR_HOVER)
        destacado = estilo != "normal"

        self.configure(bg=self._c_bg)
        self._lbl_icono = tk.Label(
            self, text=icono, font=FONT_ICONO, bg=self._c_bg, fg=(
                self._c_fg if destacado else COLOR_TITULO_SECCION),
            bd=0, padx=0)
        self._lbl_icono.pack(side="left", padx=(5, 2) if texto else 5,
                             pady=1)
        self._lbl_texto = None
        if texto:
            self._lbl_texto = tk.Label(
                self, text=texto,
                font=(FONT_SECCION if destacado else FONT_BOTON),
                bg=self._c_bg, fg=self._c_fg, bd=0)
            self._lbl_texto.pack(side="left", padx=(0, 5), pady=1)

        for w in self._widgets():
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<ButtonRelease-1>", self._on_click, add="+")
            w.configure(cursor="hand2")
        if tooltip:
            for w in self._widgets():
                crear_tooltip(w, tooltip)

    def _widgets(self):
        ws = [self, self._lbl_icono]
        if self._lbl_texto is not None:
            ws.append(self._lbl_texto)
        return ws

    def _pintar(self, bg, borde=None):
        for w in self._widgets():
            w.configure(bg=bg)
        self.configure(highlightbackground=borde or bg)

    def _color_reposo(self):
        if self._activo:
            return COLOR_HOVER if self._estilo == "normal" else self._c_hover
        return self._c_bg

    def _on_enter(self, _e=None):
        if not self._habilitado:
            return
        borde = COLOR_ACENTO if self._estilo == "normal" else None
        self._pintar(self._c_hover, borde)

    def _on_leave(self, _e=None):
        borde = COLOR_ACENTO if self._activo else None
        self._pintar(self._color_reposo(), borde)

    def _on_click(self, e=None):
        if not self._habilitado:
            return
        # Ignorar si se suelta fuera del botón
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            if w not in self._widgets():
                return
        except Exception:
            pass
        if callable(self._comando):
            self._comando()

    def invoke(self):
        if self._habilitado and callable(self._comando):
            self._comando()

    def set_activo(self, activo: bool):
        self._activo = bool(activo)
        self._on_leave()

    @property
    def activo(self) -> bool:
        return self._activo

    def set_habilitado(self, habilitado: bool):
        habilitado = bool(habilitado)
        if habilitado == self._habilitado:
            return
        self._habilitado = habilitado
        if habilitado:
            fg = self._c_fg
            fg_ic = self._c_fg if self._estilo != "normal" else COLOR_TITULO_SECCION
            self._pintar(self._color_reposo())
        else:
            fg = fg_ic = (COLOR_TEXTO_GRIS if self._estilo == "normal"
                          or TEMA != "claro"
                          else _ajustar_brillo(self._c_fg, 0.85))
            if self._estilo != "normal":
                self._pintar(COLOR_BORDE)
        self._lbl_icono.configure(fg=fg_ic)
        if self._lbl_texto is not None:
            self._lbl_texto.configure(fg=fg)
        cursor = "hand2" if habilitado else "arrow"
        for w in self._widgets():
            w.configure(cursor=cursor)


def separador_vertical(parent, bg=None) -> tk.Frame:
    """Separador vertical fino para barras de herramientas."""
    f = tk.Frame(parent, bg=bg or COLOR_HEADER, width=9)
    tk.Frame(f, bg=COLOR_BORDE, width=1).pack(fill="y", expand=True,
                                               padx=4, pady=4)
    return f


# ── Tooltips ─────────────────────────────────────────────────────────────

class Tooltip:
    """Tooltip ligero para cualquier widget.

    Muestra un pequeño Toplevel tras ~500 ms sobre el widget y lo
    destruye al salir o al pulsar. Es seguro aunque el widget se destruya.
    """

    def __init__(self, widget, texto, retardo=500, wraplength=320):
        self.widget = widget
        self.texto = texto
        self.retardo = retardo
        self.wraplength = wraplength
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self._ocultar, add="+")
        widget.bind("<ButtonPress>", self._ocultar, add="+")
        widget.bind("<Destroy>", self._ocultar, add="+")

    def _programar(self, _evento=None):
        self._cancelar()
        try:
            self._after_id = self.widget.after(self.retardo, self._mostrar)
        except Exception:
            self._after_id = None

    def _cancelar(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _mostrar(self):
        self._after_id = None
        if self._tip is not None:
            return
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return
        try:
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f"+{x}+{y}")
            self._tip.configure(bg=COLOR_BORDE)
            tk.Label(
                self._tip, text=self.texto, justify="left",
                bg="#ffffe1" if TEMA == "claro" else COLOR_PANEL_ALT,
                fg=COLOR_TEXTO,
                font=FONT_SMALL, wraplength=self.wraplength,
                relief="flat", bd=0, padx=8, pady=5,
            ).pack(padx=1, pady=1)
        except Exception:
            self._tip = None

    def _ocultar(self, _evento=None):
        self._cancelar()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def crear_tooltip(widget, texto, **kwargs) -> Tooltip:
    """Atajo para asociar un tooltip a un widget."""
    return Tooltip(widget, texto, **kwargs)
