# Generador de Planos Forestales v2.0 — Documentacion Completa del Proyecto

## 1. Contexto General

Aplicacion de escritorio Python para generacion de planos cartograficos profesionales en serie (PDF A3/A4/A2), orientada a infraestructuras forestales de Andalucia (INFOCA / Junta de Andalucia).

- **Version:** 2.0.0
- **Licencia:** MIT
- **Autor:** Jose Caballero Sanchez (Cazorla, 2026)
- **Repositorio:** https://github.com/cazorlatravel-prog/MAPA_PDF
- **Python requerido:** >=3.9

---

## 2. Stack Tecnologico

| Libreria | Version | Uso |
|---|---|---|
| `geopandas` | >=0.14 | Lectura de Shapefiles/GDB, reproyeccion CRS |
| `matplotlib` | >=3.8 | Renderizado cartografico y maquetacion del plano |
| `numpy` | >=1.26 | Calculos geometricos |
| `requests` | >=2.31 | Descarga de teselas y servicios WMS/WFS |
| `Pillow` | >=10.0 | Manipulacion de imagenes |
| `contextily` | >=1.6 | Descarga de teselas WMS/WMTS de fondo |
| `pyproj` | >=3.6 | Transformacion de coordenadas |
| `reportlab` | >=4.0 | Generacion final de PDF |
| `shapely` | >=2.0 | Operaciones geometricas |
| `adjustText` | >=1.0 | Evitar solapamiento de etiquetas |
| `openpyxl` | >=3.1 | Lectura de archivos Excel |

**Dependencia opcional:**
| `pyinstaller` | >=6.0 | Creacion de ejecutables Windows |

---

## 3. Estructura del Proyecto

```
MAPA_PDF/
|-- .gitignore
|-- pyproject.toml                    # Metadatos del proyecto (PEP 517/518)
|-- requirements.txt                  # Dependencias pip
|-- PLANOS_FORESTALES.md              # Especificacion original del proyecto
|-- plan.md                           # Plan de implementacion de 3 funcionalidades
|-- PROYECTO_COMPLETO.md              # Este archivo
|
|-- generador_planos/                 # Paquete principal
|   |-- __init__.py                   # Inicializacion del paquete
|   |-- __main__.py                   # Punto de entrada: python -m generador_planos
|   |-- main.py                       # Arranque, splash screen, verificacion deps
|   |-- requirements.txt              # Copia de dependencias
|   |
|   |-- motor/                        # Logica de negocio y generacion
|   |   |-- __init__.py               # Exporta API publica del motor
|   |   |-- generador.py              # Clase principal GeneradorPlanos (1226 lineas)
|   |   |-- maquetacion.py            # MaquetadorPlano: layout y renderizado (1645 lineas)
|   |   |-- cartografia.py            # Descarga teselas/WMS/WFS/raster (587 lineas)
|   |   |-- escala.py                 # Seleccion de escala y formatos (98 lineas)
|   |   |-- simbologia.py             # Gestion de simbologia por categorias (224 lineas)
|   |   |-- plantillas_layout.py      # Definiciones de plantillas de layout (45 lineas)
|   |   |-- proyecto.py               # Persistencia de proyecto en JSON (260 lineas)
|   |   |-- capas_extra.py            # Gestion de capas adicionales (158 lineas)
|   |   |-- paginas_especiales.py     # Portada, indice, mapa guia (277 lineas)
|   |   |-- perfil.py                 # Perfil topografico longitudinal (139 lineas)
|   |   |-- _elementos_mapa.py        # Mixin: grid UTM, escala, leyenda, norte (360 lineas)
|   |   |-- _utils_geo.py             # Utilidades geoespaciales compartidas (151 lineas)
|   |
|   |-- gui/                          # Interfaz grafica (tkinter)
|   |   |-- __init__.py               # Exporta clase App
|   |   |-- app.py                    # Ventana principal App(tk.Tk) (614 lineas)
|   |   |-- estilos.py                # Paleta de colores, fuentes, widgets (319 lineas)
|   |   |-- panel_capas.py            # Carga de capas SHP/GDB (578 lineas)
|   |   |-- panel_config.py           # Configuracion general (683 lineas)
|   |   |-- panel_campos.py           # Selector de campos visibles (126 lineas)
|   |   |-- panel_cajetin.py          # Editor de cajetin y plantilla (310 lineas)
|   |   |-- panel_simbologia.py       # Editor de simbologia (368 lineas)
|   |   |-- panel_filtros.py          # Filtros avanzados (186 lineas)
|   |   |-- panel_generacion.py       # Control de generacion (938 lineas)
|   |
|   |-- assets/                       # Recursos (vacio en runtime)
|
|-- assets/                           # Recursos de build
|   |-- crear_icono.py                # Generador de icono (82 lineas)
|   |-- icon.ico                      # Icono de la aplicacion
|
|-- tests/                            # Tests unitarios
|   |-- __init__.py
|   |-- test_utils_geo.py             # Tests de utilidades geo (169 lineas)
|   |-- test_simbologia.py            # Tests de simbologia (76 lineas)
|   |-- test_proyecto.py              # Tests de proyecto (61 lineas)
|   |-- test_escala.py                # Tests de escala (107 lineas)
|
|-- legacy/                           # Codigo anterior
|   |-- generador_planos_v1.py        # Version monolitica v1.0 (1333 lineas)
|
|-- build_exe.py                      # Build ejecutable PyInstaller (233 lineas)
|-- build_portable.py                 # Build portable single-file (363 lineas)
|-- installer.iss                     # Script Inno Setup (68 lineas)
```

**Total codigo fuente:** ~8.700+ lineas (motor ~4.170 + gui ~4.120 + otros ~410)

---

## 4. Modulo Motor (`generador_planos/motor/`)

Contiene toda la logica de negocio: generacion de planos, cartografia, escalas, simbologia y persistencia.

### 4.1. `generador.py` — Clase GeneradorPlanos (1226 lineas)

Orquestador principal de generacion de mapas. Coordina carga de datos, calculo de escala, maquetacion y exportacion PDF.

**Clase `GeneracionCancelada(Exception)`**
Excepcion lanzada cuando el usuario cancela la generacion en curso.

**Clase `GeneradorPlanos`**

