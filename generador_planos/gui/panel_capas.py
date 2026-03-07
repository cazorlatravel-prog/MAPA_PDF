"""
Panel de carga de capas (Infraestructuras SHP/GDB + Montes SHP/GDB + Capas extra +
Transparencia).

Incluye previsualización rápida de la capa en un mini-canvas al cargarla,
diálogo de mapeo de campos, selección de capa dentro de geodatabases
y gestión de capas SHP/GDB adicionales.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE,
    COLOR_ACENTO, COLOR_ERROR,
    FONT_BOLD, FONT_SMALL,
    crear_frame_seccion, crear_boton,
)
from ..motor.maquetacion import ETIQUETAS_CAMPOS
from ..motor.capas_extra import TIPOS_CAPA

CAMPOS_ESPERADOS = list(ETIQUETAS_CAMPOS.keys())


class PanelCapas:
    """Panel lateral para carga de shapefiles y control de transparencia."""

    def __init__(self, parent, motor, callback_log, callback_tabla):
        self.motor = motor
        self.callback_log = callback_log
        self.callback_tabla = callback_tabla

        f = crear_frame_seccion(parent, "\U0001f4c2  CAPAS")

        # ── Infraestructuras ──
        tk.Label(f, text="Capa Infraestructuras *",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=0, column=0, sticky="w", pady=(0, 2))

        self._ruta_infra = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_infra, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=1, column=0, sticky="w")

        btn_infra_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_infra_f.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        btn_infra_f.columnconfigure(0, weight=1)
        btn_infra_f.columnconfigure(1, weight=1)
        crear_boton(btn_infra_f, "Cargar SHP", self._cargar_infra,
                    icono="\U0001f4e5").grid(row=0, column=0, sticky="ew", padx=(0, 2))
        crear_boton(btn_infra_f, "Cargar GDB", self._cargar_infra_gdb,
                    icono="\U0001f4c1").grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # ── Montes ──
        tk.Label(f, text="Capa Montes (opcional)",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=3, column=0, sticky="w", pady=(0, 2))

        self._ruta_montes = tk.StringVar(value="Sin cargar")
        tk.Label(f, textvariable=self._ruta_montes, font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS,
                 wraplength=240, justify="left").grid(row=4, column=0, sticky="w")

        btn_montes_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_montes_f.grid(row=5, column=0, sticky="ew", pady=(4, 2))
        btn_montes_f.columnconfigure(0, weight=1)
        btn_montes_f.columnconfigure(1, weight=1)
        crear_boton(btn_montes_f, "Cargar SHP", self._cargar_montes,
                    icono="\U0001f332").grid(row=0, column=0, sticky="ew", padx=(0, 2))
        crear_boton(btn_montes_f, "Cargar GDB", self._cargar_montes_gdb,
                    icono="\U0001f4c1").grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # ── Transparencia ──
        transp_header = tk.Frame(f, bg=COLOR_PANEL)
        transp_header.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        tk.Label(transp_header, text="Transparencia capa montes:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).pack(side="left")
        self._lbl_transp = tk.Label(transp_header, text="0.50", font=FONT_SMALL,
                                     bg=COLOR_PANEL, fg=COLOR_ACENTO)
        self._lbl_transp.pack(side="right")

        self.transparencia = tk.DoubleVar(value=0.5)
        self.transparencia.trace_add("write", lambda *_: self._lbl_transp.configure(
            text=f"{self.transparencia.get():.2f}"))
        sl = ttk.Scale(f, from_=0.0, to=1.0, variable=self.transparencia,
                        orient="horizontal")
        sl.grid(row=7, column=0, sticky="ew", pady=(2, 4))

        # ── Capas extra ──
        tk.Label(f, text="Capas adicionales:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=8, column=0, sticky="w", pady=(6, 2))

        self._frame_capas_extra = tk.Frame(f, bg=COLOR_PANEL)
        self._frame_capas_extra.grid(row=9, column=0, sticky="ew")

        btn_capas_f = tk.Frame(f, bg=COLOR_PANEL)
        btn_capas_f.grid(row=10, column=0, sticky="ew", pady=(4, 2))
        btn_capas_f.columnconfigure(0, weight=1)
        btn_capas_f.columnconfigure(1, weight=1)
        btn_capas_f.columnconfigure(2, weight=1)
        tk.Button(btn_capas_f, text="+ SHP",
                  command=self._añadir_capa_extra, font=FONT_SMALL,
                  bg=COLOR_BORDE, fg=COLOR_TEXTO, relief="flat",
                  cursor="hand2", padx=4).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        tk.Button(btn_capas_f, text="+ GDB",
                  command=self._añadir_capa_extra_gdb, font=FONT_SMALL,
                  bg=COLOR_BORDE, fg=COLOR_TEXTO, relief="flat",
                  cursor="hand2", padx=4).grid(row=0, column=1, sticky="ew", padx=2)
        tk.Button(btn_capas_f, text="- Eliminar",
                  command=self._eliminar_capa_extra, font=FONT_SMALL,
                  bg=COLOR_BORDE, fg=COLOR_TEXTO, relief="flat",
                  cursor="hand2", padx=4).grid(row=0, column=2, sticky="ew", padx=(2, 0))

        self._lista_capas = tk.Listbox(
            self._frame_capas_extra, height=3, font=FONT_SMALL,
            bg="#0D1117", fg=COLOR_TEXTO, selectbackground=COLOR_ACENTO,
            selectforeground="#1A1A2E", relief="flat",
        )
        self._lista_capas.pack(fill="x", pady=(2, 0))

        # ── Mini-canvas de previsualización ──
        self._preview_frame = tk.Frame(f, bg=COLOR_PANEL, height=120)
        self._preview_frame.grid(row=11, column=0, sticky="ew", pady=(4, 8))
        self._preview_frame.grid_propagate(False)
        self._canvas_widget = None

        f.columnconfigure(0, weight=1)

    def _cargar_infra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Infraestructuras",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        ok, msg, faltantes = self.motor.cargar_infraestructuras(ruta)
        if ok:
            self._ruta_infra.set(os.path.basename(ruta))
            self.callback_log(msg, "ok")
            self.callback_tabla()
            self._previsualizar(self.motor.gdf_infra)

            if faltantes:
                self._dialogo_mapeo_campos(faltantes)
        else:
            self._ruta_infra.set("Error al cargar")
            self.callback_log(msg, "error")
            messagebox.showerror("Error", msg)

    def _cargar_montes(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de Montes",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        ok, msg = self.motor.cargar_montes(ruta)
        if ok:
            self._ruta_montes.set(os.path.basename(ruta))
            self.callback_log(msg, "ok")
        else:
            self._ruta_montes.set("Error al cargar")
            self.callback_log(msg, "error")

    # ── GDB helpers ────────────────────────────────────────────────────

    def _listar_capas_gdb(self, ruta_gdb: str) -> list:
        """Lista las capas disponibles en una geodatabase (FileGDB / OpenFileGDB)."""
        try:
            import fiona
            # Intentar con driver OpenFileGDB (solo lectura, más compatible con ArcGIS)
            try:
                return fiona.listlayers(ruta_gdb, driver="OpenFileGDB")
            except Exception:
                pass
            # Fallback: driver por defecto
            return fiona.listlayers(ruta_gdb)
        except ImportError:
            pass
        # Fallback a geopandas
        import geopandas as _gpd
        df = _gpd.list_layers(ruta_gdb)
        return list(df["name"])

    @staticmethod
    def _encontrar_ruta_gdb(ruta: str) -> str | None:
        """Busca la carpeta .gdb en la ruta o sus padres."""
        # Si la propia ruta es un .gdb
        if ruta.lower().endswith(".gdb") and os.path.isdir(ruta):
            return ruta
        # Buscar .gdb en componentes del path (usuario seleccionó archivo dentro)
        partes = os.path.normpath(ruta).split(os.sep)
        for i, parte in enumerate(partes):
            if parte.lower().endswith(".gdb"):
                candidato = os.sep.join(partes[: i + 1])
                if os.path.isdir(candidato):
                    return candidato
        return None

    def _seleccionar_gdb(self, titulo: str = "Seleccionar Geodatabase"):
        """Abre diálogo para elegir GDB y devuelve (ruta_gdb, capa) o (None, None).

        Permite seleccionar la carpeta .gdb directamente o cualquier archivo
        dentro de ella (se auto-detecta la raíz .gdb).
        """
        # Primer intento: askdirectory para seleccionar la carpeta .gdb
        ruta = filedialog.askdirectory(title=titulo)
        if not ruta:
            return None, None

        ruta_gdb = self._encontrar_ruta_gdb(ruta)

        if ruta_gdb is None:
            # Si no se detectó .gdb, pedir que seleccione un archivo dentro
            messagebox.showinfo(
                "Seleccionar GDB",
                "No se detectó una geodatabase (.gdb).\n\n"
                "Selecciona cualquier archivo DENTRO de la carpeta .gdb\n"
                "(por ejemplo el archivo 'gdb' o cualquier .gdbtable).")
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
                    "No se encontró una carpeta .gdb en la ruta seleccionada.")
                return None, None

        try:
            capas = self._listar_capas_gdb(ruta_gdb)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la GDB:\n{e}")
            return None, None

        if not capas:
            messagebox.showinfo("GDB vacía", "La geodatabase no contiene capas.")
            return None, None

        if len(capas) == 1:
            return ruta_gdb, capas[0]

        # Diálogo de selección de capa
        seleccion = [None]
        dialog = tk.Toplevel()
        dialog.title("Seleccionar capa de la GDB")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("400x350")
        dialog.transient()
        dialog.grab_set()

        tk.Label(dialog, text=f"GDB: {os.path.basename(ruta_gdb)}",
                 font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_ACENTO).pack(
                 padx=10, pady=(10, 2))
        tk.Label(dialog, text=f"{len(capas)} capas encontradas. Selecciona una:",
                 font=FONT_SMALL, bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(
                 padx=10, pady=(0, 6))

        frame_list = tk.Frame(dialog, bg=COLOR_PANEL)
        frame_list.pack(fill="both", expand=True, padx=10)

        lb = tk.Listbox(frame_list, font=FONT_SMALL, bg="#0D1117",
                        fg=COLOR_TEXTO, selectbackground=COLOR_ACENTO,
                        selectforeground="#1A1A2E", relief="flat")
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
                messagebox.showinfo("Selección", "Selecciona una capa de la lista.")

        tk.Button(dialog, text="Cargar capa seleccionada", command=_aceptar,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", pady=4).pack(
                  padx=10, pady=10, fill="x")

        dialog.wait_window()
        if seleccion[0] is None:
            return None, None
        return ruta_gdb, seleccion[0]

    def _cargar_infra_gdb(self):
        """Carga infraestructuras desde una capa de geodatabase."""
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB de Infraestructuras")
        if not ruta:
            return

        ok, msg, faltantes = self.motor.cargar_infraestructuras(ruta, layer=capa)
        if ok:
            self._ruta_infra.set(f"{os.path.basename(ruta)} / {capa}")
            self.callback_log(msg, "ok")
            self.callback_tabla()
            self._previsualizar(self.motor.gdf_infra)
            if faltantes:
                self._dialogo_mapeo_campos(faltantes)
        else:
            self._ruta_infra.set("Error al cargar")
            self.callback_log(msg, "error")
            messagebox.showerror("Error", msg)

    def _cargar_montes_gdb(self):
        """Carga capa de montes desde una geodatabase."""
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB de Montes")
        if not ruta:
            return

        ok, msg = self.motor.cargar_montes(ruta, layer=capa)
        if ok:
            self._ruta_montes.set(f"{os.path.basename(ruta)} / {capa}")
            self.callback_log(msg, "ok")
        else:
            self._ruta_montes.set("Error al cargar")
            self.callback_log(msg, "error")

    def _añadir_capa_extra_gdb(self):
        """Añade capa extra desde una geodatabase."""
        ruta, capa = self._seleccionar_gdb(
            "Seleccionar GDB para capa adicional")
        if not ruta:
            return

        # Diálogo para nombre y tipo
        dialog = tk.Toplevel()
        dialog.title("Configurar capa GDB")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("350x200")
        dialog.transient()
        dialog.grab_set()

        tk.Label(dialog, text="Nombre de la capa:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(padx=10, pady=(10, 2))
        nombre_var = tk.StringVar(value=capa)
        tk.Entry(dialog, textvariable=nombre_var, font=FONT_SMALL,
                 bg=COLOR_BORDE, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").pack(padx=10, fill="x")

        tk.Label(dialog, text="Tipo de capa:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(padx=10, pady=(10, 2))
        tipo_var = tk.StringVar(value="Personalizada")
        ttk.Combobox(dialog, textvariable=tipo_var, values=TIPOS_CAPA,
                     state="readonly", font=FONT_SMALL).pack(padx=10, fill="x")

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

        tk.Button(dialog, text="Añadir capa", command=_aceptar,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", pady=4).pack(
                  padx=10, pady=10, fill="x")

    def _añadir_capa_extra(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar Shapefile de capa adicional",
            filetypes=[("Shapefile", "*.shp"), ("Todos", "*.*")],
        )
        if not ruta:
            return

        # Diálogo para nombre y tipo
        dialog = tk.Toplevel()
        dialog.title("Configurar capa")
        dialog.configure(bg=COLOR_PANEL)
        dialog.geometry("350x200")
        dialog.transient()
        dialog.grab_set()

        tk.Label(dialog, text="Nombre de la capa:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(padx=10, pady=(10, 2))
        nombre_var = tk.StringVar(
            value=os.path.splitext(os.path.basename(ruta))[0])
        tk.Entry(dialog, textvariable=nombre_var, font=FONT_SMALL,
                 bg=COLOR_BORDE, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").pack(padx=10, fill="x")

        tk.Label(dialog, text="Tipo de capa:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).pack(padx=10, pady=(10, 2))
        tipo_var = tk.StringVar(value="Personalizada")
        ttk.Combobox(dialog, textvariable=tipo_var, values=TIPOS_CAPA,
                     state="readonly", font=FONT_SMALL).pack(padx=10, fill="x")

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

        tk.Button(dialog, text="A\u00f1adir capa", command=_aceptar,
                  font=FONT_SMALL, bg=COLOR_ACENTO, fg="#1A1A2E",
                  relief="flat", cursor="hand2", pady=4).pack(
                  padx=10, pady=10, fill="x")

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
            self._canvas_widget.get_tk_widget().destroy()

        fig, ax = plt.subplots(1, 1, figsize=(3, 1.5), dpi=72)
        fig.patch.set_facecolor(COLOR_PANEL)
        ax.set_facecolor("#0D1117")

        try:
            gdf.plot(ax=ax, color=COLOR_ACENTO, linewidth=0.5, markersize=2, alpha=0.8)
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
        dialog.geometry("450x500")
        dialog.transient()
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Campos no encontrados en el Shapefile.\n"
                 "Selecciona el campo equivalente para cada uno:",
            font=FONT_BOLD, bg=COLOR_PANEL, fg=COLOR_TEXTO,
            justify="left", wraplength=420,
        ).pack(padx=10, pady=(10, 5))

        frame = tk.Frame(dialog, bg=COLOR_PANEL)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        combos = {}
        opciones = ["(ninguno)"] + cols_disponibles

        for i, campo in enumerate(faltantes):
            etiq = ETIQUETAS_CAMPOS.get(campo, campo)
            tk.Label(frame, text=f"{etiq}:", font=FONT_SMALL,
                     bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                     row=i, column=0, sticky="w", pady=2, padx=(0, 8))
            var = tk.StringVar(value="(ninguno)")
            cb = ttk.Combobox(frame, textvariable=var, values=opciones,
                              state="readonly", font=FONT_SMALL, width=25)
            cb.grid(row=i, column=1, sticky="ew", pady=2)
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
            dialog.destroy()

        crear_boton(dialog, "Aplicar mapeo", aplicar,
                    color_bg=COLOR_ACENTO, color_fg="#1A1A2E").pack(
                    pady=(5, 10), padx=10, fill="x")
