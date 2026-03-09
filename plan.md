# Plan de implementación: 3 funcionalidades nuevas

## 1. SISTEMA DE PLANTILLAS (Plantilla 1 = actual, Plantilla 2 = estilo Junta de Andalucía)

### Concepto
La "plantilla" actual controla colores de cabecera/marcos. Ampliaremos el concepto para incluir **layout completo** (distribución de paneles, posiciones, tamaños).

### Plantilla 1 (actual)
- Layout actual: Mapa arriba (75%), panel inferior dividido en 3 columnas (cajetín 28%, atributos 42%, minimapa 30%)
- Se mantiene tal cual, sin cambios

### Plantilla 2 (estilo Junta de Andalucía - imagen de referencia)
- **Mapa principal** ocupa ~75% izquierda de la página
- **Panel lateral derecho** (~25%) contiene de arriba a abajo:
  - Mapa de situación (minimapa)
  - Tabla de atributos (formato tabla con columnas: COD_INFR, NOMBRE_INFR, TIPO_TRAB, etc.)
  - Leyenda dividida en: Tipo Infraestructura + Montes Públicos
  - Logo + título institucional
  - Cajetín: proyecto, autor, firmas, nº plano, escala, fecha

### Cambios necesarios

**Archivo nuevo: `motor/plantillas_layout.py`**
- Diccionario `LAYOUTS` con dos claves: `"Plantilla 1 (Clásica)"` y `"Plantilla 2 (Panel lateral)"`
- Cada layout define:
  - GridSpec config (nrows, ncols, width_ratios, height_ratios)
  - Posiciones de cada eje (mapa, info, mini, escala/cajetin)
  - Ratios de mapa

**Archivo: `motor/maquetacion.py`**
- `crear_figura()` recibe parámetro `layout_key` y usa la config del layout seleccionado
- Nueva distribución para Plantilla 2: GridSpec 1 fila × 2 columnas, con el panel derecho subdivido verticalmente
- Nuevos métodos de dibujo adaptados al panel lateral:
  - `dibujar_panel_atributos_lateral()` — tabla con columnas tipo spreadsheet
  - `dibujar_leyenda_lateral()` — leyenda con dos secciones (infraestructura + montes)
  - `dibujar_cajetin_lateral()` — cajetín con estructura de la imagen

**Archivo: `gui/panel_cajetin.py`**
- Añadir selector de layout (combobox "Plantilla 1" / "Plantilla 2")
- Almacenar selección en variable `layout_key`

**Archivo: `gui/app.py`**
- Pasar `layout_key` a la config y al motor

**Archivo: `motor/generador.py`**
- Pasar `layout_key` a `MaquetadorPlano` en todas las funciones de generación

**Archivo: `motor/proyecto.py`**
- Añadir campo `layout_key` para guardar/cargar

---

## 2. WMS 1:25.000 (IGN MTN25)

### URLs disponibles
El IGN España ofrece WMTS con la capa MTN que incluye el topográfico 1:25.000.
Ya existe "IGN Topográfico" que usa esta misma capa (`LAYER=MTN`), pero con `GoogleMapsCompatible` (Web Mercator).

Para mayor calidad a escala 1:25.000, se puede usar el **TileMatrixSet nativo en EPSG:25830** que ofrece resolución de 5.04 m/pixel (escala ~1:25.000).

### Enfoque: WMS directo (no WMTS tiles)
Añadir soporte WMS `GetMap` que solicita una imagen completa para el bbox exacto. Esto da mejor calidad que tiles a escalas específicas.

### Cambios necesarios

**Archivo: `motor/cartografia.py`**
- Añadir entrada en `CAPAS_BASE`: `"IGN MTN25 (WMS 1:25.000)"`
- URL WMS: `https://www.ign.es/wms-inspire/mapa-raster?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=mtn_rasterizado&CRS=EPSG:25830&FORMAT=image/png&WIDTH={w}&HEIGHT={h}&BBOX={bbox}`
- Nueva función `_descargar_wms()` que calcula el bbox en EPSG:25830, resuelve WIDTH/HEIGHT según DPI, y descarga la imagen completa
- Modificar `añadir_fondo_cartografico()` para detectar si el proveedor es WMS (no tiles) y usar la nueva función
- Añadir en `PROVIDERS_CTX` y `_PROV_META`

---

## 3. COLOREAR MONTES POR CAMPO DE ATRIBUTOS

### Concepto
Similar a como ya funciona la categorización de infraestructuras: el usuario elige un campo del shapefile de montes y cada valor único se colorea con un color distinto.

### Cambios necesarios

**Archivo: `motor/simbologia.py`**
- Añadir `categorias_montes = {}` en `GestorSimbologia`
- Método `generar_por_categoria_montes(campo, valores)` — genera paleta automática
- Método `obtener_simbologia_monte(campo_cat, valor)` — obtiene color por valor

**Archivo: `motor/generador.py`**
- En `_dibujar_capas_mapa()`: si hay categorización de montes activa, hacer plot por categoría en vez de color fijo
- En `_construir_items_leyenda()`: añadir items de montes por categoría

**Archivo: `gui/panel_simbologia.py`**
- Añadir sección "Colorear montes por campo" debajo de la sección de infraestructuras
- Combobox con campos del shapefile de montes + "(ninguno)"
- Lista de valores con color editable (mismo patrón que infraestructuras)

**Archivo: `gui/app.py`**
- Pasar campo de categorización de montes al motor

**Archivo: `motor/proyecto.py`**
- Guardar/cargar configuración de categorización de montes

---

## Orden de implementación

1. **WMS 1:25.000** — cambio más contenido, sin cambios de UI complejos
2. **Colorear montes por campo** — reutiliza patrón existente de infraestructuras
3. **Sistema de plantillas** — el más complejo, requiere nuevo layout completo