| Atributo | Tipo | Descripcion |
|---|---|---|
| `gdf_infra` | GeoDataFrame | Capa de infraestructuras cargada |
| `gdf_montes` | GeoDataFrame | Capa de montes cargada |
| `gestor_capas` | GestorCapasExtra | Gestor de capas adicionales |
| `gestor_simbologia` | GestorSimbologia | Gestor de simbologia |
| `layout_key` | str | Plantilla seleccionada |
| `dpi_figura` | int | DPI de renderizado |
| `dpi_guardado` | int | DPI de exportacion PDF |
| `ruta_raster_general` | str | Raster de fondo general |
| `ruta_raster_localizacion` | str | Raster del mapa de posicion |
| `ruta_capa_localizacion` | str | Capa vectorial para posicion |
| `wms_custom_general` | dict | Config WMS personalizado general |
| `wfs_custom_general` | dict | Config WFS personalizado general |
| `wms_custom_localizacion` | dict | Config WMS personalizado localizacion |
| `wfs_custom_localizacion` | dict | Config WFS personalizado localizacion |
| `escala_localizacion` | int | Escala del mapa de posicion |
| `prov_localizacion` | str | Proveedor del mapa de posicion |

**Metodos de configuracion:**

| Metodo | Descripcion |
|---|---|
| `set_cajetin(cajetin: dict)` | Establece datos del cajetin (autor, proyecto, org...) |
| `set_plantilla(plantilla: dict)` | Establece colores de plantilla |
| `cargar_excel_tabla(ruta, hoja, campo_shp, campo_excel, cols)` | Vincula tabla Excel a shapefile |
| `limpiar_excel_tabla()` | Elimina vinculacion Excel |

**Metodos de carga de datos:**

| Metodo | Retorno | Descripcion |
|---|---|---|
| `cargar_infraestructuras(ruta, layer=None)` | `(bool, str, list)` | Carga SHP/GDB de infraestructuras; auto-CRS, calcula Longitud/Superficie |
| `cargar_montes(ruta, layer=None)` | `(bool, str)` | Carga SHP/GDB de montes |
| `establecer_mapeo_campos(mapeo: dict)` | — | Mapea nombres de campo esperados a reales |
| `obtener_columnas_shapefile()` | `list` | Columnas disponibles del shapefile |
| `obtener_valores_unicos(campo)` | `list` | Valores unicos de un campo |
| `obtener_indices_por_valor(campo, valor)` | `list` | Indices de filas con valor dado |

**Metodos de generacion individual:**

| Metodo | Retorno | Descripcion |
|---|---|---|
| `generar_plano(idx, formato, proveedor, transp, campos, color, salida, ...)` | `str` (ruta PDF) | Genera plano de una infraestructura |
| `generar_plano_agrupado(indices, campo_grupo, valor, ...)` | `str` (ruta PDF) | Genera plano con varias infraestructuras agrupadas |
| `generar_vista_previa(idx, ...)` | `plt.Figure` | Vista previa a baja resolucion (no guarda) |
| `generar_mapa_guia(indices, formato, ...)` | `Figure o str` | Mapa guia con todas las infra numeradas |

**Metodos de generacion en serie:**

| Metodo | Retorno | Descripcion |
|---|---|---|
| `generar_serie(indices, ...)` | `list[str]` | Un PDF por infraestructura |
| `generar_serie_agrupada(campo, valores, ...)` | `list[str]` | Un PDF por grupo |
| `generar_pdf_multipagina(indices, ...)` | `str` | Un unico PDF con portada + indice + mapa guia + planos |
| `generar_lotes_csv(ruta_csv, ...)` | `list[str]` | Generacion por lotes desde CSV |
| `cancelar_generacion()` | — | Senala cancelacion al hilo de generacion |

**Metodos internos:**

| Metodo | Descripcion |
|---|---|
| `_check_cancelado()` | Lanza GeneracionCancelada si hay flag |
| `_ensure_agg()` | Cambia backend matplotlib a Agg (seguro para hilos) |
| `_añadir_fondo(maq, gdf, proveedor, xmin, xmax, ymin, ymax)` | Dibuja fondo cartografico |
| `_dibujar_capas_mapa(maq, gdf_sel, config, xmin, xmax, ymin, ymax)` | Dibuja infra + montes + capas extra (con categorizacion) |
| `_construir_items_leyenda(config)` | Construye items de leyenda |
| `_obtener_filas_tabla(row, campos)` | Obtiene datos de tabla (Excel o shapefile) |

---

### 4.2. `maquetacion.py` — Clase MaquetadorPlano (1645 lineas)

Gestiona el layout completo del plano en matplotlib y la exportacion a PDF. Hereda de `ElementosMapaMixin`.

**Constantes del modulo:**

| Constante | Valor | Descripcion |
|---|---|---|
| `_FONT_CORP` | `"Noto Sans HK"` | Fuente preferida |
| `ETIQUETAS_CAMPOS` | dict | Mapeo campo → etiqueta (ej: `Superficie` → `Superficie (ha)`) |
| `CALIDADES_PDF` | dict | Presets de DPI: `{"Borrador": (150,150), "Normal": (300,300), ...}` |
| `_CABECERA_MM` | 6 | Altura de cabecera en mm |

**Funciones auxiliares:**

| Funcion | Descripcion |
|---|---|
| `_fmt_valor(valor_raw) -> str` | Formatea numeros a 2 decimales, maneja NaN |
| `_etiqueta_campo(campo) -> str` | Devuelve etiqueta legible del campo |

**Clase `MaquetadorPlano(ElementosMapaMixin)`**

| Atributo | Tipo | Descripcion |
|---|---|---|
| `formato_key` | str | Formato papel seleccionado |
| `fmt_mm` | tuple | Dimensiones en mm (ancho, alto) |
| `escala` | int | Escala del plano |
| `layout_key` | str | Plantilla de layout |
| `dpi` | int | DPI de figura |
| `fig` | Figure | Figura matplotlib |
| `ax_map` | Axes | Eje del mapa principal |
| `ax_info` | Axes | Eje del panel de atributos |
| `ax_mini` | Axes | Eje del mapa de posicion |
| `ax_esc` | Axes | Eje de la barra de escala/cajetin |
| `ax_tabla` | Axes | Eje tabla infra (solo Plantilla 2) |

| Propiedad | Tipo | Descripcion |
|---|---|---|
| `es_lateral` | bool | True si es Plantilla 2 (Panel lateral) |

**Metodos de creacion de figura:**

| Metodo | Descripcion |
|---|---|
| `crear_figura() -> tuple` | Crea figura y ejes segun layout seleccionado |
| `_crear_figura_clasica()` | Layout Plantilla 1: 2 filas x 3 columnas |
| `_crear_figura_lateral()` | Layout Plantilla 2: 1 fila x 2 columnas con panel lateral |

**Metodos de extension del mapa:**

| Metodo | Descripcion |
|---|---|
| `calcular_extension_mapa(geom) -> (xmin, xmax, ymin, ymax)` | Calcula limites del mapa segun escala y geometria |
| `configurar_mapa_principal(xmin, xmax, ymin, ymax)` | Aplica limites y aspecto al eje del mapa |

**Metodos de paneles de contenido:**

