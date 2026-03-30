"""
Panel de informacion tecnica y manual de usuario.

Muestra las caracteristicas tecnicas de la aplicacion, tecnologias usadas,
arquitectura del sistema y un manual de usuario completo.
"""

import tkinter as tk
from tkinter import ttk

from .estilos import (
    COLOR_FONDO_APP, COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS,
    COLOR_BORDE, COLOR_ACENTO, COLOR_ACENTO2, COLOR_ENTRY, COLOR_HEADER,
    FONT_BOLD, FONT_SMALL, FONT_SECCION, FONT_MONO, FONT_SUBTITULO,
)


# ── Contenido de las secciones ─────────────────────────────────────────

FICHA_TECNICA = """
FICHA TECNICA DE LA APLICACION
==============================

  Nombre:        EstelaGis — Planos Forestales
  Version:       2.0.0
  Autor:         Jose Caballero Sanchez
  Ubicacion:     Cazorla (Jaen), 2026
  Licencia:      MIT
  Python:        >= 3.9
  Plataformas:   Windows, Linux, macOS
  Interfaz:      Aplicacion de escritorio (Tkinter)
  Distribucion:  PyPI / PyInstaller (ejecutable Windows)


PROPOSITO
=========

EstelaGis es una aplicacion de escritorio para la generacion
automatizada de planos cartograficos profesionales en formato
PDF (A3/A4, horizontal/vertical) para la gestion de
infraestructuras forestales del servicio INFOCA (Plan de
Emergencias por Incendios Forestales de Andalucia).

Permite producir lotes de planos con maquetacion normalizada,
cajetin reglamentario, simbologia categorizada, cuadriculas UTM,
leyendas, escalas graficas y mapas de localizacion.
"""

STACK_TECNOLOGICO = """
STACK TECNOLOGICO
=================

CAPA DE INTERFAZ (GUI)
----------------------
  tkinter             Framework nativo Python para GUI de escritorio
  ttk                 Widgets tematizados (Combobox, Treeview, Notebook...)
  Tema visual         Oscuro (Blue-Night #0F1923 + Esmeralda #10B981)
  Layout              Sidebar scroll + Panel derecho (tabla + log)
  Scroll              Canvas con mousewheel (Linux/Windows)

CAPA GEOESPACIAL (GIS)
-----------------------
  geopandas >= 0.14   Lectura de Shapefiles (.shp) y Geodatabases (.gdb)
                      Manipulacion de GeoDataFrames, reproyeccion CRS
  shapely >= 2.0      Operaciones geometricas (buffer, interseccion,
                      centroide, bounds, simplificacion)
  pyproj >= 3.6       Transformacion de coordenadas entre SRC
                      EPSG:25830 (ETRS89 / UTM zona 30N) como base
  contextily >= 1.6   Descarga de teselas WMS/WMTS para fondos de mapa
                      (PNOA, OpenStreetMap, Stamen, etc.)

CAPA DE RENDERIZADO
--------------------
  matplotlib >= 3.8   Motor principal de renderizado cartografico
                      GridSpec para maquetacion multi-panel
                      Artists para cuadricula UTM, barra de escala,
                      leyenda, rosa de los vientos
  adjustText >= 1.0   Algoritmo anti-solapamiento de etiquetas
  Pillow >= 10.0      Manipulacion de imagenes (logos, fondos raster)
  numpy >= 1.26       Calculos geometricos y transformaciones

CAPA DE SALIDA
---------------
  reportlab >= 4.0    Generacion final de documentos PDF
                      Soporte A3/A4 horizontal/vertical
                      Multipagina (portada, indice, planos, guia)

CAPA DE DATOS
--------------
  openpyxl >= 3.1     Lectura de archivos Excel (.xlsx)
                      Enlace de datos tabulares con capas SHP
  requests >= 2.31    Descarga de teselas y servicios WMS/WFS/WCS
  JSON                Persistencia de proyectos (.json)

OPCIONAL
---------
  pyinstaller >= 6.0  Empaquetado como ejecutable Windows (.exe)
"""

