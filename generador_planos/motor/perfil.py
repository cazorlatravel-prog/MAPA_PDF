"""
Generación de perfiles topográficos a lo largo de infraestructuras lineales.

Calcula y dibuja el perfil longitudinal de una geometría lineal, mostrando
la variación de altitud a lo largo de su recorrido.

Nota: Requiere un DEM (Digital Elevation Model) para funcionar. Si no hay
DEM disponible, genera un perfil plano con la longitud y pendiente estimada.
"""

import math

import numpy as np
from matplotlib.patches import Rectangle


def calcular_perfil_desde_geometria(geom, n_puntos=50):
    """Extrae puntos equidistantes a lo largo de una geometría lineal.

    Devuelve (distancias_acumuladas, coords_xy) sin elevación.
    La elevación se puede obtener de un DEM externo.
    """
    if not hasattr(geom, "interpolate") or geom.length == 0:
        return np.array([0]), np.array([[geom.centroid.x, geom.centroid.y]])

    longitud_total = geom.length
    distancias = np.linspace(0, longitud_total, n_puntos)
    coords = []
    for d in distancias:
        pt = geom.interpolate(d)
        coords.append([pt.x, pt.y])

    return distancias, np.array(coords)


def estimar_pendiente(geom):
    """Estima la pendiente media de una geometría lineal (sin DEM).

    Calcula basándose en la diferencia de coordenadas entre inicio y fin.
    Sin DEM real, devuelve 0 pero estructura preparada para DEM.
    """
    if not hasattr(geom, "coords") and hasattr(geom, "geoms"):
        # MultiLineString: tomar la primera línea
        for g in geom.geoms:
            if hasattr(g, "coords"):
                geom = g
                break
            return 0.0

    if not hasattr(geom, "coords") or len(list(geom.coords)) < 2:
        return 0.0

    coords = list(geom.coords)
    if len(coords[0]) >= 3:
        # Tiene coordenada Z
        z_inicio = coords[0][2]
        z_fin = coords[-1][2]
        dist_horiz = geom.length
        if dist_horiz > 0:
            return (z_fin - z_inicio) / dist_horiz * 100  # %
    return 0.0


def generar_elevaciones_sinteticas(distancias, z_base=500, variacion=50):
    """Genera elevaciones sintéticas para demostración cuando no hay DEM.

    Usa una función suave (seno + ruido) para simular un perfil topográfico.
    """
    n = len(distancias)
    if n <= 1:
        return np.array([z_base])

    # Pendiente general suave + ondulación
    d_norm = distancias / distancias[-1] if distancias[-1] > 0 else distancias
    elevaciones = (
        z_base
        + variacion * 0.3 * np.sin(d_norm * math.pi * 2)
        + variacion * 0.2 * np.sin(d_norm * math.pi * 5)
        + variacion * 0.5 * d_norm  # pendiente general ascendente
    )
    # Suavizar con media móvil
    kernel = np.ones(3) / 3
    if n > 3:
        elevaciones = np.convolve(elevaciones, kernel, mode="same")

    return elevaciones


def dibujar_perfil(ax, distancias, elevaciones, titulo="PERFIL LONGITUDINAL",
                    color_relleno="#2ECC7144", color_linea="#27AE60"):
    """Dibuja un perfil topográfico en un eje matplotlib.

    ax: eje matplotlib donde dibujar
    distancias: array de distancias acumuladas (m)
    elevaciones: array de elevaciones (m)
    """
    ax.set_facecolor("#F8F9FA")

    if len(distancias) <= 1:
        ax.text(0.5, 0.5, "Perfil no disponible\n(geometría sin longitud)",
                ha="center", va="center", fontsize=6, color="#666666",
                transform=ax.transAxes)
        ax.axis("off")
        return

    # Área rellena
    ax.fill_between(distancias, elevaciones, elevaciones.min() - 5,
                     color=color_relleno, zorder=2)
    # Línea del perfil
    ax.plot(distancias, elevaciones, color=color_linea, linewidth=1.2, zorder=3)

    # Etiquetas
    ax.set_xlabel("Distancia (m)", fontsize=5.5, color="#555555")
    ax.set_ylabel("Elevación (m)", fontsize=5.5, color="#555555")
    ax.set_title(titulo, fontsize=6, fontweight="bold", color="#2C3E50", pad=2)

    ax.tick_params(labelsize=5, colors="#555555")
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)
        spine.set_color("#CCCCCC")

    # Información resumida
    long_total = distancias[-1]
    z_min = elevaciones.min()
    z_max = elevaciones.max()
    desnivel = z_max - z_min
    pendiente_media = desnivel / long_total * 100 if long_total > 0 else 0

    info = (f"L={long_total:.0f}m | "
            f"Z: {z_min:.0f}-{z_max:.0f}m | "
            f"\u0394h={desnivel:.0f}m | "
            f"Pend.={pendiente_media:.1f}%")
    ax.text(0.98, 0.02, info, ha="right", va="bottom", fontsize=4.5,
            color="#666666", transform=ax.transAxes, style="italic")