| Metodo | Descripcion |
|---|---|
| `dibujar_panel_atributos(row, campos, ...)` | Tabla 2 columnas de atributos (Plantilla 1) |
| `dibujar_panel_atributos_multi(rows, campos, ...)` | Version multi-fila, 2 columnas |
| `dibujar_tabla_infra(rows, campos, ...)` | Tabla compacta con cabecera verde y filas zebra (Plantilla 2) |
| `dibujar_mapa_posicion(cx, cy, ...)` | Mapa de localizacion con marcador y rectangulo de extension |
| `dibujar_barra_escala(proveedor, cx, cy, cajetin, items)` | Cajetin con org, proyecto, escala, fecha, leyenda, barra grafica |
| `dibujar_leyenda_lateral(items_infra, items_montes)` | Leyenda lateral en 2 secciones (Plantilla 2) |
| `dibujar_cajetin_lateral(row, cajetin, plantilla, num, prov, ...)` | Cajetin institucional estilo Junta (Plantilla 2) |

**Metodos de cabecera y marcos:**

| Metodo | Descripcion |
|---|---|
| `dibujar_cabecera(row, titulo, num_plano, cajetin, plantilla)` | Cabecera 6mm: logo + titulo + subtitulo + num plano |
| `dibujar_marcos(plantilla, cajetin)` | Marco doble exterior + copyright vertical |

**Metodo de exportacion:**

| Metodo | Descripcion |
|---|---|
| `guardar(ruta_out, dpi_save=None)` | Guarda figura a PDF y cierra la figura |

---

### 4.3. `cartografia.py` — Fondos Cartograficos (587 lineas)

Gestiona descarga de teselas XYZ, servicios WMS/WFS, rasters locales y fondos de mapa.

**Proveedores de teselas XYZ (`CAPAS_BASE`):**

| Clave | Fuente |
|---|---|
| `OpenStreetMap` | Teselas estandar OSM |
| `PNOA Ortofoto (IGN)` | Ortofoto WMTS del IGN Espana |
| `IGN Topografico (MTN)` | Topografico WMTS del IGN Espana |
| `Stamen Terrain` | Terreno con relieve |

**Proveedores WMS (`CAPAS_WMS`):**

| Clave | URL / Descripcion |
|---|---|
| `IGN MTN25 (WMS 1:25.000)` | `ign.es/wms-inspire/mapa-raster` LAYERS=mtn_rasterizado, CRS=EPSG:25830 |
| `IGN MTN50 (WMS 1:50.000)` | Mismo servicio, capa MTN50 |

**Funciones principales:**

| Funcion | Descripcion |
|---|---|
| `añadir_fondo_cartografico(ax, gdf, proveedor, xmin, xmax, ymin, ymax)` | Funcion principal: anade fondo al eje. Intenta contextily → teselas manuales → WMS → gris |
| `_descargar_teselas_manual(ax, url, xmin, xmax, ymin, ymax)` | Descarga teselas XYZ en paralelo (8 workers), con cache en disco |
| `_descargar_wms(ax, url, xmin, xmax, ymin, ymax)` | Descarga imagen WMS GetMap completa (~2 m/px, max 4096px) con cache |
| `añadir_fondo_raster_local(ax, ruta, xmin, xmax, ymin, ymax)` | Carga raster local (GeoTIFF, ECW, JP2) con lectura windowed |
| `construir_vrt_desde_carpeta(carpeta) -> str` | Crea mosaico virtual VRT desde carpeta de hojas raster |
| `descargar_wfs(url, capa, xmin, ymin, xmax, ymax) -> GeoDataFrame` | Descarga features WFS con filtro BBOX |
| `descargar_wms_custom(ax, url, capa, xmin, xmax, ymin, ymax) -> bool` | Descarga WMS desde servicio personalizado |
| `dibujar_wfs_en_eje(ax, gdf, estilo)` | Dibuja GeoDataFrame en eje matplotlib |

**Cache:**
- Directorio: `~/.mapa_pdf_cache/tiles/`
- Clave: hash MD5 de URL
- Persistente entre sesiones

---

### 4.4. `escala.py` — Escalas y Formatos (98 lineas)

Define escalas permitidas, intervalos de grid, formatos de papel y margenes.

**Constantes:**

| Constante | Valor | Descripcion |
|---|---|---|
| `ESCALAS` | `[5000, 7500, 10000, 15000, 20000, 25000, 30000]` | Escalas permitidas |
| `INTERVALOS_GRID` | `{5000:500, 7500:500, 10000:1000, ...}` | Intervalo de grid UTM (metros) por escala |
| `BARRA_ESCALA_M` | `{5000:1000, ..., 20000:2000, ...}` | Longitud barra de escala (metros) |
| `MARGENES_MM` | `{"izq":10, "der":10, "sup":10, "inf":12}` | Margenes de pagina en mm |
| `FORMATOS` | `{"A4 Horizontal":(297,210), "A3 Horizontal":(420,297), "A2 Horizontal":(594,420)}` | Formatos de papel (ancho, alto mm) |
| `RATIO_MAPA_ANCHO` | 1.0 | Ratio ancho del mapa |
| `RATIO_MAPA_ALTO` | 0.78 | Ratio alto del mapa |
| `DPI_DEFAULT` | 400 | DPI por defecto |

**Funcion:**

```
seleccionar_escala(geom, formato_key, escala_manual=None, es_lateral=False) -> int
```
Selecciona la escala optima de `ESCALAS` segun la extension de la geometria y el formato de papel. Si `escala_manual` no es None, la devuelve directamente.

---

### 4.5. `simbologia.py` — Gestion de Simbologia (224 lineas)

Sistema de colorizacion por categorias para infraestructuras, montes y capas extra.

**Constantes:**

| Constante | Descripcion |
|---|---|
| `TIPOS_TRAZO` | `{"Continuo":"-", "Discontinuo":"--", "Punto-raya":"-.", "Punteado":":"}` |
| `MARCADORES` | `{"Circulo":"o", "Cuadrado":"s", "Triangulo":"^", ...}` |
| `PALETA_CATEGORIAS` | 15 colores distintos para categorizacion automatica |
| `SIMBOLOGIA_CAPAS_EXTRA` | Estilos por defecto para Hidrografia, Vias, Parcelas, Zonas protegidas |

**Clase `ConfigSimbologia`**

Configuracion de estilo individual para un elemento.

| Atributo | Tipo | Default |
|---|---|---|
| `color` | str | `"#E74C3C"` |
| `linewidth` | float | 2.5 |
| `linestyle` | str | `"-"` |
| `alpha` | float | 0.85 |
| `marker` | str | `"o"` |
| `markersize` | float | 6.0 |
| `facecolor` | str | `"none"` |
| `label` | str | `""` |

Metodos: `to_dict()`, `from_dict(d)` (serializacion).

**Clase `GestorSimbologia`**

Gestor central de simbologia para todas las capas.