ARQUITECTURA = """
ARQUITECTURA DEL SISTEMA
=========================

Patron:  MVC simplificado (Motor + GUI)
Modulos: 2 paquetes principales (gui/ y motor/)

generador_planos/
  |
  +-- gui/                     CAPA DE PRESENTACION
  |   +-- app.py               Ventana principal, orquestacion de paneles
  |   +-- estilos.py           Paleta de colores, fuentes, temas TTK
  |   +-- panel_capas.py       Carga de capas SHP/GDB + transparencia
  |   +-- panel_filtros.py     Filtros avanzados por campo/valor
  |   +-- panel_simbologia.py  Editor de simbologia por categorias
  |   +-- panel_campos.py      Selector de campos visibles
  |   +-- panel_cajetin.py     Editor de cajetin y plantillas de layout
  |   +-- panel_config.py      Configuracion de salida (formato, proveedor)
  |   +-- panel_generacion.py  Control de generacion y barra de progreso
  |   +-- panel_info.py        Info tecnica y manual de usuario
  |
  +-- motor/                   CAPA DE LOGICA DE NEGOCIO
      +-- generador.py         Clase GeneradorPlanos (coordinador central)
      +-- maquetacion.py       Maquetacion y renderizado del mapa
      +-- cartografia.py       Descarga de teselas WMS/WFS/raster
      +-- escala.py            Seleccion automatica de escala
      +-- simbologia.py        Gestor de simbologia por categorias
      +-- proyecto.py          Persistencia de proyecto en JSON
      +-- capas_extra.py       Gestion de capas auxiliares
      +-- paginas_especiales.py Portada, indice, mapa guia
      +-- perfil.py            Perfil longitudinal topografico
      +-- plantillas_layout.py Definiciones de plantillas de layout
      +-- _elementos_mapa.py   Cuadricula UTM, escala, leyenda, norte
      +-- _utils_geo.py        Utilidades geoespaciales compartidas


FLUJO DE DATOS
===============

  1. Carga SHP/GDB --> GeoDataFrame (geopandas)
  2. Reproyeccion a ETRS89 UTM 30N (EPSG:25830)
  3. Filtrado y seleccion de registros
  4. Calculo de extent y escala automatica
  5. Descarga de fondo cartografico (WMS/WMTS/raster)
  6. Renderizado con matplotlib (GridSpec layout)
  7. Adicion de elementos: cuadricula UTM, escala, leyenda
  8. Exportacion a PDF via reportlab
  9. Opcion multipagina: portada + indice + planos + guia
"""

ESPECIFICACIONES_CARTOGRAFICAS = """
ESPECIFICACIONES CARTOGRAFICAS
===============================

SISTEMA DE REFERENCIA
  SRC base:          ETRS89 / UTM zona 30N (EPSG:25830)
  Reproyeccion:      Automatica desde cualquier CRS de entrada

ESCALAS PERMITIDAS
  1:5.000  |  1:7.500  |  1:10.000  |  1:15.000  |  1:20.000
  Seleccion automatica basada en el extent de la geometria
  Opcion de escala manual configurable

FORMATOS DE SALIDA
  A3 Horizontal (420 x 297 mm)
  A3 Vertical   (297 x 420 mm)
  A4 Horizontal (297 x 210 mm)
  A4 Vertical   (210 x 297 mm)

PROVEEDORES DE FONDO
  PNOA Ortofoto   (IGN - Espana)
  PNOA Mapa Base   (IGN - Espana)
  OpenStreetMap
  Stamen Terrain
  CartoDB Positron / DarkMatter
  Raster local     (GeoTIFF, ECW, MrSID)
  WMS/WFS custom   (URL configurable)

ELEMENTOS DEL PLANO
  Cuadricula UTM con etiquetas de coordenadas
  Barra de escala grafica (metros/km)
  Rosa de los vientos (flecha norte)
  Leyenda de simbologia
  Cajetin reglamentario (personalizable)
  Mapa de localizacion (esquina inferior)
  Tabla de datos asociada (opcional)

MODOS DE GENERACION
  Individual       Un plano por registro
  Todos             Todos los registros del SHP
  Seleccion         Solo registros seleccionados
  Rango             Rango numerico (desde-hasta)
  Agrupado          Por campo (ej: por municipio)
  Lote CSV          Lista de IDs desde archivo CSV
  Multipagina       PDF unico con portada + indice

SIMBOLOGIA
  Por categorias (campo seleccionable)
  Colores personalizables por categoria
  Tamano de punto/linea configurable
  Transparencia ajustable
  Patron de relleno (solo poligonos)
"""

