"""
Panel de carga de capas (Infraestructuras SHP/GDB + Montes SHP/GDB + Capas extra +
Transparencia).

Incluye previsualizacion rapida de la capa en un mini-canvas al cargarla,
dialogo de mapeo de campos, seleccion de capa dentro de geodatabases
y gestion de capas SHP/GDB adicionales.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .estilos import (
    COLOR_PANEL, COLOR_PANEL_ALT, COLOR_TEXTO, COLOR_TEXTO_GRIS,
    COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, COLOR_ACENTO2, COLOR_ACENTO3, COLOR_ERROR, COLOR_HEADER,
    COLOR_HOVER, COLOR_FONDO_APP,
    FONT_BOLD, FONT_SMALL, FONT_SECCION, FONT_BOTON,
    crear_frame_seccion, crear_boton, crear_entry, crear_label,
    crear_tooltip,
)
from . import recientes
from ..motor.maquetacion import ETIQUETAS_CAMPOS
from ..motor.capas_extra import TIPOS_CAPA

CAMPOS_ESPERADOS = list(ETIQUETAS_CAMPOS.keys())


class PanelCapas:
    """Panel lateral para carga de shapefiles y control de transparencia."""

    def __init__(self, parent, motor, callback_log, callback_tabla,
                 callback_montes_cargados=None):
        self.motor = motor
        self.callback_log = callback_log
        self.callback_tabla = callback_tabla
        self.callback_montes_cargados = callback_montes_cargados

        f = crear_frame_seccion(parent, "\U0001f4c2  CAPAS")

        # ── Infraestructuras ──
        crear_label(f, "Capa Infraestructuras", tipo="titulo").grid(
            row=0, column=0, sticky="w", pady=(0, 2))

        self._ruta_infra_completa = ""   # Ruta absoluta para guardar proyecto
        self._ruta_montes_completa = ""  # Ruta absoluta para guardar proyecto
        self._layer_infra = None         # Nombre de capa GDB (si aplica)
        self._layer_montes = None        # Nombre de capa GDB (si aplica)
        self._ruta_infra = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_infra, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=260, justify="left").grid(row=1, column=0, sticky="ew")

        btn_infra_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_infra_f.grid(row=2, column=0, sticky="ew", pady=(6, 4))
        btn_infra_f.columnconfigure(0, weight=1)
        btn_infra_f.columnconfigure(1, weight=1)
        _btn_infra_shp = crear_boton(btn_infra_f, "Cargar SHP", self._cargar_infra,
                    icono="\U0001f4e5")
        _btn_infra_shp.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        _btn_infra_gdb = crear_boton(btn_infra_f, "Cargar GDB", self._cargar_infra_gdb,
                    icono="\U0001f4c1")
        _btn_infra_gdb.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        crear_tooltip(
            _btn_infra_shp,
            "Carga el shapefile (.shp) de infraestructuras.\n"
            "Es la capa principal: una entidad por plano generado.")
        crear_tooltip(
            _btn_infra_gdb,
            "Carga las infraestructuras desde una geodatabase (.gdb).\n"
            "Permite elegir la capa dentro de la GDB.")

        # Menú de shapefiles recientes (fila propia dentro del frame de botones)
        self._mb_recientes = tk.Menubutton(
            btn_infra_f, text="Recientes ▾", font=FONT_SMALL,
            bg=COLOR_BORDE, fg=COLOR_TEXTO, activebackground=COLOR_ACENTO,
            activeforeground="#FFFFFF", relief="flat", cursor="hand2",
            bd=0, highlightthickness=0, padx=8, pady=3,
        )
        self._menu_recientes = tk.Menu(
            self._mb_recientes, tearoff=0,
            bg=COLOR_PANEL_ALT, fg=COLOR_TEXTO,
            activebackground=COLOR_ACENTO, activeforeground="#FFFFFF",
            font=FONT_SMALL)
        self._mb_recientes.configure(menu=self._menu_recientes)
        self._mb_recientes.grid(row=1, column=0, columnspan=2, sticky="w",
                                pady=(4, 0))
        crear_tooltip(
            self._mb_recientes,
            "Vuelve a abrir un shapefile de infraestructuras\n"
            "cargado recientemente.")
        self._menu_recientes_actualizar()

        # ── Montes ──
        crear_label(f, "Capa Montes (opcional)", tipo="titulo").grid(
            row=3, column=0, sticky="w", pady=(0, 2))

        self._ruta_montes = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_montes, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=260, justify="left").grid(row=4, column=0, sticky="ew")

        btn_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_montes_f.grid(row=5, column=0, sticky="ew", pady=(6, 4))
        btn_montes_f.columnconfigure(0, weight=1)
        btn_montes_f.columnconfigure(1, weight=1)
        _btn_montes_shp = crear_boton(btn_montes_f, "Cargar SHP", self._cargar_montes,
                    icono="\U0001f332")
        _btn_montes_shp.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        _btn_montes_gdb = crear_boton(btn_montes_f, "Cargar GDB", self._cargar_montes_gdb,
                    icono="\U0001f4c1")
        _btn_montes_gdb.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        crear_tooltip(
            _btn_montes_shp,
            "Carga el shapefile (.shp) de montes (capa opcional de fondo).")
        crear_tooltip(
            _btn_montes_gdb,
            "Carga la capa de montes desde una geodatabase (.gdb).")

        # ── Transparencia infraestructuras ──
        transp_infra_header = tk.Frame(f, bg=COLOR_PANEL)
        transp_infra_header.grid(row=6, column=0, sticky="ew", pady=(8, 0))
        crear_label(transp_infra_header, "Transparencia infraestructuras:",
                    tipo="secundario").pack(side="left")
        self._lbl_transp_infra = tk.Label(transp_infra_header, text="0.35",
                                           font=FONT_SMALL, bg=COLOR_PANEL,
                                           fg=COLOR_ACENTO)
        self._lbl_transp_infra.pack(side="right")

        self.transparencia_infra = tk.DoubleVar(value=0.35)
        self.transparencia_infra.trace_add("write", lambda *_: self._lbl_transp_infra.configure(
            text=f"{self.transparencia_infra.get():.2f}"))
        _sc_transp_infra = ttk.Scale(f, from_=0.0, to=1.0,
                  variable=self.transparencia_infra, orient="horizontal")
        _sc_transp_infra.grid(row=7, column=0, sticky="ew", pady=(2, 4))
        crear_tooltip(
            _sc_transp_infra,
            "Transparencia del relleno de las infraestructuras.\n"
            "0 = opaco · 1 = totalmente transparente.")

        # ── Transparencia montes ──
        transp_header = tk.Frame(f, bg=COLOR_PANEL)
        transp_header.grid(row=8, column=0, sticky="ew", pady=(4, 0))
        crear_label(transp_header, "Transparencia capa montes:",
                    tipo="secundario").pack(side="left")
        self._lbl_transp = tk.Label(transp_header, text="0.30", font=FONT_SMALL,
                                     bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_transp.pack(side="right")

        self.transparencia = tk.DoubleVar(value=0.3)
        self.transparencia.trace_add("write", lambda *_: self._lbl_transp.configure(
            text=f"{self.transparencia.get():.2f}"))
        _sc_transp_montes = ttk.Scale(f, from_=0.0, to=1.0,
                  variable=self.transparencia, orient="horizontal")
        _sc_transp_montes.grid(row=9, column=0, sticky="ew", pady=(2, 4))
        crear_tooltip(
            _sc_transp_montes,
            "Transparencia de la capa de montes.\n"
            "0 = opaco · 1 = totalmente transparente.")

        # ── Capas extra ──
        crear_label(f, "Capas adicionales:", tipo="titulo").grid(
            row=10, column=0, sticky="w", pady=(8, 2))

        self._frame_capas_extra = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_capas_extra.grid(row=11, column=0, sticky="ew")

        btn_capas_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_capas_f.grid(row=12, column=0, sticky="ew", pady=(4, 2))
        btn_capas_f.columnconfigure(0, weight=1)
        btn_capas_f.columnconfigure(1, weight=1)
        btn_capas_f.columnconfigure(2, weight=1)
        crear_boton(btn_capas_f, "+ SHP",
                    self._añadir_capa_extra).grid(
            row=0, column=0, sticky="ew", padx=(0, 2))
        crear_boton(btn_capas_f, "+ GDB",
                    self._añadir_capa_extra_gdb).grid(
            row=0, column=1, sticky="ew", padx=2)
        crear_boton(btn_capas_f, "Eliminar",
                    self._eliminar_capa_extra).grid(
            row=0, column=2, sticky="ew", padx=(2, 0))

        self._lista_capas = tk.Listbox(
            self._frame_capas_extra, height=3, font=FONT_SMALL,
            bg=COLOR_ENTRY, fg=COLOR_TEXTO, selectbackground=COLOR_ACENTO,
            selectforeground="#FFFFFF", relief="flat",
            highlightthickness=1, highlightbackground=COLOR_BORDE,
            highlightcolor=COLOR_ACENTO, bd=0,
        )
        self._lista_capas.pack(fill="x", pady=(2, 0))

        # ── Mini-canvas de previsualizacion ──
        self._preview_frame = tk.Frame(f, bg=COLOR_PANEL, height=120)
        self._preview_frame.grid(row=13, column=0, sticky="ew", pady=(6, 4))
        self._preview_frame.grid_propagate(False)
        self._canvas_widget = None

        f.columnconfigure(0, weight=1)

    def _pedir_nueva_ruta(self, ruta_original: str, tipo_capa: str) -> str | None:
        """Pide al usuario una nueva ruta cuando el archivo no se encuentra."""
        respuesta = messagebox.askyesno(
            "Archivo no encontrado",
            f"No se encuentra la capa de {tipo_capa}:\n\n"
            f"{ruta_original}\n\n"
            f"¿Desea seleccionar la nueva ubicación del archivo?")
        if not respuesta:
            return None

        es_gdb = ruta_original.lower().rstrip("/\\").endswith(".gdb")
        if es_gdb:
            nueva = filedialog.askdirectory(
                title=f"Seleccionar nueva ubicación GDB ({tipo_capa})")
        else:
            nueva = filedialog.askopenfilename(
                title=f"Seleccionar nueva ubicación ({tipo_capa})",
                filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")])
        return nueva if nueva else None

    def cargar_infra_desde_proyecto(self, ruta: str, layer: str = None,
                                     mapeo: dict = None):
        """Carga infraestructuras desde una ruta guardada en proyecto (sin diálogo)."""
        if not ruta:
            return
        if not os.path.exists(ruta):
            nueva = self._pedir_nueva_ruta(ruta, "infraestructuras")
            if not nueva:
                self.callback_log(
                    f"Capa de infraestructuras omitida (no encontrada).", "warn")
                return
            ruta = nueva

        def tarea():
            return self.motor.cargar_infraestructuras(ruta, layer=layer)

        def on_ok(resultado):
            ok, msg, faltantes = resultado
            if ok:
                if layer:
                    self._ruta_infra.set(
                        f"{os.path.basename(ruta)}\n{layer}")
                else:
                    self._ruta_infra.set(os.path.basename(ruta))
                self._ruta_infra_completa = ruta
                self._layer_infra = layer
                self._registrar_reciente_infra(ruta)
                self.callback_log(msg, "ok")
                # Aplicar mapeo guardado antes de notificar la tabla
                if mapeo:
                    self.motor.establecer_mapeo_campos(mapeo)
                    self.callback_log(
                        f"Mapeo de campos restaurado: {mapeo}", "info")
                self.callback_tabla()
                self._previsualizar(self.motor.gdf_infra)
            else:
                self.callback_log(msg, "error")

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga="Cargando infraestructuras del proyecto...")

    def cargar_montes_desde_proyecto(self, ruta: str, layer: str = None):
        """Carga montes desde una ruta guardada en proyecto (sin diálogo)."""
        if not ruta:
            return
        if not os.path.exists(ruta):
            nueva = self._pedir_nueva_ruta(ruta, "montes")
            if not nueva:
                self.callback_log(
                    f"Capa de montes omitida (no encontrada).", "warn")
                return
            ruta = nueva

        def tarea():
            return self.motor.cargar_montes(ruta, layer=layer)

        def on_ok(resultado):
            ok, msg = resultado
            if ok:
                if layer:
                    self._ruta_montes.set(
                        f"{os.path.basename(ruta)}\n{layer}")
                else:
                    self._ruta_montes.set(os.path.basename(ruta))
                self._ruta_montes_completa = ruta
                self._layer_montes = layer
                self.callback_log(msg, "ok")
                if self.callback_montes_cargados:
                    self.callback_montes_cargados()
            else:
                self.callback_log(msg, "error")

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga="Cargando montes del proyecto...")

    def cargar_capas_extra_desde_proyecto(self, capas_data: list):
        """Recarga capas extra desde la lista guardada en proyecto."""
        if not capas_data:
            return
        # Verificar rutas y pedir nuevas si no se encuentran
        for d in capas_data:
            ruta = d.get("ruta", "")
            if ruta and not os.path.exists(ruta):
                nombre = d.get("nombre", "desconocida")
                nueva = self._pedir_nueva_ruta(ruta, f"capa '{nombre}'")
                if nueva:
                    d["ruta"] = nueva
                else:
                    d["_omitir"] = True
                    self.callback_log(
                        f"Capa extra '{nombre}' omitida (no encontrada).", "warn")

        capas_validas = [d for d in capas_data if not d.get("_omitir")]
        errores = self.motor.gestor_capas.cargar_desde_dict(capas_validas)
        self._actualizar_lista_capas()
        n = len(self.motor.gestor_capas.capas)
        self.callback_log(
            f"Capas extra restauradas: {n} cargadas.", "ok")
        for err in errores:
            self.callback_log(err, "warn")

    def _ejecutar_en_hilo(self, tarea, callback_ok, callback_error=None,
                           msg_carga="Cargando..."):
        """Ejecuta una tarea pesada en un hilo secundario con feedback visual."""
        self.callback_log(f"\u23f3 {msg_carga}", "info")

        def _worker():
            try:
                resultado = tarea()
            except Exception as e:
                resultado = ("error", str(e))

            try:
                self._preview_frame.after(0, lambda: _on_done(resultado))
            except Exception:
                pass

        def _on_done(resultado):
            if isinstance(resultado, tuple) and len(resultado) > 0 and resultado[0] == "error":
                if callback_error:
                    callback_error(resultado[1])
                else:
                    self.callback_log(f"Error: {resultado[1]}", "error")
            else:
                callback_ok(resultado)

        threading.Thread(target=_worker, daemon=True).start()

    # ── Shapefiles recientes ────────────────────────────────────────────

    def _menu_recientes_actualizar(self):
        """Reconstruye el menú de shapefiles recientes."""
        menu = self._menu_recientes
        menu.delete(0, "end")
        lista = recientes.cargar_recientes().get(recientes.TIPO_SHAPEFILE, [])
        if not lista:
            menu.add_command(label="(sin recientes)", state="disabled")
            return
        for ruta in lista:
            existe = os.path.exists(ruta)
            etiqueta = os.path.basename(ruta) or ruta
            if existe:
                menu.add_command(
                    label=etiqueta,
                    command=lambda r=ruta: self._cargar_infra_reciente(r))
            else:
                menu.add_command(label=f"{etiqueta} (no encontrado)",
                                 state="disabled")

    def _cargar_infra_reciente(self, ruta: str):
        """Carga un shapefile reciente a través de la ruta de carga sin diálogo."""
        if not os.path.exists(ruta):
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El archivo ya no existe:\n{ruta}")
            self._menu_recientes_actualizar()
            return
        # Reutiliza la ruta de carga existente (maneja capa/mapeo)
        self.cargar_infra_desde_proyecto(ruta)

    def _registrar_reciente_infra(self, ruta: str):
        """Registra un shapefile como reciente y refresca el menú."""
        if ruta and ruta.lower().endswith(".shp"):
            recientes.agregar_reciente(recientes.TIPO_SHAPEFILE, ruta)
            self._menu_recientes_actualizar()

    def _cargar_infra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Infraestructuras",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        def tarea():
            return self.motor.cargar_infraestructuras(ruta)

        def on_ok(resultado):
            ok, msg, faltantes = resultado
            if ok:
                self._ruta_infra.set(os.path.basename(ruta))
                self._ruta_infra_completa = ruta
                self._layer_infra = None
                self._registrar_reciente_infra(ruta)
                self.callback_log(msg, "ok")
                self.callback_tabla()
                self._previsualizar(self.motor.gdf_infra)
                if faltantes:
                    self._dialogo_mapeo_campos(faltantes)
            else:
                self._ruta_infra.set("Error al cargar")
                self.callback_log(msg, "error")
                messagebox.showerror("Error", msg)

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga="Cargando infraestructuras...")

    def _cargar_montes(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Montes",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        def tarea():
            return self.motor.cargar_montes(ruta)

        def on_ok(resultado):
            ok, msg = resultado
            if ok:
                self._ruta_montes.set(os.path.basename(ruta))
                self._ruta_montes_completa = ruta
                self._layer_montes = None
                self.callback_log(msg, "ok")
                if self.callback_montes_cargados:
                    self.callback_montes_cargados()
            else:
                self._ruta_montes.set("Error al cargar")
                self.callback_log(msg, "error")

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga="Cargando montes...")

    # ── GDB helpers ────────────────────────────────────────────────────

    def _listar_capas_gdb(self, ruta_gdb: str) -> list:
        try:
            import fiona
            try:
                return fiona.listlayers(ruta_gdb, driver="OpenFileGDB")
            except Exception:
                pass
            return fiona.listlayers(ruta_gdb)
        except ImportError:
            pass
        import geopandas as _gpd
        df = _gpd.list_layers(ruta_gdb)
        return list(df["name"])

    @staticmethod
    def _encontrar_ruta_gdb(ruta: str) -> str | None:
        if ruta.lower().endswith(".gdb") and os.path.isdir(ruta):
            return ruta
        partes = os.path.normpath(ruta).split(os.sep)
        for i, parte in enumerate(partes):
            if parte.lower().endswith(".gdb"):
                candidato = os.sep.join(partes[: i + 1])
                if os.path.isdir(candidato):
                    return candidato
        return None

    def _seleccionar_gdb(self, titulo: str = "Seleccionar Geodatabase"):
        ruta = filedialog.askdirectory(title=titulo)
        if not ruta:
            return None, None

        ruta_gdb = self._encontrar_ruta_gdb(ruta)

        if ruta_gdb is None:
            messagebox.showinfo(
                "Seleccionar GDB",
                "No se detecto una geodatabase (.gdb).\n\n"
                "Selecciona cualquier archivo DENTRO de la carpeta .gdb.")
            ruta2 = filedialog.askopenfilename(
                title="Seleccionar archivo dentro de la .gdb",
                filetypes=[("Todos los archivos", "*.*")],
            )
            if not ruta2:
                return None, None
            ruta_gdb = self._encontrar_ruta_gdb(ruta2)
            if ruta_gdb is None:
                messagebox.showerror(
                    "Error",
                    "No se encontro una carpeta .gdb en la ruta seleccionada.")
                return None, None

        try:
            capas = self._listar_capas_gdb(ruta_gdb)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la GDB:\n{e}")
            return None, None

        if not capas:
            messagebox.showinfo("GDB vacia", "La geodatabase no contiene capas.")
            return None, None

        if len(capas) == 1:
            return ruta_gdb, capas[0]

        # Dialogo de seleccion de capa
        seleccion = [None]
        dialog = tk.Toplevel()
        dialog.title("Seleccionar capa de la GDB")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("420x380")
        dialog.transient()
        dialog.grab_set()

        tk.Label(dialog, text=f"GDB: {os.path.basename(ruta_gdb)}",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_ACENTO).pack(
                 padx=12, pady=(12, 4))
        tk.Label(dialog, text=f"{len(capas)} capas encontradas:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(
                 padx=12, pady=(0, 8))

        frame_list = tk.Frame(dialog, bg=COLOR_PANEL)
        frame_list.pack(fill="both", expand=True, padx=12)

        lb = tk.Listbox(frame_list, font=FONT_SMALL, bg=COLOR_ENTRY,
                        fg=COLOR_TEXTO, selectbackground=COLOR_ACENTO,
                        selectforeground="#FFFFFF", relief="flat",
                        highlightthickness=1, highlightbackground=COLOR_BORDE,
                        bd=0)
        sb = ttk.Scrollbar(frame_list, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for capa in capas:
            lb.insert("end", capa)

        def _aceptar():
            idx = lb.curselection()
            if idx:
                seleccion[0] = capas[idx[0]]
                dialog.destroy()
            else:
                messagebox.showinfo("Seleccion", "Selecciona una capa de la lista.")

        crear_boton(dialog, "Cargar capa seleccionada", _aceptar,
                    estilo="primario").pack(padx=12, pady=12, fill="x")

        dialog.wait_window()
        if seleccion[0] is None:
            return None, None
        return ruta_gdb, seleccion[0]

    def _cargar_infra_gdb(self):
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB de Infraestructuras")
        if not ruta:
            return

        def tarea():
            return self.motor.cargar_infraestructuras(ruta, layer=capa)

        def on_ok(resultado):
            ok, msg, faltantes = resultado
            if ok:
                self._ruta_infra.set(f"{os.path.basename(ruta)}\n{capa}")
                self._ruta_infra_completa = ruta
                self._layer_infra = capa
                self.callback_log(msg, "ok")
                self.callback_tabla()
                self._previsualizar(self.motor.gdf_infra)
                if faltantes:
                    self._dialogo_mapeo_campos(faltantes)
            else:
                self._ruta_infra.set("Error al cargar")
                self.callback_log(msg, "error")
                messagebox.showerror("Error", msg)

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga=f"Cargando GDB ({capa})...")

    def _cargar_montes_gdb(self):
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB de Montes")
        if not ruta:
            return

        def tarea():
            return self.motor.cargar_montes(ruta, layer=capa)

        def on_ok(resultado):
            ok, msg = resultado
            if ok:
                self._ruta_montes.set(f"{os.path.basename(ruta)}\n{capa}")
                self._ruta_montes_completa = ruta
                self._layer_montes = capa
                self.callback_log(msg, "ok")
                if self.callback_montes_cargados:
                    self.callback_montes_cargados()
            else:
                self._ruta_montes.set("Error al cargar")
                self.callback_log(msg, "error")

        self._ejecutar_en_hilo(tarea, on_ok,
                                msg_carga=f"Cargando GDB montes ({capa})...")

    def _añadir_capa_extra_gdb(self):
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB para capa adicional")
        if not ruta:
            return

        dialog = tk.Toplevel()
        dialog.title("Configurar capa GDB")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("380x220")
        dialog.transient()
        dialog.grab_set()

        crear_label(dialog, "Nombre de la capa:", tipo="titulo").pack(
            padx=12, pady=(12, 4), anchor="w")
        nombre_var = tk.StringVar(value=capa)
        crear_entry(dialog, textvariable=nombre_var).pack(
            padx=12, fill="x")

        crear_label(dialog, "Tipo de capa:", tipo="titulo").pack(
            padx=12, pady=(10, 4), anchor="w")
        tipo_var = tk.StringVar(value="Personalizada")
        ttk.Combobox(dialog, textvariable=tipo_var, values=TIPOS_CAPA,
                     state="readonly", font=FONT_SMALL).pack(padx=12, fill="x")

        def _aceptar():
            nombre = nombre_var.get().strip() or capa
            tipo = tipo_var.get()
            ok, msg, capa_obj = self.motor.gestor_capas.cargar_capa(
                ruta, nombre, tipo, layer=capa)
            if ok:
                self.callback_log(msg, "ok")
                self._actualizar_lista_capas()
            else:
                self.callback_log(msg, "error")
                messagebox.showerror("Error", msg)
            dialog.destroy()

        crear_boton(dialog, "Añadir capa", _aceptar,
                    estilo="primario").pack(padx=12, pady=12, fill="x")

    def _añadir_capa_extra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de capa adicional",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        dialog = tk.Toplevel()
        dialog.title("Configurar capa")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("380x220")
        dialog.transient()
        dialog.grab_set()

        crear_label(dialog, "Nombre de la capa:", tipo="titulo").pack(
            padx=12, pady=(12, 4), anchor="w")
        nombre_var = tk.StringVar(
            value=os.path.splitext(os.path.basename(ruta))[0])
        crear_entry(dialog, textvariable=nombre_var).pack(
            padx=12, fill="x")

        crear_label(dialog, "Tipo de capa:", tipo="titulo").pack(
            padx=12, pady=(10, 4), anchor="w")
        tipo_var = tk.StringVar(value="Personalizada")
        ttk.Combobox(dialog, textvariable=tipo_var, values=TIPOS_CAPA,
                     state="readonly", font=FONT_SMALL).pack(padx=12, fill="x")

        def _aceptar():
            nombre = nombre_var.get().strip() or "Capa"
            tipo = tipo_var.get()
            ok, msg, capa = self.motor.gestor_capas.cargar_capa(
                ruta, nombre, tipo)
            if ok:
                self.callback_log(msg, "ok")
                self._actualizar_lista_capas()
            else:
                self.callback_log(msg, "error")
                messagebox.showerror("Error", msg)
            dialog.destroy()

        crear_boton(dialog, "Añadir capa", _aceptar,
                    estilo="primario").pack(padx=12, pady=12, fill="x")

    def _eliminar_capa_extra(self):
        sel = self._lista_capas.curselection()
        if not sel:
            return
        nombre = self._lista_capas.get(sel[0]).split(" (")[0]
        self.motor.gestor_capas.eliminar_capa(nombre)
        self._actualizar_lista_capas()
        self.callback_log(f"Capa '{nombre}' eliminada.", "info")

    def _actualizar_lista_capas(self):
        self._lista_capas.delete(0, "end")
        for capa in self.motor.gestor_capas.capas:
            vis = "\u2713" if capa.visible else "\u2717"
            self._lista_capas.insert("end",
                                      f"{capa.nombre} ({capa.tipo}) [{vis}]")

    def _previsualizar(self, gdf):
        if self._canvas_widget is not None:
            try:
                plt.close(self._canvas_widget.figure)
            except Exception:
                pass
            self._canvas_widget.get_tk_widget().destroy()

        fig, ax = plt.subplots(1, 1, figsize=(3, 1.5), dpi=72)
        fig.patch.set_facecolor(COLOR_ENTRY)
        ax.set_facecolor(COLOR_ENTRY)

        try:
            gdf_preview = gdf.copy()
            gdf_preview["geometry"] = gdf_preview.geometry.simplify(
                tolerance=50, preserve_topology=False)
            if len(gdf_preview) > 2000:
                gdf_preview = gdf_preview.sample(2000, random_state=42)
            gdf_preview.plot(ax=ax, color=COLOR_ACENTO, linewidth=0.5,
                             markersize=2, alpha=0.8)
        except Exception:
            pass

        ax.set_axis_off()
        fig.tight_layout(pad=0.1)

        self._canvas_widget = FigureCanvasTkAgg(fig, master=self._preview_frame)
        self._canvas_widget.draw()
        self._canvas_widget.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def _dialogo_mapeo_campos(self, faltantes):
        cols_disponibles = self.motor.obtener_columnas_shapefile()
        if not cols_disponibles:
            return

        dialog = tk.Toplevel()
        dialog.title("Mapeo de campos")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("480x520")
        dialog.transient()
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Campos no encontrados en el Shapefile.\n"
                 "Selecciona el campo equivalente para cada uno:",
            font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO,
            justify="left", wraplength=440,
        ).pack(padx=12, pady=(12, 8))

        frame = tk.Frame(dialog, bg=COLOR_PANEL)
        frame.pack(fill="both", expand=True, padx=12, pady=4)

        combos = {}
        opciones = ["(ninguno)"] + cols_disponibles

        for i, campo in enumerate(faltantes):
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            crear_label(frame, f"{etiq}:", tipo="normal").grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 8))
            var = tk.StringVar(value="(ninguno)")
            cb = ttk.Combobox(frame, textvariable=var, values=opciones,
                              state="readonly", font=FONT_SMALL, width=25)
            cb.grid(row=i, column=1, sticky="ew", pady=3)
            combos[campo] = var

        frame.columnconfigure(1, weight=1)

        def aplicar():
            mapeo = {}
            for campo, var in combos.items():
                val = var.get()
                if val != "(ninguno)":
                    mapeo[campo] = val
            if mapeo:
                self.motor.establecer_mapeo_campos(mapeo)
                self.callback_log(
                    f"Mapeo de campos aplicado: {mapeo}", "info")
                # Refrescar tabla y paneles dependientes con el mapeo nuevo
                self.callback_tabla()
            dialog.destroy()

        crear_boton(dialog, "Aplicar mapeo", aplicar,
                    estilo="primario").pack(pady=(8, 12), padx=12, fill="x")