| Atributo | Tipo | Descripcion |
|---|---|---|
| `categorias` | `dict[str, dict[str, ConfigSimbologia]]` | Categorias de infraestructuras |
| `capas_extra` | `dict[str, ConfigSimbologia]` | Estilos de capas extra |
| `montes` | `ConfigSimbologia` | Estilo base de montes |
| `categorias_montes` | `dict[str, dict[str, ConfigSimbologia]]` | Categorias de montes |
| `infra_fondo` | `ConfigSimbologia` | Estilo de fondo de infraestructura |

| Metodo | Descripcion |
|---|---|
| `generar_por_categoria(campo, valores)` | Genera paleta automatica para valores de infraestructura |
| `generar_por_categoria_montes(campo, valores)` | Genera paleta automatica (tonos verdes) para montes |
| `obtener_simbologia_infra(campo, valor)` | Obtiene estilo de infra por categoria |
| `obtener_simbologia_monte(campo, valor)` | Obtiene estilo de monte por categoria |
| `obtener_simbologia_capa(nombre)` | Obtiene estilo de capa extra |
| `set_simbologia_capa(nombre, simb)` | Establece estilo de capa extra |
| `to_dict() / from_dict(d)` | Serializacion completa |

---

### 4.6. `plantillas_layout.py` — Plantillas de Layout (45 lineas)

Define las dos plantillas de maquetacion disponibles.

**`PLANTILLAS_DISPONIBLES`:** `["Plantilla 1 (Clasica)", "Plantilla 2 (Panel lateral)"]`

**`LAYOUTS`:**

| Plantilla | Tipo | Grid | Descripcion |
|---|---|---|---|
| Plantilla 1 (Clasica) | `clasica` | 2 filas x 3 cols | Mapa arriba (75%), panel inferior: cajetin (28%) + atributos (42%) + minimapa (30%) |
| Plantilla 2 (Panel lateral) | `lateral` | 1 fila x 2 cols | Mapa izquierda (80%), panel derecho (20%): minimapa + tabla + leyenda + cajetin |

---

### 4.7. `proyecto.py` — Persistencia de Proyecto (260 lineas)

Guarda/carga toda la configuracion del proyecto en formato JSON.

**Clase `Proyecto`**

Campos principales (todos serializables):

| Grupo | Campos |
|---|---|
| Capas | `ruta_infra, ruta_montes, ruta_raster_general, ruta_raster_localizacion, ruta_capa_localizacion` |
| Mapa | `formato, proveedor, escala_manual, transparencia_montes, transparencia_infra, color_infra` |
| WMS/WFS custom | `wms_custom_general, wfs_custom_general, wms_custom_localizacion, wfs_custom_localizacion` |
| Localizacion | `prov_localizacion, escala_localizacion` |
| Layout | `layout_key` (plantilla seleccionada, default: "Plantilla 2 (Panel lateral)") |
| Campos | `campos_visibles, campo_mapeo, campo_encabezado` |
| Excel | `origen_datos_tabla, ruta_excel_tabla, hoja_excel_tabla, campo_enlace_shp, campo_enlace_excel, columnas_excel_activas` |
| Generacion | `modo_gen, rango_desde, rango_hasta, campo_agrupacion, multipagina, incluir_portada` |
| Salida | `carpeta_salida, patron_nombre, calidad_pdf` |
| Metadatos | `cajetin, plantilla, capas_extra, simbologia, fecha_creacion, fecha_modificacion` |

| Metodo | Descripcion |
|---|---|
| `to_dict() -> dict` | Serializa a diccionario JSON-compatible |
| `from_dict(d) -> Proyecto` | Deserializa desde diccionario |
| `guardar(ruta: str)` | Guarda a archivo JSON |
| `cargar(ruta: str) -> Proyecto` | Carga desde archivo JSON |

**Funcion `cargar_lotes_csv(ruta_csv) -> list[dict]`**
Lee configuracion de lotes desde CSV (columnas: ruta_shp, nombre, formato, carpeta_salida).

---

### 4.8. `capas_extra.py` — Capas Adicionales (158 lineas)

Permite cargar capas vectoriales adicionales (hidrografia, vias, parcelas, etc.).

**Clase `CapaExtra`**

| Atributo | Tipo | Descripcion |
|---|---|---|
| `nombre` | str | Nombre de la capa |
| `ruta` | str | Ruta al archivo |
| `gdf` | GeoDataFrame | Datos cargados |
| `tipo` | str | Tipo: Hidrografia, Vias, Parcelas, Zonas protegidas, Personalizada |
| `visible` | bool | Visible en el mapa |

**Clase `GestorCapasExtra`**

| Metodo | Descripcion |
|---|---|
| `cargar_capa(ruta, nombre, tipo, layer) -> (bool, str, CapaExtra)` | Carga SHP/GDB, auto-reproyecta a EPSG:25830 |
| `eliminar_capa(nombre)` | Elimina capa por nombre |
| `obtener_capas_visibles() -> list[CapaExtra]` | Capas con visible=True |
| `dibujar_en_mapa(ax, xmin, xmax, ymin, ymax, gestor_simb)` | Renderiza capas visibles en el eje |
| `obtener_items_leyenda(gestor_simb) -> list` | Items de leyenda: (label, color, geom_type, ...) |
| `to_dict() / cargar_desde_dict(data)` | Serializacion/deserializacion |

---

### 4.9. `paginas_especiales.py` — Portada, Indice, Mapa Guia (277 lineas)

Genera paginas especiales para PDFs multipagina.

| Funcion | Descripcion |
|---|---|
| `crear_portada(formato, titulo, subtitulo, datos_extra, cajetin, plantilla) -> Figure` | Pagina de portada con titulo, organizacion y datos |
| `crear_indice(formato, items, plantilla) -> Figure` | Pagina de indice (hasta 35 items por pagina) |
| `crear_mapa_guia(formato, gdf_infra, indices, gdf_montes, ...) -> Figure` | Mapa con todas las infraestructuras numeradas + lista en leyenda |

---

### 4.10. `perfil.py` — Perfil Topografico (139 lineas)

Genera perfiles longitudinales a lo largo de geometrias lineales.

| Funcion | Descripcion |
|---|---|
| `calcular_perfil_desde_geometria(geom, n_puntos=50) -> (distancias, coords)` | Extrae puntos equidistantes a lo largo de la geometria |
| `estimar_pendiente(geom) -> float` | Pendiente (%) desde coordenadas Z inicio/fin |
| `generar_elevaciones_sinteticas(distancias, z_base=500, variacion=50) -> array` | Perfil de elevacion sintetico (demo) |
| `dibujar_perfil(ax, distancias, elevaciones, titulo, color_relleno, color_linea)` | Renderiza perfil topografico en eje matplotlib |

---

### 4.11. `_elementos_mapa.py` — Elementos Cartograficos (360 lineas)

Mixin que proporciona metodos de dibujo de elementos cartograficos. Heredado por `MaquetadorPlano`.