MANUAL_USUARIO = """
MANUAL DE USUARIO
==================

1. INICIO RAPIDO
-----------------
  1. Ejecute EstelaGis (estelagis o python -m generador_planos)
  2. Cargue un Shapefile (.shp) o Geodatabase (.gdb) de infraestructuras
  3. Opcionalmente cargue una capa de Montes Publicos
  4. Configure el formato de salida (A3/A4)
  5. Seleccione la carpeta de salida
  6. Pulse "GENERAR PLANOS"

2. CARGA DE DATOS
------------------
  Panel "CAPAS DE DATOS" (primer panel del sidebar):

  * Infraestructuras: Pulse "Cargar SHP/GDB" para seleccionar el archivo
    con las infraestructuras forestales (pistas, cortafuegos, puntos de agua...).
    - Si es una Geodatabase (.gdb), se le pedira seleccionar la capa.
    - Si los campos no coinciden con los esperados, se abrira un dialogo
      de mapeo de campos para asignar la correspondencia.
    - La capa se reproyecta automaticamente a ETRS89 UTM 30N.

  * Montes: Pulse "Cargar Montes" para anadir la capa de montes publicos.
    Esta capa se usa como fondo y para el mapa de localizacion.

  * Capas extra: Anada capas SHP/GDB adicionales (hidrografia, carreteras...)
    con su propia simbologia y transparencia.

  * Transparencia: Ajuste los deslizadores para controlar la opacidad
    de las capas de montes e infraestructuras.

3. FILTRADO DE DATOS
---------------------
  Panel "FILTROS":

  * Seleccione un campo del shapefile
  * Elija un operador (=, !=, contiene, >, <, etc.)
  * Introduzca el valor de filtro
  * Pulse "Aplicar filtro" para filtrar los registros
  * La tabla se actualiza mostrando solo los registros que cumplen
  * Puede combinar multiples filtros

4. SIMBOLOGIA
--------------
  Panel "SIMBOLOGIA":

  * Campo de categoria: Seleccione el campo por el cual categorizar
  * Se generaran colores automaticos para cada valor unico
  * Puede personalizar el color de cada categoria haciendo clic
  * Ajuste el tamano del simbolo y la transparencia
  * La simbologia se aplica automaticamente al generar

5. CAMPOS VISIBLES
-------------------
  Panel "CAMPOS":

  * Marque/desmarque los campos que desea mostrar en la tabla del plano
  * Seleccione un campo de encabezado para el titulo de cada plano
  * Los campos marcados aparecen en la tabla dentro del PDF

6. CAJETIN Y PLANTILLA
------------------------
  Panel "CAJETIN":

  * Titulo: Texto principal del cajetin
  * Subtitulo: Puede usar campos del SHP con {NOMBRE_CAMPO}
  * Organismo: Entidad que emite el plano
  * Autor: Nombre del tecnico/autor
  * Fecha: Se autocompleta con la fecha actual
  * Layout: Elija la distribucion del plano (clasico, compacto, etc.)

7. CONFIGURACION DE SALIDA
----------------------------
  Panel "CONFIGURACION":

  * Formato: A3H, A3V, A4H, A4V
  * Proveedor de fondo: PNOA, OSM, Stamen, raster local, WMS custom...
  * Escala: Automatica o manual (1:5.000 a 1:20.000)
  * Color de infraestructura: Color por defecto para simbolos
  * Carpeta de salida: Donde se guardaran los PDF generados
  * Patron de nombre: Formato del nombre de archivo
    Ejemplo: {TIPO}_{NOMBRE}_{MUNICIPIO} --> Pista_FortalezaAlta_Cazorla.pdf
  * Calidad PDF: Baja (150dpi), Media (200dpi), Alta (300dpi)

  Datos tabulares:
  * Origen: Desde el shapefile o desde un archivo Excel
  * Si elige Excel: seleccione archivo, hoja, campo de enlace
  * Configure que columnas del Excel mostrar en el plano

8. GENERACION DE PLANOS
-------------------------
  Panel "GENERACION":

  * Modo:
    - Todos: Genera un plano por cada registro
    - Seleccion: Solo los seleccionados en la tabla
    - Rango: Desde registro N hasta registro M
    - Agrupado: Agrupa por un campo (ej: por municipio)
    - Lote CSV: Lee IDs desde un archivo CSV

  * Multipagina: Genera un unico PDF con todos los planos
    - Incluye portada con titulo y datos del proyecto
    - Incluye indice con listado de planos y paginas
    - Incluye mapa guia general al final

  * Incluir portada: Anade pagina de portada al multipagina

  * Pulse "GENERAR PLANOS" para iniciar el proceso
  * La barra de progreso muestra el avance
  * El log de proceso muestra mensajes detallados
  * Puede cancelar la generacion en cualquier momento

9. PROYECTOS
--------------
  * Guardar proyecto: Barra superior > "Guardar"
    Guarda toda la configuracion actual en un archivo JSON
    (capas, simbologia, cajetin, formato, filtros, etc.)

  * Cargar proyecto: Barra superior > "Cargar"
    Restaura la configuracion desde un archivo JSON guardado

10. ATAJOS Y CONSEJOS
-----------------------
  * La tabla derecha muestra las infraestructuras cargadas.
    Puede seleccionar registros para generacion individual.

  * El log de proceso (parte inferior derecha) muestra:
    - Verde: Operaciones completadas con exito
    - Amarillo: Advertencias
    - Rojo: Errores
    - Azul: Informacion del sistema

  * Use "Escala manual = 0" para seleccion automatica de escala.

  * Los campos de subtitulo admiten variables:
    {CAMPO} se sustituye por el valor del registro actual.

  * Para geodatabases grandes, la carga puede tardar.
    La previsualizacion rapida se muestra en miniatura.

  * El CRS se muestra en la barra superior como badge:
    "ETRS89 - UTM H30N" (EPSG:25830)
"""


