# 🗺 Generador de Planos Forestales — Especificación de Proyecto

## Contexto
Aplicación de escritorio Python para generación de planos cartográficos profesionales en serie (PDF A3/A4), orientada a infraestructuras forestales de Andalucía (INFOCA / Junta de Andalucía).

El código base inicial está en `generador_planos.py` y necesita ser completado, refinado y testeado.

---

## Stack tecnológico

| Librería | Uso |
|---|---|
| `tkinter` | GUI de escritorio |
| `geopandas` | Lectura de Shapefiles, reproyección CRS |
| `matplotlib` | Renderizado cartográfico y maquetación del plano |
| `contextily` | Descarga de teselas WMS/WMTS de fondo |
| `pyproj` | Transformación de coordenadas |
| `reportlab` | Generación final de PDF |
| `Pillow` | Manipulación de imágenes |
| `numpy` | Cálculos geométricos |

---

## Funcionalidades requeridas

### 1. Carga de capas
- [x] Shapefile de infraestructuras → reproyectado a **ETRS89 UTM Huso 30N (EPSG:25830)**
- [x] Shapefile de montes (opcional) → con **slider de transparencia**
- [ ] Validación de campos obligatorios al cargar el shapefile
- [ ] Previsualización rápida de la capa en un mini-canvas al cargarla

### 2. Cartografía de fondo (teselas)
Opciones disponibles mediante `contextily`:
- `OpenStreetMap` — teselas estándar
- `PNOA Ortofoto (IGN)` — WMTS IGN España
- `IGN Topográfico (MTN)` — WMTS IGN España
- `Stamen Terrain` — terreno con relieve

> ⚠️ Las URLs de IGN son WMTS con parámetros `{z}/{y}/{x}`. Verificar compatibilidad con contextily o implementar descarga manual de teselas si falla.

### 3. Selección automática de escala
Escalas permitidas (solo estas, nunca otras):
```
1:5.000 | 1:7.500 | 1:10.000 | 1:15.000 | 1:20.000
```
La escala se elige automáticamente según la extensión de la geometría + márgenes del 20%.

### 4. Maquetación del plano (matplotlib)

#### Estructura del plano (GridSpec):
```
┌──────────────────────────────────────────────────────────┐
│  CABECERA: Logo org. | Título infra | Nº plano            │
├─────────────────────────────┬────────────────────────────┤
│                             │                            │
│     MAPA PRINCIPAL (63%)    │  PANEL ATRIBUTOS (37%)     │
│     con grid UTM            │  tabla campos + escala     │
│     + fondo WMS             │  + CRS                     │
│     + capa montes           │                            │
│     + infraestructura       ├────────────────────────────┤
│       resaltada             │  MAPA DE POSICIÓN          │
│                             │  (España con punto rojo)   │
├─────────────────────────────┴────────────────────────────┤
│  BARRA ESCALA GRÁFICA + NORTE + CRÉDITOS CARTOGRAFÍA     │
├──────────────────────────────────────────────────────────┤
│  MARCO DOBLE EXTERIOR (profesional)                      │
└──────────────────────────────────────────────────────────┘
```

#### Formatos de salida:
- A4 Vertical: 210×297 mm
- A4 Horizontal: 297×210 mm
- A3 Vertical: 297×420 mm
- A3 Horizontal: 420×297 mm

#### Márgenes (mm):
```python
izquierdo: 20mm | derecho: 15mm | superior: 15mm | inferior: 30mm
```

### 5. Grid de coordenadas UTM
- Líneas de cuadrícula punteadas azul oscuro
- Cruces en intersecciones
- Etiquetas de coordenadas UTM en bordes del mapa
- Intervalo según escala:
  ```
  1:5.000  → 500 m
  1:7.500  → 500 m
  1:10.000 → 1.000 m
  1:15.000 → 1.000 m
  1:20.000 → 2.000 m
  ```

### 6. Panel de atributos
Campos a mostrar (extraídos de la tabla de atributos del Shapefile):

| Campo Shapefile | Etiqueta en plano |
|---|---|
| `Provincia` | Provincia |
| `Municipio` | Municipio |
| `Monte` | Monte |
| `Cod_Monte` | Código Monte |
| `CEDEFO` | CEDEFO |
| `Cod_Infoca` | Cód. INFOCA |
| `Nombre_Infra` | Nombre Infraestructura |
| `Superficie` | Superficie (ha) |
| `Longitud` | Longitud (m) |
| `Ancho` | Ancho (m) |
| `Tipo_Trabajos` | Tipo de Trabajos |

- Filas alternas con fondo diferente (tabla legible)
- Al pie del panel: **Sistema de referencia** y **Escala**
- El usuario puede activar/desactivar cada campo desde la UI

### 7. Mapa de posición
- Muestra contorno de España
- Punto rojo en la ubicación de la infraestructura
- Coordenadas convertidas de EPSG:25830 → EPSG:4326 para el mini-mapa
- Título "LOCALIZACIÓN"

### 8. Barra de escala gráfica
- Barra bicolor (blanco/negro) con divisiones
- `1:5.000–1:10.000` → barra de 1.000 m
- `1:15.000–1:20.000` → barra de 2.000 m
- Flecha de Norte
- Créditos de cartografía + fecha