**Clase `ElementosMapaMixin`**

| Metodo | Descripcion |
|---|---|
| `_formato_coord(valor) -> str` | Formatea coordenada UTM con separador de miles (508000 → "508.000") |
| `dibujar_grid_utm(xmin, xmax, ymin, ymax)` | Grid UTM con ticks etiquetados en los 4 bordes + info ETRS89 |
| `dibujar_escala_grafica_mapa()` | Barra de escala grafica 4 segmentos en esquina inferior izquierda |
| `dibujar_etiquetas_infra(gdf, campo, campo_mapeo)` | Etiquetas de infraestructuras con adjustText anti-solapamiento |
| `dibujar_etiquetas_montes(gdf, campo, campo_mapeo)` | Etiquetas de montes en italica, color rosa |
| `dibujar_vertices_numerados(geom) -> list` | Vertices numerados a intervalos regulares |
| `dibujar_leyenda(items, stats)` | Leyenda con muestras de simbolo + etiquetas (punto/linea/poligono) |
| `dibujar_norte_en_mapa()` | Flecha de norte minimalista (triangulos claro/oscuro + "N") |

---

### 4.12. `_utils_geo.py` — Utilidades Geoespaciales (151 lineas)

Funciones compartidas de manejo de CRS, geometrias y calculo.

| Funcion | Descripcion |
|---|---|
| `_asegurar_crs(gdf, origen="") -> (GeoDataFrame, str)` | Verifica/asigna CRS, reproyecta a EPSG:25830 si necesario |
| `_detectar_geom_type(gdf) -> str` | Tipo de geometria predominante (point, line, polygon) |
| `_plot_gdf_por_tipo(gdf, ax, ...)` | Dibuja GeoDataFrame separando por tipo de geometria |
| `_limpiar_tipos_mixtos(gdf) -> GeoDataFrame` | Convierte columnas de tipo mixto a strings |
| `_auto_calcular_campos(gdf) -> GeoDataFrame` | Calcula Longitud (m) para lineas, Superficie (ha) para poligonos |
| `_calcular_stats_grupo(gdf) -> dict` | Estadisticas: num_infraestructuras, total_longitud_km, total_superficie_ha |
| `_leer_geodatos(ruta, layer=None) -> GeoDataFrame` | Lee SHP/GDB con fallback OpenFileGDB |

---

## 5. Modulo GUI (`generador_planos/gui/`)

Interfaz grafica construida con tkinter/ttk. Tema oscuro profesional.

### 5.1. `estilos.py` — Paleta y Widgets (319 lineas)

**Paleta de colores:**

| Constante | Color | Uso |
|---|---|---|
| `COLOR_FONDO_APP` | `#0F1923` | Fondo principal (azul noche oscuro) |
| `COLOR_PANEL` | `#162230` | Fondo de paneles/secciones |
| `COLOR_PANEL_ALT` | `#1B2B3D` | Panel alternativo (hover/activo) |
| `COLOR_ACENTO` | `#10B981` | Acento esmeralda (primario) |
| `COLOR_ACENTO2` | `#34D399` | Esmeralda claro (hover) |
| `COLOR_ACENTO3` | `#059669` | Esmeralda oscuro (pulsado) |
| `COLOR_TEXTO` | `#E8ECF1` | Texto principal (blanco suave) |
| `COLOR_TEXTO_GRIS` | `#8899AA` | Texto secundario (gris) |
| `COLOR_BORDE` | `#243447` | Bordes y separadores |
| `COLOR_ENTRY` | `#0D1620` | Fondo de campos de texto |
| `COLOR_HOVER` | `#1E3348` | Estado hover |
| `COLOR_ERROR` | `#EF4444` | Error (rojo) |
| `COLOR_ADVERTENCIA` | `#F59E0B` | Advertencia (amarillo) |
| `COLOR_EXITO` | `#10B981` | Exito (verde) |
| `COLOR_HEADER` | `#0B1219` | Barra superior |

**Fuentes:**

| Constante | Valor |
|---|---|
| `FONT_TITULO` | Segoe UI 18 bold |
| `FONT_SUBTITULO` | Segoe UI 12 bold |
| `FONT_LABEL` | Segoe UI 10 |
| `FONT_SMALL` | Segoe UI 9 |
| `FONT_BOLD` | Segoe UI 10 bold |
| `FONT_MONO` | Consolas 9 |
| `FONT_SECCION` | Segoe UI 9 bold |
| `FONT_BOTON` | Segoe UI 9 |

**Funciones fabrica:**

| Funcion | Descripcion |
|---|---|
| `aplicar_estilos(root)` | Configura estilos TTK globales |
| `crear_frame_seccion(parent, titulo, colapsable=False) -> Frame` | Seccion con titulo y linea de acento |
| `crear_boton(parent, texto, comando, estilo="normal") -> Button` | Boton con hover (estilos: primario, peligro, normal) |
| `crear_entry(parent, textvariable, width) -> Entry` | Campo de texto estilizado |
| `crear_label(parent, text, tipo="normal") -> Label` | Etiqueta (tipos: titulo, secundario, acento, normal) |

---

### 5.2. `app.py` — Ventana Principal (614 lineas)

**Clase `App(tk.Tk)`**

Ventana principal que orquesta todos los paneles. Tamano minimo: 1100x780 px.

**Layout de la ventana:**

```
+---------------------------------------------------------------+
|  BARRA SUPERIOR: Titulo app + CRS badge + Guardar/Cargar      |
+-------------------+-------------------------------------------+
| PANEL IZQUIERDO   |  TABLA DE INFRAESTRUCTURAS                |
| (scrollable)      |  (Treeview con filas del shapefile)        |
|                   |                                           |
| - Panel Capas     |                                           |
| - Panel Filtros   |                                           |
| - Panel Simbologia|                                           |
| - Panel Campos    +-------------------------------------------+
| - Panel Cajetin   |  LOG DE PROCESO                           |
| - Panel Config    |  (terminal verde sobre negro)             |
| - Panel Generacion|                                           |
+-------------------+-------------------------------------------+
```

**Paneles hijos (en orden de workflow):**

| Panel | Clase | Descripcion |
|---|---|---|
| Capas | `PanelCapas` | Carga SHP/GDB de infraestructuras y montes |
| Filtros | `PanelFiltros` | Filtrado avanzado de la tabla |
| Simbologia | `PanelSimbologia` | Colores y estilos por categoria |
| Campos | `PanelCampos` | Seleccion de campos visibles en el plano |
| Cajetin | `PanelCajetin` | Datos del cajetin y plantilla de colores |
| Configuracion | `PanelConfig` | Formato, proveedor, escala, calidad PDF, Excel |
| Generacion | `PanelGeneracion` | Modos de generacion, progreso, preview |

**Metodos principales:**

