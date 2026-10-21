"""
Ventana principal de la aplicacion EstelaGis.

Disposición tipo escritorio SIG (QGIS / ArcGIS Pro):

    ┌──────────────────── barra de herramientas ─────────────────────┐
    │ panel lateral │              lienzo de mapa                    │
    │  (pestañas:   │                                                │
    │  Capas,       ├────────────────────────────────────────────────┤
    │  Filtros...)  │  Tabla de atributos (N) │ Registro             │
    ├───────────────┴────────────────────────────────────────────────┤
    │ barra de estado: mensaje · progreso · coordenadas · escala · CRS│
    └────────────────────────────────────────────────────────────────┘

Los separadores (sash) son arrastrables y sus posiciones se recuerdan en
los ajustes, igual que la geometría de la ventana.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import estilos
from .estilos import (
    COLOR_FONDO_APP, COLOR_ACENTO, COLOR_ACENTO2, COLOR_TEXTO_GRIS,
    COLOR_PANEL, COLOR_PANEL_ALT, COLOR_TEXTO, COLOR_BORDE, COLOR_HEADER,
    COLOR_ENTRY, COLOR_HOVER, COLOR_FILA_PAR, COLOR_FILA_IMPAR,
    COLOR_LOG_FONDO, COLOR_LOG_TEXTO, COLOR_LOG_OK, COLOR_LOG_ERROR,
    COLOR_LOG_WARN, COLOR_LOG_INFO, COLOR_TITULO_SECCION,
    FONT_BOLD, FONT_MONO, FONT_SMALL, FONT_SUBTITULO, FONT_SECCION,
    FONT_BOTON, FONT_MINI,
    aplicar_estilos, crear_boton, crear_tooltip, crear_frame_seccion,
    crear_label, BotonHerramienta, separador_vertical,
)
from .panel_capas import PanelCapas
from .panel_config import PanelConfig
from .panel_campos import PanelCampos
from .panel_filtros import PanelFiltros
from .panel_simbologia import PanelSimbologia
from .panel_cajetin import PanelCajetin
from .panel_generacion import PanelGeneracion
from .panel_info import PanelInfo
from .panel_mapa import PanelMapa, TablaContenidos, CRS_TEXTO
from . import recientes
from ..motor.generador import GeneradorPlanos
from ..motor.proyecto import Proyecto
from ..motor.escala import FORMATOS
from ..motor.maquetacion import CALIDADES_PDF
from ..motor.plantillas_layout import PLANTILLAS_DISPONIBLES


ANCHO_PANEL_LATERAL = 360     # px por defecto del panel lateral
ALTO_PANEL_INFERIOR = 260     # px por defecto de tabla/registro
ANCHO_MIN_LATERAL = 330


# ── Contenedor desplazable para cada pestaña del panel lateral ──────────

class MarcoDesplazable(tk.Frame):
    """Frame con scroll vertical cuyo ancho sigue al contenido.

    - El ancho pedido por el canvas = ancho pedido por el contenido
      (mín. 320 px), de modo que el panel nunca recorta los controles.
    - Si el canvas es más ancho que el contenido, el contenido se estira
      hasta el ancho del canvas.
    """

    def __init__(self, parent):
        super().__init__(parent, bg=COLOR_PANEL, bd=0, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=COLOR_PANEL, highlightthickness=0,
                                bd=0, width=320)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                       command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, bg=COLOR_PANEL, bd=0)
        self._win = self.canvas.create_window((0, 0), window=self.interior,
                                              anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.interior.bind("<Configure>", self._on_interior)
        self.canvas.bind("<Configure>", self._on_canvas)

    def _on_interior(self, _event=None):
        self.canvas.configure(
            scrollregion=self.canvas.bbox("all"),
            width=max(self.interior.winfo_reqwidth(), 320))

    def _on_canvas(self, event):
        req = self.interior.winfo_reqwidth()
        self.canvas.itemconfigure(self._win, width=max(event.width, req))

    def desplazar(self, unidades: int):
        try:
            primero, ultimo = self.canvas.yview()
        except Exception:
            return
        if primero <= 0.0 and ultimo >= 1.0:
            return  # todo el contenido cabe: nada que desplazar
        self.canvas.yview_scroll(unidades, "units")

    def ancho_necesario(self) -> int:
        return self.interior.winfo_reqwidth() + self.scrollbar.winfo_reqwidth()


class BarraPestanas(tk.Frame):
    """Barra de pestañas que se reparte en varias filas si no cabe.

    Controla un ``ttk.Notebook`` con estilo sin pestañas propias
    ("Dock.TNotebook"): así los 7 nombres completos se ven siempre, sin
    recortes, aunque el panel lateral sea estrecho.
    """

    def __init__(self, parent, notebook):
        super().__init__(parent, bg=COLOR_HEADER, bd=0)
        self.notebook = notebook
        self._pestanas = []   # [(frame, label)]
        self._filas = []
        self._ancho = 0
        self.bind("<Configure>", self._on_configure)
        notebook.bind("<<NotebookTabChanged>>", lambda e: self._pintar(),
                      add="+")

    def añadir(self, frame, texto):
        lbl = tk.Label(self, text=texto, font=FONT_SECCION, bd=0,
                       padx=9, pady=4, cursor="hand2",
                       highlightthickness=1)
        lbl.bind("<Button-1>", lambda e, f=frame: self.notebook.select(f))
        lbl.bind("<Enter>", lambda e, l=lbl, f=frame: self._hover(l, f, True))
        lbl.bind("<Leave>", lambda e, l=lbl, f=frame: self._hover(l, f, False))
        self._pestanas.append((frame, lbl))
        self._reflujo()
        self._pintar()

    def _seleccionado(self):
        try:
            return str(self.notebook.select())
        except Exception:
            return ""

    def _hover(self, lbl, frame, dentro):
        if str(frame) == self._seleccionado():
            return
        lbl.configure(bg=COLOR_HOVER if dentro else COLOR_HEADER)

    def _pintar(self):
        sel = self._seleccionado()
        for frame, lbl in self._pestanas:
            if str(frame) == sel:
                lbl.configure(bg=COLOR_PANEL, fg=COLOR_TITULO_SECCION,
                              highlightbackground=COLOR_BORDE)
            else:
                lbl.configure(bg=COLOR_HEADER, fg=COLOR_TEXTO_GRIS,
                              highlightbackground=COLOR_HEADER)

    def _on_configure(self, event):
        if abs(event.width - self._ancho) > 2:
            self._ancho = event.width
            self._reflujo()

    def _reflujo(self):
        """Reparte las pestañas en filas (cada fila con su propio ancho)."""
        ancho = self._ancho or ANCHO_PANEL_LATERAL
        filas, actual, usado = [], [], 4
        for _, lbl in self._pestanas:
            w = lbl.winfo_reqwidth() + 2
            if actual and usado + w > ancho:
                filas.append(actual)
                actual, usado = [], 4
            actual.append(lbl)
            usado += w
        if actual:
            filas.append(actual)
        while len(self._filas) < len(filas):
            self._filas.append(tk.Frame(self, bg=COLOR_HEADER))
        for i, f in enumerate(self._filas):
            f.pack_forget()
        for i, grupo in enumerate(filas):
            f = self._filas[i]
            f.pack(side="top", fill="x", padx=2, pady=(3 if i == 0 else 1, 0))
            for lbl in grupo:
                # Las etiquetas son hijas de la barra; se colocan dentro de
                # la fila con "in_" y se elevan sobre ella
                lbl.pack_forget()
                lbl.pack(in_=f, side="left", padx=(0, 2))
                lbl.lift(f)

    def textos(self):
        return [lbl.cget("text") for _, lbl in self._pestanas]


class App(tk.Tk):
    """Ventana principal de la aplicacion."""

    def __init__(self):
        super().__init__()
        self.title("EstelaGis — Planos Forestales")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1480, sw)}x{min(920, max(sh - 60, 760))}")
        self.minsize(1200, 700)
        self.configure(bg=COLOR_FONDO_APP)
        self.resizable(True, True)

        self.motor = GeneradorPlanos()
        self._ultimo_dir_proyecto = os.path.expanduser("~")
        self._n_ocupado = 0
        self._generando = False
        self._firma_mapa = None
        self._gdf_infra_mapa = None
        self._sash_pendiente = {}
        self._indices_filtro = None      # None = sin filtro
        self._indices_tabla = None       # filas mostradas (None = todas)
        self._cerrando = False

        self._establecer_icono()
        aplicar_estilos(self)
        self._desactivar_rueda_combobox()
        self._construir_ui()
        self._configurar_atajos()
        self._cargar_ajustes()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(200, self._colocar_separadores)
        self.after(300, self._sincronizar_barra)

    # ── Ajustes persistentes entre sesiones ──────────────────────────────

    def _recoger_ajustes(self) -> dict:
        """Opciones de la interfaz que merece la pena recordar."""
        try:
            datos = {
                "proveedor": self.panel_config.proveedor.get(),
                "formato": self.panel_config.formato.get(),
                "calidad_pdf": self.panel_config._calidad_pdf.get(),
                "prov_localizacion": self.panel_config._prov_localizacion.get(),
                "layout_key": self.panel_cajetin.obtener_layout_key(),
                "salida": self.panel_config.salida.get(),
                "patron_nombre": self.panel_config.patron_nombre.get(),
                "opciones_salida": self.panel_generacion.obtener_opciones_salida(),
                "tema": self._tema_elegido.get() if hasattr(
                    self, "_tema_elegido") else estilos.TEMA,
            }
        except Exception:
            return {}
        try:
            # Solo en estado normal (minimizada en Windows da +-32000)
            if self.state() == "normal":
                datos["geometria"] = self.geometry()
            else:
                from . import ajustes as _aj
                previa = _aj.cargar_ajustes().get("geometria")
                if previa:
                    datos["geometria"] = previa
        except Exception:
            pass
        try:
            datos["sash_izq"] = int(self._pw_principal.sashpos(0))
            # Alto del panel inferior (no la posición absoluta: así se
            # conserva al cambiar de resolución)
            datos["alto_inferior"] = int(self._pw_derecha.winfo_height()
                                         - self._pw_derecha.sashpos(0))
            datos["pestana_lateral"] = self._nb_lateral.index(
                self._nb_lateral.select())
        except Exception:
            pass
        return datos

    def _cargar_ajustes(self):
        """Restaura las últimas opciones usadas (si existen y son válidas)."""
        from . import ajustes
        datos = ajustes.cargar_ajustes()
        if not datos:
            return

        def _set_combo(combo, var, valor):
            # Solo aceptar valores que sigan existiendo en el desplegable
            try:
                if valor and valor in list(combo["values"]):
                    var.set(valor)
                    return True
            except Exception:
                pass
            return False

        pc = self.panel_config
        try:
            if _set_combo(pc._cb_prov, pc.proveedor, datos.get("proveedor")):
                pc._on_proveedor_changed()
            if _set_combo(pc._cb_prov_loc, pc._prov_localizacion,
                          datos.get("prov_localizacion")):
                pc._on_prov_loc_changed()
            if datos.get("formato") in FORMATOS:
                pc.formato.set(datos["formato"])
            if datos.get("calidad_pdf") in CALIDADES_PDF:
                pc._calidad_pdf.set(datos["calidad_pdf"])
            if datos.get("salida") and os.path.isdir(datos["salida"]):
                pc.salida.set(datos["salida"])
            if datos.get("patron_nombre"):
                pc.patron_nombre.set(datos["patron_nombre"])
            lk = datos.get("layout_key")
            if lk in PLANTILLAS_DISPONIBLES:
                self.panel_cajetin._layout_key.set(lk)
                self.motor.layout_key = lk
            self.panel_generacion.cargar_opciones_salida(
                datos.get("opciones_salida") or {})
            geo = self._geometria_en_pantalla(datos.get("geometria"))
            if geo:
                try:
                    self.geometry(geo)
                except Exception:
                    pass
            for clave in ("sash_izq", "alto_inferior"):
                v = datos.get(clave)
                if isinstance(v, int) and v > 0:
                    self._sash_pendiente[clave] = v
            pest = datos.get("pestana_lateral")
            if isinstance(pest, int) and 0 <= pest < len(self._marcos):
                self._nb_lateral.select(pest)
        except Exception as e:
            self._escribir_log(f"No se pudieron restaurar los ajustes: {e}", "warn")

    def _geometria_en_pantalla(self, geo):
        """Ajusta una geometría guardada a la pantalla actual (o None).

        Evita restaurar la ventana fuera de la pantalla (monitor
        desconectado, o la posición -32000 de una ventana minimizada).
        """
        import re
        if not isinstance(geo, str):
            return None
        m = re.fullmatch(r"(\d+)x(\d+)([+-]+-?\d+)?([+-]+-?\d+)?", geo.strip())
        if not m:
            return None
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = min(max(int(m.group(1)), 1200), sw)
        h = min(max(int(m.group(2)), 700), sh)

        def _num(g):
            try:
                return int(g.replace("+", "")) if g else 0
            except ValueError:
                return 0
        x, y = _num(m.group(3)), _num(m.group(4))
        x = min(max(x, 0), max(sw - w, 0))
        y = min(max(y, 0), max(sh - h, 0))
        return f"{w}x{h}+{x}+{y}"

    def _guardar_ajustes(self):
        from . import ajustes
        datos = self._recoger_ajustes()
        if datos:
            ajustes.guardar_ajustes(datos)

    def _al_cerrar(self):
        """Guarda los ajustes y cierra la ventana.

        Con una generación en marcha pide confirmación, la cancela y espera
        a que el hilo termine el plano en curso (matar el hilo daemon a
        mitad de un savefig dejaba PDFs truncados).
        """
        if self._cerrando:
            return
        if self.panel_generacion._generacion_en_curso():
            if not messagebox.askyesno(
                    "Generación en curso",
                    "Se están generando planos.\n\n¿Detener la generación y "
                    "cerrar la aplicación?\n(Los planos ya terminados se "
                    "conservan.)"):
                return
            self._cerrando = True
            self.motor.cancelar_generacion()
            self._escribir_log("Cerrando: esperando a que termine el plano "
                               "en curso…", "warn")
            self._set_estado("Cerrando: esperando a que termine el plano en curso…")
            self._esperar_y_cerrar()
            return
        try:
            self._guardar_ajustes()
        finally:
            self.destroy()

    def _esperar_y_cerrar(self, intentos=0):
        pg = self.panel_generacion
        if pg._generacion_en_curso() and intentos < 600:   # máx. ~2 min
            self.after(200, lambda: self._esperar_y_cerrar(intentos + 1))
            return
        try:
            self._guardar_ajustes()
        finally:
            self.destroy()

    # ── Icono de ventana ─────────────────────────────────────────────────

    def _establecer_icono(self):
        """Pone el icono de la app en la barra de título/tareas.

        Busca assets/icon.ico tanto en el repositorio como dentro del
        .exe (sys._MEIPASS). Si no existe o la plataforma no admite .ico,
        se deja el icono por defecto sin fallar.
        """
        import sys
        candidatos = []
        base_frozen = getattr(sys, "_MEIPASS", None)
        if base_frozen:
            candidatos.append(os.path.join(base_frozen, "assets", "icon.ico"))
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        candidatos.append(os.path.join(raiz, "assets", "icon.ico"))
        for ruta in candidatos:
            if os.path.isfile(ruta):
                try:
                    self.iconbitmap(ruta)
                    return
                except Exception:
                    continue

    # ── Errores no capturados en callbacks de Tk ─────────────────────────

    def report_callback_exception(self, exc, val, tb):
        """Registra y muestra errores de callbacks de Tkinter.

        En el .exe (modo ventana) no hay consola: sin esto, un error en un
        botón no se veía en ningún sitio y la app "no hacía nada".
        """
        import traceback as _tb
        texto = "".join(_tb.format_exception(exc, val, tb))
        try:
            from pathlib import Path
            carpeta = Path.home() / ".mapa_pdf_cache"
            carpeta.mkdir(parents=True, exist_ok=True)
            with open(carpeta / "error.log", "a", encoding="utf-8") as fh:
                from datetime import datetime
                fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{texto}")
        except Exception:
            pass
        try:
            self._escribir_log(f"✗ Error inesperado: {val}", "error")
        except Exception:
            pass
        try:
            messagebox.showerror(
                "Error inesperado",
                f"{val}\n\nSe ha guardado el detalle en:\n"
                f"{os.path.join(os.path.expanduser('~'), '.mapa_pdf_cache', 'error.log')}")
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  Construcción de la interfaz
    # ══════════════════════════════════════════════════════════════════════

    def _construir_ui(self):
        # Barra de herramientas (arriba) y barra de estado (abajo) primero,
        # para que el área central ocupe el resto.
        self._barra_herramientas = tk.Frame(self, bg=COLOR_HEADER)
        self._barra_herramientas.pack(side="top", fill="x")
        tk.Frame(self, bg=COLOR_BORDE, height=1).pack(side="top", fill="x")
        self._construir_barra_estado()

        # ── Separador principal: panel lateral | (mapa / tabla) ──
        self._pw_principal = ttk.PanedWindow(self, orient="horizontal")
        self._pw_principal.pack(side="top", fill="both", expand=True)

        self._dock = tk.Frame(self._pw_principal, bg=COLOR_PANEL, bd=0,
                              highlightthickness=1,
                              highlightbackground=COLOR_BORDE,
                              highlightcolor=COLOR_BORDE)
        self._pw_principal.add(self._dock, weight=0)

        self._pw_derecha = ttk.PanedWindow(self._pw_principal,
                                           orient="vertical")
        self._pw_principal.add(self._pw_derecha, weight=1)

        # ── Panel lateral con pestañas ──
        self._construir_panel_lateral(self._dock)

        # ── Mapa ──
        marco_mapa = tk.Frame(self._pw_derecha, bg=COLOR_FONDO_APP)
        self._pw_derecha.add(marco_mapa, weight=1)
        self.panel_mapa = PanelMapa(
            marco_mapa, self.motor,
            callback_seleccion=self._on_seleccion_mapa,
            callback_log=self._escribir_log,
            callback_coords=self._on_coords_mapa,
            callback_estado=self._set_estado,
            callback_ocupado=self._set_ocupado,
        )
        self.panel_mapa.obtener_proveedor = self._proveedor_fondo
        self.panel_mapa.callback_capas = self._refrescar_toc
        self.panel_mapa.set_color_infra(self.panel_config.color_infra)
        self.panel_mapa.pack(fill="both", expand=True, padx=(0, 4),
                             pady=(4, 2))
        self.panel_mapa.var_fondo.trace_add(
            "write", lambda *_: self._btn_fondo.set_activo(
                self.panel_mapa.fondo_activo))

        # ── Abajo: tabla de atributos + registro ──
        marco_inf = tk.Frame(self._pw_derecha, bg=COLOR_FONDO_APP)
        self._pw_derecha.add(marco_inf, weight=0)
        self._nb_inferior = ttk.Notebook(marco_inf)
        self._nb_inferior.pack(fill="both", expand=True, padx=(0, 4),
                               pady=(2, 4))
        self._crear_panel_tabla(self._nb_inferior)
        self._crear_panel_log(self._nb_inferior)

        # Barra de herramientas al final: necesita los paneles creados
        self._construir_barra_herramientas(self._barra_herramientas)

        # Ganchos de los paneles hacia el mapa / estado
        self.panel_capas.callback_ocupado = self._set_ocupado
        self.panel_capas.callback_capas_extra = self._on_capas_extra
        self.panel_simbologia.callback_aplicado = self._on_simbologia_aplicada
        self.panel_config.callback_color = self._on_color_infra
        en_curso = lambda: self.panel_generacion._generacion_en_curso()
        self.panel_capas.generacion_en_curso = en_curso
        self.panel_capas.callback_infra_omitida = \
            self._limpiar_pendientes_proyecto
        self.panel_filtros.generacion_en_curso = en_curso
        self.panel_generacion.obtener_indices_filtrados = \
            lambda: self._indices_filtro
        self.panel_generacion.validar_config = self._validar_antes_de_generar
        # Un único control de opacidad de infraestructuras (pestaña Capas)
        self.panel_simbologia._alpha_infra = self.panel_capas.transparencia_infra
        self.panel_capas.transparencia_infra.trace_add(
            "write", lambda *_: self._programar_opacidad())
        self._after_opacidad = None

        self._refrescar_toc()
        self._escribir_log(
            "EstelaGis iniciado. Carga un shapefile para comenzar.", "info")

    # ── Panel lateral ───────────────────────────────────────────────────

    def _construir_panel_lateral(self, dock):
        self._nb_lateral = ttk.Notebook(dock, style="Dock.TNotebook")
        self._barra_pestanas = BarraPestanas(dock, self._nb_lateral)
        self._barra_pestanas.pack(side="top", fill="x")
        tk.Frame(dock, bg=COLOR_BORDE, height=1).pack(side="top", fill="x")
        self._nb_lateral.pack(side="top", fill="both", expand=True)

        self._marcos = {}

        def _pestana(clave, texto):
            m = MarcoDesplazable(self._nb_lateral)
            self._nb_lateral.add(m, text=texto)
            self._barra_pestanas.añadir(m, texto)
            self._marcos[clave] = m
            return m.interior

        f_capas = _pestana("capas", "Capas")
        f_filtros = _pestana("filtros", "Filtros")
        f_simb = _pestana("simbologia", "Simbología")
        f_campos = _pestana("campos", "Campos")
        f_cajetin = _pestana("cajetin", "Cajetín")
        f_config = _pestana("config", "Configuración")
        f_gen = _pestana("generacion", "Generación")

        # 1. Capas: tabla de contenidos (TOC) + carga de datos.
        # El TOC necesita el mapa, que se crea después: se rellena luego.
        self._toc_contenedor = tk.Frame(f_capas, bg=COLOR_PANEL)
        self._toc_contenedor.pack(fill="x")
        self.panel_capas = PanelCapas(
            f_capas, self.motor,
            callback_log=self._escribir_log,
            callback_tabla=self._on_tabla_cargada,
            callback_montes_cargados=self._on_montes_cargados,
        )

        # 2. Filtrado de datos
        self.panel_filtros = PanelFiltros(
            f_filtros, self.motor,
            callback_filtro=self._on_filtro_aplicado,
        )

        # 3. Estilo visual
        self.panel_simbologia = PanelSimbologia(
            f_simb, self.motor,
            callback_log=self._escribir_log,
        )

        # 4. Campos a mostrar en el plano
        self.panel_campos = PanelCampos(f_campos)

        # 5. Cajetin y plantilla
        self.panel_cajetin = PanelCajetin(
            f_cajetin, self.motor,
            callback_log=self._escribir_log,
        )

        # 6. Configuracion de salida (incluye capas WMS superpuestas)
        self.panel_config = PanelConfig(f_config)
        self._construir_seccion_interfaz(f_config)

        # 7. Generacion final
        self.panel_generacion = PanelGeneracion(
            f_gen, self.motor,
            get_config=self._get_config,
            callback_log=self._escribir_log,
            auto_aplicar=self._auto_aplicar_todo,
        )

        # Rueda del ratón: desplaza la pestaña activa del panel lateral
        for sec in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sec, self._rueda_global, add="+")

    def _construir_seccion_interfaz(self, parent):
        f = crear_frame_seccion(parent, "🖥  INTERFAZ")
        crear_label(f, "Tema de la interfaz:", tipo="titulo").grid(
            row=0, column=0, sticky="w")
        etiquetas = {"claro": "Claro (tipo QGIS)", "oscuro": "Oscuro"}
        self._tema_elegido = tk.StringVar(value=estilos.TEMA)
        self._tema_combo = tk.StringVar(value=etiquetas[estilos.TEMA])
        cb = ttk.Combobox(f, textvariable=self._tema_combo,
                          values=list(etiquetas.values()), state="readonly",
                          font=FONT_SMALL)
        cb.grid(row=1, column=0, sticky="ew", pady=(2, 2))

        def _cambio(_e=None):
            inv = {v: k for k, v in etiquetas.items()}
            tema = inv.get(self._tema_combo.get(), "claro")
            self._tema_elegido.set(tema)
            from . import ajustes
            ajustes.actualizar_ajustes(tema=tema)
            self._escribir_log(
                f"Tema '{self._tema_combo.get()}' guardado: se aplicará al "
                "reiniciar la aplicación.", "info")

        cb.bind("<<ComboboxSelected>>", _cambio)
        crear_label(f, "Se aplica al reiniciar la aplicación.",
                    tipo="secundario").grid(row=2, column=0, sticky="w")
        f.columnconfigure(0, weight=1)

    def _marco_de_widget(self, widget):
        """MarcoDesplazable que contiene a ``widget`` (o None)."""
        try:
            ruta = str(widget)
        except Exception:
            return None
        for m in self._marcos.values():
            base = str(m)
            if ruta == base or ruta.startswith(base + "."):
                return m
        return None

    def _rueda_global(self, event):
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return
        if w is None or isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
            return
        m = self._marco_de_widget(w)
        if m is None:
            return
        if getattr(event, "num", None) == 4:
            pasos = -1
        elif getattr(event, "num", None) == 5:
            pasos = 1
        else:
            d = getattr(event, "delta", 0) or 0
            pasos = -1 if d > 0 else 1
            if abs(d) >= 240:
                pasos *= abs(d) // 120
        m.desplazar(int(pasos) * 2)

    def _desactivar_rueda_combobox(self):
        """La rueda no cambia el valor de los desplegables.

        Al desplazar el panel lateral con la rueda, pasar por encima de un
        Combobox cambiaba su valor sin querer (p. ej. el proveedor de
        cartografía). La rueda pasa a desplazar el panel.
        """
        for sec in ("<MouseWheel>", "<Button-4>", "<Button-5>",
                    "<Shift-MouseWheel>"):
            try:
                self.unbind_class("TCombobox", sec)
            except Exception:
                pass

    def _ancho_minimo_lateral(self) -> int:
        try:
            return max([ANCHO_MIN_LATERAL] + [
                m.ancho_necesario() + 4 for m in self._marcos.values()])
        except Exception:
            return ANCHO_MIN_LATERAL

    def _colocar_separadores(self):
        """Posición inicial (o recordada) de los separadores."""
        try:
            self.update_idletasks()
            ancho = self._sash_pendiente.get("sash_izq") or max(
                ANCHO_PANEL_LATERAL, self._ancho_minimo_lateral())
            ancho = max(ancho, self._ancho_minimo_lateral())
            ancho = min(ancho, max(self.winfo_width() - 500,
                                   self._ancho_minimo_lateral()))
            self._pw_principal.sashpos(0, ancho)
            alto_total = self._pw_derecha.winfo_height()
            alto_inf = self._sash_pendiente.get("alto_inferior") \
                or ALTO_PANEL_INFERIOR
            # Mapa de al menos 55 % del alto; panel inferior entre 120 px y 45 %
            alto_inf = min(max(alto_inf, 120), int(alto_total * 0.45))
            self._pw_derecha.sashpos(0, max(alto_total - alto_inf, 200))
        except Exception:
            pass
        self._pw_principal.bind("<ButtonRelease-1>",
                                lambda e: self.after_idle(self._limitar_sash),
                                add="+")
        self._pw_principal.bind("<B1-Motion>",
                                lambda e: self.after_idle(self._limitar_sash),
                                add="+")

    def _limitar_sash(self):
        """Impide estrechar el panel lateral por debajo de su contenido."""
        try:
            minimo = self._ancho_minimo_lateral()
            if self._pw_principal.sashpos(0) < minimo:
                self._pw_principal.sashpos(0, minimo)
        except Exception:
            pass

    # ── Barra de herramientas ───────────────────────────────────────────

    def _construir_barra_herramientas(self, barra):
        pc = self.panel_capas
        pg = self.panel_generacion
        pm = self.panel_mapa
        fila = tk.Frame(barra, bg=COLOR_HEADER)
        fila.pack(side="left", fill="y", padx=4, pady=3)

        def boton(icono, texto, cmd, tip, **kw):
            b = BotonHerramienta(fila, icono, texto, cmd, tooltip=tip, **kw)
            b.pack(side="left", padx=1)
            return b

        def sep():
            separador_vertical(fila).pack(side="left", fill="y", padx=2)

        # Datos
        bloq = self._botones_bloqueables = []
        bloq.append(boton("⊞", "Abrir SHP", pc._cargar_infra,
              "Abrir el shapefile (.shp) de infraestructuras.\n"
              "Es la capa principal: una entidad por plano."))
        bloq.append(boton("⛁", "Abrir GDB", pc._cargar_infra_gdb,
              "Abrir infraestructuras desde una geodatabase (.gdb)."))
        self._mb_recientes_shp = tk.Menubutton(
            fila, text="⟲ Recientes ▾", font=FONT_BOTON, bg=COLOR_HEADER,
            fg=COLOR_TEXTO, activebackground=COLOR_HOVER,
            activeforeground=COLOR_TEXTO, relief="flat", bd=0,
            highlightthickness=0, padx=6, pady=3, cursor="hand2")
        self._menu_recientes_shp = tk.Menu(
            self._mb_recientes_shp, tearoff=0, font=FONT_SMALL,
            postcommand=self._actualizar_menu_recientes_shp)
        self._mb_recientes_shp.configure(menu=self._menu_recientes_shp)
        self._mb_recientes_shp.pack(side="left", padx=1)
        crear_tooltip(self._mb_recientes_shp,
                      "Shapefiles de infraestructuras abiertos recientemente.")
        self._actualizar_menu_recientes_shp()
        sep()

        # Proyecto
        boton("▣", "Guardar", self._guardar_proyecto,
              "Guardar el proyecto (Ctrl+S).")
        bloq.append(boton("▤", "Cargar", self._cargar_proyecto,
              "Cargar un proyecto guardado (Ctrl+O)."))
        self._mb_recientes_proy = tk.Menubutton(
            fila, text="▾", font=FONT_BOTON, bg=COLOR_HEADER, fg=COLOR_TEXTO,
            activebackground=COLOR_HOVER, activeforeground=COLOR_TEXTO,
            relief="flat", bd=0, highlightthickness=0, padx=5, pady=3,
            cursor="hand2")
        self._menu_recientes_proy = tk.Menu(
            self._mb_recientes_proy, tearoff=0, font=FONT_SMALL)
        self._mb_recientes_proy.configure(menu=self._menu_recientes_proy)
        self._mb_recientes_proy.pack(side="left")
        crear_tooltip(self._mb_recientes_proy,
                      "Proyectos abiertos recientemente")
        self._actualizar_menu_recientes_proyecto()
        sep()

        # Navegación del mapa
        boton("⊕", "", pm.zoom_in, "Acercar (rueda del ratón hacia delante).")
        boton("⊖", "", pm.zoom_out, "Alejar (rueda del ratón hacia atrás).")
        boton("⛶", "", self._zoom_capa,
              "Zoom a la capa de infraestructuras\n(o a todas las capas).")
        self._btn_zoom_sel = boton(
            "⌖", "", self._zoom_seleccion,
            "Zoom a las entidades seleccionadas.")
        self._btn_desplazar = boton(
            "✋", "Desplazar", lambda: self._set_modo_mapa("desplazar"),
            "Herramienta Desplazar: arrastra el mapa con el botón izquierdo.\n"
            "(El botón central del ratón desplaza siempre.)",
            conmutable=True)
        self._btn_seleccionar = boton(
            "⬉", "Seleccionar", lambda: self._set_modo_mapa("seleccionar"),
            "Herramienta Seleccionar: clic sobre una infraestructura\n"
            "(Ctrl+clic añade/quita) o arrastra un rectángulo.",
            conmutable=True)
        self._btn_fondo = boton(
            "▦", "Fondo", lambda: pm.set_fondo(not pm.fondo_activo),
            "Mostrar/ocultar el fondo cartográfico en el mapa\n"
            "(proveedor elegido en Configuración; se descarga\n"
            "para la vista actual en segundo plano).",
            conmutable=True)
        self._btn_desplazar.set_activo(True)
        sep()

        # Salidas
        bloq.append(boton("◎", "Vista previa", pg._vista_previa,
              "Vista previa del primer plano según el modo de\n"
              "selección actual (F5)."))
        bloq.append(boton("⚑", "Mapa guía", pg._mapa_guia,
              "Mapa guía con las infraestructuras seleccionadas numeradas."))
        self._btn_generar_tb = boton(
            "▶", "GENERAR PLANOS", pg._iniciar_generacion,
            "Genera los planos según el modo seleccionado en la\n"
            "pestaña Generación (Ctrl+G).", estilo="exito")
        self._btn_parar_tb = boton(
            "■", "PARAR", pg._parar_generacion,
            "Detiene la generación en curso (los planos ya\n"
            "generados se conservan).", estilo="peligro")
        self._btn_parar_tb.set_habilitado(False)
        sep()
        boton("ℹ", "Info", self._mostrar_info,
              "Información técnica y manual de usuario.")

    def _habilitar_acciones(self, habilitar: bool):
        """(Des)habilita cargas y ventanas mientras se generan planos."""
        for b in self._botones_bloqueables:
            try:
                b.set_habilitado(habilitar)
            except Exception:
                pass
        estado = "normal" if habilitar else "disabled"
        widgets = list(self.panel_capas.botones_carga) + [
            self._mb_recientes_shp, self._mb_recientes_proy,
            self.panel_capas._mb_recientes]
        for w in widgets:
            try:
                w.configure(state=estado)
            except Exception:
                pass

    def _actualizar_menu_recientes_shp(self):
        menu = self._menu_recientes_shp
        menu.delete(0, "end")
        lista = recientes.cargar_recientes().get(recientes.TIPO_SHAPEFILE, [])
        if not lista:
            menu.add_command(label="(sin recientes)", state="disabled")
            return
        for ruta in lista:
            etiqueta = os.path.basename(ruta) or ruta
            if os.path.exists(ruta):
                menu.add_command(
                    label=etiqueta,
                    command=lambda r=ruta:
                        self.panel_capas._cargar_infra_reciente(r))
            else:
                menu.add_command(label=f"{etiqueta} (no encontrado)",
                                 state="disabled")

    def _set_modo_mapa(self, modo):
        self.panel_mapa.set_modo(modo)
        self._btn_desplazar.set_activo(modo == "desplazar")
        self._btn_seleccionar.set_activo(modo == "seleccionar")

    def _zoom_capa(self):
        if not self.panel_mapa.hay_datos():
            self._set_estado("No hay capas cargadas.")
            return
        self.panel_mapa.zoom_capa()

    def _zoom_seleccion(self):
        sel = [int(i) for i in self._tabla.selection()]
        if not sel:
            self._set_estado("No hay entidades seleccionadas.")
            return
        self.panel_mapa.zoom_seleccion(sel)

    def _sincronizar_barra(self):
        """Refleja en la barra/estado el estado de la generación."""
        try:
            pg = self.panel_generacion
            gen_libre = str(pg._btn_generar["state"]) == "normal"
            parar_on = str(pg._btn_parar["state"]) == "normal"
            self._btn_generar_tb.set_habilitado(gen_libre)
            for b in (pg._btn_generar, pg._btn_parar, pg._btn_ultimo_pdf):
                estilos.actualizar_color_estado(b)
            self._btn_parar_tb.set_habilitado(parar_on)
            generando = not gen_libre
            if generando != self._generando:
                self._generando = generando
                self._set_ocupado(generando)
                self._habilitar_acciones(not generando)
            if generando:
                txt = pg._lbl_progreso.cget("text")
                if txt and txt != "—":
                    self._set_estado(f"Generando planos: {txt}")
        except Exception:
            pass
        try:
            self.after(300, self._sincronizar_barra)
        except Exception:
            pass

    # ── Barra de estado ─────────────────────────────────────────────────

    def _construir_barra_estado(self):
        barra = tk.Frame(self, bg=COLOR_HEADER, height=26)
        barra.pack(side="bottom", fill="x")
        barra.pack_propagate(False)
        tk.Frame(self, bg=COLOR_BORDE, height=1).pack(side="bottom", fill="x")

        # Derecha: CRS + coordenadas/escala
        crs = tk.Label(barra, text=" EPSG:25830 ", font=(FONT_MINI[0], 8, "bold"),
                       bg=COLOR_ENTRY, fg=COLOR_TITULO_SECCION, bd=0,
                       highlightthickness=1, highlightbackground=COLOR_BORDE)
        crs.pack(side="right", padx=(4, 8), pady=3)
        crear_tooltip(crs, f"Sistema de referencia del proyecto:\n{CRS_TEXTO}")
        self._lbl_coords = tk.Label(
            barra, text="X: —   Y: —   |   Escala aprox. —   |   " + CRS_TEXTO,
            font=FONT_MINI, bg=COLOR_HEADER, fg=COLOR_TEXTO, anchor="e")
        self._lbl_coords.pack(side="right", padx=4)
        tk.Frame(barra, bg=COLOR_BORDE, width=1).pack(side="right", fill="y",
                                                      pady=4, padx=4)
        self._barra_progreso = ttk.Progressbar(
            barra, mode="indeterminate", length=140,
            style="Estado.Horizontal.TProgressbar")
        # Izquierda: mensajes (última línea del registro / progreso)
        self._lbl_estado = tk.Label(
            barra, text="Listo.", font=FONT_MINI, bg=COLOR_HEADER,
            fg=COLOR_TEXTO_GRIS, anchor="w")
        self._lbl_estado.pack(side="left", fill="x", expand=True, padx=8)
        self._barra_estado = barra

    def _set_estado(self, msg: str):
        try:
            linea = next((l for l in str(msg).splitlines() if l.strip()), "")
            self._lbl_estado.configure(text=linea.strip()[:180])
        except Exception:
            pass

    def _set_ocupado(self, ocupado: bool):
        """Muestra/oculta la barra de progreso indeterminada (contador)."""
        self._n_ocupado = max(0, self._n_ocupado + (1 if ocupado else -1))
        try:
            if self._n_ocupado > 0:
                if not self._barra_progreso.winfo_ismapped():
                    self._barra_progreso.pack(side="right", padx=6,
                                              before=self._lbl_coords)
                    self._barra_progreso.start(12)
            else:
                self._barra_progreso.stop()
                self._barra_progreso.pack_forget()
        except Exception:
            pass

    def _on_coords_mapa(self, texto):
        try:
            self._lbl_coords.configure(text=texto)
        except Exception:
            pass

    # ── Tabla de atributos y registro ───────────────────────────────────

    def _crear_panel_tabla(self, notebook):
        """Crea la tabla de atributos (pestaña inferior)."""
        marco = tk.Frame(notebook, bg=COLOR_PANEL)
        notebook.add(marco, text="Tabla de atributos (0)")
        self._tab_tabla = marco

        # Mini barra de la tabla
        barra = tk.Frame(marco, bg=COLOR_PANEL)
        barra.pack(fill="x", padx=4, pady=(3, 2))
        for texto, cmd, tip in (
                ("⌖ Zoom a selección", self._zoom_seleccion,
                 "Zoom del mapa a las filas seleccionadas."),
                ("☐ Quitar selección",
                 lambda: self._tabla.selection_set(()),
                 "Deselecciona todas las filas."),
                ("☑ Seleccionar todo",
                 lambda: self._tabla.selection_set(
                     self._tabla.get_children()),
                 "Selecciona todas las filas visibles.")):
            b = tk.Button(barra, text=texto, command=cmd, font=FONT_MINI,
                          bg=COLOR_PANEL, fg=COLOR_TEXTO, relief="flat",
                          bd=0, padx=6, pady=1, cursor="hand2",
                          activebackground=COLOR_HOVER,
                          activeforeground=COLOR_TEXTO,
                          highlightthickness=0)
            b.pack(side="left", padx=(0, 2))
            crear_tooltip(b, tip)
        self._lbl_sel_tabla = tk.Label(barra, text="", font=FONT_MINI,
                                       bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_sel_tabla.pack(side="right", padx=6)

        tabla_container = tk.Frame(marco, bg=COLOR_ENTRY, bd=0,
                                   highlightthickness=1,
                                   highlightbackground=COLOR_BORDE)
        tabla_container.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        cols = ["#"]
        self._tabla = ttk.Treeview(tabla_container, columns=cols,
                                   show="headings", selectmode="extended")
        self._tabla.heading("#", text="#")
        self._tabla.column("#", width=60, minwidth=40)
        self._tabla.tag_configure("par", background=COLOR_FILA_PAR)
        self._tabla.tag_configure("impar", background=COLOR_FILA_IMPAR)

        sb_v = ttk.Scrollbar(tabla_container, orient="vertical",
                             command=self._tabla.yview)
        sb_h = ttk.Scrollbar(tabla_container, orient="horizontal",
                             command=self._tabla.xview)
        self._tabla.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        sb_h.pack(side="bottom", fill="x")
        sb_v.pack(side="right", fill="y")
        self._tabla.pack(side="left", fill="both", expand=True)

        self._tabla.bind("<<TreeviewSelect>>", self._on_seleccion_tabla)
        self._tabla.bind("<Double-1>", self._on_doble_clic_tabla)

    def _reconfigurar_tabla(self, columnas: list):
        """Reconfigura las columnas de la tabla."""
        cols = ["#"] + columnas
        self._tabla.configure(columns=cols)
        for col in cols:
            ancho = 50 if col == "#" else 120
            self._tabla.heading(col, text=col)
            self._tabla.column(col, width=ancho, minwidth=40)

    def _crear_panel_log(self, notebook):
        marco = tk.Frame(notebook, bg=COLOR_PANEL)
        notebook.add(marco, text="Registro")
        self._tab_log = marco

        log_container = tk.Frame(marco, bg=COLOR_LOG_FONDO, bd=0,
                                 highlightthickness=1,
                                 highlightbackground=COLOR_BORDE)
        log_container.pack(fill="both", expand=True, padx=4, pady=4)

        self._log = tk.Text(
            log_container, height=7, font=FONT_MONO,
            bg=COLOR_LOG_FONDO, fg=COLOR_LOG_TEXTO,
            insertbackground=COLOR_TEXTO, relief="flat", state="disabled",
            padx=10, pady=6, bd=0,
            selectbackground=COLOR_ACENTO, selectforeground="#FFFFFF",
        )
        sb = ttk.Scrollbar(log_container, orient="vertical",
                           command=self._log.yview)
        self._log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # Tags de color
        self._log.tag_config("error", foreground=COLOR_LOG_ERROR)
        self._log.tag_config("ok", foreground=COLOR_LOG_OK)
        self._log.tag_config("warn", foreground=COLOR_LOG_WARN)
        self._log.tag_config("info", foreground=COLOR_LOG_INFO)

    def _escribir_log(self, msg: str, tipo: str = ""):
        def _do():
            self._log.configure(state="normal")
            tag = tipo if tipo else ""
            self._log.insert("end", msg + "\n", tag)
            self._log.see("end")
            self._log.configure(state="disabled")
            # La última línea del registro se refleja en la barra de estado
            ultima = [l for l in str(msg).splitlines() if l.strip()]
            if ultima:
                self._set_estado(ultima[-1])
        self.after(0, _do)

    def _poblar_tabla(self, indices=None):
        gdf = self.motor.gdf_infra
        if gdf is None:
            return

        children = self._tabla.get_children()
        if children:
            self._tabla.delete(*children)

        self._tabla.tag_configure("par", background=COLOR_FILA_PAR)
        self._tabla.tag_configure("impar", background=COLOR_FILA_IMPAR)

        columnas = [c for c in gdf.columns if c != "geometry"]

        if indices is None:
            indices = range(len(gdf))
        lista = [int(i) for i in indices]
        self._indices_tabla = (None if len(lista) == len(gdf)
                               and lista == list(range(len(gdf))) else lista)

        # itertuples sobre el subconjunto: ~10x más rápido que gdf.iloc[i]
        sub = gdf[columnas]
        if self._indices_tabla is not None:
            sub = sub.iloc[lista]
        guion = "—"
        for i, fila in zip(lista, sub.itertuples(index=False, name=None)):
            vals = [i + 1]
            for v in fila:
                t = str(v) if v is not None else "nan"
                vals.append(guion if t in ("nan", "None", "NaT", "<NA>")
                            else t)
            tag = "par" if i % 2 == 0 else "impar"
            # iid = posición real en el GeoDataFrame. Con la tabla filtrada,
            # Treeview.index() devolvería la posición visual (0,1,2...) y la
            # generación usaría infraestructuras equivocadas.
            self._tabla.insert("", "end", iid=str(i), values=vals, tags=(tag,))

        n = len(lista)
        try:
            total = len(gdf)
            texto = (f"Tabla de atributos ({n})" if n == total
                     else f"Tabla de atributos ({n} de {total})")
            self._nb_inferior.tab(self._tab_tabla, text=texto)
        except Exception:
            pass
        self._actualizar_lbl_seleccion()
        self._escribir_log(f"Tabla actualizada: {n} infraestructuras.", "info")

    # ── Sincronización tabla ↔ mapa ─────────────────────────────────────

    def _on_seleccion_tabla(self, _event=None):
        sel = [int(i) for i in self._tabla.selection()]
        self.panel_mapa.resaltar(sel)
        self._actualizar_lbl_seleccion()

    def _actualizar_lbl_seleccion(self):
        try:
            n = len(self._tabla.selection())
            filas = len(self._tabla.get_children())
            self._lbl_sel_tabla.configure(
                text=f"{n} seleccionadas · {filas} filas")
        except Exception:
            pass

    def _on_doble_clic_tabla(self, event):
        iid = self._tabla.identify_row(event.y)
        if iid:
            self.panel_mapa.zoom_seleccion([int(iid)])

    def _on_seleccion_mapa(self, indices):
        """Clic/rectángulo en el mapa → selección en la tabla."""
        iids = [str(i) for i in indices if self._tabla.exists(str(i))]
        self._tabla.selection_set(iids)
        if iids:
            self._tabla.see(iids[0])
            try:
                self._nb_inferior.select(self._tab_tabla)
            except Exception:
                pass
        self._set_estado(f"{len(iids)} entidades seleccionadas en el mapa.")

    # ── Mapa: actualización desde el motor ──────────────────────────────

    def _firma_simbologia(self):
        try:
            return json.dumps([
                self.motor.config_infra,
                self.motor.gestor_simbologia.to_dict(),
                self.panel_config.color_infra,
                id(self.motor.gdf_infra), id(self.motor.gdf_montes),
                [id(c) for c in self.motor.gestor_capas.capas],
            ], sort_keys=True, default=str)
        except Exception:
            return None

    def _refrescar_mapa(self, forzar=False):
        """Redibuja el mapa si cambió algo (capas o simbología)."""
        firma = self._firma_simbologia()
        if not forzar and firma is not None and firma == self._firma_mapa:
            return
        self._firma_mapa = firma
        self.panel_mapa.set_color_infra(self.panel_config.color_infra)
        self.panel_mapa.actualizar_capas()
        gdf = self.motor.gdf_infra
        if gdf is not None and id(gdf) != self._gdf_infra_mapa:
            # Capa de infraestructuras nueva: encuadrarla
            self._gdf_infra_mapa = id(gdf)
            self.panel_mapa.zoom_capa()

    def _refrescar_toc(self):
        try:
            if not hasattr(self, "_toc"):
                self._toc = TablaContenidos(self._toc_contenedor,
                                            self.panel_mapa)
                self._toc.pack(fill="x")
            else:
                self._toc.refrescar()
        except Exception as e:
            self._escribir_log(f"Lista de capas: {e}", "warn")

    def _programar_opacidad(self):
        if self._after_opacidad is not None:
            self.after_cancel(self._after_opacidad)
        self._after_opacidad = self.after(250, self._aplicar_opacidad)

    def _aplicar_opacidad(self):
        self._after_opacidad = None
        try:
            alpha = float(self.panel_capas.transparencia_infra.get())
        except Exception:
            return
        ci = dict(self.motor.config_infra or {})
        ci["alpha"] = alpha
        self.motor.config_infra = ci
        self._refrescar_mapa()

    def _validar_antes_de_generar(self) -> bool:
        """Escalas legibles y patrón de nombre válido antes de generar."""
        avisos = self.panel_config.validar_escalas()
        if avisos:
            messagebox.showwarning("Escala no válida", "\n\n".join(avisos))
            return False
        patron = self.panel_config.patron_nombre.get().strip()
        if patron:
            try:
                patron.format(num="0001", nombre="Nombre", campo="Valor")
            except (KeyError, IndexError, ValueError) as e:
                if not messagebox.askyesno(
                        "Patrón de nombre no válido",
                        f"El patrón de nombre de archivo «{patron}» no es "
                        f"válido ({type(e).__name__}: {e}).\n\nVariables "
                        "disponibles: {num}, {nombre}, {campo}.\n\n"
                        "¿Generar de todos modos?"):
                    return False
        return True

    def _limpiar_pendientes_proyecto(self):
        """Olvida lo pendiente de aplicar de un proyecto (campos, filtros...).

        Si no, se aplicaría a la SIGUIENTE carga manual de una capa.
        """
        self._campos_visibles_proyecto = []
        self._campos_orden_proyecto = []
        self._simbologia_ui_proyecto = {}
        self._filtros_proyecto = {}

    def _bloqueado_por_generacion(self) -> bool:
        if self.panel_generacion._generacion_en_curso():
            messagebox.showinfo(
                "Generación en curso",
                "Espera a que termine la generación (o pulsa PARAR).")
            return True
        return False

    def _on_capas_extra(self):
        self.panel_simbologia.actualizar_capas_extra()
        self._refrescar_mapa(forzar=True)

    def _on_simbologia_aplicada(self):
        self._refrescar_mapa()

    def _on_color_infra(self, color):
        self.panel_mapa.set_color_infra(color)
        self.panel_mapa.canvas.draw_idle()
        self._refrescar_toc()

    def _proveedor_fondo(self) -> str:
        """Proveedor del fondo del mapa (el mismo que usarán los planos)."""
        pc = self.panel_config
        m = self.motor
        m.ruta_raster_general = pc.ruta_raster_general
        m.wms_custom_general = pc.wms_custom_general
        m.wfs_custom_general = pc.wfs_custom_general
        return pc.proveedor.get()

    def _on_tabla_cargada(self):
        columnas = self.motor.obtener_columnas_shapefile()
        self._indices_filtro = None
        self._reconfigurar_tabla(columnas)
        self._poblar_tabla()
        self.panel_generacion.actualizar_campos_agrupacion()
        self.panel_generacion.actualizar_valores_si_agrupado()
        self.panel_filtros.actualizar_campos()
        self.panel_simbologia.actualizar_capas_extra()
        self.panel_simbologia.actualizar_campo_categoria()
        self.panel_simbologia.actualizar_campo_categoria_montes()
        self.panel_campos.actualizar_campos(columnas)
        mapeo = dict(getattr(self.motor, "_campo_mapeo", None) or {})
        campo_real = getattr(self.motor, "_campo_real", None)
        if callable(campo_real):
            for campo in ("Nombre_Infra", "Tipo_Trabajos"):
                mapeo.setdefault(campo, campo_real(campo))
        self.panel_cajetin.actualizar_campos_subtitulo(columnas, mapeo=mapeo)
        try:
            col = mapeo.get("Nombre_Infra", "Nombre_Infra")
            gdf = self.motor.gdf_infra
            if gdf is not None and col in gdf.columns and len(gdf):
                self.panel_config.actualizar_ejemplo_nombre(gdf[col].iloc[0])
        except Exception:
            pass
        self.panel_config.actualizar_campos_shp_enlace(columnas)

        if hasattr(self, "_campos_visibles_proyecto") and self._campos_visibles_proyecto:
            campos_proy = self._campos_visibles_proyecto
            for campo, var in self.panel_campos._check_campos.items():
                var.set(campo in campos_proy)
            self.panel_campos._actualizar_count()
            self._campos_visibles_proyecto = []

        # Restaurar orden de campos personalizado
        if hasattr(self, "_campos_orden_proyecto") and self._campos_orden_proyecto:
            self.panel_campos.restaurar_orden(self._campos_orden_proyecto)
            self._campos_orden_proyecto = []

        # Restaurar estado UI de simbología
        if hasattr(self, "_simbologia_ui_proyecto") and self._simbologia_ui_proyecto:
            sui = self._simbologia_ui_proyecto
            if "grosor_infra" in sui:
                self.panel_simbologia._grosor_infra.set(sui["grosor_infra"])
            if "alpha_infra" in sui:
                self.panel_simbologia._alpha_infra.set(sui["alpha_infra"])
            if "trazo_infra" in sui:
                self.panel_simbologia._trazo_infra.set(sui["trazo_infra"])
            if "marcador" in sui:
                self.panel_simbologia._marcador.set(sui["marcador"])
            if "color_montes" in sui:
                self.panel_simbologia._color_montes = sui["color_montes"]
                self.panel_simbologia._lbl_col_montes.configure(
                    bg=sui["color_montes"])
            if "campo_categoria" in sui and sui["campo_categoria"] != "(ninguno)":
                self.panel_simbologia._campo_categoria.set(sui["campo_categoria"])
                self.panel_simbologia._on_campo_cat_changed()
            if "campo_cat_montes" in sui and sui["campo_cat_montes"] != "(ninguno)":
                self.panel_simbologia._campo_cat_montes.set(sui["campo_cat_montes"])
                self.panel_simbologia._on_campo_cat_montes_changed()
            # Aplicar simbología restaurada al motor
            self.panel_simbologia._aplicar()
            self._simbologia_ui_proyecto = {}

        # Restaurar filtros
        if hasattr(self, "_filtros_proyecto") and self._filtros_proyecto:
            flt = self._filtros_proyecto
            if flt.get("busqueda"):
                self.panel_filtros._busqueda.set(flt["busqueda"])
            if flt.get("campo_filtro") and flt["campo_filtro"] != "(todos)":
                self.panel_filtros._campo_filtro.set(flt["campo_filtro"])
                self.panel_filtros._on_campo_changed()
            if flt.get("valor_filtro") and flt["valor_filtro"] != "(todos)":
                self.panel_filtros._valor_filtro.set(flt["valor_filtro"])
            if flt.get("sup_min"):
                self.panel_filtros._sup_min.delete(0, "end")
                self.panel_filtros._sup_min.insert(0, flt["sup_min"])
            if flt.get("sup_max"):
                self.panel_filtros._sup_max.delete(0, "end")
                self.panel_filtros._sup_max.insert(0, flt["sup_max"])
            if flt.get("lon_min"):
                self.panel_filtros._lon_min.delete(0, "end")
                self.panel_filtros._lon_min.insert(0, flt["lon_min"])
            if flt.get("lon_max"):
                self.panel_filtros._lon_max.delete(0, "end")
                self.panel_filtros._lon_max.insert(0, flt["lon_max"])
            # Aplicar filtros si hay algo activo
            hay_filtro = any(flt.get(k) for k in [
                "busqueda", "sup_min", "sup_max", "lon_min", "lon_max"])
            hay_filtro = hay_filtro or flt.get("campo_filtro", "(todos)") != "(todos)"
            if hay_filtro:
                self.panel_filtros._aplicar_filtros()
            self._filtros_proyecto = {}

        # Mapa: dibujar la capa (y encuadrarla si es nueva)
        self._refrescar_mapa(forzar=True)

    def _on_montes_cargados(self):
        self.panel_simbologia.actualizar_campo_categoria_montes()
        if self.motor.gdf_montes is not None:
            cols = [c for c in self.motor.gdf_montes.columns
                    if c.lower() != "geometry"]
            self.panel_cajetin.actualizar_campos_montes(cols)
        self._refrescar_mapa(forzar=True)

    def _on_filtro_aplicado(self, indices: list):
        gdf = self.motor.gdf_infra
        lista = [int(i) for i in indices]
        todos = gdf is not None and len(lista) == len(gdf)
        self._indices_filtro = None if todos else lista
        nuevo = None if todos else lista
        # No volver a rellenar la tabla si ya muestra exactamente eso
        if nuevo != self._indices_tabla or \
                len(self._tabla.get_children()) != len(lista):
            self._poblar_tabla(indices)
        self.panel_mapa.set_filtro(None if todos else lista)

    def _auto_aplicar_todo(self):
        """Aplica cajetin, plantilla, layout y simbologia al motor antes de generar."""
        cajetin = self.panel_cajetin.obtener_cajetin()
        plantilla = self.panel_cajetin.obtener_plantilla()
        self.motor.set_cajetin(cajetin)
        self.motor.set_plantilla(plantilla)
        self.motor.layout_key = self.panel_cajetin.obtener_layout_key()
        self.motor.dpi_figura = self.panel_config.dpi_figura
        self.motor.dpi_guardado = self.panel_config.dpi_guardado
        self.panel_simbologia._aplicar()
        self.motor.config_infra["alpha"] = self.panel_capas.transparencia_infra.get()
        self.motor.ruta_raster_general = self.panel_config.ruta_raster_general
        self.motor.ruta_raster_localizacion = self.panel_config.ruta_raster_localizacion
        self.motor.ruta_capa_localizacion = self.panel_config.ruta_capa_localizacion
        self.motor.wms_custom_general = self.panel_config.wms_custom_general
        self.motor.wfs_custom_general = self.panel_config.wfs_custom_general
        self.motor.wms_custom_localizacion = self.panel_config.wms_custom_localizacion
        self.motor.wfs_custom_localizacion = self.panel_config.wfs_custom_localizacion
        self.motor.escala_localizacion = self.panel_config.escala_localizacion
        self.motor.prov_localizacion = self.panel_config._prov_localizacion.get()
        # Capas WMS superpuestas y opciones de salida (formato / marca de agua)
        self.motor.overlays_wms = self.panel_config.obtener_overlays()
        self.panel_generacion._aplicar_opciones_salida()
        if self.panel_config.usa_excel and self.panel_config.ruta_excel:
            try:
                self.motor.cargar_excel_tabla(
                    self.panel_config.ruta_excel,
                    hoja=self.panel_config.hoja_excel or None,
                    campo_enlace_shp=self.panel_config.campo_enlace_shp,
                    campo_enlace_excel=self.panel_config.campo_enlace_excel,
                    columnas_activas=self.panel_config.columnas_excel_activas)
            except Exception as e:
                self._escribir_log(f"Error al cargar Excel: {e}", "error")
                self.motor.limpiar_excel_tabla()
        else:
            self.motor.limpiar_excel_tabla()

    def _get_config(self) -> dict:
        return {
            "formato": self.panel_config.formato.get(),
            "proveedor": self.panel_config.proveedor.get(),
            "ruta_raster_general": self.panel_config.ruta_raster_general,
            "ruta_raster_localizacion": self.panel_config.ruta_raster_localizacion,
            "transparencia": self.panel_capas.transparencia.get(),
            "campos": self.panel_campos.obtener_campos_activos(),
            "campo_encabezado": self.panel_campos.obtener_campo_encabezado(),
            "color_infra": self.panel_config.color_infra,
            "salida": self.panel_config.salida.get(),
            "patron_nombre": self.panel_config.patron_nombre.get(),
            "escala_manual": self.panel_config.escala_manual,
            "tabla": self._tabla,
        }

    # ── Guardar/Cargar proyecto ──────────────────────────────────────────

    def _guardar_proyecto(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar proyecto",
            defaultextension=".json",
            filetypes=[("Proyecto JSON", "*.json")],
            initialdir=self._ultimo_dir_proyecto,
        )
        if not ruta:
            return
        self._ultimo_dir_proyecto = os.path.dirname(ruta)

        try:
            p = Proyecto()
            p.nombre = os.path.splitext(os.path.basename(ruta))[0]
            p.formato = self.panel_config.formato.get()
            p.proveedor = self.panel_config.proveedor.get()
            p.ruta_raster_general = self.panel_config.ruta_raster_general
            p.ruta_raster_localizacion = self.panel_config.ruta_raster_localizacion
            p.prov_localizacion = self.panel_config._prov_localizacion.get()
            p.escala_localizacion = self.panel_config.escala_localizacion
            p.ruta_capa_localizacion = self.panel_config.ruta_capa_localizacion
            p.wms_custom_general = self.panel_config.wms_custom_general
            p.wfs_custom_general = self.panel_config.wfs_custom_general
            p.wms_custom_localizacion = self.panel_config.wms_custom_localizacion
            p.wfs_custom_localizacion = self.panel_config.wfs_custom_localizacion
            p.escala_manual = self.panel_config.escala_manual
            p.transparencia_montes = self.panel_capas.transparencia.get()
            p.transparencia_infra = self.panel_capas.transparencia_infra.get()
            p.color_infra = self.panel_config.color_infra
            p.calidad_pdf = self.panel_config.calidad_pdf
            p.campos_visibles = self.panel_campos.obtener_campos_activos()
            p.campo_encabezado = self.panel_campos.obtener_campo_encabezado() or ""
            p.carpeta_salida = self.panel_config.salida.get()
            p.patron_nombre = self.panel_config.patron_nombre.get()
            p.layout_key = self.panel_cajetin.obtener_layout_key()
            p.cajetin = self.panel_cajetin.obtener_cajetin()
            p.plantilla = self.panel_cajetin.obtener_plantilla()
            p.simbologia = self.motor.gestor_simbologia.to_dict()
            p.capas_extra = self.motor.gestor_capas.to_dict()
            p.overlays_wms = self.panel_config.obtener_overlays()
            p.opciones_salida = self.panel_generacion.obtener_opciones_salida()
            p.origen_datos_tabla = self.panel_config._origen_datos.get()
            p.ruta_excel_tabla = self.panel_config.ruta_excel
            p.hoja_excel_tabla = self.panel_config.hoja_excel
            p.campo_enlace_shp = self.panel_config.campo_enlace_shp
            p.campo_enlace_excel = self.panel_config.campo_enlace_excel
            p.columnas_excel_activas = self.panel_config.columnas_excel_activas

            # Rutas de capas, nombres de capa GDB y mapeo de campos
            p.ruta_infra = getattr(self.panel_capas, '_ruta_infra_completa', "")
            p.ruta_montes = getattr(self.panel_capas, '_ruta_montes_completa', "")
            p.layer_infra = getattr(self.panel_capas, '_layer_infra', "") or ""
            p.layer_montes = getattr(self.panel_capas, '_layer_montes', "") or ""
            p.campo_mapeo = self.motor._campo_mapeo or {}

            p.modo_gen = self.panel_generacion._modo_gen.get()
            try:
                p.rango_desde = int(self.panel_generacion._rango_desde.get())
            except ValueError:
                p.rango_desde = 1
            try:
                p.rango_hasta = int(self.panel_generacion._rango_hasta.get())
            except ValueError:
                p.rango_hasta = 10
            p.campo_agrupacion = self.panel_generacion._campo_agrupacion.get()
            p.multipagina = self.panel_generacion._multipagina.get()
            p.incluir_portada = self.panel_generacion._incluir_portada.get()

            # Estado UI de simbología
            p.simbologia_ui = {
                "grosor_infra": self.panel_simbologia._grosor_infra.get(),
                "alpha_infra": self.panel_simbologia._alpha_infra.get(),
                "trazo_infra": self.panel_simbologia._trazo_infra.get(),
                "marcador": self.panel_simbologia._marcador.get(),
                "color_montes": self.panel_simbologia._color_montes,
                "campo_categoria": self.panel_simbologia._campo_categoria.get(),
                "campo_cat_montes": self.panel_simbologia._campo_cat_montes.get(),
            }

            # Filtros activos
            p.filtros = {
                "busqueda": self.panel_filtros._busqueda.get(),
                "campo_filtro": self.panel_filtros._campo_filtro.get(),
                "valor_filtro": self.panel_filtros._valor_filtro.get(),
                "sup_min": self.panel_filtros._sup_min.get().strip(),
                "sup_max": self.panel_filtros._sup_max.get().strip(),
                "lon_min": self.panel_filtros._lon_min.get().strip(),
                "lon_max": self.panel_filtros._lon_max.get().strip(),
            }

            # Orden de campos personalizado
            p.campos_orden = list(self.panel_campos._campos_orden)

            p.guardar(ruta)
            recientes.agregar_reciente(recientes.TIPO_PROYECTO, ruta)
            self._actualizar_menu_recientes_proyecto()
            self._escribir_log(f"Proyecto guardado: {ruta}", "ok")
        except Exception as e:
            self._escribir_log(f"Error al guardar proyecto: {e}", "error")
            messagebox.showerror("Error", str(e))

    def _cargar_proyecto(self, ruta: str = None):
        # El hilo de generación lee motor.gdf_infra en vivo: cargar otro
        # proyecto a mitad abortaba la serie con IndexError
        if self._bloqueado_por_generacion():
            return
        if not ruta:
            ruta = filedialog.askopenfilename(
                title="Cargar proyecto",
                filetypes=[("Proyecto JSON", "*.json")],
                initialdir=self._ultimo_dir_proyecto,
            )
        if not ruta:
            return
        if not os.path.exists(ruta):
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El proyecto ya no existe:\n{ruta}")
            self._actualizar_menu_recientes_proyecto()
            return
        self._ultimo_dir_proyecto = os.path.dirname(ruta)

        try:
            p = Proyecto.cargar(ruta)

            # ── Configuracion general ──
            self.panel_config.formato.set(p.formato)
            self.panel_config.proveedor.set(p.proveedor)
            # Rutas y servicios: se restauran SIEMPRE (también vacíos);
            # antes quedaban los del proyecto/sesión anterior
            pcf = self.panel_config
            sin_raster = "Sin r\u00e1ster seleccionado"
            r = p.ruta_raster_general or ""
            pcf._ruta_raster.set(r)
            pcf._lbl_raster.configure(
                text=os.path.basename(r) if r else sin_raster)
            r = p.ruta_raster_localizacion or ""
            pcf._ruta_raster_loc.set(r)
            pcf._lbl_raster_loc.configure(
                text=os.path.basename(r) if r else sin_raster)
            if getattr(p, "prov_localizacion", ""):
                pcf._prov_localizacion.set(p.prov_localizacion)
            if getattr(p, "escala_localizacion", None):
                pcf._escala_localizacion.set(f"{p.escala_localizacion:,}")
            r = getattr(p, "ruta_capa_localizacion", "") or ""
            pcf._ruta_capa_loc.set(r)
            pcf._lbl_capa_loc.configure(
                text=os.path.basename(r) if r else "Sin capa seleccionada")
            d = getattr(p, "wms_custom_general", None) or {}
            pcf._wms_url.set(d.get("url", ""))
            pcf._wms_capa.set(d.get("capa", ""))
            pcf._wms_formato.set(d.get("formato", "image/png"))
            d = getattr(p, "wfs_custom_general", None) or {}
            pcf._wfs_url.set(d.get("url", ""))
            pcf._wfs_capa.set(d.get("capa", ""))
            d = getattr(p, "wms_custom_localizacion", None) or {}
            pcf._wms_loc_url.set(d.get("url", ""))
            pcf._wms_loc_capa.set(d.get("capa", ""))
            pcf._wms_loc_formato.set(d.get("formato", "image/png"))
            d = getattr(p, "wfs_custom_localizacion", None) or {}
            pcf._wfs_loc_url.set(d.get("url", ""))
            pcf._wfs_loc_capa.set(d.get("capa", ""))
            self.panel_config._on_proveedor_changed()
            self.panel_config._on_prov_loc_changed()
            self.panel_config.salida.set(p.carpeta_salida)
            if p.patron_nombre:
                self.panel_config.patron_nombre.set(p.patron_nombre)

            if p.escala_manual:
                self.panel_config._escala_manual.set(f"{p.escala_manual:,}")
            else:
                self.panel_config._escala_manual.set("0 (auto)")

            if p.color_infra:
                self.panel_config._color_infra = p.color_infra
                self.panel_config._lbl_color.configure(bg=p.color_infra)

            if hasattr(p, "calidad_pdf") and p.calidad_pdf:
                self.panel_config._calidad_pdf.set(p.calidad_pdf)

            # ── Transparencias ──
            self.panel_capas.transparencia.set(p.transparencia_montes)
            if hasattr(p, "transparencia_infra"):
                self.panel_capas.transparencia_infra.set(p.transparencia_infra)

            # ── Campos ──
            self.panel_campos._combo_encabezado.set(
                getattr(p, "campo_encabezado", "") or "(automatico)")

            # ── Layout y cajetin ──
            if p.layout_key:
                self.panel_cajetin._layout_key.set(p.layout_key)
                self.motor.layout_key = p.layout_key
            self.panel_cajetin.cargar_desde_proyecto(p.cajetin, p.plantilla)

            self.motor.set_cajetin(p.cajetin)
            self.motor.set_plantilla(p.plantilla)

            # ── Origen datos tabla ──
            self.panel_config._origen_datos.set(
                getattr(p, "origen_datos_tabla", "")
                or "Shapefile (capa cargada)")
            self.panel_config._on_origen_datos_changed()
            if not getattr(p, "ruta_excel_tabla", ""):
                self.panel_config._ruta_excel.set("")
                self.panel_config._lbl_excel.configure(
                    text="Sin archivo seleccionado")
                self.panel_config._poblar_columnas_excel([])
            if hasattr(p, "ruta_excel_tabla") and p.ruta_excel_tabla:
                self.panel_config._ruta_excel.set(p.ruta_excel_tabla)
                self.panel_config._lbl_excel.configure(
                    text=os.path.basename(p.ruta_excel_tabla))
                hoja = getattr(p, "hoja_excel_tabla", "") or ""
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(
                        p.ruta_excel_tabla, read_only=True, data_only=True)
                    self.panel_config._cb_hoja.configure(values=wb.sheetnames)
                    wb.close()
                    if hoja:
                        self.panel_config._hoja_excel.set(hoja)
                    self.panel_config._cargar_columnas_excel(
                        p.ruta_excel_tabla, hoja or wb.sheetnames[0])
                except Exception:
                    pass
            self.panel_config._hoja_excel.set(
                getattr(p, "hoja_excel_tabla", "") or "")
            self.panel_config._campo_enlace_shp.set(
                getattr(p, "campo_enlace_shp", "") or "")
            self.panel_config._campo_enlace_excel.set(
                getattr(p, "campo_enlace_excel", "") or "")
            if hasattr(p, "columnas_excel_activas") and p.columnas_excel_activas:
                cols_proy = p.columnas_excel_activas
                for col, var in self.panel_config._check_cols_excel.items():
                    var.set(col in cols_proy)

            # ── Simbologia ──
            if p.simbologia:
                from ..motor.simbologia import GestorSimbologia
                self.motor.gestor_simbologia = GestorSimbologia.from_dict(p.simbologia)

            # ── Generacion ──
            if hasattr(p, "modo_gen") and p.modo_gen:
                self.panel_generacion._modo_gen.set(p.modo_gen)
            if hasattr(p, "rango_desde"):
                self.panel_generacion._rango_desde.delete(0, "end")
                self.panel_generacion._rango_desde.insert(0, str(p.rango_desde))
            if hasattr(p, "rango_hasta"):
                self.panel_generacion._rango_hasta.delete(0, "end")
                self.panel_generacion._rango_hasta.insert(0, str(p.rango_hasta))
            if hasattr(p, "campo_agrupacion") and p.campo_agrupacion:
                self.panel_generacion._campo_agrupacion.set(p.campo_agrupacion)
            if hasattr(p, "multipagina"):
                self.panel_generacion._multipagina.set(p.multipagina)
            if hasattr(p, "incluir_portada"):
                self.panel_generacion._incluir_portada.set(p.incluir_portada)

            self._campos_visibles_proyecto = p.campos_visibles or []
            self._campos_orden_proyecto = getattr(p, 'campos_orden', []) or []
            self._simbologia_ui_proyecto = getattr(p, 'simbologia_ui', {}) or {}
            self._filtros_proyecto = getattr(p, 'filtros', {}) or {}

            # ── Auto-cargar capas desde rutas guardadas ──
            if not p.ruta_infra:
                # Nada que cargar: no dejar pendientes para la próxima
                # carga manual (filtro guardado, campos...)
                self._limpiar_pendientes_proyecto()
            if p.ruta_infra:
                layer_infra = getattr(p, 'layer_infra', "") or None
                mapeo = p.campo_mapeo if p.campo_mapeo else None
                self.panel_capas.cargar_infra_desde_proyecto(
                    p.ruta_infra, layer=layer_infra, mapeo=mapeo)

            if p.ruta_montes:
                layer_montes = getattr(p, 'layer_montes', "") or None
                self.panel_capas.cargar_montes_desde_proyecto(
                    p.ruta_montes, layer=layer_montes)

            # Las capas extra del proyecto SUSTITUYEN a las actuales (antes
            # se añadían otra vez en cada carga)
            self.motor.gestor_capas.capas.clear()
            self.panel_capas._actualizar_lista_capas()
            if p.capas_extra:
                self.panel_capas.cargar_capas_extra_desde_proyecto(p.capas_extra)

            # ── Capas WMS superpuestas (también las empuja al motor) ──
            self.panel_config.cargar_overlays(getattr(p, "overlays_wms", []) or [])
            self.motor.overlays_wms = self.panel_config.obtener_overlays()
            self.panel_generacion.cargar_opciones_salida(
                getattr(p, "opciones_salida", {}) or {})

            recientes.agregar_reciente(recientes.TIPO_PROYECTO, ruta)
            self._actualizar_menu_recientes_proyecto()
            self._refrescar_mapa(forzar=True)
            self._refrescar_toc()
            self._escribir_log(f"Proyecto cargado: {p.nombre}", "ok")
        except Exception as e:
            self._limpiar_pendientes_proyecto()
            self._escribir_log(f"Error al cargar proyecto: {e}", "error")
            messagebox.showerror("Error", str(e))

    def _actualizar_menu_recientes_proyecto(self):
        """Reconstruye el menú de proyectos recientes en la barra superior."""
        menu = self._menu_recientes_proy
        menu.delete(0, "end")
        lista = recientes.cargar_recientes().get(recientes.TIPO_PROYECTO, [])
        if not lista:
            menu.add_command(label="(sin recientes)", state="disabled")
            return
        for ruta in lista:
            existe = os.path.exists(ruta)
            etiqueta = os.path.basename(ruta) or ruta
            if existe:
                menu.add_command(
                    label=etiqueta,
                    command=lambda r=ruta: self._cargar_proyecto(r))
            else:
                menu.add_command(label=f"{etiqueta} (no encontrado)",
                                 state="disabled")

    def _limpiar_log(self):
        """Vacía el registro de proceso."""
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._escribir_log("Registro limpiado.", "info")

    # ── Atajos de teclado ─────────────────────────────────────────────────

    def _configurar_atajos(self):
        """Vincula atajos de teclado a las acciones principales.

        Cada manejador es tolerante: los validadores subyacentes ya
        comprueban si hay datos cargados, por lo que un atajo pulsado
        prematuramente simplemente no hace nada perjudicial.
        """
        self.bind("<Control-g>", self._atajo_generar)
        self.bind("<Control-G>", self._atajo_generar)
        self.bind("<F5>", self._atajo_vista_previa)
        self.bind("<Control-s>", self._atajo_guardar)
        self.bind("<Control-S>", self._atajo_guardar)
        self.bind("<Control-o>", self._atajo_cargar)
        self.bind("<Control-O>", self._atajo_cargar)
        self.bind("<Control-l>", self._atajo_limpiar_log)
        self.bind("<Control-L>", self._atajo_limpiar_log)

    def _foco_en_texto(self) -> bool:
        """True si el foco está en un widget de edición de texto.

        Los atajos no deben dispararse mientras el usuario escribe en un
        Entry/Combobox/Text (p. ej. Ctrl+S por costumbre al editar el
        patrón de nombre abriría el diálogo de guardar proyecto).
        """
        try:
            w = self.focus_get()
        except Exception:
            return False
        if isinstance(w, ttk.Combobox):
            # Un desplegable de solo lectura no admite escritura: no debe
            # bloquear los atajos tras elegir, p. ej., el proveedor
            try:
                return str(w.cget("state")) != "readonly"
            except Exception:
                return True
        return isinstance(w, (tk.Entry, tk.Text, ttk.Entry, tk.Spinbox))

    def _atajo_generar(self, event=None):
        if self._foco_en_texto():
            return
        try:
            self.panel_generacion._iniciar_generacion()
        except Exception as e:
            self._escribir_log(f"Atajo generar: {e}", "warn")
        return "break"

    def _atajo_vista_previa(self, event=None):
        if self._foco_en_texto():
            return
        try:
            self.panel_generacion._vista_previa()
        except Exception as e:
            self._escribir_log(f"Atajo vista previa: {e}", "warn")
        return "break"

    def _atajo_guardar(self, event=None):
        if self._foco_en_texto():
            return
        try:
            self._guardar_proyecto()
        except Exception as e:
            self._escribir_log(f"Atajo guardar: {e}", "warn")
        return "break"

    def _atajo_cargar(self, event=None):
        if self._foco_en_texto():
            return
        try:
            self._cargar_proyecto()
        except Exception as e:
            self._escribir_log(f"Atajo cargar: {e}", "warn")
        return "break"

    def _atajo_limpiar_log(self, event=None):
        if self._foco_en_texto():
            return
        try:
            self._limpiar_log()
        except Exception as e:
            self._escribir_log(f"Atajo limpiar log: {e}", "warn")
        return "break"

    def _mostrar_info(self):
        """Abre la ventana de informacion tecnica y manual de usuario."""
        panel_info = PanelInfo(self)
        panel_info.mostrar()
