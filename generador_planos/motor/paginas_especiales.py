"""Páginas especiales: portada, índice y mapa guía."""

import math
from datetime import date

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle

from .escala import FORMATOS, DPI_DEFAULT


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

    ax.add_patch(Rectangle((0, 0.55), 1, 0.45, facecolor=c_fondo))
    ax.add_patch(Rectangle((0.02, 0.02), 0.96, 0.96,
                            fill=False, edgecolor=c_fondo, linewidth=3.0))
    ax.add_patch(Rectangle((0.03, 0.03), 0.94, 0.94,
                            fill=False, edgecolor=c_acento, linewidth=0.8))

    ax.text(0.5, 0.80, titulo_proyecto.upper(), ha="center", va="center",
            fontsize=20, fontweight="bold", color=c_acento)
    if subtitulo:
        ax.text(0.5, 0.72, subtitulo.upper(), ha="center", va="center",
                fontsize=12, color="white")

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
    rh = 0.85 / max(mx + 1, 1)
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

    # Colores para las infraestructuras
    n = len(indices)
    cmap = plt.cm.get_cmap("tab20", max(n, 1))

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
            str(i + 1), xy=(cx, cy), fontsize=6, fontweight="bold",
            ha="center", va="center", color="white",
            bbox=dict(boxstyle="round,pad=0.2", facecolor=c_fondo,
                      edgecolor=c_acento, linewidth=0.5, alpha=0.85),
            zorder=10,
        )

    # Ejes con coordenadas UTM simplificadas
    ax_map.tick_params(labelsize=5, length=2)
    ax_map.ticklabel_format(useOffset=False, style="plain")

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