| Metodo | Descripcion |
|---|---|
| `_construir_ui()` | Construye toda la interfaz |
| `_barra_superior()` | Header con titulo y botones de proyecto |
| `_crear_panel_tabla(parent)` | Treeview de datos con scrollbars |
| `_crear_panel_log(parent)` | Widget de log con colores (error/ok/warn/info) |
| `_escribir_log(msg, tipo)` | Escribe en log (thread-safe) |
| `_poblar_tabla(indices=None)` | Rellena tabla con filas del GeoDataFrame |
| `_on_tabla_cargada()` | Callback: actualiza todos los paneles dependientes |
| `_on_montes_cargados()` | Callback: actualiza cajetin y simbologia |
| `_on_filtro_aplicado(indices)` | Callback: filtra tabla |
| `_auto_aplicar_todo()` | Sincroniza toda la UI con el motor antes de generar |
| `_get_config() -> dict` | Retorna config completa para generacion |
| `_guardar_proyecto()` | Guarda estado completo a JSON |
| `_cargar_proyecto()` | Restaura estado desde JSON |

---

### 5.3. `panel_capas.py` — Carga de Capas (578 lineas)

**Clase `PanelCapas`**

Gestiona la carga de shapefiles y geodatabases, transparencia y capas extra.

**Componentes UI:**
- Botones de carga SHP + GDB para infraestructuras
- Botones de carga SHP + GDB para montes
- 2 sliders de transparencia (infraestructuras y montes)
- Lista de capas extra con botones +SHP / +GDB / Eliminar
- Mini canvas de previsualizacion

**Metodos principales:**

| Metodo | Descripcion |
|---|---|
| `_cargar_infra()` | Dialogo para cargar SHP de infraestructuras |
| `_cargar_montes()` | Dialogo para cargar SHP de montes |
| `_cargar_infra_gdb() / _cargar_montes_gdb()` | Carga desde geodatabase |
| `_seleccionar_gdb(titulo) -> (ruta, capa)` | Seleccion interactiva de GDB y capa |
| `_añadir_capa_extra() / _añadir_capa_extra_gdb()` | Anade capas adicionales |
| `_eliminar_capa_extra()` | Elimina capa seleccionada |
| `_previsualizar(gdf)` | Muestra preview en mini-canvas |
| `_dialogo_mapeo_campos(faltantes)` | Dialogo de mapeo cuando faltan campos esperados |
| `_ejecutar_en_hilo(tarea, ok, error, msg)` | Ejecucion en hilo separado con spinner |

---

### 5.4. `panel_config.py` — Configuracion General (683 lineas)

**Clase `PanelConfig`**

Panel mas complejo de la GUI. Controla formato, proveedor cartografico, rasters, WMS/WFS, escala, color, calidad PDF, Excel y salida.

**Secciones UI:**
- **Formato:** Combobox A4/A3/A2 Horizontal
- **Proveedor cartografico:** Combobox con frames condicionales (raster local, WMS custom, WFS custom)
- **Proveedor localizacion:** Idem para mapa de posicion
- **Escala:** Manual o automatica
- **Color infraestructura:** Selector de color
- **Calidad PDF:** Borrador / Normal / Alta / Maxima
- **Origen datos tabla:** Shapefile o Excel (con frame condicional para Excel)
- **Patron de nombre:** Plantilla de nombre de archivo con preview
- **Carpeta de salida:** Selector de directorio

**Propiedades (lectura):**

| Propiedad | Tipo | Descripcion |
|---|---|---|
| `calidad_pdf` | str | Etiqueta de calidad seleccionada |
| `dpi_figura / dpi_guardado` | int | DPI segun calidad |
| `color_infra` | str | Color hex de infraestructura |
| `escala_manual` | int/None | Escala manual o None (auto) |
| `usa_excel` | bool | True si origen es Excel |
| `ruta_excel / hoja_excel` | str | Ruta y hoja del Excel |
| `campo_enlace_shp / campo_enlace_excel` | str | Campos de enlace SHP-Excel |
| `columnas_excel_activas` | list | Columnas Excel seleccionadas |
| `ruta_raster_general / ruta_raster_localizacion` | str | Rutas de raster local |
| `ruta_capa_localizacion` | str | Capa vectorial para posicion |
| `wms_custom_general / wfs_custom_general` | dict | Config WMS/WFS personalizado |
| `wms_custom_localizacion / wfs_custom_localizacion` | dict | Config localizacion |
| `escala_localizacion` | int | Escala del mapa de posicion |

---

### 5.5. `panel_campos.py` — Campos Visibles (126 lineas)

**Clase `PanelCampos`**

Checkboxes para seleccionar que campos del shapefile aparecen en el plano.

| Metodo | Descripcion |
|---|---|
| `actualizar_campos(columnas)` | Reconstruye checkboxes con nuevas columnas |
| `obtener_campos_activos() -> list` | Lista de campos marcados |
| `obtener_campo_encabezado() -> str/None` | Campo para encabezado del plano |
| `_sel_todos() / _sel_ninguno()` | Marcar/desmarcar todos |

---

### 5.6. `panel_cajetin.py` — Cajetin y Plantilla (310 lineas)

**Clase `PanelCajetin`**

Editor del cajetin (cuadro de titulo) y la plantilla de colores.

**Campos del cajetin:**
- Autor, Cargo autor, Proyecto, Num. proyecto
- Firma, Cargo firma, Revision, Cargo revision
- Organizacion, Titulo mapa, Subtitulo, Campo subtitulo
- Logo (selector de archivo), Num plano inicio
- Campo etiqueta infraestructuras, Campo etiqueta montes

**Colores de la plantilla:**
- `color_cabecera_fondo`, `color_cabecera_texto`, `color_cabecera_acento`
- `color_marco_exterior`, `color_marco_interior`

| Metodo | Descripcion |
|---|---|
| `obtener_cajetin() -> dict` | Retorna todos los campos del cajetin |
| `obtener_plantilla() -> dict` | Retorna colores de la plantilla |
| `obtener_layout_key() -> str` | Plantilla de layout seleccionada |
| `cargar_desde_proyecto(cajetin, plantilla)` | Restaura desde proyecto guardado |
| `actualizar_campos_subtitulo(columnas)` | Actualiza dropdown de campo subtitulo |
| `actualizar_campos_montes(columnas)` | Actualiza dropdown de etiqueta montes |

---

### 5.7. `panel_simbologia.py` — Simbologia (368 lineas)

**Clase `PanelSimbologia`**

Editor visual de simbologia para infraestructuras, montes y capas extra.

**Secciones:**
- **Infraestructuras:** Campo de categoria + selectores de color por valor
- **Estilo linea:** Grosor (slider 0.5-15), transparencia (0.1-1.0), tipo de trazo, marcador
- **Montes:** Color base + campo de categoria + selectores por valor
- **Capas extra:** Color por capa cargada

