"""Páginas especiales: portada, índice y mapa guía."""

import math
import textwrap
from datetime import date

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

from .escala import FORMATOS, DPI_DEFAULT
from ._elementos_mapa import halo, formato_miles

_PT_MM = 25.4 / 72.0


def ajustar_texto(texto, ancho_mm, fontsize, max_lineas=3,
                  factor_ancho=0.62, fontsize_min=8.0):
    """Parte ``texto`` en líneas (textwrap) para que quepa en ``ancho_mm``.

    Si aun así salen más de ``max_lineas`` líneas, reduce la fuente
    progresivamente (hasta ``fontsize_min``). ``factor_ancho`` es el ancho
    medio de un carácter en ems (≈0.62 mayúsculas normales, ≈0.68 negrita).
    Devuelve ``(texto_con_saltos, fontsize)``.
    """
    texto = " ".join(str(texto or "").split())
    if not texto:
        return "", fontsize
    fsz = float(fontsize)
    while True:
        chars = max(8, int(ancho_mm / (fsz * _PT_MM * factor_ancho)))
        lineas = textwrap.wrap(texto, width=chars, break_long_words=True)
        if len(lineas) <= max_lineas or fsz <= fontsize_min:
            break
        fsz = max(fontsize_min, fsz * 0.9)
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = lineas[-1][:max(1, chars - 1)].rstrip() + "…"
    return "\n".join(lineas), fsz


def crear_portada(formato_key: str, titulo_proyecto: str,
                   subtitulo: str = "", datos_extra: dict = None,
                   cajetin: dict = None, plantilla: dict = None) -> plt.Figure:
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#007932")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
                      dpi=DPI_DEFAULT, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Banda superior dentro del marco (antes desbordaba hasta el borde)
    ax.add_patch(Rectangle((0.03, 0.55), 0.94, 0.42, facecolor=c_fondo,
                            edgecolor="none"))
    ax.add_patch(Rectangle((0.03, 0.548), 0.94, 0.006, facecolor=c_acento,
                            edgecolor="none"))
    ax.add_patch(Rectangle((0.02, 0.02), 0.96, 0.96,
                            fill=False, edgecolor=c_fondo, linewidth=3.0))
    ax.add_patch(Rectangle((0.03, 0.03), 0.94, 0.94,
                            fill=False, edgecolor=c_acento, linewidth=0.8))

    # Título y subtítulo ajustados al ancho de la página (textwrap)
    ancho_txt_mm = fmt[0] * 0.84
    titulo_txt, fsz_tit = ajustar_texto(
        str(titulo_proyecto or "").upper(), ancho_txt_mm, 20,
        max_lineas=3, factor_ancho=0.70, fontsize_min=11)
    ax.text(0.5, 0.745, titulo_txt, ha="center", va="bottom",
            fontsize=fsz_tit, fontweight="bold", color=c_acento,
            linespacing=1.15)
    if subtitulo:
        sub_txt, fsz_sub = ajustar_texto(
            str(subtitulo).upper(), ancho_txt_mm, 12,
            max_lineas=2, factor_ancho=0.64, fontsize_min=8)
        ax.text(0.5, 0.715, sub_txt, ha="center", va="top",
                fontsize=fsz_sub, color="white", linespacing=1.2)

    org = ""
    if cajetin and cajetin.get("organizacion"):
        org = cajetin["organizacion"].replace("\n", " - ")
    ax.text(0.5, 0.62, org, ha="center", va="center", fontsize=8,
            color="#95A5A6")

    if datos_extra:
        y = 0.45
        for k, v in datos_extra.items():
            ax.text(0.3, y, f"{k}:", ha="right", va="center", fontsize=9,
                    fontweight="bold", color="#2C3E50")
            ax.text(0.32, y, str(v), ha="left", va="center", fontsize=9,
                    color="#555")
            y -= 0.045

    ax.text(0.5, 0.08,
            f"Fecha de generación: {date.today().strftime('%d/%m/%Y')}",
            ha="center", va="center", fontsize=8, color="#999")

    if cajetin:
        parts = []
        if cajetin.get("autor"):
            parts.append(f"Autor: {cajetin['autor']}")
        if cajetin.get("num_proyecto"):
            parts.append(f"Proyecto: {cajetin['num_proyecto']}")
        if cajetin.get("revision"):
            parts.append(f"Revisión: {cajetin['revision']}")
        if parts:
            ax.text(0.5, 0.12, " | ".join(parts), ha="center", va="center",
                    fontsize=7, color="#777")

    return fig