class PanelInfo:
    """Ventana emergente con informacion tecnica y manual de usuario."""

    def __init__(self, parent):
        self.parent = parent

    def mostrar(self):
        """Abre la ventana de informacion."""
        win = tk.Toplevel(self.parent)
        win.title("EstelaGis — Informacion Tecnica y Manual de Usuario")
        win.geometry("820x680")
        win.minsize(700, 500)
        win.configure(bg=COLOR_FONDO_APP)
        win.transient(self.parent)
        win.grab_set()

        # ── Header ──
        header = tk.Frame(win, bg=COLOR_HEADER, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="\u2139\ufe0f  EstelaGis — Informacion Tecnica",
            font=("Segoe UI", 13, "bold"), bg=COLOR_HEADER, fg=COLOR_TEXTO,
        ).pack(side="left", padx=16, pady=10)

        tk.Label(
            header, text="v2.0.0",
            font=("Segoe UI", 10, "bold"), bg=COLOR_HEADER, fg=COLOR_ACENTO,
        ).pack(side="right", padx=16)

        # ── Notebook (pestanas) ──
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Pestana 1: Ficha Tecnica
        tab_ficha = self._crear_tab_texto(nb, FICHA_TECNICA)
        nb.add(tab_ficha, text="  Ficha Tecnica  ")

        # Pestana 2: Stack Tecnologico
        tab_stack = self._crear_tab_texto(nb, STACK_TECNOLOGICO)
        nb.add(tab_stack, text="  Stack Tecnologico  ")

        # Pestana 3: Arquitectura
        tab_arq = self._crear_tab_texto(nb, ARQUITECTURA)
        nb.add(tab_arq, text="  Arquitectura  ")

        # Pestana 4: Especificaciones Cartograficas
        tab_carto = self._crear_tab_texto(nb, ESPECIFICACIONES_CARTOGRAFICAS)
        nb.add(tab_carto, text="  Cartografia  ")

        # Pestana 5: Manual de Usuario
        tab_manual = self._crear_tab_texto(nb, MANUAL_USUARIO)
        nb.add(tab_manual, text="  Manual de Usuario  ")

        # ── Boton cerrar ──
        btn_frame = tk.Frame(win, bg=COLOR_FONDO_APP)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        btn_cerrar = tk.Button(
            btn_frame, text="Cerrar", command=win.destroy,
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_ACENTO, fg="#FFFFFF",
            activebackground=COLOR_ACENTO2, activeforeground="#FFFFFF",
            relief="flat", cursor="hand2", padx=20, pady=6,
            bd=0, highlightthickness=0,
        )
        btn_cerrar.pack(side="right")

        # Hover
        btn_cerrar.bind("<Enter>", lambda e: btn_cerrar.configure(bg=COLOR_ACENTO2))
        btn_cerrar.bind("<Leave>", lambda e: btn_cerrar.configure(bg=COLOR_ACENTO))

    def _crear_tab_texto(self, notebook, contenido):
        """Crea una pestana con texto scrollable."""
        frame = tk.Frame(notebook, bg=COLOR_FONDO_APP)

        text_widget = tk.Text(
            frame,
            font=FONT_MONO,
            bg=COLOR_ENTRY,
            fg="#6EE7B7",
            relief="flat",
            state="normal",
            padx=16,
            pady=12,
            bd=0,
            wrap="word",
            selectbackground=COLOR_ACENTO,
            selectforeground="#FFFFFF",
            insertbackground=COLOR_ACENTO,
            highlightthickness=1,
            highlightbackground=COLOR_BORDE,
            highlightcolor=COLOR_ACENTO,
        )

        scrollbar = ttk.Scrollbar(frame, orient="vertical",
                                   command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        text_widget.pack(side="left", fill="both", expand=True)

        # Insertar contenido con formato
        text_widget.insert("1.0", contenido.strip())

        # Tags de formato
        text_widget.tag_config("titulo",
                                foreground=COLOR_ACENTO,
                                font=("Consolas", 11, "bold"))
        text_widget.tag_config("subtitulo",
                                foreground=COLOR_ACENTO2,
                                font=("Consolas", 10, "bold"))
        text_widget.tag_config("separador",
                                foreground=COLOR_BORDE)

        # Aplicar formato a titulos (lineas con === o ---)
        self._aplicar_formato(text_widget)

        text_widget.configure(state="disabled")
        return frame

    def _aplicar_formato(self, text_widget):
        """Aplica formato visual a titulos y subtitulos en el texto."""
        content = text_widget.get("1.0", "end")
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()

            # Lineas de separacion (=== o ---)
            if stripped and all(c == "=" for c in stripped) and len(stripped) > 3:
                start = f"{line_num}.0"
                end = f"{line_num}.end"
                text_widget.tag_add("separador", start, end)
                # La linea anterior es un titulo
                if line_num > 1:
                    prev_start = f"{line_num - 1}.0"
                    prev_end = f"{line_num - 1}.end"
                    text_widget.tag_add("titulo", prev_start, prev_end)

            elif stripped and all(c == "-" for c in stripped) and len(stripped) > 3:
                start = f"{line_num}.0"
                end = f"{line_num}.end"
                text_widget.tag_add("separador", start, end)
                # La linea anterior es un subtitulo
                if line_num > 1:
                    prev_start = f"{line_num - 1}.0"
                    prev_end = f"{line_num - 1}.end"
                    text_widget.tag_add("subtitulo", prev_start, prev_end)