| Metodo | Descripcion |
|---|---|
| `_on_campo_cat_changed(event)` | Actualiza selectores de color por categoria de infra |
| `_on_campo_cat_montes_changed(event)` | Idem para montes |
| `obtener_config_infra() -> dict` | Config: linewidth, alpha, linestyle, marker, campos_categoria |
| `actualizar_capas_extra()` | Refresca lista de capas extra |
| `_aplicar()` | Aplica toda la simbologia al motor |

---

### 5.8. `panel_filtros.py` — Filtros Avanzados (186 lineas)

**Clase `PanelFiltros`**

Filtrado de la tabla de infraestructuras con multiples criterios.

**Filtros disponibles:**
- Busqueda de texto libre (con debounce 300ms)
- Filtro por campo + valor (comboboxes)
- Rango de superficie (ha): min - max
- Rango de longitud (m): min - max

| Metodo | Descripcion |
|---|---|
| `_aplicar_filtros()` | Aplica todos los filtros activos, muestra contador de resultados |
| `_limpiar_filtros()` | Limpia todos los filtros |
| `actualizar_campos()` | Actualiza dropdown de campos con columnas del shapefile |

---

### 5.9. `panel_generacion.py` — Control de Generacion (938 lineas)

**Clase `PanelGeneracion`**

Panel mas grande de la GUI. Controla todos los modos de generacion.

**Modos de generacion:**

| Modo | Descripcion |
|---|---|
| Todos | Un plano por cada fila del shapefile |
| Seleccionados | Solo filas seleccionadas en la tabla |
| Rango | Desde fila N hasta fila M |
| Agrupado | Un plano por grupo (campo + valores seleccionados) |
| Lotes CSV | Generacion desde archivo CSV de configuracion |

**Opciones adicionales:**
- **PDF multipagina:** Un unico PDF con todas las paginas
- **Incluir portada:** Portada + indice + mapa guia al inicio del PDF

**Componentes UI:**
- 5 RadioButtons de modo
- Entradas de rango (desde/hasta)
- Selector de campo de agrupacion + selector de valores
- Selector de CSV
- Checkbox multipagina + portada
- Barra de progreso (ttk.Progressbar)
- Etiqueta de progreso (n/total)
- Boton Vista Previa
- Boton Mapa Guia
- Boton GENERAR (estilo primario grande)
- Boton PARAR (estilo peligro)
- Boton Abrir Carpeta
- Boton Vaciar Cache

| Metodo | Descripcion |
|---|---|
| `_iniciar_generacion()` | Punto de entrada principal, delega al worker correcto |
| `_iniciar_generacion_todos/rango/agrupado/csv()` | Workers especificos por modo |
| `_actualizar_progreso(actual, total)` | Actualiza barra y label de progreso |
| `_parar_generacion()` | Solicita cancelacion |
| `_vista_previa()` | Genera preview de baja resolucion |
| `_mapa_guia()` | Genera mapa guia con infra numeradas |
| `_mostrar_preview(fig)` | Muestra figura en ventana popup |
| `actualizar_campos_agrupacion()` | Refresca campos de agrupacion |

---

## 6. Scripts de Build y Distribucion

### 6.1. `build_exe.py` — Ejecutable PyInstaller (233 lineas)

Genera ejecutable Windows con PyInstaller. Dos modos:

| Modo | Descripcion | Resultado |
|---|---|---|
| 1 - Carpeta | Distribucion con dependencias separadas | `dist/GeneradorPlanos/` (arranque rapido) |
| 2 - Archivo unico | Todo empaquetado en un .exe | `dist/GeneradorPlanos.exe` (mas portable, arranque lento) |

Incluye 15+ hidden imports (matplotlib, contextily, geopandas, pyproj, shapely, numpy, PIL, reportlab, requests, certifi, pyogrio, xyzservices). Excluye pytest, pip, IPython, jupyter, sphinx.

### 6.2. `build_portable.py` — Portable Single-File (363 lineas)

Genera un ejecutable portable unico (~150-300 MB) que no requiere Python instalado.

**Salida:**
- `dist/GeneradorPlanos_Portable.exe`
- `GeneradorPlanos_Portable_v2.0.zip` (listo para distribuir)

Incluye metadatos de version Windows, configuracion automatica de backend Agg para matplotlib.

### 6.3. `installer.iss` — Instalador Inno Setup (68 lineas)

Script para crear instalador profesional Windows con Inno Setup.

| Campo | Valor |
|---|---|
| Aplicacion | Generador de Planos Forestales v2.0 |
| Publisher | Jose Caballero |
| Directorio | Program Files\GeneradorPlanos |
| Salida | Output/InstaladorPlanos_v2.0.exe |
| Compresion | LZMA2 ultra64 |
| Idioma | Espanol + Ingles |

Crea iconos de escritorio y barra de inicio rapido. Requiere ejecutar `build_exe.py` (modo carpeta) previamente.

---

## 7. Tests Unitarios (`tests/`)

48 tests organizados en 4 archivos. Ejecutar con `pytest`:

```bash
pytest tests/ -v
```

### 7.1. `test_utils_geo.py` (169 lineas)

| Clase Test | Tests | Cubre |
|---|---|---|
| `TestAsegurarCRS` | 3 | Preservacion EPSG:25830, reproyeccion desde 4326, auto-deteccion CRS |
| `TestDetectarGeomType` | 3 | Deteccion Point, LineString, Polygon; GeoDataFrame vacio |
| `TestLimpiarTiposMixtos` | 2 | Limpieza columnas tipo mixto, preservacion geometria |
| `TestAutoCalcularCampos` | 3 | Calculo Longitud (m), Superficie (ha), no-sobreescritura |
| `TestCalcularStatsGrupo` | 2 | Estadisticas de grupo, manejo campos faltantes |

### 7.2. `test_simbologia.py` (76 lineas)

| Clase Test | Tests | Cubre |
|---|---|---|
| `TestConfigSimbologia` | 2 | Valores por defecto, serializacion roundtrip |
| `TestGestorSimbologia` | 5 | Generacion categorias, obtencion simbolo, fallback, diversidad colores, serializacion |
| `TestConstantes` | 3 | TIPOS_TRAZO, MARCADORES, PALETA_CATEGORIAS (>=10 colores) |

### 7.3. `test_proyecto.py` (61 lineas)

| Test | Cubre |
|---|---|
| Creacion proyecto vacio | Valores por defecto |
| Serializacion a dict | to_dict() |
| Roundtrip to_dict/from_dict | Integridad datos |
| Guardar/cargar archivo JSON | Persistencia en disco |
| Validez JSON | Formato correcto |
| Preservacion formato y cajetin | Campos especificos |

### 7.4. `test_escala.py` (107 lineas)

