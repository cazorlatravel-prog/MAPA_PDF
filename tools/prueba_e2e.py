"""Prueba de humo de extremo a extremo del motor (sin GUI).

Crea datos sintéticos (shapefiles, ráster, mosaico con CRS mezclados, CSV
de lotes) y ejecuta todas las rutas de generación del motor capturando
cualquier excepción. Imprime un resumen final.
"""
import os
import sys
import traceback
import warnings

import matplotlib
matplotlib.use("Agg")

import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, LineString, Point, box

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "datos")
OUT = os.path.join(BASE, "salida")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, "/home/user/MAPA_PDF")

RESULTADOS = []
LOGS = []


def log(msg, tipo=None):
    LOGS.append(str(msg))


def paso(nombre, fn):
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            r = fn()
        avisos = [str(x.message)[:120] for x in w
                  if "Noto Sans" not in str(x.message)]
        RESULTADOS.append((nombre, "OK", avisos, r))
        print(f"  ✓ {nombre}" + (f"  [{len(avisos)} avisos]" if avisos else ""))
        for a in avisos[:3]:
            print(f"      ⚠ {a}")
        return r
    except Exception as e:
        tb = traceback.format_exc()
        RESULTADOS.append((nombre, "FALLO", [], f"{e}\n{tb}"))
        print(f"  ✗ {nombre}: {type(e).__name__}: {e}")
        print("      " + tb.strip().replace("\n", "\n      ")[-1500:])
        return None


# ── 1. Datos sintéticos ────────────────────────────────────────────────
X0, Y0 = 502000, 4196000  # cerca de Cazorla, EPSG:25830