def crear_indice(formato_key: str, items: list,
                  plantilla: dict = None) -> plt.Figure:
    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#007932")

    fmt = FORMATOS[formato_key]
    fig = plt.figure(figsize=(fmt[0] / 25.4, fmt[1] / 25.4),
                      dpi=DPI_DEFAULT, facecolor="white")
    ax = fig.add_axes([0.08, 0.05, 0.84, 0.88])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.97, "ÍNDICE DE PLANOS", ha="center", va="top",
            fontsize=14, fontweight="bold", color=c_fondo)
    ax.axhline(y=0.94, xmin=0.1, xmax=0.9, color=c_acento, linewidth=1.5)

    ax.text(0.08, 0.91, "N\u00ba", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)
    ax.text(0.55, 0.91, "Nombre", ha="center", va="center", fontsize=8,
            fontweight="bold", color=c_fondo)

    mx = min(len(items), 35)
    # Altura de fila acotada: una página de continuación con pocas
    # entradas no debe estirar las filas hasta ocupar toda la hoja
    rh = 0.85 / max(mx + 1, 12)
    for i, (num, nombre, extra) in enumerate(items[:mx]):
        y = 0.88 - i * rh
        if i % 2 == 0:
            ax.add_patch(Rectangle((0.02, y - rh + 0.002), 0.96, rh - 0.002,
                                    facecolor="#F0F4F8", edgecolor="none"))
        txt = nombre + (f" ({extra})" if extra else "")
        ax.text(0.08, y - rh / 2, str(num), ha="center", va="center",
                fontsize=7, color="#333")
        ax.text(0.15, y - rh / 2, txt, ha="left", va="center",
                fontsize=7, color="#333")

    if len(items) > mx:
        ax.text(0.5, 0.03, f"... y {len(items) - mx} planos más",
                ha="center", va="center", fontsize=7, color="#999",
                style="italic")

    return fig


