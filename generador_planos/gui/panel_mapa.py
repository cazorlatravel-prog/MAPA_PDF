"""
Lienzo de mapa interactivo (estilo QGIS / ArcGIS Pro).

``PanelMapa`` dibuja en una figura matplotlib embebida en Tk las capas
cargadas en el motor (montes, capas extra, infraestructuras y, si se
activa, el fondo cartográfico) y ofrece:

- zoom con la rueda centrado en el cursor, desplazamiento arrastrando
  (botón izquierdo en modo *Desplazar*, botón central siempre);
- selección de entidades de infraestructura por clic (Ctrl+clic añade)
  o por rectángulo en modo *Seleccionar*, con halo amarillo;
- coordenadas y escala aproximada en la barra de estado;
- fondo cartográfico descargado en un hilo para la vista actual.

Cada capa se convierte UNA vez en colecciones de matplotlib
(``LineCollection`` / ``PathCollection``) y se guardan los manejadores:
desplazar o hacer zoom solo cambia los límites del eje y llama a
``draw_idle``. Las capas de más de 3 000 entidades se simplifican para
la visualización (tolerancia = extensión / 2500).

``TablaContenidos`` es la lista de capas (TOC) con casilla de
visibilidad, muestra de color, nombre y nº de entidades.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk

import numpy as np
import shapely
from shapely.geometry import box as _box, Point as _Point

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.path import Path as MplPath
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgba, to_rgba_array

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, COLOR_HOVER, COLOR_SELECCION_MAPA, COLOR_MAPA_FONDO,
    FONT_SMALL, FONT_MINI, FONT_SECCION,
    crear_tooltip,
)

# Estilo fijo de visualización (independiente de la maquetación del PDF)
_MONTES_FILL = "#cfe8c9"
_MONTES_EDGE = "#6aa36a"
_LW_LINEA_INFRA = 1.6
_LW_BORDE_INFRA = 1.0
_ALPHA_ATENUADO = 0.25          # entidades fuera del filtro
_UMBRAL_SIMPLIFICAR = 3000      # entidades
_PX_TOLERANCIA_CLIC = 8
_DPI_PANTALLA = 96
_M_POR_PULGADA = 0.0254
_FACTOR_ZOOM = 1.25

CRS_TEXTO = "ETRS89 / UTM 30N (EPSG:25830)"


# ── Conversión shapely → matplotlib ─────────────────────────────────────

_MULTI = (4, 5, 6, 7)  # MultiPoint, MultiLineString, MultiPolygon, GeometryCollection


def _descomponer(geoms):
    """Separa un array de geometrías en partes simples.

    Devuelve (partes, propietario) donde ``propietario[i]`` es la posición
    de la geometría original a la que pertenece ``partes[i]``.
    """
    geoms = np.asarray(geoms, dtype=object)
    if len(geoms) == 0:
        return np.array([], dtype=object), np.array([], dtype=np.int64)
    validas = ~(shapely.is_missing(geoms) | shapely.is_empty(geoms))
    owners = np.flatnonzero(validas)
    partes = geoms[owners]
    for _ in range(4):  # colecciones anidadas: pocas iteraciones bastan
        tipos = shapely.get_type_id(partes)
        if not np.isin(tipos, _MULTI).any():
            break
        partes, idx = shapely.get_parts(partes, return_index=True)
        owners = owners[idx]
    no_vacias = ~shapely.is_empty(partes)
    return partes[no_vacias], owners[no_vacias]


def construir_geometria(geoms):
    """Convierte geometrías shapely en estructuras para colecciones.

    Devuelve un dict con:
    - "lineas": (lista de arrays Nx2, propietarios)
    - "poligonos": (lista de matplotlib Path, propietarios)
    - "puntos": (array Nx2, propietarios)
    """
    partes, owners = _descomponer(geoms)
    res = {
        "lineas": ([], np.array([], dtype=np.int64)),
        "poligonos": ([], np.array([], dtype=np.int64)),
        "puntos": (np.empty((0, 2)), np.array([], dtype=np.int64)),
    }
    if len(partes) == 0:
        return res
    tipos = shapely.get_type_id(partes)

    # Puntos
    m = tipos == 0
    if m.any():
        coords = shapely.get_coordinates(partes[m])
        res["puntos"] = (coords, owners[m])

    # Líneas (LineString / LinearRing)
    m = (tipos == 1) | (tipos == 2)
    if m.any():
        lin = partes[m]
        coords, cidx = shapely.get_coordinates(lin, return_index=True)
        cortes = np.flatnonzero(np.diff(cidx)) + 1
        segs = np.split(coords, cortes)
        # cidx es creciente: el propietario de cada tramo es el de su 1er vértice
        inicio = np.concatenate([[0], cortes])
        res["lineas"] = (segs, owners[m][cidx[inicio]])

    # Polígonos (con huecos) → Path compuesto por anillos
    m = tipos == 3
    if m.any():
        pol = partes[m]
        pol_owners = owners[m]
        anillos, ridx = shapely.get_rings(pol, return_index=True)
        coords, cidx = shapely.get_coordinates(anillos, return_index=True)
        n_an = len(anillos)
        n_v = np.bincount(cidx, minlength=n_an)
        off_v = np.concatenate([[0], np.cumsum(n_v)])
        codigos = np.full(len(coords), MplPath.LINETO, dtype=MplPath.code_type)
        con_v = n_v > 0
        codigos[off_v[:-1][con_v]] = MplPath.MOVETO
        codigos[off_v[1:][con_v] - 1] = MplPath.CLOSEPOLY
        n_r = np.bincount(ridx, minlength=len(pol))
        off_r = np.concatenate([[0], np.cumsum(n_r)])
        paths = []
        prop = []
        for p in range(len(pol)):
            a, b = off_v[off_r[p]], off_v[off_r[p + 1]]
            if b - a < 3:
                continue
            paths.append(MplPath(coords[a:b], codigos[a:b]))
            prop.append(pol_owners[p])
        res["poligonos"] = (paths, np.asarray(prop, dtype=np.int64))
    return res


def _simplificar_si_grande(geoms):
    """Simplifica para pantalla las capas grandes (tol = extensión/2500)."""
    geoms = np.asarray(geoms, dtype=object)
    if len(geoms) <= _UMBRAL_SIMPLIFICAR:
        return geoms
    try:
        b = shapely.total_bounds(geoms)
        ext = max(b[2] - b[0], b[3] - b[1])
        if not np.isfinite(ext) or ext <= 0:
            return geoms
        return shapely.simplify(geoms, ext / 2500.0, preserve_topology=True)
    except Exception:
        return geoms


def _claves_categoria(serie):
    """Claves de categoría como texto, igual que el motor (nulos incluidos)."""
    try:
        from ..motor.generador import _clave_categoria
        return np.asarray(_clave_categoria(serie).values, dtype=object)
    except Exception:
        return np.asarray(serie.astype(str).values, dtype=object)


def _fmt_miles(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


# ── Lienzo ──────────────────────────────────────────────────────────────

class PanelMapa:
    """Lienzo de mapa interactivo basado en matplotlib + Tk."""

    MODO_DESPLAZAR = "desplazar"
    MODO_SELECCIONAR = "seleccionar"

    def __init__(self, parent, motor, callback_seleccion, callback_log,
                 callback_coords=None, callback_estado=None,
                 callback_ocupado=None):
        self.motor = motor
        self.callback_seleccion = callback_seleccion
        self.callback_log = callback_log
        self.callback_coords = callback_coords
        self.callback_estado = callback_estado
        self.callback_ocupado = callback_ocupado
        # Devuelve la clave de proveedor de fondo (la app lo sustituye)
        self.obtener_proveedor = lambda: "IGN Base"
        # Se invoca cuando cambia la lista/visibilidad de capas (TOC)
        self.callback_capas = None

        self.frame = tk.Frame(parent, bg=COLOR_BORDE, bd=0,
                              highlightthickness=0)

        self.fig = Figure(figsize=(6, 4), dpi=_DPI_PANTALLA,
                          facecolor=COLOR_MAPA_FONDO)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_facecolor(COLOR_MAPA_FONDO)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for sp in self.ax.spines.values():
            sp.set_visible(False)
        self.ax.set_autoscale_on(False)
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(bg=COLOR_MAPA_FONDO, highlightthickness=0, bd=0,
                              cursor="fleur")
        self.widget.pack(fill="both", expand=True, padx=1, pady=1)

        self._txt_vacio = self.ax.text(
            0.5, 0.5,
            "Sin capas cargadas\n\nAbre un SHP o una GDB de infraestructuras "
            "desde la barra de herramientas",
            transform=self.ax.transAxes, ha="center", va="center",
            color="#8a8a8a", fontsize=10, linespacing=1.4)

        # Estado de la vista: centro (x, y) y metros por píxel
        self._vista = None
        self._vista_token = 0
        self._modo = self.MODO_DESPLAZAR

        # Visibilidad por capa (clave → bool)
        self._visible = {"infra": True, "montes": True, "fondo": False}
        # Artistas por clave
        self._artistas = {}
        self._halo = []
        self._infra_cols = []        # [(colección, propietarios, tipo)]
        self._infra_base = None      # (edge RGBA, face RGBA) por entidad
        self._infra_n = 0
        self._filtro = None          # set de índices visibles o None
        self._seleccion = []
        self._color_infra = "#E74C3C"
        self._gdf_infra_id = None

        # Interacción
        self._arrastre = None        # dict con estado del pan/rectángulo
        self._rect = None
        self._ultimo_coords = 0.0

        # Fondo cartográfico
        self.var_fondo = tk.BooleanVar(value=False)
        self.var_fondo.trace_add("write", lambda *_: self._on_var_fondo())
        self._fondo_hilo = None
        self._fondo_pendiente = False
        self._fondo_after = None
        self._fondo_artistas = []

        c = self.canvas
        c.mpl_connect("scroll_event", self._on_scroll)
        c.mpl_connect("button_press_event", self._on_press)
        c.mpl_connect("button_release_event", self._on_release)
        c.mpl_connect("motion_notify_event", self._on_motion)
        c.mpl_connect("resize_event", self._on_resize)
        c.mpl_connect("figure_leave_event", self._on_leave)

    # ── API pública ─────────────────────────────────────────────────────

    def pack(self, **kw):
        self.frame.pack(**kw)

    def grid(self, **kw):
        self.frame.grid(**kw)

    @property
    def modo(self) -> str:
        return self._modo

    def set_modo(self, modo: str):
        if modo not in (self.MODO_DESPLAZAR, self.MODO_SELECCIONAR):
            return
        self._modo = modo
        try:
            self.widget.configure(
                cursor="fleur" if modo == self.MODO_DESPLAZAR else "crosshair")
        except Exception:
            pass

    def set_color_infra(self, color: str):
        if color and color != self._color_infra:
            self._color_infra = color
            if self._infra_cols:
                self._recolorear_infra()

    def hay_datos(self) -> bool:
        return self._extension_datos() is not None

    def actualizar_capas(self):
        """Redibuja todas las capas desde el estado del motor."""
        t0 = time.perf_counter()
        self._quitar_artistas()
        hay = False
        try:
            hay |= self._dibujar_montes()
        except Exception as e:
            self._log(f"Mapa: no se pudo dibujar montes: {e}", "warn")
        try:
            hay |= self._dibujar_extra()
        except Exception as e:
            self._log(f"Mapa: no se pudieron dibujar capas extra: {e}", "warn")
        try:
            hay |= self._dibujar_infra()
        except Exception as e:
            self._log(f"Mapa: no se pudo dibujar infraestructuras: {e}", "warn")
        self._txt_vacio.set_visible(not hay)
        # Mantener la selección si sigue siendo válida
        n = self._infra_n
        self._seleccion = [i for i in self._seleccion if 0 <= i < n]
        self._dibujar_halo()
        if self._vista is None and hay:
            self.zoom_capa()
        else:
            self._aplicar_vista()
        self._notificar_capas()
        self._t_construccion = time.perf_counter() - t0

    def set_filtro(self, indices):
        """Atenúa (alpha 0.25) las entidades fuera de ``indices``.

        ``None`` o todos los índices = sin filtro.
        """
        if indices is None or (self._infra_n and len(indices) >= self._infra_n):
            self._filtro = None
        else:
            self._filtro = set(int(i) for i in indices)
        if self._infra_cols:
            self._recolorear_infra()
            self.canvas.draw_idle()

    def resaltar(self, indices):
        """Dibuja el halo de selección (amarillo) sobre ``indices``."""
        n = self._infra_n
        self._seleccion = [int(i) for i in (indices or []) if 0 <= int(i) < n]
        self._dibujar_halo()
        self.canvas.draw_idle()

    @property
    def seleccion(self) -> list:
        return list(self._seleccion)

    def zoom_a_bounds(self, minx, miny, maxx, maxy, margen=0.1):
        if not all(np.isfinite([minx, miny, maxx, maxy])):
            return
        w = max(maxx - minx, 0.0)
        h = max(maxy - miny, 0.0)
        if w < 1 and h < 1:
            w = h = 200.0   # entidad puntual: ventana de 200 m
        w *= (1 + 2 * margen)
        h *= (1 + 2 * margen)
        wpx, hpx = self._tam_px()
        mpp = max(w / wpx, h / hpx, 0.01)
        self._vista = ((minx + maxx) / 2, (miny + maxy) / 2, mpp)
        self._aplicar_vista()

    def zoom_capa(self):
        ext = self._extension_datos()
        if ext is not None:
            self.zoom_a_bounds(*ext)

    def zoom_seleccion(self, indices=None):
        if indices is None:
            indices = self._seleccion
        gdf = self.motor.gdf_infra
        if gdf is None or not indices:
            return
        idx = [i for i in indices if 0 <= i < len(gdf)]
        if not idx:
            return
        b = shapely.total_bounds(gdf.geometry.values[idx])
        self.zoom_a_bounds(*b, margen=0.25)

    def zoom_in(self):
        self._zoom_factor(1 / _FACTOR_ZOOM)

    def zoom_out(self):
        self._zoom_factor(_FACTOR_ZOOM)

    def capas_toc(self) -> list:
        """Lista de capas para la tabla de contenidos (de arriba abajo)."""
        capas = []
        gdf = self.motor.gdf_infra
        if gdf is not None:
            capas.append({"clave": "infra", "nombre": "Infraestructuras",
                          "color": self._color_toc_infra(), "n": len(gdf),
                          "visible": self._visible.get("infra", True)})
        for capa in getattr(self.motor.gestor_capas, "capas", []):
            clave = ("extra", id(capa))
            try:
                simb = self.motor.gestor_simbologia.obtener_simbologia_capa(
                    capa.tipo)
                color = simb.color
            except Exception:
                color = "#888888"
            capas.append({"clave": clave, "nombre": capa.nombre,
                          "color": color, "n": len(capa.gdf),
                          "visible": self._visible.get(clave, True)})
        if self.motor.gdf_montes is not None:
            capas.append({"clave": "montes", "nombre": "Montes",
                          "color": _MONTES_FILL,
                          "n": len(self.motor.gdf_montes),
                          "visible": self._visible.get("montes", True)})
        capas.append({"clave": "fondo", "nombre": "Fondo cartográfico",
                      "color": None, "n": None,
                      "visible": bool(self.var_fondo.get())})
        return capas

    def set_visible_capa(self, clave, visible: bool):
        if clave == "fondo":
            self.var_fondo.set(bool(visible))
            return
        self._visible[clave] = bool(visible)
        for art in self._artistas.get(clave, []):
            art.set_visible(bool(visible))
        if clave == "infra":
            for art in self._halo:
                art.set_visible(bool(visible))
        self.canvas.draw_idle()

    def set_fondo(self, activo: bool):
        self.var_fondo.set(bool(activo))

    @property
    def fondo_activo(self) -> bool:
        return bool(self.var_fondo.get())

    def tiempo_redibujado(self, repeticiones=5) -> float:
        """Tiempo medio (s) de un redibujado completo (diagnóstico)."""
        t0 = time.perf_counter()
        for _ in range(repeticiones):
            self.canvas.draw()
        return (time.perf_counter() - t0) / repeticiones

    # ── Construcción de capas ───────────────────────────────────────────

    def _quitar_artistas(self):
        for arts in self._artistas.values():
            for a in arts:
                try:
                    a.remove()
                except Exception:
                    pass
        self._artistas = {}
        self._infra_cols = []
        self._infra_base = None

    def _registrar(self, clave, artista):
        artista.set_visible(self._visible.get(clave, True))
        self.ax.add_collection(artista, autolim=False)
        self._artistas.setdefault(clave, []).append(artista)

    def _dibujar_montes(self) -> bool:
        gdf = self.motor.gdf_montes
        if gdf is None or len(gdf) == 0:
            return False
        geoms = _simplificar_si_grande(gdf.geometry.values)
        g = construir_geometria(geoms)
        paths, owners = g["poligonos"]
        n = len(gdf)
        face = np.tile(to_rgba(_MONTES_FILL, 0.6), (n, 1))
        edge = np.tile(to_rgba(_MONTES_EDGE, 1.0), (n, 1))
        campo = (self.motor.config_infra or {}).get("campo_categoria_montes")
        if campo and campo in gdf.columns:
            gs = self.motor.gestor_simbologia
            vals = _claves_categoria(gdf[campo])
            for v in set(vals):
                simb = gs.obtener_simbologia_monte(campo, v)
                try:
                    face[vals == v] = to_rgba(simb.facecolor, 0.45)
                    edge[vals == v] = to_rgba(simb.color, 1.0)
                except ValueError:
                    pass
        if paths:
            col = PathCollection(paths, facecolors=face[owners],
                                 edgecolors=edge[owners], linewidths=0.6,
                                 zorder=1)
            self._registrar("montes", col)
        lin, lown = g["lineas"]
        if lin:
            self._registrar("montes", LineCollection(
                lin, colors=edge[lown], linewidths=0.6, zorder=1))
        return True

    def _dibujar_extra(self) -> bool:
        hay = False
        gs = self.motor.gestor_simbologia
        for capa in getattr(self.motor.gestor_capas, "capas", []):
            gdf = capa.gdf
            if gdf is None or len(gdf) == 0:
                continue
            clave = ("extra", id(capa))
            simb = gs.obtener_simbologia_capa(capa.tipo)
            geoms = _simplificar_si_grande(gdf.geometry.values)
            g = construir_geometria(geoms)
            color = simb.color
            try:
                to_rgba(color)
            except ValueError:
                color = "#888888"
            try:
                face = to_rgba(simb.facecolor)
            except ValueError:
                face = to_rgba(color, 0.25)
            ls = simb.linestyle or "-"
            lw = max(float(simb.linewidth or 1.0), 0.8)
            paths, _ = g["poligonos"]
            if paths:
                self._registrar(clave, PathCollection(
                    paths, facecolors=[face], edgecolors=[color],
                    linewidths=lw, linestyles=ls, zorder=2))
            lin, _ = g["lineas"]
            if lin:
                self._registrar(clave, LineCollection(
                    lin, colors=[color], linewidths=lw, linestyles=ls,
                    zorder=2))
            pts, _ = g["puntos"]
            if len(pts):
                sc = self.ax.scatter(
                    pts[:, 0], pts[:, 1], s=28, marker=simb.marker or "o",
                    c=[color], edgecolors="white", linewidths=0.5, zorder=2)
                sc.remove()
                self._registrar(clave, sc)
            hay = True
        return hay

    def _colores_base_infra(self, gdf):
        """RGBA de borde y relleno por entidad según la simbología."""
        n = len(gdf)
        ci = self.motor.config_infra or {}
        alpha_relleno = float(ci.get("alpha", 0.35) or 0.35)
        alpha_relleno = min(max(alpha_relleno, 0.15), 0.9)
        colores = np.tile(to_rgba(self._color_infra), (n, 1))
        campo = ci.get("campo_categoria")
        if campo:
            campo_real = campo
            mapeo = getattr(self.motor, "_campo_mapeo", None) or {}
            if campo in mapeo:
                campo_real = mapeo[campo]
            if campo_real in gdf.columns:
                gs = self.motor.gestor_simbologia
                vals = _claves_categoria(gdf[campo_real])
                for v in set(vals):
                    try:
                        colores[vals == v] = to_rgba(
                            gs.obtener_simbologia_infra(campo, v).color)
                    except ValueError:
                        pass
        edge = colores.copy()
        face = colores.copy()
        face[:, 3] = alpha_relleno
        return edge, face

    def _dibujar_infra(self) -> bool:
        gdf = self.motor.gdf_infra
        if gdf is None or len(gdf) == 0:
            self._infra_n = 0
            return False
        if id(gdf) != self._gdf_infra_id:
            self._gdf_infra_id = id(gdf)
            self._seleccion = []
            self._filtro = None
        self._infra_n = len(gdf)
        geoms = _simplificar_si_grande(gdf.geometry.values)
        g = construir_geometria(geoms)
        self._infra_base = self._colores_base_infra(gdf)
        ci = self.motor.config_infra or {}
        ls = ci.get("linestyle") or "-"
        paths, pown = g["poligonos"]
        if paths:
            col = PathCollection(paths, linewidths=_LW_BORDE_INFRA, zorder=3)
            self._registrar("infra", col)
            self._infra_cols.append((col, pown, "poligono"))
        lin, lown = g["lineas"]
        if lin:
            col = LineCollection(lin, linewidths=_LW_LINEA_INFRA,
                                 linestyles=ls, zorder=4,
                                 capstyle="round", joinstyle="round")
            self._registrar("infra", col)
            self._infra_cols.append((col, lown, "linea"))
        pts, ptown = g["puntos"]
        if len(pts):
            sc = self.ax.scatter(pts[:, 0], pts[:, 1], s=40,
                                 marker=ci.get("marker") or "o",
                                 linewidths=0.8, zorder=5)
            sc.remove()
            self._registrar("infra", sc)
            self._infra_cols.append((sc, ptown, "punto"))
        self._recolorear_infra()
        return True

    def _recolorear_infra(self):
        gdf = self.motor.gdf_infra
        if gdf is None or not self._infra_cols:
            return
        if id(gdf) != self._gdf_infra_id:
            # Capa sustituida y aún no redibujada: actualizar_capas()
            # reconstruirá las colecciones (los índices viejos no valen)
            return
        if self._infra_base is None or len(self._infra_base[0]) != len(gdf):
            self._infra_base = self._colores_base_infra(gdf)
        edge, face = self._infra_base
        edge = edge.copy()
        face = face.copy()
        if self._filtro is not None:
            fuera = np.ones(len(gdf), dtype=bool)
            dentro = [i for i in self._filtro if 0 <= i < len(gdf)]
            fuera[dentro] = False
            edge[fuera, 3] *= _ALPHA_ATENUADO
            face[fuera, 3] *= _ALPHA_ATENUADO
        for col, owners, tipo in self._infra_cols:
            if tipo == "linea":
                col.set_color(edge[owners])
            elif tipo == "poligono":
                col.set_facecolor(face[owners])
                col.set_edgecolor(edge[owners])
            else:
                fc = edge[owners].copy()
                ec = np.tile(to_rgba("white"), (len(owners), 1))
                ec[:, 3] = fc[:, 3]
                col.set_facecolor(fc)
                col.set_edgecolor(ec)

    def _dibujar_halo(self):
        for a in self._halo:
            try:
                a.remove()
            except Exception:
                pass
        self._halo = []
        gdf = self.motor.gdf_infra
        if gdf is None or not self._seleccion:
            return
        sel = [i for i in self._seleccion if i < len(gdf)]
        if not sel:
            return
        geoms = gdf.geometry.values[sel]
        g = construir_geometria(geoms)
        visible = self._visible.get("infra", True)
        amarillo = COLOR_SELECCION_MAPA
        paths, _ = g["poligonos"]
        if paths:
            col = PathCollection(paths, facecolors=[to_rgba(amarillo, 0.35)],
                                 edgecolors=[amarillo], linewidths=3,
                                 zorder=10)
            self.ax.add_collection(col, autolim=False)
            self._halo.append(col)
        lin, _ = g["lineas"]
        if lin:
            col = LineCollection(lin, colors=[amarillo], linewidths=3,
                                 zorder=10, capstyle="round",
                                 joinstyle="round")
            self.ax.add_collection(col, autolim=False)
            self._halo.append(col)
        pts, _ = g["puntos"]
        if len(pts):
            sc = self.ax.scatter(pts[:, 0], pts[:, 1], s=140,
                                 facecolors="none", edgecolors=amarillo,
                                 linewidths=3, zorder=10)
            self._halo.append(sc)
        for a in self._halo:
            a.set_visible(visible)

    def _color_toc_infra(self):
        ci = self.motor.config_infra or {}
        if ci.get("campo_categoria") and self._infra_base is not None \
                and len(self._infra_base[0]):
            r, g, b, _ = self._infra_base[0][0]
            return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
        return self._color_infra

    def _notificar_capas(self):
        if callable(self.callback_capas):
            try:
                self.callback_capas()
            except Exception:
                pass

    # ── Vista ───────────────────────────────────────────────────────────

    def _extension_datos(self):
        bounds = []
        m = self.motor
        for gdf in (m.gdf_infra, m.gdf_montes):
            if gdf is not None and len(gdf):
                bounds.append(gdf.total_bounds)
        for capa in getattr(m.gestor_capas, "capas", []):
            if capa.gdf is not None and len(capa.gdf):
                bounds.append(capa.gdf.total_bounds)
        # Prioridad a infraestructuras (la capa de trabajo)
        if m.gdf_infra is not None and len(m.gdf_infra):
            b = m.gdf_infra.total_bounds
        elif bounds:
            arr = np.array(bounds, dtype=float)
            b = (np.nanmin(arr[:, 0]), np.nanmin(arr[:, 1]),
                 np.nanmax(arr[:, 2]), np.nanmax(arr[:, 3]))
        else:
            return None
        if not all(np.isfinite(b)):
            return None
        return tuple(float(v) for v in b)

    def _tam_px(self):
        try:
            w = float(self.fig.bbox.width)
            h = float(self.fig.bbox.height)
        except Exception:
            w = h = 0
        if w < 20 or h < 20:
            try:
                w = max(w, self.widget.winfo_width())
                h = max(h, self.widget.winfo_height())
            except Exception:
                pass
        return max(w, 50.0), max(h, 50.0)

    def _limites(self):
        if self._vista is None:
            return None
        cx, cy, mpp = self._vista
        w, h = self._tam_px()
        return (cx - w * mpp / 2, cx + w * mpp / 2,
                cy - h * mpp / 2, cy + h * mpp / 2)

    def _aplicar_vista(self, programar_fondo=True):
        lim = self._limites()
        if lim is not None:
            self.ax.set_xlim(lim[0], lim[1])
            self.ax.set_ylim(lim[2], lim[3])
            self._vista_token += 1
            if programar_fondo and self.fondo_activo:
                self._programar_fondo()
            if callable(self.callback_coords) and self._arrastre is None:
                try:
                    self.callback_coords(self._texto_estado(None, None))
                except Exception:
                    pass
        self.canvas.draw_idle()

    def _zoom_factor(self, factor, centro=None):
        if self._vista is None:
            self.zoom_capa()
            return
        cx, cy, mpp = self._vista
        nuevo = min(max(mpp * factor, 0.005), 5000.0)
        if centro is not None:
            x, y = centro
            r = nuevo / mpp
            cx = x - (x - cx) * r
            cy = y - (y - cy) * r
        self._vista = (cx, cy, nuevo)
        self._aplicar_vista()

    def escala_aprox(self) -> float | None:
        if self._vista is None:
            return None
        return self._vista[2] * _DPI_PANTALLA / _M_POR_PULGADA

    # ── Eventos ─────────────────────────────────────────────────────────

    def _on_resize(self, _event=None):
        if self._vista is not None:
            self._aplicar_vista()

    def _on_scroll(self, event):
        if self._vista is None:
            return
        factor = 1 / _FACTOR_ZOOM if event.button == "up" else _FACTOR_ZOOM
        pasos = abs(getattr(event, "step", 1) or 1)
        factor = factor ** min(pasos, 3)
        centro = None
        if event.xdata is not None and event.ydata is not None:
            centro = (event.xdata, event.ydata)
        self._zoom_factor(factor, centro)
        self._actualizar_coords(event, forzar=True)

    def _on_press(self, event):
        if self._vista is None or event.x is None:
            return
        if event.button == 2 or (event.button == 1
                                 and self._modo == self.MODO_DESPLAZAR):
            self._arrastre = {"tipo": "pan", "x0": event.x, "y0": event.y,
                              "vista0": self._vista, "movido": False}
            try:
                self.widget.configure(cursor="fleur")
            except Exception:
                pass
        elif event.button == 1 and self._modo == self.MODO_SELECCIONAR:
            mods = getattr(event, "modifiers", None) or ()
            self._arrastre = {"tipo": "sel", "x0": event.x, "y0": event.y,
                              "xd0": event.xdata, "yd0": event.ydata,
                              "ctrl": "ctrl" in mods or event.key in (
                                  "control", "ctrl"),
                              "movido": False}

    def _on_motion(self, event):
        a = self._arrastre
        if a is not None and event.x is not None:
            dx = event.x - a["x0"]
            dy = event.y - a["y0"]
            if abs(dx) + abs(dy) > 3:
                a["movido"] = True
            if a["tipo"] == "pan":
                cx0, cy0, mpp = a["vista0"]
                self._vista = (cx0 - dx * mpp, cy0 - dy * mpp, mpp)
                self._aplicar_vista(programar_fondo=False)
            elif a["tipo"] == "sel" and a["movido"] \
                    and event.xdata is not None and a["xd0"] is not None:
                x0, y0 = a["xd0"], a["yd0"]
                if self._rect is None:
                    self._rect = Rectangle(
                        (x0, y0), 0, 0, fill=True,
                        facecolor=to_rgba(COLOR_ACENTO, 0.12),
                        edgecolor=COLOR_ACENTO, linewidth=1.2,
                        linestyle="--", zorder=20)
                    self.ax.add_patch(self._rect)
                self._rect.set_bounds(min(x0, event.xdata),
                                      min(y0, event.ydata),
                                      abs(event.xdata - x0),
                                      abs(event.ydata - y0))
                self.canvas.draw_idle()
        self._actualizar_coords(event)

    def _on_release(self, event):
        a = self._arrastre
        self._arrastre = None
        if a is None:
            return
        if a["tipo"] == "pan":
            self.set_modo(self._modo)  # restaura el cursor
            if a["movido"] and self.fondo_activo:
                self._programar_fondo()
            return
        # Selección
        if self._rect is not None:
            try:
                self._rect.remove()
            except Exception:
                pass
            self._rect = None
        if a["movido"] and event.xdata is not None and a["xd0"] is not None:
            nuevos = self._entidades_en_rectangulo(
                a["xd0"], a["yd0"], event.xdata, event.ydata)
        elif event.xdata is not None:
            idx = self._entidad_cercana(event.xdata, event.ydata)
            nuevos = [] if idx is None else [idx]
        else:
            nuevos = []
        if a["ctrl"]:
            sel = list(self._seleccion)
            for i in nuevos:
                if i in sel and not a["movido"]:
                    sel.remove(i)       # Ctrl+clic sobre seleccionada: quita
                elif i not in sel:
                    sel.append(i)
        else:
            sel = nuevos
        self.resaltar(sel)
        if callable(self.callback_seleccion):
            self.callback_seleccion(list(self._seleccion))

    def _on_leave(self, _event=None):
        if callable(self.callback_coords):
            try:
                self.callback_coords(self._texto_estado(None, None))
            except Exception:
                pass

    def _actualizar_coords(self, event, forzar=False):
        if not callable(self.callback_coords):
            return
        ahora = time.perf_counter()
        if not forzar and ahora - self._ultimo_coords < 0.05:
            return
        self._ultimo_coords = ahora
        try:
            self.callback_coords(self._texto_estado(event.xdata, event.ydata))
        except Exception:
            pass

    def _texto_estado(self, x, y):
        partes = []
        if x is not None and y is not None and self._vista is not None:
            partes.append(f"X: {_fmt_miles(x)}   Y: {_fmt_miles(y)}")
        else:
            partes.append("X: —   Y: —")
        esc = self.escala_aprox()
        partes.append(f"Escala aprox. 1:{_fmt_miles(esc)}" if esc
                      else "Escala aprox. —")
        partes.append(CRS_TEXTO)
        return "   |   ".join(partes)

    # ── Selección espacial ──────────────────────────────────────────────

    def _candidatos_visibles(self, cand):
        cand = np.asarray(cand, dtype=np.int64)
        if self._filtro is not None and len(cand):
            cand = np.array([c for c in cand if int(c) in self._filtro],
                            dtype=np.int64)
        return cand

    def _entidad_cercana(self, x, y):
        gdf = self.motor.gdf_infra
        if gdf is None or self._vista is None \
                or not self._visible.get("infra", True):
            return None
        tol = _PX_TOLERANCIA_CLIC * self._vista[2]
        try:
            cand = gdf.sindex.query(_box(x - tol, y - tol, x + tol, y + tol))
        except Exception:
            cand = np.arange(len(gdf))
        cand = self._candidatos_visibles(cand)
        if not len(cand):
            return None
        d = shapely.distance(gdf.geometry.values[cand], _Point(x, y))
        d = np.where(np.isnan(d), np.inf, d)
        k = int(np.argmin(d))
        return int(cand[k]) if d[k] <= tol else None

    def _entidades_en_rectangulo(self, x0, y0, x1, y1):
        gdf = self.motor.gdf_infra
        if gdf is None or not self._visible.get("infra", True):
            return []
        caja = _box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        try:
            cand = gdf.sindex.query(caja, predicate="intersects")
        except Exception:
            cand = np.flatnonzero(shapely.intersects(gdf.geometry.values, caja))
        cand = self._candidatos_visibles(np.sort(cand))
        return [int(c) for c in cand]

    # ── Fondo cartográfico ─────────────────────────────────────────────

    def _on_var_fondo(self):
        activo = self.fondo_activo
        self._visible["fondo"] = activo
        if activo:
            if self._vista is None:
                self._estado("Fondo: carga primero una capa para saber la zona.")
            else:
                self._lanzar_fondo()
        else:
            if self._fondo_after is not None:
                try:
                    self.widget.after_cancel(self._fondo_after)
                except Exception:
                    pass
                self._fondo_after = None
            self._fondo_pendiente = False
            self._quitar_fondo()
            self.canvas.draw_idle()
        self._notificar_capas()

    def _quitar_fondo(self):
        for a in self._fondo_artistas:
            try:
                a.remove()
            except Exception:
                pass
        self._fondo_artistas = []

    def _programar_fondo(self, ms=600):
        if self._fondo_after is not None:
            try:
                self.widget.after_cancel(self._fondo_after)
            except Exception:
                pass
        self._fondo_after = self.widget.after(ms, self._lanzar_fondo)

    def _lanzar_fondo(self):
        self._fondo_after = None
        if not self.fondo_activo or self._vista is None:
            return
        if self._fondo_hilo is not None:
            self._fondo_pendiente = True   # una petición a la vez
            return
        lim = self._limites()
        token = self._vista_token
        wpx, hpx = self._tam_px()
        try:
            proveedor = self.obtener_proveedor()
        except Exception:
            proveedor = "IGN Base"
        self._estado(f"Cargando fondo… ({proveedor})")
        self._ocupado(True)
        motor = self.motor

        def _trabajo():
            imgs, error = [], None
            try:
                imgs = _descargar_fondo(motor, proveedor, lim, wpx, hpx)
                if not imgs:
                    error = "el proveedor no devolvió imagen"
            except Exception as e:
                error = str(e)
            try:
                self.widget.after(0, lambda: self._fondo_listo(
                    token, imgs, error, proveedor))
            except Exception:
                pass

        self._fondo_hilo = threading.Thread(target=_trabajo, daemon=True)
        self._fondo_hilo.start()

    def _fondo_listo(self, token, imgs, error, proveedor):
        self._fondo_hilo = None
        self._ocupado(False)
        try:
            if not self.widget.winfo_exists():
                return
        except Exception:
            return
        if not self.fondo_activo:
            self._estado("Fondo desactivado.")
            return
        if token != self._vista_token or self._fondo_pendiente:
            # La vista cambió mientras se descargaba: resultado obsoleto
            self._fondo_pendiente = False
            self._lanzar_fondo()
            return
        if error:
            self._estado(f"Fondo no disponible: {error[:120]}")
            self._log(f"Fondo cartográfico ({proveedor}) no disponible: {error}",
                      "warn")
            return
        self._quitar_fondo()
        for arr, extent, interp in imgs:
            im = self.ax.imshow(arr, extent=extent, zorder=0,
                                interpolation=interp or "bilinear",
                                aspect="auto")
            self._fondo_artistas.append(im)
        # imshow puede tocar los límites: restaurar la vista exacta
        self._aplicar_vista(programar_fondo=False)
        self._estado(f"Fondo cargado ({proveedor}).")

    # ── Utilidades ──────────────────────────────────────────────────────

    def _estado(self, msg):
        if callable(self.callback_estado):
            try:
                self.callback_estado(msg)
            except Exception:
                pass

    def _ocupado(self, si):
        if callable(self.callback_ocupado):
            try:
                self.callback_ocupado(bool(si))
            except Exception:
                pass

    def _log(self, msg, tipo=""):
        if callable(self.callback_log):
            try:
                self.callback_log(msg, tipo)
            except Exception:
                pass


def _descargar_fondo(motor, proveedor, lim, wpx, hpx):
    """Descarga el fondo para ``lim`` en un eje fuera de pantalla.

    Se ejecuta en un hilo de trabajo: usa una ``Figure`` sin pyplot y el
    despacho de proveedores del motor (ráster local, WMS/WFS propio,
    teselas o WMS), y devuelve [(array, extent, interpolación), ...].
    """
    import geopandas as gpd
    xmin, xmax, ymin, ymax = lim
    fig = Figure(figsize=(max(wpx, 100) / _DPI_PANTALLA,
                          max(hpx, 100) / _DPI_PANTALLA), dpi=_DPI_PANTALLA)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    gdf_view = gpd.GeoDataFrame(geometry=[_box(xmin, ymin, xmax, ymax)],
                                crs="EPSG:25830")
    metodo = getattr(motor, "_añadir_fondo_base", None)
    if callable(metodo):
        metodo(ax, gdf_view, proveedor, xmin, xmax, ymin, ymax)
    else:
        from ..motor.cartografia import añadir_fondo_cartografico
        añadir_fondo_cartografico(ax, gdf_view, proveedor, xmin=xmin,
                                  xmax=xmax, ymin=ymin, ymax=ymax)
    res = []
    for im in ax.images:
        try:
            arr = im.get_array()
            if arr is None:
                continue
            res.append((np.ma.asarray(arr).copy(), tuple(im.get_extent()),
                        im.get_interpolation()))
        except Exception:
            continue
    return res


# ── Tabla de contenidos (lista de capas) ────────────────────────────────

class TablaContenidos:
    """Lista de capas tipo QGIS: casilla de visibilidad, color, nombre, nº."""

    def __init__(self, parent, panel_mapa, callback_zoom=None):
        self.panel_mapa = panel_mapa
        self.callback_zoom = callback_zoom
        self._vars = []

        self.frame = tk.Frame(parent, bg=COLOR_PANEL)
        cab = tk.Frame(self.frame, bg=COLOR_PANEL)
        cab.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(cab, text="CAPAS DEL MAPA", font=FONT_SECCION,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(side="left")
        tk.Label(cab, text="(doble clic: zoom a la capa)", font=FONT_MINI,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(side="right")
        self._lista = tk.Frame(self.frame, bg=COLOR_ENTRY,
                               highlightthickness=1,
                               highlightbackground=COLOR_BORDE)
        self._lista.pack(fill="x", padx=12, pady=(0, 4))
        self.refrescar()

    def pack(self, **kw):
        self.frame.pack(**kw)

    def refrescar(self):
        for w in self._lista.winfo_children():
            w.destroy()
        self._vars = []
        for capa in self.panel_mapa.capas_toc():
            self._fila(capa)

    def _fila(self, capa):
        fila = tk.Frame(self._lista, bg=COLOR_ENTRY)
        fila.pack(fill="x")
        clave = capa["clave"]
        if clave == "fondo":
            var = self.panel_mapa.var_fondo
        else:
            var = tk.BooleanVar(value=capa["visible"])
            var.trace_add("write", lambda *_, c=clave, v=var:
                          self.panel_mapa.set_visible_capa(c, v.get()))
        self._vars.append(var)
        chk = ttk.Checkbutton(fila, variable=var, style="TOC.TCheckbutton",
                              takefocus=False)
        chk.pack(side="left", padx=(6, 2), pady=2)
        sw = tk.Frame(fila, width=14, height=14, highlightthickness=1,
                      highlightbackground="#7a7a7a",
                      bg=capa["color"] or COLOR_ENTRY)
        sw.pack(side="left", padx=(0, 6))
        sw.pack_propagate(False)
        if capa["color"] is None:
            tk.Label(sw, text="▦", font=FONT_MINI, bg=COLOR_ENTRY,
                     fg=COLOR_TEXTO_GRIS, bd=0).pack(expand=True)
        nombre = tk.Label(fila, text=capa["nombre"], font=FONT_SMALL,
                          bg=COLOR_ENTRY, fg=COLOR_TEXTO, anchor="w")
        nombre.pack(side="left", fill="x", expand=True)
        if capa["n"] is not None:
            tk.Label(fila, text=f"[{_fmt_miles(capa['n'])}]", font=FONT_MINI,
                     bg=COLOR_ENTRY, fg=COLOR_TEXTO_GRIS).pack(
                side="right", padx=(4, 8))
        else:
            tk.Label(fila, text="(apagado por defecto)" if not capa["visible"]
                     else "", font=FONT_MINI, bg=COLOR_ENTRY,
                     fg=COLOR_TEXTO_GRIS).pack(side="right", padx=(4, 8))

        def _hover(on, f=fila):
            color = COLOR_HOVER if on else COLOR_ENTRY
            for w in [f] + [c for c in f.winfo_children()
                            if isinstance(c, tk.Label)]:
                try:
                    w.configure(bg=color)
                except Exception:
                    pass

        for w in (fila, nombre):
            w.bind("<Enter>", lambda e: _hover(True))
            w.bind("<Leave>", lambda e: _hover(False))
            w.bind("<Double-Button-1>",
                   lambda e, c=clave: self._zoom(c))
        crear_tooltip(nombre, f"{capa['nombre']}"
                      + (f" — {capa['n']} entidades" if capa["n"] is not None
                         else " — se descarga para la vista actual"))

    def _zoom(self, clave):
        pm = self.panel_mapa
        m = pm.motor
        gdf = None
        if clave == "infra":
            gdf = m.gdf_infra
        elif clave == "montes":
            gdf = m.gdf_montes
        elif isinstance(clave, tuple):
            for capa in m.gestor_capas.capas:
                if id(capa) == clave[1]:
                    gdf = capa.gdf
        if gdf is not None and len(gdf):
            pm.zoom_a_bounds(*gdf.total_bounds)