def crear_datos():
    feats = []
    nombres = ["Cortafuegos Ñ-1", "Pista forestal El Ágila", "Área cortafuegos",
               "Senda Río Borosa", "Punto de agua Año 2024",
               "Faja auxiliar (larga denominación para desbordar celdas)"]
    tipos = ["Cortafuegos", "Pista", "Cortafuegos", "Senda", "Punto de agua",
             "Faja auxiliar"]
    geoms = [
        Polygon([(X0, Y0), (X0 + 800, Y0), (X0 + 800, Y0 + 60), (X0, Y0 + 60)]),
        LineString([(X0 + 100, Y0 + 300), (X0 + 1500, Y0 + 900),
                    (X0 + 2200, Y0 + 700)]),
        Polygon([(X0 + 3000, Y0 + 2000), (X0 + 3600, Y0 + 2100),
                 (X0 + 3400, Y0 + 2500)]),
        LineString([(X0 - 2000, Y0 - 1500), (X0 - 500, Y0 - 200)]),
        Point(X0 + 1200, Y0 - 800),
        LineString([(X0 + 5000, Y0 + 5000), (X0 + 9000, Y0 + 6500)]),
    ]
    for i, (n, t, g) in enumerate(zip(nombres, tipos, geoms)):
        feats.append({
            "Provincia": "Jaén", "Municipio": "Cazorla",
            "Monte": f"Monte {i % 2 + 1}", "Cod_Monte": f"JA-{1000 + i}",
            "CEDEFO": "Cazorla", "Cod_Infoca": f"INF-{i:03d}",
            "Nombre_Infra": n,
            "Superficie": (float("nan") if i == 2 else round(g.area / 1e4, 3)),
            "Longitud": round(g.length, 1),
            "Ancho": 10 if i % 2 else None,
            "Tipo_Trabajos": t,
            "geometry": g,
        })
    gdf = gpd.GeoDataFrame(feats, crs="EPSG:25830")
    # Un shapefile no admite geometrías mixtas: la capa principal va en
    # GeoPackage (misma ruta de lectura gpd.read_file) y además se escribe
    # un shapefile solo de líneas (con ñ/acentos en UTF-8) para los lotes.
    ruta_infra = os.path.join(DATA, "infra.gpkg")
    gdf.to_file(ruta_infra, driver="GPKG")
    ruta_infra_shp = os.path.join(DATA, "infra_lineas.shp")
    gdf[gdf.geom_type == "LineString"].to_file(ruta_infra_shp, encoding="utf-8")

    montes = gpd.GeoDataFrame({
        "Nombre": ["Monte Público A", "Monte Público B"],
        "Propiedad": ["Junta", "Ayuntamiento"],
        "geometry": [box(X0 - 3000, Y0 - 3000, X0 + 2000, Y0 + 2000),
                     box(X0 + 2000, Y0 + 1000, X0 + 10000, Y0 + 8000)],
    }, crs="EPSG:25830")
    ruta_montes = os.path.join(DATA, "montes.shp")
    montes.to_file(ruta_montes, encoding="utf-8")

    # Capa extra sin CRS (prueba de heurística _asegurar_crs)
    rios = gpd.GeoDataFrame({
        "Nombre": ["Río Guadalquivir"],
        "geometry": [LineString([(X0 - 4000, Y0 + 3000), (X0 + 8000, Y0 - 2000)])],
    })
    ruta_rios = os.path.join(DATA, "rios.shp")
    rios.to_file(ruta_rios)

    # Capa en EPSG:4326 (prueba de reproyección)
    rios4326 = rios.set_crs("EPSG:25830").to_crs("EPSG:4326")
    ruta_rios4326 = os.path.join(DATA, "rios4326.shp")
    rios4326.to_file(ruta_rios4326)

    # Ráster local RGB en 25830 cubriendo la zona
    import rasterio
    from rasterio.transform import from_origin
    w, h = 400, 400
    tr = from_origin(X0 - 6000, Y0 + 9000, 40, 40)  # 16 km x 16 km
    rng = np.random.default_rng(0)
    arr = (rng.random((3, h, w)) * 80 + 150).astype("uint8")
    ruta_tif = os.path.join(DATA, "fondo.tif")
    with rasterio.open(ruta_tif, "w", driver="GTiff", width=w, height=h,
                       count=3, dtype="uint8", crs="EPSG:25830",
                       transform=tr) as dst:
        dst.write(arr)

    # Mosaico con 2 hojas en CRS distintos (25830 y 25829) + 1 sin CRS
    mos = os.path.join(DATA, "mosaico")
    os.makedirs(mos, exist_ok=True)
    with rasterio.open(os.path.join(mos, "h1.tif"), "w", driver="GTiff",
                       width=200, height=200, count=1, dtype="uint8",
                       crs="EPSG:25830",
                       transform=from_origin(X0 - 6000, Y0 + 9000, 40, 40)) as d:
        d.write(arr[0, :200, :200], 1)
    # Hoja 2: misma zona pero expresada en EPSG:25829
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:25830", "EPSG:25829", always_xy=True)
    x29, y29 = t.transform(X0 + 2000, Y0 + 9000)
    with rasterio.open(os.path.join(mos, "h2.tif"), "w", driver="GTiff",
                       width=200, height=200, count=1, dtype="uint8",
                       crs="EPSG:25829",
                       transform=from_origin(x29, y29, 40, 40)) as d:
        d.write(arr[1, :200, :200], 1)

    mos_sin = os.path.join(DATA, "mosaico_sin_crs")
    os.makedirs(mos_sin, exist_ok=True)
    with rasterio.open(os.path.join(mos_sin, "ok.tif"), "w", driver="GTiff",
                       width=100, height=100, count=1, dtype="uint8",
                       crs="EPSG:25830",
                       transform=from_origin(X0, Y0 + 4000, 40, 40)) as d:
        d.write(arr[0, :100, :100], 1)
    with rasterio.open(os.path.join(mos_sin, "sin_crs.tif"), "w", driver="GTiff",
                       width=100, height=100, count=1, dtype="uint8",
                       transform=from_origin(X0 + 4000, Y0 + 4000, 40, 40)) as d:
        d.write(arr[0, :100, :100], 1)

    # CSV de lotes "a la Excel español": BOM UTF-8, separador ';', una fila
    # corta, ruta relativa y carpeta de salida vacía
    ruta_csv = os.path.join(DATA, "lotes.csv")
    with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as f:
        f.write("Ruta_SHP ;nombre;formato;carpeta_salida\r\n")
        f.write(f"infra_lineas.shp;Lote Ñorte;A4 Horizontal;{os.path.join(OUT, 'lote1')}\r\n")
        f.write(f"{os.path.join(DATA, 'noexiste.shp')};Lote Roto\r\n")
        f.write(f"{ruta_infra_shp};Lote sin carpeta;A4 Vertical;\r\n")

    # Excel para tabla
    ruta_xlsx = os.path.join(DATA, "tabla.xlsx")
    pd.DataFrame({
        "Cod_Infoca": [f"INF-{i:03d}" for i in range(6)],
        "Presupuesto": [1000.5 * (i + 1) for i in range(6)],
        "Estado": ["Ejecutado", "Pendiente"] * 3,
    }).to_excel(ruta_xlsx, index=False)

    return dict(infra=ruta_infra, infra_shp=ruta_infra_shp, montes=ruta_montes,
                rios=ruta_rios,
                rios4326=ruta_rios4326, tif=ruta_tif, mosaico=mos,
                mosaico_sin=mos_sin, csv=ruta_csv, xlsx=ruta_xlsx)