def crear_mapa_guia(formato_key: str, gdf_infra, indices: list,
                     gdf_montes=None, transparencia_montes: float = 0.3,
                     plantilla: dict = None, cajetin: dict = None,
                     titulo: str = "MAPA GUÍA",
                     campo_nombre: str = "Nombre_Infra") -> plt.Figure:
    """Crea un mapa guía/índice cartográfico mostrando todas las
    infraestructuras numeradas sobre un fondo simplificado.

    A diferencia de ``crear_indice`` (tabla textual), este genera un
    plano cartográfico real con las geometrías dibujadas y etiquetadas
    con su número de orden.
    """
    from shapely.ops import unary_union

    pl = plantilla or {}
    c_fondo = pl.get("color_cabecera_fondo", "#1C2333")
    c_acento = pl.get("color_cabecera_acento", "#007932")

    fmt = FORMATOS[formato_key]
    fig_w = fmt[0] / 25.4
    fig_h = fmt[1] / 25.4
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI_DEFAULT,
                      facecolor="white")

    # Layout: cabecera + mapa + leyenda inferior
    gs = gridspec.GridSpec(3, 1, figure=fig,
                           height_ratios=[0.06, 0.78, 0.16],
                           hspace=0.02,
                           left=0.06, right=0.94, top=0.96, bottom=0.03)

    ax_header = fig.add_subplot(gs[0])
    ax_map = fig.add_subplot(gs[1])
    ax_legend = fig.add_subplot(gs[2])

    # ── Cabecera ──
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)
    ax_header.axis("off")
    ax_header.add_patch(Rectangle((0, 0), 1, 1, facecolor=c_fondo,
                                   edgecolor=c_acento, linewidth=1.0))
    ax_header.text(0.5, 0.5, titulo.upper(), ha="center", va="center",
                    fontsize=12, fontweight="bold", color=c_acento)

    # ── Mapa principal ──
    gdf_sel = gdf_infra.iloc[indices]
    geom_union = unary_union(gdf_sel.geometry)
    bounds = geom_union.bounds  # minx, miny, maxx, maxy
    if not bounds or any(b != b for b in bounds):  # NaN con indices vacíos
        plt.close(fig)
        raise ValueError(
            "No hay geometrías válidas para el mapa guía "
            "(selección vacía o geometrías nulas)")
    dx = bounds[2] - bounds[0]
    dy = bounds[3] - bounds[1]
    # Margen del 15 %
    margin = max(dx, dy) * 0.15
    if margin < 500:
        margin = 500
    xmin = bounds[0] - margin
    xmax = bounds[2] + margin
    ymin = bounds[1] - margin
    ymax = bounds[3] + margin

    ax_map.set_xlim(xmin, xmax)
    ax_map.set_ylim(ymin, ymax)
    ax_map.set_facecolor("#F5F5F0")
    ax_map.set_aspect("equal", adjustable="datalim")

    # Dibujar montes si existen
    if gdf_montes is not None and not gdf_montes.empty:
        try:
            montes_vis = gdf_montes.cx[xmin:xmax, ymin:ymax]
            if not montes_vis.empty:
                montes_vis.plot(ax=ax_map, facecolor="#C8E6C9",
                                edgecolor="#81C784", linewidth=0.3,
                                alpha=transparencia_montes)
        except Exception:
            pass

    # Colores para las infraestructuras (plt.cm.get_cmap fue eliminado
    # en matplotlib >= 3.9; matplotlib.colormaps existe desde 3.5)
    n = len(indices)
    try:
        import matplotlib
        cmap = matplotlib.colormaps["tab20"]
    except (AttributeError, KeyError):
        cmap = plt.cm.get_cmap("tab20")

    for i, idx in enumerate(indices):
        row = gdf_infra.iloc[idx]
        geom = row.geometry
        color = cmap(i % 20)
        gt = str(geom.geom_type).lower()
        if "polygon" in gt:
            ax_map.fill(*geom.exterior.xy, facecolor=color, edgecolor="black",
                         linewidth=0.8, alpha=0.6)
        elif "line" in gt:
            ax_map.plot(*geom.xy, color=color, linewidth=2.0, alpha=0.8)
        elif "point" in gt:
            ax_map.plot(geom.x, geom.y, marker="o", color=color,
                         markersize=8, markeredgecolor="black",
                         markeredgewidth=0.5)
        else:
            # MultiGeometry
            try:
                gdf_infra.iloc[[idx]].plot(ax=ax_map, color=color,
                                            linewidth=1.5, alpha=0.7)
            except Exception:
                pass

        # Número en el centroide
        cx, cy = geom.centroid.x, geom.centroid.y
        ax_map.annotate(
            str(i + 1), xy=(cx, cy), fontsize=7, fontweight="bold",
            ha="center", va="center", color=c_fondo,
            path_effects=halo(2.5), zorder=10,
        )

    # Ejes con coordenadas UTM (punto de miles: 4.196.000)
    ax_map.tick_params(labelsize=5, length=2)
    _fmt = FuncFormatter(lambda v, _p: formato_miles(v))
    ax_map.xaxis.set_major_formatter(_fmt)
    ax_map.yaxis.set_major_formatter(_fmt)
    ax_map.set_xlabel("")
    ax_map.set_ylabel("")

    # ── Leyenda inferior: lista numerada ──
    ax_legend.set_xlim(0, 1)
    ax_legend.set_ylim(0, 1)
    ax_legend.axis("off")

    # Calcular cuántas columnas caben
    max_cols = 3
    items_per_col = math.ceil(n / max_cols) if n > 0 else 1
    col_width = 1.0 / max_cols

    for i, idx in enumerate(indices):
        row = gdf_infra.iloc[idx]
        nombre = str(row.get(campo_nombre, f"Infra #{idx}"))
        if nombre == "nan":
            nombre = f"Infra #{idx}"
        if len(nombre) > 35:
            nombre = nombre[:34] + "\u2026"

        col = i // items_per_col
        row_in_col = i % items_per_col
        x = col * col_width + 0.02
        y = 0.92 - row_in_col * (0.85 / max(items_per_col, 1))

        color = cmap(i % 20)
        ax_legend.add_patch(Rectangle((x, y - 0.03), 0.02, 0.06,
                                       facecolor=color, edgecolor="none"))
        ax_legend.text(x + 0.03, y, f"{i + 1}. {nombre}",
                        fontsize=5, va="center", color="#333")

        if i + 1 >= items_per_col * max_cols:
            # No hay espacio para más
            if i + 1 < n:
                ax_legend.text(0.5, 0.02,
                                f"... y {n - i - 1} más",
                                ha="center", fontsize=5, color="#999",
                                style="italic")
            break

    # Marco exterior
    for ax in [ax_map]:
        for spine in ax.spines.values():
            spine.set_edgecolor(c_fondo)
            spine.set_linewidth(0.8)

    return fig
