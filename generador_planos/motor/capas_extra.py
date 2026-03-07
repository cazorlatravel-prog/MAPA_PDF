"""
Gestión de capas SHP adicionales (hidrografía, vías, parcelas, zonas protegidas, etc.).

Cada capa se carga, reproyecta y almacena con un nombre y simbología asociada.
"""

import geopandas as gpd

from .simbologia import GestorSimbologia, ConfigSimbologia, SIMBOLOGIA_CAPAS_EXTRA

# Tipos de capa reconocidos para asignar simbología por defecto
TIPOS_CAPA = list(SIMBOLOGIA_CAPAS_EXTRA.keys()) + ["Personalizada"]


class CapaExtra:
    """Una capa SHP auxiliar con su GeoDataFrame y metadatos."""

    def __init__(self, nombre: str, ruta: str, gdf: gpd.GeoDataFrame,
                 tipo: str = "Personalizada", visible: bool = True):
        self.nombre = nombre
        self.ruta = ruta
        self.gdf = gdf
        self.tipo = tipo
        self.visible = visible


class GestorCapasExtra:
    """Gestor de múltiples capas SHP auxiliares."""

    def __init__(self):
        self.capas: list[CapaExtra] = []

    def cargar_capa(self, ruta: str, nombre: str = "",
                    tipo: str = "Personalizada") -> tuple:
        """Carga un shapefile como capa adicional.

        Devuelve (ok, mensaje, CapaExtra o None).
        """
        try:
            gdf = gpd.read_file(ruta)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdf = gdf.to_crs("EPSG:25830")

            if not nombre:
                import os
                nombre = os.path.splitext(os.path.basename(ruta))[0]

            capa = CapaExtra(nombre=nombre, ruta=ruta, gdf=gdf, tipo=tipo)
            self.capas.append(capa)

            msg = f"\u2713 Capa '{nombre}': {len(gdf)} elementos ({tipo})"
            return True, msg, capa
        except Exception as e:
            return False, f"Error al cargar capa: {e}", None

    def eliminar_capa(self, nombre: str):
        self.capas = [c for c in self.capas if c.nombre != nombre]

    def obtener_capas_visibles(self) -> list:
        return [c for c in self.capas if c.visible]

    def dibujar_en_mapa(self, ax, xmin, xmax, ymin, ymax,
                         gestor_simb: GestorSimbologia):
        """Dibuja todas las capas visibles en el eje matplotlib."""
        for capa in self.obtener_capas_visibles():
            clip = capa.gdf.cx[xmin:xmax, ymin:ymax]
            if clip.empty:
                continue

            simb = gestor_simb.obtener_simbologia_capa(capa.tipo)

            geom_type = ""
            for g in clip.geometry:
                if g is not None:
                    geom_type = str(g.geom_type).lower()
                    break

            if "point" in geom_type:
                clip.plot(
                    ax=ax, color=simb.color, markersize=simb.markersize,
                    marker=simb.marker, alpha=simb.alpha, zorder=3,
                    edgecolor="white", linewidth=0.3,
                )
            elif "line" in geom_type or "string" in geom_type:
                clip.plot(
                    ax=ax, color=simb.color, linewidth=simb.linewidth,
                    linestyle=simb.linestyle, alpha=simb.alpha, zorder=3,
                )
            else:
                clip.plot(
                    ax=ax, facecolor=simb.facecolor, edgecolor=simb.color,
                    linewidth=simb.linewidth, linestyle=simb.linestyle,
                    alpha=simb.alpha, zorder=3,
                )

    def obtener_items_leyenda(self, gestor_simb: GestorSimbologia) -> list:
        """Devuelve items para la leyenda: [(label, color, tipo_geom, linestyle, marker)]."""
        items = []
        for capa in self.obtener_capas_visibles():
            simb = gestor_simb.obtener_simbologia_capa(capa.tipo)
            geom_type = ""
            for g in capa.gdf.geometry:
                if g is not None:
                    geom_type = str(g.geom_type).lower()
                    break
            items.append((
                capa.nombre,
                simb.color,
                geom_type,
                simb.linestyle,
                simb.marker,
                simb.facecolor,
            ))
        return items

    def to_dict(self) -> list:
        return [
            {"nombre": c.nombre, "ruta": c.ruta, "tipo": c.tipo, "visible": c.visible}
            for c in self.capas
        ]

    def cargar_desde_dict(self, data: list) -> list:
        """Recarga capas desde una lista de dicts. Devuelve errores."""
        errores = []
        for d in data:
            ok, msg, _ = self.cargar_capa(d["ruta"], d["nombre"], d.get("tipo", "Personalizada"))
            if ok:
                self.capas[-1].visible = d.get("visible", True)
            else:
                errores.append(msg)
        return errores