print("\n== Creación de datos sintéticos ==")
R = paso("crear_datos", crear_datos)
if R is None:
    sys.exit(1)

from generador_planos.motor.generador import GeneradorPlanos, GeneracionCancelada
from generador_planos.motor import cartografia

CAMPOS = ["Provincia", "Municipio", "Monte", "Nombre_Infra", "Superficie",
          "Longitud", "Tipo_Trabajos"]
CAJETIN = {
    "autor": "J. Caballero", "proyecto": "Plan de prevención 2026",
    "num_proyecto": "PP-2026-01", "revision": "A", "cargo_revision": "Jefe",
    "firma": "Dirección", "cargo_firma": "Director", "fecha": "10/2026",
    "organizacion": "Junta de Andalucía\nConsejería", "titulo_mapa": "PLANO DE SITUACIÓN",
    "subtitulo": "Infraestructuras", "campo_subtitulo": "Monte",
    "logo_path": "", "num_plano_inicio": 1,
    "campo_etiqueta": "Nombre_Infra", "campo_etiqueta_montes": "Nombre",
}


def nuevo_motor(layout="Plantilla 1 (Clásica)"):
    m = GeneradorPlanos()
    m.dpi_figura = 72
    m.dpi_guardado = 72
    m.layout_key = layout
    ok, msg, falt = m.cargar_infraestructuras(R["infra"])
    assert ok, msg
    ok, msg = m.cargar_montes(R["montes"])[:2]
    assert ok, msg
    m.set_cajetin(CAJETIN)
    m.gestor_simbologia.generar_por_categoria(
        "Tipo_Trabajos", m.obtener_valores_unicos("Tipo_Trabajos"))
    m.gestor_simbologia.generar_por_categoria_montes("Propiedad", ["Junta", "Ayuntamiento"])
    m.config_infra = {"campo_categoria": "Tipo_Trabajos",
                      "campo_categoria_montes": "Propiedad"}
    return m


print("\n== Carga de capas ==")
motor = paso("cargar motor clásico", nuevo_motor)
if motor is None:
    sys.exit(1)
paso("valores únicos / índices por valor", lambda: (
    motor.obtener_valores_unicos("Tipo_Trabajos"),
    motor.obtener_indices_por_valor("Tipo_Trabajos", "Cortafuegos"),
    motor.obtener_valores_unicos("Superficie"),
    motor.obtener_indices_por_valor("Ancho", "10"),
))
paso("capa extra sin CRS (heurística)", lambda: motor.gestor_capas.cargar_capa(
    R["rios"], nombre="Ríos", tipo="Hidrografía"))
paso("capa extra en 4326", lambda: motor.gestor_capas.cargar_capa(
    R["rios4326"], nombre="Ríos4326", tipo="Personalizada"))
paso("excel tabla con enlace", lambda: motor.cargar_excel_tabla(
    R["xlsx"], campo_enlace_shp="Cod_Infoca", campo_enlace_excel="Cod_Infoca",
    columnas_activas=["Presupuesto", "Estado"]))

print("\n== Mosaico VRT ==")
vrt = paso("mosaico CRS mezclados (25830+25829)", lambda: cartografia.construir_vrt_desde_carpeta(R["mosaico"]))
if vrt:
    def _abrir_vrt():
        import rasterio
        with rasterio.open(vrt) as s:
            return (s.crs.to_epsg(), s.width, s.height, s.count)
    paso("abrir VRT resultante", _abrir_vrt)
    paso("segunda llamada usa caché", lambda: cartografia.construir_vrt_desde_carpeta(R["mosaico"]))


def _mos_sin():
    try:
        cartografia.construir_vrt_desde_carpeta(R["mosaico_sin"])
    except Exception as e:
        return f"error esperado: {type(e).__name__}: {str(e)[:160]}"
    raise AssertionError("debería fallar con hoja sin CRS")
paso("mosaico con hoja sin CRS → error claro", _mos_sin)

