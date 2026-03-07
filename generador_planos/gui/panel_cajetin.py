"""
Panel de configuración del cajetín profesional y plantilla de colores.

Permite configurar: autor, proyecto, número de proyecto, revisión,
firma, organización, subtítulo (estático o desde campo), logo,
número de plano inicial y colores de la plantilla.
"""

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog

from .estilos import (
    COLOR_PANEL, COLOR_TEXTO, COLOR_TEXTO_GRIS, COLOR_BORDE, COLOR_ENTRY,
    COLOR_ACENTO, FONT_BOLD, FONT_SMALL,
    crear_frame_seccion,
)


class PanelCajetin:
    """Panel de configuración del cajetín y plantilla de colores."""

    def __init__(self, parent, motor, callback_log):
        self.motor = motor
        self.callback_log = callback_log

        f = crear_frame_seccion(parent, "\U0001f4cb  CAJETÍN / PLANTILLA")

        # ── Campos del cajetín ──
        campos = [
            ("Autor:", "autor"),
            ("Proyecto:", "proyecto"),
            ("Nº Proyecto:", "num_proyecto"),
            ("Revisión:", "revision"),
            ("Firma:", "firma"),
        ]
        self._vars = {}
        row_idx = 0
        for label, key in campos:
            tk.Label(f, text=label, font=FONT_SMALL, bg=COLOR_PANEL,
                     fg=COLOR_TEXTO).grid(row=row_idx, column=0, sticky="w")
            var = tk.StringVar()
            tk.Entry(f, textvariable=var, font=FONT_SMALL, bg=COLOR_ENTRY,
                     fg=COLOR_TEXTO, insertbackground="white",
                     relief="flat").grid(row=row_idx + 1, column=0,
                                          sticky="ew", pady=(2, 4))
            self._vars[key] = var
            row_idx += 2

        self._vars["revision"].set("0")

        # ── Organización ──
        tk.Label(f, text="Organización:", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).grid(row=row_idx, column=0, sticky="w")
        self._org = tk.StringVar(
            value="")
        tk.Entry(f, textvariable=self._org, font=FONT_SMALL, bg=COLOR_ENTRY,
                 fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=row_idx + 1, column=0,
                                      sticky="ew", pady=(2, 4))
        row_idx += 2

        # ── Logo ──
        tk.Label(f, text="Logo (imagen):", font=FONT_SMALL, bg=COLOR_PANEL,
                 fg=COLOR_TEXTO).grid(row=row_idx, column=0, sticky="w")
        logo_f = tk.Frame(f, bg=COLOR_PANEL)
        logo_f.grid(row=row_idx + 1, column=0, sticky="ew", pady=(2, 4))
        self._logo_path = tk.StringVar(value="")
        self._lbl_logo = tk.Label(logo_f, text="Sin logo", font=FONT_SMALL,
                                   bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS)
        self._lbl_logo.pack(side="left", padx=(0, 6))
        tk.Button(logo_f, text="Elegir", command=self._elegir_logo,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left")
        tk.Button(logo_f, text="Quitar", command=self._quitar_logo,
                  font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                  relief="flat", cursor="hand2", padx=4).pack(side="left",
                                                                padx=(4, 0))
        row_idx += 2

        # ── Título del mapa ──
        tk.Label(f, text="Título del mapa:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=row_idx, column=0, sticky="w")
        self._titulo_mapa = tk.StringVar(value="")
        tk.Entry(f, textvariable=self._titulo_mapa, font=FONT_SMALL,
                 bg=COLOR_ENTRY, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=row_idx + 1, column=0,
                                      sticky="ew", pady=(2, 4))
        row_idx += 2

        # ── Subtítulo (estático o desde campo) ──
        tk.Label(f, text="Subtítulo cabecera:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=row_idx, column=0, sticky="w")
        self._subtitulo = tk.StringVar(value="PLANO DE INFRAESTRUCTURA FORESTAL")
        tk.Entry(f, textvariable=self._subtitulo, font=FONT_SMALL,
                 bg=COLOR_ENTRY, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat").grid(row=row_idx + 1, column=0,
                                      sticky="ew", pady=(2, 4))
        row_idx += 2

        tk.Label(f, text="Subtítulo desde campo (opcional):", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=row_idx, column=0, sticky="w")
        self._campo_subtitulo = tk.StringVar(value="")
        self._cb_campo_sub = ttk.Combobox(
            f, textvariable=self._campo_subtitulo,
            values=["(ninguno)"], state="readonly", font=FONT_SMALL,
        )
        self._cb_campo_sub.grid(row=row_idx + 1, column=0,
                                 sticky="ew", pady=(2, 4))
        self._cb_campo_sub.current(0)
        row_idx += 2

        # ── Nº plano inicial ──
        tk.Label(f, text="Nº plano inicial:", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=row_idx, column=0, sticky="w")
        self._num_plano_inicio = tk.StringVar(value="1")
        tk.Entry(f, textvariable=self._num_plano_inicio, font=FONT_SMALL,
                 bg=COLOR_ENTRY, fg=COLOR_TEXTO, insertbackground="white",
                 relief="flat", width=8).grid(row=row_idx + 1, column=0,
                                               sticky="w", pady=(2, 6))
        row_idx += 2

        # ── Etiquetas en el mapa (campo para nombres) ──
        tk.Label(f, text="Etiqueta en mapa (campo):", font=FONT_SMALL,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO).grid(
                 row=row_idx, column=0, sticky="w")
        self._campo_etiqueta = tk.StringVar(value="Nombre_Infra")
        self._cb_campo_etiq = ttk.Combobox(
            f, textvariable=self._campo_etiqueta,
            values=["(sin etiqueta)", "Nombre_Infra"], state="readonly",
            font=FONT_SMALL,
        )
        self._cb_campo_etiq.grid(row=row_idx + 1, column=0,
                                  sticky="ew", pady=(2, 6))
        self._cb_campo_etiq.current(1)
        row_idx += 2

        # ── Colores de plantilla ──
        tk.Label(f, text="Colores plantilla:", font=FONT_BOLD,
                 bg=COLOR_PANEL, fg=COLOR_TEXTO_GRIS).grid(
                 row=row_idx, column=0, sticky="w", pady=(4, 2))
        row_idx += 1

        self._colores = {
            "color_cabecera_fondo": "#1C2333",
            "color_cabecera_texto": "#FFFFFF",
            "color_cabecera_acento": "#2ECC71",
            "color_marco_exterior": "#1C2333",
            "color_marco_interior": "#2ECC71",
        }
        self._lbl_colores = {}

        etiquetas = {
            "color_cabecera_fondo": "Fondo cabecera",
            "color_cabecera_texto": "Texto cabecera",
            "color_cabecera_acento": "Acento cabecera",
            "color_marco_exterior": "Marco exterior",
            "color_marco_interior": "Marco interior",
        }

        for i, (key, label) in enumerate(etiquetas.items()):
            row_f = tk.Frame(f, bg=COLOR_PANEL)
            row_f.grid(row=row_idx + i, column=0, sticky="ew", pady=1)

            lbl_c = tk.Label(row_f, bg=self._colores[key], width=3,
                              relief="solid", bd=1)
            lbl_c.pack(side="left", padx=(0, 6))
            self._lbl_colores[key] = lbl_c

            def _elegir(k=key, lbl=lbl_c):
                c = colorchooser.askcolor(color=self._colores[k],
                                          title=f"Color: {k}")[1]
                if c:
                    self._colores[k] = c
                    lbl.configure(bg=c)

            tk.Button(row_f, text=label, command=_elegir,
                      font=FONT_SMALL, bg=COLOR_BORDE, fg=COLOR_TEXTO,
                      relief="flat", cursor="hand2").pack(side="left", fill="x",
                                                           expand=True)

        row_idx += len(etiquetas)

        # ── Botón aplicar ──
        tk.Button(f, text="Aplicar cajetín y plantilla",
                  command=self._aplicar, font=FONT_SMALL,
                  bg=COLOR_ACENTO, fg="#1A1A2E", relief="flat",
                  cursor="hand2", pady=3).grid(
                  row=row_idx, column=0, sticky="ew", pady=(6, 4))

        f.columnconfigure(0, weight=1)

    # ── Acciones ──────────────────────────────────────────────────────

    def _elegir_logo(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"),
                       ("Todos", "*.*")],
        )
        if ruta:
            self._logo_path.set(ruta)
            import os
            self._lbl_logo.configure(text=os.path.basename(ruta),
                                      fg=COLOR_ACENTO)

    def _quitar_logo(self):
        self._logo_path.set("")
        self._lbl_logo.configure(text="Sin logo", fg=COLOR_TEXTO_GRIS)

    def actualizar_campos_subtitulo(self, columnas: list):
        """Actualiza los combobox de campo para subtítulo y etiquetas."""
        cols = [c for c in columnas if c.lower() != "geometry"]
        valores_sub = ["(ninguno)"] + cols
        self._cb_campo_sub.configure(values=valores_sub)
        if self._campo_subtitulo.get() not in valores_sub:
            self._cb_campo_sub.current(0)

        valores_etiq = ["(sin etiqueta)"] + cols
        self._cb_campo_etiq.configure(values=valores_etiq)
        if self._campo_etiqueta.get() not in valores_etiq:
            # Default to Nombre_Infra if available
            if "Nombre_Infra" in cols:
                self._campo_etiqueta.set("Nombre_Infra")
            else:
                self._cb_campo_etiq.current(0)

    def _aplicar(self):
        cajetin = self.obtener_cajetin()
        plantilla = self.obtener_plantilla()
        self.motor.set_cajetin(cajetin)
        self.motor.set_plantilla(plantilla)
        self.callback_log("Cajetín y plantilla actualizados.", "info")

    def obtener_cajetin(self) -> dict:
        org = self._org.get().replace(" - ", "\n")
        campo_sub = self._campo_subtitulo.get()
        if campo_sub == "(ninguno)":
            campo_sub = ""
        try:
            num_inicio = int(self._num_plano_inicio.get())
        except ValueError:
            num_inicio = 1
        return {
            "autor": self._vars["autor"].get(),
            "proyecto": self._vars["proyecto"].get(),
            "num_proyecto": self._vars["num_proyecto"].get(),
            "revision": self._vars["revision"].get(),
            "firma": self._vars["firma"].get(),
            "organizacion": org,
            "titulo_mapa": self._titulo_mapa.get(),
            "subtitulo": self._subtitulo.get(),
            "campo_subtitulo": campo_sub,
            "logo_path": self._logo_path.get(),
            "num_plano_inicio": num_inicio,
            "campo_etiqueta": (self._campo_etiqueta.get()
                               if self._campo_etiqueta.get() != "(sin etiqueta)"
                               else ""),
        }

    def obtener_plantilla(self) -> dict:
        return dict(self._colores)

    def cargar_desde_proyecto(self, cajetin: dict, plantilla: dict):
        """Carga valores desde un proyecto guardado."""
        if cajetin:
            for key, var in self._vars.items():
                var.set(cajetin.get(key, ""))
            org = cajetin.get("organizacion", "")
            self._org.set(org.replace("\n", " - "))
            self._titulo_mapa.set(cajetin.get("titulo_mapa", ""))
            self._subtitulo.set(cajetin.get("subtitulo", ""))
            self._logo_path.set(cajetin.get("logo_path", ""))
            if self._logo_path.get():
                import os
                self._lbl_logo.configure(
                    text=os.path.basename(self._logo_path.get()),
                    fg=COLOR_ACENTO)
            campo_sub = cajetin.get("campo_subtitulo", "")
            if campo_sub:
                self._campo_subtitulo.set(campo_sub)
            self._num_plano_inicio.set(
                str(cajetin.get("num_plano_inicio", 1)))

        if plantilla:
            for key, color in plantilla.items():
                if key in self._colores:
                    self._colores[key] = color
                    if key in self._lbl_colores:
                        self._lbl_colores[key].configure(bg=color)