| Test | Cubre |
|---|---|
| Constantes | ESCALAS ordenadas, FORMATOS correctos, INTERVALOS_GRID, BARRA_ESCALA_M |
| Escala manual | Override de escala automatica |
| Auto-seleccion | Geometria pequena → escala baja, grande → escala alta |
| Tipos geometria | Point, LineString, Polygon |
| Formato | Impacto del formato en la escala |
| Extremos | Geometria enorme → escala maxima |
| Lateral | Impacto de orientacion lateral |

---

## 8. Assets

| Archivo | Descripcion |
|---|---|
| `assets/icon.ico` | Icono de la aplicacion (multi-resolucion: 16-256 px) |
| `assets/crear_icono.py` | Script generador del icono: circulo azul oscuro + mapa verde + arbol + punto rojo |

---

## 9. Legacy

| Archivo | Descripcion |
|---|---|
| `legacy/generador_planos_v1.py` | Version monolitica v1.0 (1333 lineas). Aplicacion completa en un solo archivo. Mantenida como referencia. |

---

## 10. Funcionalidades Implementadas

### 10.1. Carga de datos
- Shapefiles (.shp) y Geodatabases (.gdb) de infraestructuras y montes
- Reproyeccion automatica a ETRS89 UTM Huso 30N (EPSG:25830)
- Calculo automatico de Longitud (m) para lineas y Superficie (ha) para poligonos
- Mapeo interactivo de campos cuando faltan los esperados
- Carga de capas extra (hidrografia, vias, parcelas, zonas protegidas, personalizada)
- Vinculacion con tabla Excel externa

### 10.2. Cartografia de fondo
- **Teselas XYZ:** OpenStreetMap, PNOA Ortofoto, IGN Topografico, Stamen Terrain
- **WMS directo:** IGN MTN25 (1:25.000), IGN MTN50 (1:50.000)
- **WMS/WFS personalizado:** URL, capa y formato configurables
- **Raster local:** GeoTIFF, ECW, JP2 con lectura windowed
- **Mosaico virtual:** Construccion automatica de VRT desde carpeta de hojas
- Cache en disco persistente entre sesiones

### 10.3. Seleccion de escala
- Escalas: 1:5.000, 1:7.500, 1:10.000, 1:15.000, 1:20.000, 1:25.000, 1:30.000
- Seleccion automatica segun extension de geometria + formato de papel
- Override manual disponible
- Ajuste para orientacion lateral (Plantilla 2)

### 10.4. Maquetacion del plano
- **Plantilla 1 (Clasica):** Mapa arriba (75%), panel inferior con cajetin + atributos + minimapa
- **Plantilla 2 (Panel lateral):** Mapa izquierda (80%), panel derecho con minimapa + tabla + leyenda + cajetin institucional
- Formatos: A4, A3, A2 (horizontal)
- Grid UTM con etiquetas de coordenadas en los 4 bordes
- Barra de escala grafica de 4 segmentos
- Flecha de norte minimalista
- Cabecera con logo + titulo + subtitulo + numero de plano
- Marco doble profesional con copyright vertical
- Mapa de posicion con fondo cartografico

### 10.5. Panel de atributos
- Tabla de campos seleccionables por el usuario
- Filas alternas con fondo diferente (tabla zebra)
- Soporte para datos de shapefile o Excel vinculado
- Sistema de referencia y escala al pie

### 10.6. Simbologia por categorias
- Categorizacion automatica de infraestructuras por campo de atributo
- Categorizacion automatica de montes por campo de atributo (paleta de verdes)
- Colores editables por valor
- Estilos configurables: grosor, transparencia, tipo de trazo, marcador
- Simbologia independiente para capas extra
- Leyenda automatica con todos los elementos

### 10.7. Generacion en serie
- **Todos:** Un plano por cada fila del shapefile
- **Seleccionados:** Solo filas seleccionadas en la tabla
- **Rango:** Desde fila N hasta fila M
- **Agrupado:** Un plano por grupo (campo + valores seleccionados)
- **Lotes CSV:** Configuracion desde archivo CSV
- **PDF multipagina:** Un unico PDF con portada + indice + mapa guia + todos los planos
- Barra de progreso en tiempo real
- Log de proceso con colores
- Cancelacion en cualquier momento
- Nombre de archivo configurable con patron

### 10.8. Paginas especiales (PDF multipagina)
- Portada con titulo, organizacion y datos del proyecto
- Indice con lista numerada de infraestructuras
- Mapa guia con todas las infraestructuras numeradas y leyenda

### 10.9. Filtros avanzados
- Busqueda de texto libre con debounce
- Filtro por campo + valor
- Rangos de superficie (ha) y longitud (m)

### 10.10. Gestion de proyectos
- Guardar/cargar toda la configuracion en JSON
- Incluye: capas, formato, proveedor, escala, simbologia, cajetin, plantilla, campos, Excel, generacion

---

## 11. Ejecucion

### Desde codigo fuente:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicacion
python -m generador_planos

# Ejecutar tests
pytest tests/ -v
```

### Puntos de entrada:

| Comando | Archivo | Descripcion |
|---|---|---|
| `python -m generador_planos` | `__main__.py` → `main.py` | Arranque con splash screen |
| `generador-planos` | CLI entry point (pyproject.toml) | Idem tras `pip install` |
| `generador-planos-gui` | GUI entry point (pyproject.toml) | Idem |

### Construir ejecutable Windows:

```bash
# Opcion 1: Carpeta con dependencias
python build_exe.py    # elegir modo 1

# Opcion 2: Ejecutable portable unico
python build_portable.py

# Opcion 3: Instalador Windows (requiere Inno Setup + build_exe modo 1)
# Compilar installer.iss con Inno Setup
```

---

## 12. Configuracion del Proyecto (`pyproject.toml`)

```toml
[project]
name = "generador-planos-forestales"
version = "2.0.0"
requires-python = ">=3.9"
license = "MIT"
keywords = ["cartografia", "forestal", "planos", "SHP", "PDF", "INFOCA"]
```

**Entry points CLI:**
- `generador-planos` → `generador_planos.main:main`
- `generador-planos-gui` → `generador_planos.main:main`

---

## 13. Flujo de Trabajo Tipico

1. **Cargar** shapefile de infraestructuras (SHP o GDB)
2. **Cargar** shapefile de montes (opcional)
3. **Configurar** formato de papel, proveedor cartografico, escala
4. **Seleccionar** campos visibles en el plano
5. **Configurar** cajetin (autor, proyecto, organizacion)
6. **Ajustar** simbologia (colores por categoria, grosor, transparencia)
7. **Filtrar** infraestructuras si es necesario
8. **Vista previa** para verificar el resultado
9. **Generar** planos en el modo deseado
10. **Guardar** proyecto para reutilizar la configuracion

---

*Documento generado automaticamente. Ultima actualizacion: 2026-03-30.*