print("\n== Generación de planos (sin red: ráster local) ==")
motor.ruta_raster_general = R["tif"]
motor.ruta_raster_localizacion = R["tif"]
motor.prov_localizacion = "WMS IGN (online)"
for i in range(6):
    paso(f"generar_plano clásico #{i}", lambda i=i: motor.generar_plano(
        idx_fila=i, formato_key="A3 Horizontal", proveedor="OpenStreetMap",
        transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000",
        salida_dir=OUT, callback_log=log, campo_encabezado="Nombre_Infra",
        patron_nombre="{num}_{nombre}"))

paso("generar_plano A4 escala manual 5000", lambda: motor.generar_plano(
    idx_fila=0, formato_key="A4 Horizontal", proveedor="OpenStreetMap",
    transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000",
    salida_dir=OUT, escala_manual=5000, callback_log=log))
paso("generar_plano A2 todos los campos", lambda: motor.generar_plano(
    idx_fila=5, formato_key="A2 Horizontal", proveedor="OpenStreetMap",
    transparencia_montes=0.3, campos_visibles=list(CAMPOS) + ["Cod_Monte", "CEDEFO", "Cod_Infoca", "Ancho"],
    color_infra="#FF0000", salida_dir=OUT, callback_log=log))
paso("generar_plano_agrupado", lambda: motor.generar_plano_agrupado(
    indices=[0, 1, 2], campo_grupo="Monte", valor_grupo="Monte 1",
    formato_key="A3 Horizontal", proveedor="OpenStreetMap",
    transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000",
    salida_dir=OUT, num_plano=7, callback_log=log))
paso("generar_serie_agrupada", lambda: motor.generar_serie_agrupada(
    campo_grupo="Tipo_Trabajos", valores=motor.obtener_valores_unicos("Tipo_Trabajos"),
    formato_key="A4 Horizontal", proveedor="OpenStreetMap", transparencia=0.3,
    campos=CAMPOS, color_infra="#00AA00", salida_dir=OUT, callback_log=log,
    indices_filtro={"Cortafuegos": [0]}))