### 9. Generación en serie
Modos:
- **Todos** → genera plano por cada fila del shapefile
- **Seleccionados** → solo los seleccionados en la tabla de la UI
- **Rango** → desde fila N hasta fila M

Salida:
- Un PDF por infraestructura
- Nombre: `plano_0001_NombreInfra.pdf`
- En carpeta elegida por el usuario
- Barra de progreso + log en tiempo real (hilo separado para no bloquear UI)

---

## GUI — Diseño y paleta

### Paleta de colores
```python
COLOR_FONDO_APP  = "#1C2333"   # fondo principal oscuro
COLOR_PANEL      = "#242D40"   # paneles laterales
COLOR_ACENTO     = "#2ECC71"   # verde forestal
COLOR_ACENTO2    = "#27AE60"
COLOR_TEXTO      = "#ECF0F1"
COLOR_TEXTO_GRIS = "#95A5A6"
COLOR_BORDE      = "#2C3E50"
COLOR_ERROR      = "#E74C3C"
COLOR_EXITO      = "#27AE60"
```

### Layout de la ventana (1100×780 px mínimo, redimensionable)
```
┌─────────────────────────────────────────────────────────────┐
│  🗺 GENERADOR DE PLANOS FORESTALES          ETRS89·UTM H30N │
├──────────────────┬──────────────────────────────────────────┤
│ 📂 CAPAS         │  TABLA DE INFRAESTRUCTURAS               │
│  - Infra SHP     │  (Treeview con filas de la capa)         │
│  - Montes SHP    │                                          │
│  - Transparencia │                                          │
├──────────────────┤                                          │
│ ⚙ CONFIGURACIÓN  │                                          │
│  - Formato A3/A4 ├──────────────────────────────────────────┤
│  - Cartografía   │  LOG DE PROCESO                          │
│  - Color infra   │  (terminal verde sobre negro)            │
│  - Carpeta sal.  │                                          │
├──────────────────┤                                          │
│ 🏷 CAMPOS PLANO  │                                          │
│  (checkboxes)    │                                          │
├──────────────────┤                                          │
│ 🖨 GENERACIÓN    │                                          │
│  - Modo (todos / │                                          │
│    selec/rango)  │                                          │
│  - Progreso      │                                          │
│  - [GENERAR]     │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## Pendiente / Bugs conocidos

- [ ] **Teselas IGN**: las URLs WMTS del IGN pueden requerir implementación manual (requests + PIL) si contextily no las soporta directamente. Implementar fallback.
- [ ] **Escala real garantizada**: verificar que los límites del eje matplotlib correspondan exactamente a los metros calculados con la escala elegida (no dejar que matplotlib reajuste).
- [ ] **Geometrías punto**: el cálculo de extensión cuando la geometría es un punto puro devuelve 0. Usar radio mínimo de 500 m centrado en el punto.
- [ ] **Cabecera dinámica**: el `add_axes` de la cabecera debe calcularse tras conocer el GridSpec real.
- [ ] **Hilo de generación**: asegurarse de que matplotlib no comparte estado entre hilos (usar `plt.switch_backend('Agg')` al inicio del hilo).
- [ ] **Shapefile con campos distintos**: si el shapefile no tiene exactamente los nombres de campo esperados, mostrar diálogo de mapeo de campos.
- [ ] **Exportación a PDF multipágina**: opción para generar un único PDF con todos los planos en páginas consecutivas (usando reportlab PdfWriter o matplotlib PdfPages).

---

## Estructura de archivos sugerida

```
generador_planos/
├── main.py                  # Punto de entrada
├── motor/
│   ├── __init__.py
│   ├── generador.py         # Clase GeneradorPlanos
│   ├── cartografia.py       # Descarga teselas WMS/WMTS
│   ├── maquetacion.py       # Layout matplotlib del plano
│   └── escala.py            # Lógica de selección de escala
├── gui/
│   ├── __init__.py
│   ├── app.py               # Ventana principal (App)
│   ├── panel_capas.py
│   ├── panel_config.py
│   ├── panel_campos.py
│   ├── panel_generacion.py
│   └── estilos.py           # Paleta + ttk styles
├── assets/
│   └── logo.png             # Logo opcional org.
├── requirements.txt
└── README.md
```

---

## requirements.txt

```
geopandas>=0.14
matplotlib>=3.8
numpy>=1.26
requests>=2.31
Pillow>=10.0
contextily>=1.6
pyproj>=3.6
reportlab>=4.0
```

---

## Notas adicionales para Claude Code

1. El archivo `generador_planos.py` contiene la versión monolítica inicial. Refactorizar según la estructura de archivos de arriba.
2. Priorizar que **la escala sea métrica real**: 1 mm en papel = `escala/1000` metros en el terreno. Esto debe ser exacto.
3. El **grid UTM debe mostrarse en metros** (no en grados), ya que todo está en EPSG:25830.
4. La **barra de escala gráfica** debe calcularse en función del DPI y tamaño de figura real, no de forma aproximada.
5. Para el mapa de posición usar el contorno de España como GeoJSON embebido o descargado de Natural Earth, no un polígono dibujado a mano.
6. El plano debe verse **idéntico al generado por QGIS Print Layout** en cuanto a profesionalidad: marcos dobles, tipografía limpia, sin elementos flotando.
