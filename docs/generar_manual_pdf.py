"""Generador del Manual Tecnico en PDF para Generador de Planos Forestales v2.0.

Lee PROYECTO_COMPLETO.md y produce un PDF con maquetacion profesional
usando ReportLab. Incluye portada, indice automatico, cabecera/pie con
numeracion de paginas y estilos acordes a la paleta de la aplicacion.

Uso:
    python docs/generar_manual_pdf.py

Salida:
    docs/Manual_Tecnico_GeneradorPlanos_v2.0.pdf
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
FUENTE_MD = ROOT / "PROYECTO_COMPLETO.md"
SALIDA_PDF = ROOT / "docs" / "Manual_Tecnico_GeneradorPlanos_v2.0.pdf"

# Paleta corporativa (extraida de gui/estilos.py)
AZUL_NOCHE = colors.HexColor("#0F1923")
AZUL_PANEL = colors.HexColor("#162230")
ESMERALDA = colors.HexColor("#10B981")
ESMERALDA_OSC = colors.HexColor("#059669")
TEXTO_CLARO = colors.HexColor("#E8ECF1")
TEXTO_GRIS = colors.HexColor("#8899AA")
BORDE = colors.HexColor("#243447")


# ---------------------------------------------------------------------------
# Parser Markdown minimalista
# ---------------------------------------------------------------------------
class BloqueMD:
    """Representa un bloque logico extraido del markdown."""

    def __init__(self, tipo: str, contenido):
        self.tipo = tipo  # h1, h2, h3, h4, parrafo, lista, tabla, codigo, hr
        self.contenido = contenido

    def __repr__(self) -> str:
        return f"BloqueMD({self.tipo}, {str(self.contenido)[:40]!r})"


def parsear_markdown(texto: str) -> list[BloqueMD]:
    """Parser markdown suficiente para PROYECTO_COMPLETO.md."""
    lineas = texto.splitlines()
    bloques: list[BloqueMD] = []
    i = 0
    n = len(lineas)
    en_codigo = False
    buffer_codigo: list[str] = []
    buffer_parrafo: list[str] = []

    def _flush_parrafo() -> None:
        if buffer_parrafo:
            texto_p = " ".join(l.strip() for l in buffer_parrafo).strip()
            if texto_p:
                bloques.append(BloqueMD("parrafo", texto_p))
            buffer_parrafo.clear()

    while i < n:
        linea = lineas[i]

        # Bloques de codigo triple backtick
        if linea.startswith("```"):
            _flush_parrafo()
            if en_codigo:
                bloques.append(BloqueMD("codigo", "\n".join(buffer_codigo)))
                buffer_codigo = []
                en_codigo = False
            else:
                en_codigo = True
            i += 1
            continue
        if en_codigo:
            buffer_codigo.append(linea)
            i += 1
            continue

        # Separadores
        if linea.strip() in {"---", "***", "___"}:
            _flush_parrafo()
            bloques.append(BloqueMD("hr", None))
            i += 1
            continue

        # Cabeceras
        m = re.match(r"^(#{1,4})\s+(.*)$", linea)
        if m:
            _flush_parrafo()
            nivel = len(m.group(1))
            bloques.append(BloqueMD(f"h{nivel}", m.group(2).strip()))
            i += 1
            continue

        # Tablas (| ... |)
        if linea.lstrip().startswith("|") and i + 1 < n and re.match(
            r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lineas[i + 1]
        ):
            _flush_parrafo()
            cabecera = _parsear_fila_tabla(linea)
            i += 2  # salta separador
            filas: list[list[str]] = []
            while i < n and lineas[i].lstrip().startswith("|"):
                filas.append(_parsear_fila_tabla(lineas[i]))
                i += 1
            bloques.append(BloqueMD("tabla", {"cabecera": cabecera, "filas": filas}))
            continue

        # Listas
        if re.match(r"^\s*[-*+]\s+", linea):
            _flush_parrafo()
            items: list[str] = []
            while i < n and re.match(r"^\s*[-*+]\s+", lineas[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lineas[i]).strip())
                i += 1
            bloques.append(BloqueMD("lista", items))
            continue

        # Listas numeradas
        if re.match(r"^\s*\d+\.\s+", linea):
            _flush_parrafo()
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lineas[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lineas[i]).strip())
                i += 1
            bloques.append(BloqueMD("lista_num", items))
            continue

        # Linea en blanco -> flush
        if not linea.strip():
            _flush_parrafo()
            i += 1
            continue

        # Parrafo normal
        buffer_parrafo.append(linea)
        i += 1

    _flush_parrafo()
    return bloques


def _parsear_fila_tabla(linea: str) -> list[str]:
    partes = [p.strip() for p in linea.strip().strip("|").split("|")]
    return partes


# ---------------------------------------------------------------------------
# Formateo inline (negritas, cursivas, codigo, escape xml)
# ---------------------------------------------------------------------------
def formatear_inline(texto: str) -> str:
    """Convierte markdown inline a etiquetas minimalistas de ReportLab."""
    # Escape XML basico
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Codigo inline
    texto = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#059669">\1</font>', texto)
    # Negrita **x**
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", texto)
    # Cursiva *x*
    texto = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", texto)
    return texto


# ---------------------------------------------------------------------------
# Estilos de parrafos
# ---------------------------------------------------------------------------
def construir_estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    estilos: dict[str, ParagraphStyle] = {}

    estilos["Titulo"] = ParagraphStyle(
        name="Titulo",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=AZUL_NOCHE,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    estilos["Subtitulo"] = ParagraphStyle(
        name="Subtitulo",
        parent=base["Heading2"],
        fontName="Helvetica",
        fontSize=14,
        leading=18,
        textColor=ESMERALDA_OSC,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    estilos["Portada_meta"] = ParagraphStyle(
        name="Portada_meta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        alignment=TA_CENTER,
    )
    estilos["H1"] = ParagraphStyle(
        name="H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=AZUL_NOCHE,
        spaceBefore=18,
        spaceAfter=10,
        borderPadding=(0, 0, 4, 0),
        borderColor=ESMERALDA,
        borderWidth=0,
    )
    estilos["H2"] = ParagraphStyle(
        name="H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=ESMERALDA_OSC,
        spaceBefore=12,
        spaceAfter=6,
    )
    estilos["H3"] = ParagraphStyle(
        name="H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=AZUL_PANEL,
        spaceBefore=8,
        spaceAfter=4,
    )
    estilos["H4"] = ParagraphStyle(
        name="H4",
        parent=base["Heading4"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=6,
        spaceAfter=3,
    )
    estilos["Parrafo"] = ParagraphStyle(
        name="Parrafo",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1F2937"),
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    estilos["Lista"] = ParagraphStyle(
        name="Lista",
        parent=estilos["Parrafo"],
        leftIndent=14,
        bulletIndent=2,
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    estilos["Codigo"] = ParagraphStyle(
        name="Codigo",
        parent=base["Code"],
        fontName="Courier",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F1923"),
        backColor=colors.HexColor("#F1F5F9"),
        borderColor=BORDE,
        borderWidth=0.5,
        borderPadding=6,
        leftIndent=4,
        rightIndent=4,
        spaceAfter=8,
    )
    estilos["TOC1"] = ParagraphStyle(
        name="TOC1",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=AZUL_NOCHE,
        leftIndent=0,
        spaceAfter=2,
    )
    estilos["TOC2"] = ParagraphStyle(
        name="TOC2",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        leftIndent=16,
        spaceAfter=1,
    )
    estilos["TOC3"] = ParagraphStyle(
        name="TOC3",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXTO_GRIS,
        leftIndent=32,
        spaceAfter=1,
    )
    return estilos


# ---------------------------------------------------------------------------
# Construccion de tablas ReportLab desde markdown
# ---------------------------------------------------------------------------
def construir_tabla(datos: dict, ancho_disponible: float, estilo_celda: ParagraphStyle) -> Table:
    cabecera = datos["cabecera"]
    filas = datos["filas"]
    n_cols = len(cabecera)
    ancho_col = ancho_disponible / n_cols

    estilo_celda_tabla = ParagraphStyle(
        name="CeldaTabla",
        parent=estilo_celda,
        fontSize=8.5,
        leading=11,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    estilo_cabecera = ParagraphStyle(
        name="CabeceraTabla",
        parent=estilo_celda_tabla,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    data = [[Paragraph(formatear_inline(c), estilo_cabecera) for c in cabecera]]
    for fila in filas:
        # Ajusta numero de columnas
        fila_norm = (fila + [""] * n_cols)[:n_cols]
        data.append([Paragraph(formatear_inline(c), estilo_celda_tabla) for c in fila_norm])

    tabla = Table(data, colWidths=[ancho_col] * n_cols, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ESMERALDA_OSC),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
            ]
        )
    )
    return tabla


# ---------------------------------------------------------------------------
# DocTemplate con TOC y cabecera/pie
# ---------------------------------------------------------------------------
class ManualDocTemplate(BaseDocTemplate):
    """DocTemplate con TOC automatico y plantillas de pagina."""

    def __init__(self, filename: str, **kwargs) -> None:
        super().__init__(filename, pagesize=A4, **kwargs)

        margen_h = 2 * cm
        margen_v = 2.2 * cm

        frame_portada = Frame(
            margen_h,
            margen_v,
            A4[0] - 2 * margen_h,
            A4[1] - 2 * margen_v,
            id="portada",
        )
        frame_normal = Frame(
            margen_h,
            margen_v,
            A4[0] - 2 * margen_h,
            A4[1] - 2 * margen_v - 1.2 * cm,
            id="normal",
        )

        self.addPageTemplates(
            [
                PageTemplate(id="Portada", frames=[frame_portada], onPage=self._dibujar_portada),
                PageTemplate(id="Normal", frames=[frame_normal], onPage=self._dibujar_cabecera_pie),
            ]
        )

    def afterFlowable(self, flowable) -> None:
        """Registra entradas del TOC cuando aparecen cabeceras."""
        if isinstance(flowable, Paragraph):
            nombre_estilo = flowable.style.name
            if nombre_estilo in {"H1", "H2", "H3"}:
                nivel = {"H1": 0, "H2": 1, "H3": 2}[nombre_estilo]
                texto = flowable.getPlainText()
                clave = f"toc-{self.seq.nextf('tocentry')}"
                self.canv.bookmarkPage(clave)
                self.canv.addOutlineEntry(texto, clave, level=nivel, closed=(nivel > 0))
                self.notify("TOCEntry", (nivel, texto, self.page, clave))

    # ------------------------------------------------------------------
    # Decoracion de paginas
    # ------------------------------------------------------------------
    def _dibujar_portada(self, canvas, doc) -> None:
        canvas.saveState()
        w, h = A4
        # Fondo superior gradiente simulado (bloque solido)
        canvas.setFillColor(AZUL_NOCHE)
        canvas.rect(0, h - 11 * cm, w, 11 * cm, fill=1, stroke=0)
        # Franja esmeralda
        canvas.setFillColor(ESMERALDA)
        canvas.rect(0, h - 11 * cm - 0.35 * cm, w, 0.35 * cm, fill=1, stroke=0)
        # Pie
        canvas.setFillColor(AZUL_PANEL)
        canvas.rect(0, 0, w, 1.6 * cm, fill=1, stroke=0)
        canvas.setFillColor(TEXTO_GRIS)
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(
            w / 2, 0.65 * cm, "Generador de Planos Forestales v2.0  -  Manual Tecnico"
        )
        canvas.restoreState()

    def _dibujar_cabecera_pie(self, canvas, doc) -> None:
        canvas.saveState()
        w, h = A4
        # Cabecera
        canvas.setStrokeColor(ESMERALDA)
        canvas.setLineWidth(1.2)
        canvas.line(2 * cm, h - 1.6 * cm, w - 2 * cm, h - 1.6 * cm)
        canvas.setFillColor(AZUL_NOCHE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(2 * cm, h - 1.3 * cm, "GENERADOR DE PLANOS FORESTALES v2.0")
        canvas.setFillColor(TEXTO_GRIS)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 2 * cm, h - 1.3 * cm, "Manual Tecnico")
        # Pie
        canvas.setStrokeColor(BORDE)
        canvas.setLineWidth(0.4)
        canvas.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
        canvas.setFillColor(TEXTO_GRIS)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(2 * cm, 1.1 * cm, "Jose Caballero Sanchez - Cazorla, 2026 - MIT License")
        canvas.drawRightString(w - 2 * cm, 1.1 * cm, f"Pagina {doc.page}")
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Construccion de la historia (flowables)
# ---------------------------------------------------------------------------
def construir_portada(estilos: dict[str, ParagraphStyle]) -> list:
    hoy = dt.date.today().strftime("%d/%m/%Y")
    historia = [
        Spacer(1, 3.2 * cm),
        Paragraph(
            '<font color="#E8ECF1">MANUAL TECNICO</font>',
            ParagraphStyle(
                "PortadaEtiqueta",
                parent=estilos["Subtitulo"],
                fontSize=14,
                textColor=TEXTO_CLARO,
                alignment=TA_CENTER,
            ),
        ),
        Spacer(1, 0.4 * cm),
        Paragraph(
            '<font color="#FFFFFF">Generador de Planos Forestales</font>',
            ParagraphStyle(
                "PortadaTitulo",
                parent=estilos["Titulo"],
                fontSize=28,
                textColor=colors.white,
                alignment=TA_CENTER,
                leading=34,
            ),
        ),
        Spacer(1, 0.2 * cm),
        Paragraph(
            '<font color="#10B981">Version 2.0.0</font>',
            ParagraphStyle(
                "PortadaVersion",
                parent=estilos["Subtitulo"],
                fontSize=16,
                textColor=ESMERALDA,
                alignment=TA_CENTER,
            ),
        ),
        Spacer(1, 5.0 * cm),
        Paragraph("Aplicacion de escritorio Python para generacion", estilos["Portada_meta"]),
        Paragraph(
            "de planos cartograficos profesionales en serie (PDF A2/A3/A4)",
            estilos["Portada_meta"],
        ),
        Paragraph(
            "orientada a infraestructuras forestales de Andalucia (INFOCA)",
            estilos["Portada_meta"],
        ),
        Spacer(1, 2.5 * cm),
        Paragraph(
            "<b>Jose Caballero Sanchez</b>",
            ParagraphStyle(
                "PortadaAutor",
                parent=estilos["Portada_meta"],
                fontSize=13,
                textColor=AZUL_NOCHE,
            ),
        ),
        Paragraph("Cazorla (Jaen), Espana", estilos["Portada_meta"]),
        Spacer(1, 0.4 * cm),
        Paragraph(
            f"Documento generado el {hoy}",
            ParagraphStyle(
                "PortadaFecha",
                parent=estilos["Portada_meta"],
                fontSize=9,
                textColor=TEXTO_GRIS,
            ),
        ),
        Paragraph(
            "Repositorio: github.com/cazorlatravel-prog/MAPA_PDF",
            ParagraphStyle(
                "PortadaRepo",
                parent=estilos["Portada_meta"],
                fontSize=9,
                textColor=TEXTO_GRIS,
            ),
        ),
    ]
    return historia


def construir_indice(estilos: dict[str, ParagraphStyle]) -> list:
    toc = TableOfContents()
    toc.levelStyles = [estilos["TOC1"], estilos["TOC2"], estilos["TOC3"]]
    historia = [
        Paragraph("Indice de Contenidos", estilos["H1"]),
        Spacer(1, 0.3 * cm),
        toc,
    ]
    return historia


def construir_cuerpo(bloques: list[BloqueMD], estilos: dict[str, ParagraphStyle]) -> list:
    historia: list = []
    ancho_disponible = A4[0] - 4 * cm

    # Saltamos el primer H1 porque coincide con el titulo de portada
    primer_h1_saltado = False

    for bloque in bloques:
        if bloque.tipo == "h1":
            if not primer_h1_saltado:
                primer_h1_saltado = True
                continue
            historia.append(PageBreak())
            historia.append(Paragraph(formatear_inline(bloque.contenido), estilos["H1"]))
        elif bloque.tipo == "h2":
            historia.append(Paragraph(formatear_inline(bloque.contenido), estilos["H2"]))
        elif bloque.tipo == "h3":
            historia.append(Paragraph(formatear_inline(bloque.contenido), estilos["H3"]))
        elif bloque.tipo == "h4":
            historia.append(Paragraph(formatear_inline(bloque.contenido), estilos["H4"]))
        elif bloque.tipo == "parrafo":
            historia.append(Paragraph(formatear_inline(bloque.contenido), estilos["Parrafo"]))
        elif bloque.tipo == "lista":
            for item in bloque.contenido:
                historia.append(
                    Paragraph(
                        f"&bull; {formatear_inline(item)}",
                        estilos["Lista"],
                    )
                )
            historia.append(Spacer(1, 0.15 * cm))
        elif bloque.tipo == "lista_num":
            for idx, item in enumerate(bloque.contenido, start=1):
                historia.append(
                    Paragraph(
                        f"{idx}. {formatear_inline(item)}",
                        estilos["Lista"],
                    )
                )
            historia.append(Spacer(1, 0.15 * cm))
        elif bloque.tipo == "tabla":
            tabla = construir_tabla(bloque.contenido, ancho_disponible, estilos["Parrafo"])
            historia.append(Spacer(1, 0.1 * cm))
            historia.append(tabla)
            historia.append(Spacer(1, 0.25 * cm))
        elif bloque.tipo == "codigo":
            texto_codigo = bloque.contenido.replace("&", "&amp;")
            texto_codigo = texto_codigo.replace("<", "&lt;").replace(">", "&gt;")
            texto_codigo = texto_codigo.replace(" ", "&nbsp;").replace("\n", "<br/>")
            historia.append(Paragraph(texto_codigo, estilos["Codigo"]))
        elif bloque.tipo == "hr":
            historia.append(Spacer(1, 0.25 * cm))
    return historia


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not FUENTE_MD.exists():
        raise SystemExit(f"No se encuentra {FUENTE_MD}")

    texto = FUENTE_MD.read_text(encoding="utf-8")
    bloques = parsear_markdown(texto)

    estilos = construir_estilos()
    doc = ManualDocTemplate(str(SALIDA_PDF), title="Manual Tecnico - Generador de Planos Forestales v2.0",
                            author="Jose Caballero Sanchez", subject="Manual tecnico de la aplicacion")

    historia: list = []
    historia.extend(construir_portada(estilos))
    historia.append(NextPageTemplate("Normal"))
    historia.append(PageBreak())
    historia.extend(construir_indice(estilos))
    historia.append(PageBreak())
    historia.extend(construir_cuerpo(bloques, estilos))

    # Doble pasada para resolver TOC
    doc.multiBuild(historia)
    print(f"OK: PDF generado en {SALIDA_PDF.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