paso("vista previa", lambda: motor.generar_vista_previa(
    idx_fila=1, formato_key="A3 Horizontal", proveedor="OpenStreetMap",
    transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000"))
paso("mapa guía (figura)", lambda: motor.generar_mapa_guia(
    indices=list(range(6)), formato_key="A3 Horizontal"))
paso("mapa guía (pdf)", lambda: motor.generar_mapa_guia(
    indices=list(range(6)), formato_key="A3 Horizontal", salida_dir=OUT))
paso("pdf multipágina 42 págs + portada/índice/guía", lambda: motor.generar_pdf_multipagina(
    indices=list(range(6)) * 7, formato_key="A4 Horizontal", proveedor="OpenStreetMap",
    transparencia=0.3, campos=CAMPOS, color_infra="#FF0000",
    ruta_pdf=os.path.join(OUT, "multi.pdf"), incluir_portada=True,
    callback_log=log, callback_progreso=lambda a, b: None))


def _cancelacion():
    m = nuevo_motor()
    m.ruta_raster_general = R["tif"]
    llamadas = {"n": 0}

    def prog(a, b):
        llamadas["n"] += 1
        if a == 2:
            m.cancelar_generacion()
    try:
        m.generar_serie(indices=list(range(6)), formato_key="A4 Horizontal",
                        proveedor="OpenStreetMap", transparencia=0.3,
                        campos=CAMPOS, color_infra="#FF0000",
                        salida_dir=os.path.join(OUT, "cancel"),
                        callback_log=log, callback_progreso=prog)
    except GeneracionCancelada:
        return f"cancelada tras {llamadas['n']} planos (correcto)"
    raise AssertionError("no se propagó GeneracionCancelada")
paso("cancelación en generar_serie", _cancelacion)


def _lotes():
    from generador_planos.motor.proyecto import cargar_lotes_csv
    lotes = cargar_lotes_csv(R["csv"])
    assert len(lotes) == 3, lotes
    assert lotes[0]["ruta_shp"] == R["infra_shp"], lotes[0]
    assert lotes[0]["nombre"] == "Lote Ñorte"
    assert lotes[1]["formato"] == "A3 Horizontal" and lotes[1]["carpeta_salida"] == ""
    m = nuevo_motor()
    m.ruta_raster_general = R["tif"]
    gdf_antes = m.gdf_infra
    rutas = m.generar_lotes_csv(ruta_csv=R["csv"], proveedor="OpenStreetMap",
                                transparencia=0.3, campos=CAMPOS,
                                color_infra="#FF0000", callback_log=log)
    assert m.gdf_infra is gdf_antes, "gdf_infra no restaurado tras lotes"
    assert len(rutas) == 6, f"esperados 6 planos (2 lotes x 3 líneas), hay {len(rutas)}"
    return f"{len(rutas)} planos de lotes"
paso("generar_lotes_csv (BOM, ';', fila corta, sin carpeta, roto)", _lotes)


def _shapefile_con_nulos_y_texto():
    """Shapefile con geometría nula y Longitud/Superficie como texto español."""
    from generador_planos.motor._utils_geo import _calcular_stats_grupo
    g = gpd.GeoDataFrame({
        "Nombre_Infra": ["A", "B", "C"],
        "Longitud": ["1.234,5", "", "7,5"],
        "Superficie": ["0,5", "abc", None],
        "geometry": [LineString([(X0, Y0), (X0 + 100, Y0)]), None,
                     LineString([(X0, Y0), (X0, Y0 + 50)])],
    }, crs="EPSG:25830")
    ruta = os.path.join(DATA, "nulos.shp")
    g.to_file(ruta, encoding="utf-8")
    m = GeneradorPlanos()
    ok, msg, falt = m.cargar_infraestructuras(ruta)
    assert ok, msg
    st = _calcular_stats_grupo(m.gdf_infra)
    assert abs(st["total_longitud_km"] - 1.242) < 1e-6, st
    assert abs(st["total_superficie_ha"] - 0.5) < 1e-9, st
    return st
paso("shapefile con geometría nula y números en texto", _shapefile_con_nulos_y_texto)

print("\n== Plantilla lateral ==")
motor2 = paso("cargar motor lateral", lambda: nuevo_motor("Plantilla 2 (Panel lateral)"))
if motor2:
    motor2.ruta_raster_general = R["tif"]
    motor2.ruta_raster_localizacion = R["tif"]
    for i in (0, 4, 5):
        paso(f"generar_plano lateral #{i}", lambda i=i: motor2.generar_plano(
            idx_fila=i, formato_key="A3 Horizontal", proveedor="OpenStreetMap",
            transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000",
            salida_dir=os.path.join(OUT, "lateral"), callback_log=log))
    paso("agrupado lateral", lambda: motor2.generar_plano_agrupado(
        indices=[0, 1, 2, 3, 4, 5], campo_grupo="Monte", valor_grupo="Todos",
        formato_key="A3 Horizontal", proveedor="OpenStreetMap",
        transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000",
        salida_dir=os.path.join(OUT, "lateral"), callback_log=log))

print("\n== Proveedores online (red) ==")
motor3 = nuevo_motor()
for prov in ["OpenStreetMap", "Topográfico Andalucía (MTA10)", "Google Satélite",
             "IGN MTN25 (WMS 1:25.000)", "PNOA Ortofoto (IGN)"]:
    paso(f"vista previa con {prov}", lambda prov=prov: motor3.generar_vista_previa(
        idx_fila=0, formato_key="A4 Horizontal", proveedor=prov,
        transparencia_montes=0.3, campos_visibles=CAMPOS, color_infra="#FF0000"))

print("\n== Proyecto: guardar/cargar ==")


def _proyecto():
    from generador_planos.motor.proyecto import Proyecto
    p = Proyecto()
    p.simbologia = motor.gestor_simbologia.to_dict()
    p.cajetin = dict(CAJETIN)
    ruta = os.path.join(OUT, "proy.json")
    p.guardar(ruta)
    p2 = Proyecto.cargar(ruta)
    from generador_planos.motor.simbologia import GestorSimbologia
    g = GestorSimbologia.from_dict(p2.simbologia)
    assert "Tipo_Trabajos" in g.categorias
    return p2.nombre
paso("roundtrip proyecto", _proyecto)

import matplotlib.pyplot as plt
print(f"\nFiguras abiertas al final: {len(plt.get_fignums())}")

print("\n== Mensajes de error en el log del motor ==")
errs = [l for l in LOGS if "✗" in l or "Error" in l or "⚠" in l]
for l in errs[:30]:
    print("  " + l.strip().replace("\n", " | ")[:300])
print(f"  ({len(errs)} mensajes de {len(LOGS)})")

print("\n== RESUMEN ==")
fallos = [r for r in RESULTADOS if r[1] == "FALLO"]
print(f"  {len(RESULTADOS) - len(fallos)} OK, {len(fallos)} FALLOS")
for n, _, _, d in fallos:
    print(f"  ✗ {n}")
pdfs = [f for root, _, fs in os.walk(OUT) for f in fs if f.endswith(".pdf")]
print(f"  PDFs generados: {len(pdfs)}")
