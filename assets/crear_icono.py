#!/usr/bin/env python3
"""
Genera el icono de la aplicación (icon.ico) usando Pillow.
Ejecutar: python assets/crear_icono.py
Requiere: pip install Pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

SIZES = [16, 32, 48, 64, 128, 256]
OUTPUT = os.path.join(os.path.dirname(__file__), "icon.ico")


def crear_icono(size):
    """Crea un icono cuadrado del tamaño indicado."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo circular verde oscuro
    margin = int(size * 0.05)
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(28, 35, 51, 255),
        outline=(46, 204, 113, 255),
        width=max(1, size // 32),
    )

    # Mapa estilizado (rectángulo interior)
    m2 = int(size * 0.2)
    draw.rectangle(
        [m2, m2, size - m2, size - m2],
        fill=(13, 17, 23, 200),
        outline=(46, 204, 113, 255),
        width=max(1, size // 40),
    )

    # Cruz de coordenadas
    cx, cy = size // 2, size // 2
    line_w = max(1, size // 50)
    draw.line([(cx, m2 + 4), (cx, size - m2 - 4)],
              fill=(46, 204, 113, 180), width=line_w)
    draw.line([(m2 + 4, cy), (size - m2 - 4, cy)],
              fill=(46, 204, 113, 180), width=line_w)

    # Árbol estilizado (triángulo verde)
    tree_h = int(size * 0.25)
    tree_w = int(size * 0.18)
    tree_cx = int(size * 0.65)
    tree_cy = int(size * 0.4)
    draw.polygon(
        [(tree_cx, tree_cy - tree_h // 2),
         (tree_cx - tree_w // 2, tree_cy + tree_h // 2),
         (tree_cx + tree_w // 2, tree_cy + tree_h // 2)],
        fill=(39, 174, 96, 220),
    )

    # Punto rojo de infraestructura
    dot_r = max(2, size // 16)
    dot_cx = int(size * 0.38)
    dot_cy = int(size * 0.58)
    draw.ellipse(
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=(231, 76, 60, 255),
        outline=(255, 255, 255, 200),
        width=max(1, size // 64),
    )

    return img


def main():
    print("Generando icono...")
    imgs = [crear_icono(s) for s in SIZES]
    imgs[0].save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES],
                 append_images=imgs[1:])
    print(f"Icono guardado: {OUTPUT}")
    print(f"Tamaños: {', '.join(f'{s}x{s}' for s in SIZES)}")


if __name__ == "__main__":
    main()
