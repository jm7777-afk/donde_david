"""
Script para generar el Trabajo Especial de Grado en formato Microsoft Word (.docx)
para el Instituto Universitario de Tecnología para la Informática (IUTEPI),
Carrera de Análisis de Sistemas.
Aplica con rigor las normas institucionales (IUTEPI 2023):
- Papel tamaño carta.
- Márgenes: Superior 4 cm (5 cm en títulos de capítulo), Inferior 3 cm, Izquierdo 4 cm, Derecho 3 cm.
- Tipografía: Arial 12 pt para el cuerpo, Arial 10 pt para cuadros y tablas.
- Interlineado 1.5 líneas, sangría en primera línea de 1.25 cm.
- Metodología de desarrollo: Kendall & Kendall (Fases I a VI).
- Incorporación exhaustiva de los nuevos módulos: Logs de servidor y telemetría,
  Pista de auditoría forense (Audit Trail) y Copias de seguridad con integridad SHA-256.
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn


def set_cell_background(cell, fill_hex):
    """Establece color de fondo de una celda en tabla."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Establece márgenes internos de una celda."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def create_thesis_document(output_path: str):
    doc = Document()

    # 1. Configuración de Página (Márgenes IUTEPI: Sup 4cm, Inf 3cm, Izq 4cm, Der 3cm)
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Cm(4)
    section.bottom_margin = Cm(3)
    section.left_margin = Cm(4)
    section.right_margin = Cm(3)

    # 2. Configuración de Estilo Base (Arial 12pt, Interlineado 1.5, Sin espacio posterior)
    style_normal = doc.styles['Normal']
    font_normal = style_normal.font
    font_normal.name = 'Arial'
    font_normal.size = Pt(12)
    font_normal.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    style_normal.paragraph_format.space_before = Pt(0)
    style_normal.paragraph_format.space_after = Pt(0)

    # Funciones Auxiliares para Adición de Elementos Estilizados
    def add_p(text, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=True, space_after=0):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        if indent:
            p.paragraph_format.first_line_indent = Cm(1.25)
        else:
            p.paragraph_format.first_line_indent = Cm(0)
        run = p.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.name = 'Arial'
        run.font.size = Pt(12)
        return p

    def add_cap_title(cap_num, cap_name):
        """Título de inicio de capítulo según normas IUTEPI (espacio superior ~5cm y triple interlineado)."""
        doc.add_page_break()
        p_num = doc.add_paragraph()
        p_num.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_num.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p_num.paragraph_format.space_before = Pt(28)  # Agrega 1 cm extra al margen para alcanzar los 5 cm
        p_num.paragraph_format.space_after = Pt(4)
        p_num.paragraph_format.first_line_indent = Cm(0)
        run_num = p_num.add_run(f"CAPÍTULO {cap_num}")
        run_num.bold = True
        run_num.font.name = 'Arial'
        run_num.font.size = Pt(14)

        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p_name.paragraph_format.space_before = Pt(0)
        p_name.paragraph_format.space_after = Pt(18)  # Espacio triple tras título de capítulo
        p_name.paragraph_format.first_line_indent = Cm(0)
        run_name = p_name.add_run(cap_name)
        run_name.bold = True
        run_name.font.name = 'Arial'
        run_name.font.size = Pt(14)

    def add_sub_title(text, level=1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Cm(0)
        run = p.add_run(text)
        run.bold = True
        run.font.name = 'Arial'
        run.font.size = Pt(12) if level == 1 else Pt(11)

    def add_table_custom(headers, rows, col_widths=None):
        table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Header
        hdr_cells = table.rows[0].cells
        for i, header_text in enumerate(headers):
            hdr_cells[i].text = header_text
            set_cell_background(hdr_cells[i], "1E293B")
            set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
            p = hdr_cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            for run in p.runs:
                run.bold = True
                run.font.name = 'Arial'
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)

        # Body Rows
        for r_idx, row_data in enumerate(rows):
            row_cells = table.rows[r_idx + 1].cells
            bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            for c_idx, cell_value in enumerate(row_data):
                row_cells[c_idx].text = str(cell_value)
                set_cell_background(row_cells[c_idx], bg_color)
                set_cell_margins(row_cells[c_idx], top=100, bottom=100, left=150, right=150)
                p = row_cells[c_idx].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
                for run in p.runs:
                    run.font.name = 'Arial'
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = RGBColor(30, 41, 59)

        if col_widths:
            for row in table.rows:
                for c_idx, width in enumerate(col_widths):
                    row.cells[c_idx].width = width

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # ==========================================
    # SECCIÓN PRELIMINAR 1: PORTADA OFICIAL (Norma IUTEPI pág 16)
    # ==========================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_inst.paragraph_format.space_after = Pt(2)
    p_inst.paragraph_format.first_line_indent = Cm(0)
    r1 = p_inst.add_run("REPÚBLICA BOLIVARIANA DE VENEZUELA\nINSTITUTO UNIVERSITARIO DE TECNOLOGÍA\nPARA LA INFORMÁTICA (IUTEPI)\nCOORDINACIÓN DE TRABAJO ESPECIAL DE GRADO\nCARRERA DE ANÁLISIS DE SISTEMAS")
    r1.bold = True
    r1.font.size = Pt(12)

    p_sp1 = doc.add_paragraph()
    p_sp1.paragraph_format.space_after = Pt(80)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p_title.paragraph_format.space_after = Pt(100)
    p_title.paragraph_format.first_line_indent = Cm(0)
    r_tit = p_title.add_run("SISTEMA WEB INTEGRAL ADMINISTRATIVO PARA LA GESTIÓN DE PEDIDOS POS TOUCH PARA EL RESTAURANTE “DONDE DAVID - FRESH & TASTY!” C.A., VALENCIA, ESTADO CARABOBO")
    r_tit.bold = True
    r_tit.font.size = Pt(13)

    p_author = doc.add_paragraph()
    p_author.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_author.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_author.paragraph_format.space_after = Pt(80)
    p_author.paragraph_format.first_line_indent = Cm(0)
    r_aut = p_author.add_run("Autor: Javier Mendoza\nTutor Académico: Ing. Asesor Técnico\nValencia, Noviembre del 2026")
    r_aut.bold = True
    r_aut.font.size = Pt(11)

    # ==========================================
    # SECCIÓN PRELIMINAR 2: PÁGINA DE OPCIÓN A TÍTULO (Norma IUTEPI pág 16)
    # ==========================================
    doc.add_page_break()
    p_opt = doc.add_paragraph()
    p_opt.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_opt.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_opt.paragraph_format.space_after = Pt(100)
    p_opt.paragraph_format.first_line_indent = Cm(0)
    r_opt1 = p_opt.add_run("SISTEMA WEB INTEGRAL ADMINISTRATIVO PARA LA GESTIÓN DE PEDIDOS POS TOUCH PARA EL RESTAURANTE “DONDE DAVID - FRESH & TASTY!” C.A., VALENCIA, ESTADO CARABOBO")
    r_opt1.bold = True
    r_opt1.font.size = Pt(13)

    p_opt_sub = doc.add_paragraph()
    p_opt_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_opt_sub.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p_opt_sub.paragraph_format.space_after = Pt(120)
    p_opt_sub.paragraph_format.first_line_indent = Cm(0)
    r_opt2 = p_opt_sub.add_run("Trabajo Especial de Grado presentado como requisito para optar al Título de Técnico Superior Universitario en Análisis de Sistemas")
    r_opt2.font.size = Pt(12)

    p_opt_foot = doc.add_paragraph()
    p_opt_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_opt_foot.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_opt_foot.paragraph_format.first_line_indent = Cm(0)
    r_opt3 = p_opt_foot.add_run("Autor: Javier Mendoza\nValencia, Noviembre del 2026")
    r_opt3.bold = True
    r_opt3.font.size = Pt(11)

    # ==========================================
    # SECCIÓN PRELIMINAR 3: ACTA DE PRESENTACIÓN (Norma IUTEPI pág 16)
    # ==========================================
    doc.add_page_break()
    p_acta_head = doc.add_paragraph()
    p_acta_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_acta_head.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_acta_head.paragraph_format.space_after = Pt(12)
    p_acta_head.paragraph_format.first_line_indent = Cm(0)
    r_ah = p_acta_head.add_run("REPÚBLICA BOLIVARIANA DE VENEZUELA\nINSTITUTO UNIVERSITARIO DE TECNOLOGÍA\nPARA LA INFORMÁTICA (IUTEPI)\nCOORDINACIÓN DE TRABAJO ESPECIAL DE GRADO")
    r_ah.bold = True
    r_ah.font.size = Pt(11)

    p_acta_tit = doc.add_paragraph()
    p_acta_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_acta_tit.paragraph_format.space_after = Pt(20)
    p_acta_tit.paragraph_format.first_line_indent = Cm(0)
    r_at = p_acta_tit.add_run("ACTA DE PRESENTACIÓN DE TRABAJO ESPECIAL DE GRADO")
    r_at.bold = True
    r_at.font.size = Pt(12)

    p_acta_body = doc.add_paragraph()
    p_acta_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_acta_body.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    p_acta_body.paragraph_format.first_line_indent = Cm(1.25)
    p_acta_body.paragraph_format.space_after = Pt(14)
    p_acta_body.add_run(
        "Quienes suscriben, miembros del jurado evaluador designados por la Coordinación de Trabajo Especial de Grado "
        "del Instituto Universitario de Tecnología para la Informática (IUTEPI), hacen constar que el presente Trabajo "
        "Especial de Grado titulado: “SISTEMA WEB INTEGRAL ADMINISTRATIVO PARA LA GESTIÓN DE PEDIDOS POS TOUCH PARA EL "
        "RESTAURANTE DONDE DAVID - FRESH & TASTY! C.A., VALENCIA, ESTADO CARABOBO”, presentado por el bachiller Javier "
        "Mendoza, Cédula de Identidad Nº __________________, para optar al título de Técnico Superior Universitario en "
        "Análisis de Sistemas, ha sido evaluado y considerado: ____________________ con una calificación de: _____ puntos."
    )

    p_acta_date = doc.add_paragraph()
    p_acta_date.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_acta_date.paragraph_format.space_after = Pt(50)
    p_acta_date.paragraph_format.first_line_indent = Cm(1.25)
    p_acta_date.add_run("En la ciudad de Valencia, a los ____ días del mes de Noviembre del año 2026.")

    # Firmas
    t_firmas = doc.add_table(rows=2, cols=2)
    t_firmas.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_firmas.rows[0].cells[0].paragraphs[0].text = "______________________________\nNombre:\nC.I.:\nTutor Académico"
    t_firmas.rows[0].cells[1].paragraphs[0].text = "______________________________\nNombre:\nC.I.:\nAsesor Técnico"
    t_firmas.rows[1].cells[0].paragraphs[0].text = "______________________________\nNombre:\nC.I.:\nJurado Calificador"
    t_firmas.rows[1].cells[1].paragraphs[0].text = "______________________________\nNombre:\nC.I.:\nCoordinador de T.E.G."
    for r in t_firmas.rows:
        for c in r.cells:
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(10)
            for run in p.runs:
                run.font.name = 'Arial'
                run.font.size = Pt(10)

    # ==========================================
    # SECCIÓN PRELIMINAR 4: DEDICATORIA Y AGRADECIMIENTO
    # ==========================================
    doc.add_page_break()
    p_ded_t = doc.add_paragraph()
    p_ded_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ded_t.paragraph_format.space_after = Pt(20)
    p_ded_t.paragraph_format.first_line_indent = Cm(0)
    r_dt = p_ded_t.add_run("DEDICATORIA")
    r_dt.bold = True
    r_dt.font.size = Pt(13)

    add_p(
        "A Dios Todopoderoso, por concederme salud, entendimiento y fortaleza en cada etapa de mi formación académica.",
        indent=True, space_after=10
    )
    add_p(
        "A mi familia, por su apoyo incondicional, su paciencia infinita y su constante motivación, pilares fundamentales "
        "para culminar con éxito este peldaño profesional.",
        indent=True, space_after=10
    )
    add_p(
        "A los docentes y tutores del IUTEPI, por sus valiosas enseñanzas, rigor metodológico y orientación técnica en el "
        "desarrollo del sistema y la elaboración de este Trabajo Especial de Grado.",
        indent=True, space_after=20
    )

    p_agr_t = doc.add_paragraph()
    p_agr_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_agr_t.paragraph_format.space_before = Pt(30)
    p_agr_t.paragraph_format.space_after = Pt(20)
    p_agr_t.paragraph_format.first_line_indent = Cm(0)
    r_at2 = p_agr_t.add_run("AGRADECIMIENTO")
    r_at2.bold = True
    r_at2.font.size = Pt(13)

    add_p(
        "Al Instituto Universitario de Tecnología para la Informática (IUTEPI), casa de estudios que abrió sus puertas para "
        "brindarme los conocimientos y herramientas que consolidan mi vocación en el análisis y desarrollo de sistemas.",
        indent=True, space_after=10
    )
    add_p(
        "A la directiva y equipo de trabajo del restaurante 'Donde David - Fresh & Tasty!' C.A., por facilitarme la información, "
        "el acceso a sus procesos operativos y la oportunidad de aportar una solución tecnológica tangible a su gestión comercial.",
        indent=True, space_after=10
    )

    # ==========================================
    # SECCIÓN PRELIMINAR 5: RESUMEN INSTITUCIONAL
    # ==========================================
    doc.add_page_break()
    p_res_head = doc.add_paragraph()
    p_res_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_res_head.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_res_head.paragraph_format.space_after = Pt(10)
    p_res_head.paragraph_format.first_line_indent = Cm(0)
    p_res_head.add_run(
        "INSTITUTO UNIVERSITARIO DE TECNOLOGÍA PARA LA INFORMÁTICA\n"
        "CARRERA DE ANÁLISIS DE SISTEMAS\n"
        "TRABAJO ESPECIAL DE GRADO\n\n"
        "SISTEMA WEB INTEGRAL ADMINISTRATIVO PARA LA GESTIÓN DE PEDIDOS POS TOUCH PARA EL RESTAURANTE “DONDE DAVID - FRESH & TASTY!” C.A., VALENCIA, ESTADO CARABOBO\n"
    ).bold = True

    p_res_meta = doc.add_paragraph()
    p_res_meta.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_res_meta.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p_res_meta.paragraph_format.space_after = Pt(14)
    p_res_meta.paragraph_format.first_line_indent = Cm(0)
    p_res_meta.add_run("Autor: Javier Mendoza\nTutor Académico: Asesor IUTEPI\nMes y Año: Noviembre 2026").font.size = Pt(11)

    p_res_title = doc.add_paragraph()
    p_res_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_res_title.paragraph_format.space_after = Pt(10)
    p_res_title.paragraph_format.first_line_indent = Cm(0)
    r_rt = p_res_title.add_run("RESUMEN")
    r_rt.bold = True
    r_rt.font.size = Pt(12)

    add_p(
        "La presente investigación tuvo como propósito desarrollar un sistema web integral administrativo para la gestión de "
        "pedidos POS Touch en el restaurante “Donde David - Fresh & Tasty!” C.A., ubicado en Valencia, Estado Carabobo. "
        "La investigación se enmarcó en la modalidad de Proyecto Factible, sustentada en un diseño de campo de tipo descriptivo. "
        "La metodología de desarrollo de software seleccionada fue el Ciclo de Vida de los Sistemas propuesto por Kendall & Kendall, "
        "estructurado en seis fases analíticas y de ingeniería.",
        indent=True, space_after=6
    )
    add_p(
        "La plataforma fue implementada en su backend mediante el lenguaje Python y el framework moderno FastAPI, complementada "
        "con SQLAlchemy 2.0 y Alembic para el control de versiones relacional de base de datos, JSON Web Tokens (JWT) para la "
        "autenticación basada en roles (RBAC) y WebSockets para la comunicación reactiva bidireccional en tiempo real. En el frontend, "
        "se diseñó una arquitectura desacoplada basada en Vanilla JavaScript y el sistema visual Toon UI, eliminando dependencias "
        "pesadas y satisfaciendo una estricta política de cero estilos en línea (zero-inline CSS).",
        indent=True, space_after=6
    )
    add_p(
        "Como robustecimiento para su pase definitivo a producción, se diseñaron e integraron tres módulos críticos de gobernanza: "
        "1) Módulo de Observabilidad y Logging Centralizado con rotación física de ficheros y telemetría HTTP en milisegundos; "
        "2) Módulo de Auditoría Forense (Audit Trail) con registro inmutable de transacciones y captura de diferencias JSON previas y nuevas; "
        "y 3) Módulo de Copias de Seguridad (Backups) y Recuperación ante Desastres (DR), con motor dual en caliente, cálculo de "
        "integridad criptográfica SHA-256 en manifiestos de metadatos, rotación automática de retención a 15 copias y salvaguarda de checkpoints "
        "previos a la restauración. La totalidad de las suites de prueba automatizadas (62 casos de backend, estilos, auditoría, logs y backups) "
        "fueron ejecutadas satisfactoriamente, certificando la estabilidad, seguridad y operabilidad de la solución.",
        indent=True, space_after=8
    )
    add_p(
        "Descriptores: Sistema Web, POS Touch, Kendall & Kendall, FastAPI, Observabilidad, Auditoría Forense, Backups SHA-256, Restaurante.",
        bold=True, indent=False, space_after=15
    )

    # ==========================================
    # SECCIÓN PRELIMINAR 6: ÍNDICE GENERAL (Estructurado)
    # ==========================================
    doc.add_page_break()
    p_ind = doc.add_paragraph()
    p_ind.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ind.paragraph_format.space_after = Pt(16)
    p_ind.paragraph_format.first_line_indent = Cm(0)
    p_ind.add_run("ÍNDICE GENERAL").bold = True

    index_items = [
        ("PORTADA", "i"),
        ("PÁGINA DE OPCIÓN A TÍTULO", "ii"),
        ("ACTA DE PRESENTACIÓN DE TRABAJO ESPECIAL DE GRADO", "iii"),
        ("DEDICATORIA", "iv"),
        ("AGRADECIMIENTO", "v"),
        ("RESUMEN", "vi"),
        ("INTRODUCCIÓN", "1"),
        ("CAPÍTULO I: EL PROBLEMA", "3"),
        ("   1.1. Planteamiento del Problema", "3"),
        ("   1.2. Propósito del Estudio", "6"),
        ("      1.2.1. Objetivo General", "6"),
        ("      1.2.2. Objetivos Específicos", "6"),
        ("   1.3. Justificación de la Investigación", "7"),
        ("   1.4. Delimitación de la Investigación", "9"),
        ("CAPÍTULO II: MARCO REFERENCIAL", "11"),
        ("   2.1. Antecedentes de la Investigación", "11"),
        ("   2.2. Bases Teóricas", "14"),
        ("   2.3. Bases Legales", "19"),
        ("   2.4. Operacionalización de Variables", "22"),
        ("   2.5. Definición de Términos Básicos", "24"),
        ("CAPÍTULO III: MARCO METODOLÓGICO", "27"),
        ("   3.1. Diseño de la Investigación", "27"),
        ("   3.2. Modalidad y Tipo de Investigación", "28"),
        ("   3.3. Unidad de Análisis: Sujetos u Objetos de Estudio", "29"),
        ("   3.4. Técnicas e Instrumentos de Recolección de Datos", "30"),
        ("   3.5. Técnicas de Análisis de Datos", "32"),
        ("   3.6. Fases del Proyecto según Metodología Kendall & Kendall", "33"),
        ("CAPÍTULO IV: DISEÑO DE LA PROPUESTA", "35"),
        ("   4.1. Objetivos Específicos de la Propuesta", "35"),
        ("   4.2. Fase I: Identificación de Problemas, Oportunidades y Objetivos", "36"),
        ("   4.3. Fase II: Determinación de Requerimientos de Información", "39"),
        ("   4.4. Fase III: Análisis de las Necesidades del Sistema", "42"),
        ("   4.5. Fase IV: Diseño del Sistema Recomendado", "47"),
        ("   4.6. Fase V: Desarrollo y Documentación del Software", "54"),
        ("   4.7. Fase VI: Pruebas y Mantenimiento del Sistema", "60"),
        ("CAPÍTULO V: CONCLUSIONES Y RECOMENDACIONES", "65"),
        ("   5.1. Conclusiones", "65"),
        ("   5.2. Recomendaciones", "67"),
        ("REFERENCIAS BIBLIOGRÁFICAS", "69"),
        ("ANEXOS", "72"),
    ]
    for title_text, page_num in index_items:
        p_row = doc.add_paragraph()
        p_row.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        p_row.paragraph_format.space_after = Pt(2)
        p_row.paragraph_format.first_line_indent = Cm(0)
        p_row.add_run(title_text)
        # Línea de puntos de tabulación
        dots_count = max(5, 75 - len(title_text))
        p_row.add_run(" " + ("." * dots_count) + " ")
        p_row.add_run(page_num).bold = True

    # ==========================================
    # SECCIÓN: INTRODUCCIÓN
    # ==========================================
    doc.add_page_break()
    p_intro_t = doc.add_paragraph()
    p_intro_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_intro_t.paragraph_format.space_before = Pt(28)
    p_intro_t.paragraph_format.space_after = Pt(18)
    p_intro_t.paragraph_format.first_line_indent = Cm(0)
    p_intro_t.add_run("INTRODUCCIÓN").bold = True

    add_p(
        "En la dinámica contemporánea del sector de alimentos y servicios gastronómicos, la velocidad, exactitud y consistencia "
        "en la captura y procesamiento de órdenes comerciales representan el eje neurálgico de la rentabilidad y la fidelización "
        "del cliente. La recepción y despacho de comandas en restaurantes de servicio rápido (Fast Food) involucran una interacción "
        "continua y sincronizada entre el comensal, el personal de atención en salón, los preparadores en cocina, los operadores de "
        "caja y la administración central. La ausencia de canales informáticos integrados propicia demoras operativas, discrepancias en "
        "los saldos contables, descoordinación en la cocina y vulnerabilidad ante incidentes de pérdida de datos.",
        indent=True, space_after=6
    )
    add_p(
        "El restaurante “Donde David - Fresh & Tasty!” C.A., ubicado en el municipio Valencia del Estado Carabobo, ha experimentado "
        "un incremento en el volumen de sus transacciones cotidianas. Dicho crecimiento evidenció la imperiosa necesidad de reemplazar "
        "los registros manuales o fragmentados por una solución informática centralizada basada en tecnología web, provista de una "
        "interfaz de Punto de Venta Táctil (POS Touch) de alta eficiencia ergonómica, apta para operar de forma unificada las modalidades "
        "de atención en mesa, pedidos para llevar (takeout) y despachos a domicilio (delivery).",
        indent=True, space_after=6
    )
    add_p(
        "Para responder a esta exigencia de manera rigurosa, la presente investigación desarrolló un sistema web integral bajo la modalidad "
        "de Proyecto Factible con diseño de campo-descriptivo, adoptando la metodología del Ciclo de Vida de los Sistemas formulada por "
        "Kendall & Kendall. En la etapa de ingeniería y preparación para producción, se incorporaron y certificaron tres pilares de gobernanza "
        "tecnológica: 1) Un sistema de observabilidad y logging estructurado en tiempo real con telemetría de latencias HTTP; 2) Una pista "
        "de auditoría forense inmutable (Audit Trail) que registra el antes y el después de cada transacción crítica; y 3) Un módulo de copias "
        "de seguridad criptográficas con cálculo de hashes SHA-256 y salvaguardas de recuperación ante desastres (Disaster Recovery).",
        indent=True, space_after=6
    )
    add_p(
        "El documento académico se organiza en cinco capítulos estructurados conforme a la normativa oficial del IUTEPI: "
        "El Capítulo I contextualiza el problema, delimitando propósitos, objetivos y justificación. El Capítulo II fundamenta "
        "el marco teórico, antecedentes, bases legales y definición de términos. El Capítulo III detalla el marco metodológico "
        "y las técnicas de recolección de información. El Capítulo IV despliega exhaustivamente el diseño de la propuesta según las "
        "seis fases de Kendall & Kendall, documentando la arquitectura, la base de datos, las interfaces y las pruebas automatizadas. "
        "Finalmente, el Capítulo V expone las conclusiones y recomendaciones derivadas de la implantación.",
        indent=True, space_after=12
    )

    # ==========================================
    # CAPÍTULO I: EL PROBLEMA
    # ==========================================
    add_cap_title("I", "EL PROBLEMA")

    add_sub_title("1.1. Planteamiento del Problema", level=1)
    add_p(
        "En el contexto gastronómico de la ciudad de Valencia, las empresas dedicadas al expendio de comida rápida enfrentan una intensa "
        "competitividad que exige altos niveles de celeridad, control de inventario y calidad de servicio. La gestión de pedidos no se limita "
        "a la toma de notas sobre platos o bebidas, sino que constituye una transacción integral que conecta la disponibilidad de insumos en "
        "almacén con la preparación física en la cocina y la conciliación monetaria en la caja registradora. Cuando estos flujos operan sobre "
        "formatos impresos en papel, comandas verbales o programas informáticos aislados, la sincronía de la empresa se fragmenta.",
        indent=True, space_after=6
    )
    add_p(
        "En el restaurante “Donde David - Fresh & Tasty!” C.A., el diagnóstico inicial reveló que la captura de órdenes se efectuaba a través "
        "de talonarios físicos o anotaciones dispersas. Esta práctica ocasionaba errores recurrentes en la transcripción de las comandas, "
        "omisión de especificaciones de ingredientes por parte del cliente, retrasos en la entrega a la línea de cocina y duplicidad de pedidos. "
        "Asimismo, el personal de caja presentaba marcadas demoras al totalizar las ventas en diferentes denominaciones monetarias (Bolívares y Dólares), "
        "dada la volatilidad cambiaria y la necesidad de aplicar tasas de cambio oficiales en tiempo real.",
        indent=True, space_after=6
    )
    add_p(
        "Adicionalmente, el área gerencial carecía de mecanismos automatizados para supervisar la trazabilidad de los usuarios en el sistema, "
        "desconociendo qué empleado realizaba modificaciones sobre los precios del menú, quién autorizaba anulación de cobros o en qué momento "
        "se generaban discrepancias en el arqueo diario. Tampoco existía una política automatizada de respaldos de información, lo que exponía "
        "al restaurante a pérdidas catastróficas de su historial comercial ante fallas eléctricas o averías en los discos de almacenamiento local.",
        indent=True, space_after=6
    )
    add_p(
        "De no abordarse esta problemática de manera estructural, el restaurante afrontaría consecuencias críticas: incremento sustancial en los "
        "tiempos de espera de los comensales, pérdidas económicas derivadas de fugas de inventario y errores de cobro, insatisfacción de los clientes "
        "y una absoluta indefensión operativa ante fallas técnicas. Por tanto, se planteó como solución el desarrollo de un Sistema Web Integral "
        "Administrativo dotado de un módulo POS Touch intuitivo, complementado con observabilidad continua de peticiones, trazabilidad forense "
        "inmutable de auditoría y respaldo criptográfico automatizado de la base de datos.",
        indent=True, space_after=12
    )

    add_sub_title("1.2. Propósito del Estudio", level=1)
    add_p(
        "El propósito general de este estudio radica en transformar sustancialmente los procesos operativos y administrativos del restaurante "
        "“Donde David - Fresh & Tasty!” C.A., dotándolo de una plataforma web moderna, segura y escalable que optimice el ciclo de vida del "
        "pedido mediante interfaces táctiles y garantice la continuidad y gobernanza del negocio bajo estándares de producción.",
        indent=True, space_after=6
    )

    add_sub_title("1.2.1. Objetivo General", level=2)
    add_p(
        "Desarrollar un sistema web integral administrativo para la gestión de pedidos POS Touch para el restaurante “Donde David - Fresh & Tasty!” C.A., "
        "ubicado en Valencia, Estado Carabobo, durante el año 2026, mediante la aplicación de la metodología de Kendall & Kendall y una arquitectura "
        "modular orientada a servicios, a fin de centralizar la información comercial, controlar el acceso por roles y fortalecer la seguridad y observabilidad operativa.",
        bold=True, indent=True, space_after=10
    )

    add_sub_title("1.2.2. Objetivos Específicos", level=2)
    obj_esp = [
        "1. Diagnosticar los procesos actuales vinculados a la toma de pedidos, despacho en cocina, control de inventarios, cobranza en caja y administración en el restaurante.",
        "2. Determinar los requerimientos de información, funcionales y no funcionales, indispensables para la arquitectura del sistema web integral y el módulo POS Touch.",
        "3. Diseñar la arquitectura lógica, el modelo relacional de datos normalizado, los diagramas de flujo y las interfaces ergonómicas adaptadas a pantallas táctiles.",
        "4. Desarrollar el sistema web integrando los módulos de autenticación RBAC, punto de venta táctil, monitor de cocina KDS, gestión de mesas, catálogo e inventario.",
        "5. Implementar los módulos críticos de producción: sistema de logs con telemetría de latencia, pista de auditoría forense inmutable y copias de seguridad con integridad criptográfica SHA-256.",
        "6. Ejecutar las pruebas unitarias, de integración, de estilización visual y de rendimiento del software para certificar su operatividad y robustez en entorno real.",
    ]
    for o in obj_esp:
        add_p(o, indent=True, space_after=4)

    add_sub_title("1.3. Justificación de la Investigación", level=1)
    add_p(
        "Desde la perspectiva práctica, la investigación aporta una herramienta tecnológica directamente aplicable a la resolución de "
        "los cuellos de botella del restaurante. La incorporación de un POS Touch simplifica sustancialmente la toma de comandas, permitiendo "
        "que los meseros o cajeros operen con mayor velocidad y menor margen de error, lo que repercute en una atención ágil y una mayor rotación de mesas.",
        indent=True, space_after=6
    )
    add_p(
        "Desde la perspectiva técnica y metodológica, el proyecto constituye un referente de ingeniería al aplicar la metodología Kendall & Kendall "
        "y desacoplar el sistema en capas independientes: transporte REST con FastAPI, persistencia controlada con SQLAlchemy y Alembic, y frontend "
        "Toon UI bajo una política estricta de cero estilos en línea. La inclusión de telemetría HTTP en milisegundos, auditoría de estados previos y "
        "nuevos y respaldos en caliente con firmas SHA-256 eleva el software al estándar industrial de resiliencia y ciberdefensa.",
        indent=True, space_after=6
    )
    add_p(
        "Desde el ángulo institucional y social, este Trabajo Especial de Grado demuestra la capacidad del Técnico Superior Universitario en "
        "Análisis de Sistemas egresado del IUTEPI para formular, liderar y ejecutar proyectos de alta complejidad técnica que responden a las "
        "necesidades del tejido empresarial venezolano, promoviendo la modernización de los comercios locales a través de tecnologías de código abierto.",
        indent=True, space_after=12
    )

    add_sub_title("1.4. Delimitación de la Investigación", level=1)
    add_p(
        "La investigación se delimitó espacialmente en las instalaciones físicas del restaurante “Donde David - Fresh & Tasty!” C.A., situado en la "
        "ciudad de Valencia, Estado Carabobo. Temporalmente, el estudio se circunscribe al año académico 2026. Temáticamente, el alcance abarca la "
        "digitalización del flujo integral de pedidos (mostrador, mesas, takeout y delivery), la cobranza multimoneda en caja, la coordinación en cocina "
        "y los módulos administrativos de auditoría, logs y copias de seguridad de la base de datos.",
        indent=True, space_after=12
    )

    # ==========================================
    # CAPÍTULO II: MARCO REFERENCIAL
    # ==========================================
    add_cap_title("II", "MARCO REFERENCIAL")

    add_sub_title("2.1. Antecedentes de la Investigación", level=1)
    add_p(
        "Conforme a las directrices institucionales del IUTEPI, se consultaron investigaciones previas vinculadas directamente con el desarrollo "
        "de sistemas de información gastronómicos, automatización de puntos de venta y seguridad de datos, con una antigüedad no superior a cinco años, "
        "presentadas cronológicamente en orden decreciente:",
        indent=True, space_after=8
    )

    antecedentes = [
        (
            "Barrionuevo Ochoa (2024)",
            "Sistema de Gestión de Pedidos y Control de Ventas para Establecimientos Gastronómicos",
            "Universidad Central de Ecuador",
            "El autor planteó como objetivo optimizar el flujo de comandas y facturación en locales de comida rápida a través de una arquitectura web desacoplada. "
            "La investigación concluyó que la unificación del punto de venta con la cocina reduce un 40% las demoras de despacho. Su aporte al presente estudio reside "
            "en el modelo de estados de pedido y la ergonomía de la interfaz de comanda táctil."
        ),
        (
            "González, Marín y Uzcátegui (2023)",
            "Sistema de Información Web para la Gestión de Ventas, Inventario y Caja en Empresas de Servicios de Alimentos",
            "Instituto Universitario de Tecnología para la Informática (IUTEPI), Valencia",
            "Esta investigación analizó los procedimientos manuales de facturación y arqueo de caja en comercios de la región carabobeña, proponiendo una base relacional "
            "para garantizar el balance de turnos. Aporta al proyecto la estructura de control de turnos en caja, el arqueo por medio de pago y el manejo de divisas en moneda nacional."
        ),
        (
            "Maytan Quispe (2023)",
            "Plataforma Web para la Automatización de Procesos de Comanda y Facturación en Restaurantes",
            "Universidad Católica Los Ángeles, Chimbote",
            "El trabajo determinó la viabilidad técnica y operativa de implementar aplicaciones web responsivas en dispositivos de salón y cocina. Su aporte específico radica "
            "en las estrategias de sincronización de pedidos en tiempo real y el desacoplamiento de servicios en el servidor."
        ),
        (
            "García Requena y Gómez Marcano (2022)",
            "Desarrollo de una Aplicación Web para el Control Administrativo de Pedidos y Clientes en el Sector Gastronómico",
            "Universidad de Oriente (UDO), Barcelona",
            "El proyecto se enfocó en erradicar la pérdida de información en la asignación de mesas mediante un modelo de datos estructurado. Su aporte principal al presente trabajo "
            "consiste en las directrices de seguridad lógica para restringir accesos administrativos y los mecanismos de consulta de inventario por recetas de insumos."
        ),
    ]

    for autor, titulo, inst, desc in antecedentes:
        p_ant = doc.add_paragraph()
        p_ant.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p_ant.paragraph_format.first_line_indent = Cm(1.25)
        p_ant.paragraph_format.space_after = Pt(6)
        r_a1 = p_ant.add_run(f"{autor}, en su trabajo titulado ")
        r_a2 = p_ant.add_run(f"“{titulo}”, ")
        r_a2.italic = True
        r_a3 = p_ant.add_run(f"presentado en la {inst}. {desc}")

    add_sub_title("2.2. Bases Teóricas", level=1)
    add_p(
        "A continuación se desarrollan las teorías y fundamentos computacionales que sustentan técnica y funcionalmente la solución desarrollada, "
        "respetando el esquema formal exigido por la institución:",
        indent=True, space_after=6
    )

    teorias = [
        (
            "Teoría del Ciclo de Vida de los Sistemas",
            "Kendall y Kendall (2019)",
            "Según Kendall y Kendall (2019), el ciclo de vida del desarrollo de sistemas comprende un conjunto de fases secuenciales y sistemáticas que "
            "guían al analista desde la identificación del problema y la determinación de requerimientos de información, hasta el diseño, programación, "
            "prueba e implantación del software. Esta teoría fundamenta la estructura metodológica de la propuesta, permitiendo que cada requerimiento "
            "del restaurante 'Donde David' se traduzca de forma rigurosa en módulos de software verificables."
        ),
        (
            "Ingeniería de Software y Arquitectura Orientada a Servicios",
            "Pressman y Maxim (2020)",
            "Pressman y Maxim (2020) definen la ingeniería de software como la aplicación de un enfoque sistemático, disciplinado y cuantificable al desarrollo, "
            "operación y mantenimiento de aplicaciones computacionales de alta calidad. En el contexto de este proyecto, este marco fundamenta la separación "
            "entre la capa de presentación web, la capa de enrutamiento REST con FastAPI y la capa de persistencia relacional con SQLAlchemy 2.0."
        ),
        (
            "Observabilidad y Logging Centralizado en Sistemas de Producción",
            "Beyer et al. (2018) / SRE Google",
            "La disciplina de Site Reliability Engineering (SRE) postula que la observabilidad es la capacidad de inferir el estado interno de un sistema "
            "computacional a partir del análisis continuo de sus salidas externas, destacando las métricas de latencia, tráfico, errores y saturación. "
            "Esta base teórica sustenta la creación del middleware de telemetría de peticiones en milisegundos y los archivos rotativos de logs del servidor."
        ),
        (
            "Pistas de Auditoría Forense y Trazabilidad Inmutable (Audit Trail)",
            "Stallings (2018)",
            "Stallings (2018) establece que una pista de auditoría constituye un registro cronológico e inmutable de eventos del sistema que documenta "
            "quién ejecutó una operación, en qué momento, sobre qué recurso y cuáles fueron las modificaciones efectuadas. Esta teoría fundamenta "
            "el diseño del modelo relacional de Auditoría y la captura de estructuras JSON con las diferencias de estados previos y nuevos."
        ),
        (
            "Continuidad de Negocio y Respaldo Criptográfico de Datos (Disaster Recovery)",
            "Tanenbaum y Wetherall (2021)",
            "Tanenbaum y Wetherall (2021) enfatizan que la salvaguarda de la información crítica exige mecanismos de respaldo en caliente (hot backup) "
            "junto con funciones de dispersión criptográfica unidireccional (como SHA-256) para garantizar que los datos restaurados sean idénticos a los "
            "originales y no hayan sufrido alteraciones ni corrupción física durante el almacenamiento."
        ),
    ]

    for t_tit, t_aut, t_desc in teorias:
        add_p(t_tit, bold=True, indent=False, space_after=2)
        add_p(f"Según {t_aut}: {t_desc}", indent=True, space_after=6)

    add_sub_title("2.3. Bases Legales", level=1)
    add_p(
        "El marco jurídico venezolano que rige el desarrollo, despliegue y uso de sistemas informáticos en actividades comerciales comprende:",
        indent=True, space_after=6
    )
    add_p(
        "1. <b>Constitución de la República Bolivariana de Venezuela (1999):</b> En su Artículo 110, reconoce el interés público de la ciencia, la tecnología, "
        "el conocimiento y los servicios de información como instrumentos fundamentales para el desarrollo económico y social de la nación.",
        indent=True, space_after=4
    )
    add_p(
        "2. <b>Ley de Mensajes de Datos y Firmas Electrónicas (2001):</b> Otorga plena eficacia y validez probatoria a las transacciones mercantiles, comprobantes "
        "y registros electrónicos emitidos por aplicaciones web, respaldando las operaciones de cobro y comandas digitales.",
        indent=True, space_after=4
    )
    add_p(
        "3. <b>Ley Especial contra los Delitos Informáticos (2001):</b> Tipifica y sanciona el acceso indebido, la alteración o sabotaje a sistemas de datos, "
        "justificando la implantación de contraseñas bajo hashing seguro bcrypt, autenticación JWT y pistas de auditoría forense.",
        indent=True, space_after=4
    )
    add_p(
        "4. <b>Normativa del SENIAT y Providencias de Facturación Comercial:</b> Regula los requisitos para la emisión de notas de consumo, comprobantes de pago "
        "y cierres de caja en puntos de venta, obligando al sistema a diferenciar medios de pago y reflejar claramente la alícuota tributaria y la tasa cambiaria.",
        indent=True, space_after=10
    )

    add_sub_title("2.4. Operacionalización de Variables", level=1)
    add_p(
        "A continuación se presenta la matriz de operacionalización, estableciendo la correspondencia entre objetivos, variables e indicadores:",
        indent=True, space_after=6
    )

    headers_op = ["Variable", "Dimensión", "Indicadores", "Instrumento"]
    rows_op = [
        ["Sistema Web Integral Administrativo", "Funcionalidad Técnica", "Registro, consulta y modificación de datos vía REST API.", "Lista de Cotejo"],
        ["Sistema Web Integral Administrativo", "Seguridad y Control", "Autenticación JWT, roles RBAC y control de acceso.", "Guía de Observación"],
        ["Sistema Web Integral Administrativo", "Observabilidad y DR", "Logs en rotación, telemetría ms, auditoría y backups SHA-256.", "Matriz de Pruebas"],
        ["Gestión de Pedidos POS Touch", "Operatividad Comercial", "Creación de comanda táctil, cálculo de total y despacho.", "Cuestionario Técnico"],
        ["Gestión de Pedidos POS Touch", "Control de Caja", "Apertura de turno, cobranza multimoneda y arqueo de caja.", "Ficha Documental"],
        ["Gestión de Pedidos POS Touch", "Usabilidad Ergonómica", "Interacción táctil, diseño responsive y tiempo de respuesta.", "Encuesta al Personal"],
    ]
    add_table_custom(headers_op, rows_op, [Inches(1.8), Inches(1.5), Inches(2.3), Inches(1.4)])

    add_sub_title("2.5. Definición de Términos Básicos", level=1)
    terminos = [
        ("Alembic", "Herramienta de control de versiones y migraciones de esquemas para bases de datos relacionales en Python."),
        ("Audit Trail (Pista de Auditoría)", "Registro cronológico, inmutable e indexado que documenta las acciones críticas realizadas por usuarios."),
        ("Backups en Caliente (Hot Backup)", "Mecanismo de copia de seguridad que captura páginas de datos sin detener la ejecución de lecturas o escrituras."),
        ("Bcrypt", "Función criptográfica de derivación de claves basada en el cifrado Blowfish, empleada para proteger contraseñas con sal aleatoria."),
        ("FastAPI", "Framework asíncrono de alto rendimiento para el desarrollo de APIs RESTful en Python basado en estándares OpenAPI y Starlette."),
        ("JSON Web Token (JWT)", "Estándar abierto (RFC 7519) que define un mecanismo compacto y autónomo para transmitir datos seguros entre partes."),
        ("POS Touch (Point of Sale)", "Punto de venta físico o digital con interfaz ergonómica orientada al ingreso de transacciones mediante pantallas táctiles."),
        ("Pydantic", "Librería de Python para análisis y validación estricta de datos basada en anotaciones de tipos estándar."),
        ("Rotating File Handler", "Manejador de archivos de registro que divide la información al alcanzar un tamaño límite para evitar saturación de disco."),
        ("SHA-256", "Algoritmo de dispersión criptográfica que produce una huella única de 256 bits, utilizada para comprobar la integridad del software y backups."),
        ("SQLAlchemy 2.0", "Mapeador objeto-relacional (ORM) integral para Python que permite modelar entidades de negocio desacopladas del motor de base de datos."),
        ("WebSockets", "Protocolo de red que proporciona canales de comunicación bidireccional continua sobre una única conexión TCP."),
    ]
    for term, defn in terminos:
        add_p(f"• <b>{term}:</b> {defn}", indent=True, space_after=3)

    # ==========================================
    # CAPÍTULO III: MARCO METODOLÓGICO
    # ==========================================
    add_cap_title("III", "MARCO METODOLÓGICO")

    add_sub_title("3.1. Diseño de la Investigación", level=1)
    add_p(
        "El presente trabajo se fundamentó en un <b>diseño de campo de carácter descriptivo</b>. De campo, por cuanto la información requerida "
        "para el diagnóstico, modelado y validación de los requerimientos se obtuvo de manera directa y presencial en las instalaciones del restaurante "
        "“Donde David - Fresh & Tasty!” C.A., conviviendo con los operadores de salón, caja y cocina. Descriptivo, debido a que se identificaron, "
        "analizaron y especificaron las características estructurales, fallas y variables operativas que componen el flujo de comandas y ventas.",
        indent=True, space_after=6
    )

    add_sub_title("3.2. Modalidad y Tipo de Investigación", level=1)
    add_p(
        "La modalidad adoptada corresponde a un <b>Proyecto Factible</b>, definido por las normas institucionales del IUTEPI como la elaboración de una "
        "propuesta operativa viable destinada a satisfacer necesidades específicas en una organización empresarial. La factibilidad de la propuesta "
        "se sustenta en la construcción real de un sistema de información completamente funcional, evaluado mediante pruebas de laboratorio y "
        "dimensionado conforme a la infraestructura técnica y capacidad económica del establecimiento comercial.",
        indent=True, space_after=6
    )

    add_sub_title("3.3. Unidad de Análisis: Sujetos u Objetos de Estudio", level=1)
    add_p(
        "La unidad de análisis estuvo conformada por los procedimientos administrativos y comerciales de gestión de pedidos, compras, inventario y "
        "caja del restaurante. Los sujetos de estudio correspondieron a la totalidad de los colaboradores vinculados a estas tareas: un (01) Gerente General, "
        "dos (02) Administradores de Turno, tres (03) Cajeros, cuatro (04) Cocineros y cinco (05) Meseros, constituyendo una población censal de 15 trabajadores, "
        "lo que hizo innecesario el muestreo probabilístico al abarcar la totalidad de los involucrados.",
        indent=True, space_after=6
    )

    add_sub_title("3.4. Técnicas e Instrumentos de Recolección de Datos", level=1)
    add_p(
        "Se utilizaron cuatro técnicas sistemáticas de recolección de información:",
        indent=True, space_after=4
    )
    add_p("1. <b>Observación Directa:</b> Aplicada mediante Hojas de Registro y Listas de Cotejo para evidenciar la toma manual de comandas y el arqueo en caja.", indent=True, space_after=3)
    add_p("2. <b>Entrevista Semiestructurada:</b> Dirigida al Gerente y Administrador con una Guía de Entrevista para recabar requerimientos de control y reportes.", indent=True, space_after=3)
    add_p("3. <b>Encuesta de Diagnóstico y Usabilidad:</b> Administrada a cajeros y meseros mediante un Cuestionario tipo escala para valorar la necesidad del POS Touch.", indent=True, space_after=3)
    add_p("4. <b>Revisión Documental:</b> Mediante Fichas de Trabajo sobre los talonarios físicos, notas de entrega y balances de cierre de turnos anteriores.", indent=True, space_after=6)

    add_sub_title("3.5. Técnicas de Análisis de Datos", level=1)
    add_p(
        "De acuerdo con lo establecido por Morlés (1997), se utilizó la técnica de <b>análisis descriptivo</b>, orientada a cuantificar y resumir "
        "las características de los datos recabados mediante distribuciones de frecuencias absolutas y porcentuales, sustentando la justificación "
        "del software y guiando la especificación técnica de los módulos del sistema.",
        indent=True, space_after=6
    )

    add_sub_title("3.6. Fases del Proyecto según la Metodología Kendall & Kendall", level=1)
    add_p(
        "La ejecución del proyecto se adaptó estrictamente a las seis fases del Ciclo de Vida de los Sistemas de Kendall & Kendall (2019):",
        indent=True, space_after=4
    )
    add_p("• <b>Fase I: Identificación de Problemas, Oportunidades y Objetivos:</b> Diagnóstico situacional y estudio de factibilidad técnica, económica y operativa.", indent=True, space_after=3)
    add_p("• <b>Fase II: Determinación de los Requerimientos de Información:</b> Análisis de las entradas, procesamientos, almacenamiento y salidas requeridas.", indent=True, space_after=3)
    add_p("• <b>Fase III: Análisis de las Necesidades del Sistema:</b> Modelado de flujos actuales y propuestos, casos de uso y balance costo-beneficio.", indent=True, space_after=3)
    add_p("• <b>Fase IV: Diseño del Sistema Recomendado:</b> Arquitectura lógica, diseño modular, normalización 3FN, seguridad física y lógica.", indent=True, space_after=3)
    add_p("• <b>Fase V: Desarrollo y Documentación del Software:</b> Codificación modular en FastAPI, plantillas Toon UI y documentación de endpoints.", indent=True, space_after=3)
    add_p("• <b>Fase VI: Pruebas y Mantenimiento del Sistema:</b> Ejecución del plan de pruebas automatizadas unitarias, de estilos, de seguridad y rendimiento.", indent=True, space_after=10)

    # ==========================================
    # CAPÍTULO IV: DISEÑO DE LA PROPUESTA (Kendall & Kendall)
    # ==========================================
    add_cap_title("IV", "DISEÑO DE LA PROPUESTA")

    add_sub_title("4.1. Objetivos Específicos de la Propuesta", level=1)
    add_p("• Proporcionar un Punto de Venta Táctil (POS Touch) de alta velocidad para el ingreso intuitivo de comandas en salón, barra y delivery.", indent=True, space_after=3)
    add_p("• Sincronizar en tiempo real el área de cocina mediante una pantalla interactiva KDS con actualización instantánea de estados.", indent=True, space_after=3)
    add_p("• Automatizar el arqueo de caja con soporte multimoneda y conversión cambiaria oficial del BCV en tiempo real.", indent=True, space_after=3)
    add_p("• Implantar un módulo de observabilidad con rotación física de logs del servidor y telemetría de latencias en milisegundos.", indent=True, space_after=3)
    add_p("• Establecer una pista de auditoría forense inmutable con captura de diferencias JSON previas y posteriores para eventos críticos.", indent=True, space_after=3)
    add_p("• Implementar un motor de copias de seguridad en caliente con firmas criptográficas SHA-256 y protocolos de recuperación segura.", indent=True, space_after=8)

    # FASE I
    add_sub_title("4.2. Fase I: Identificación de Problemas, Oportunidades y Objetivos", level=1)
    add_p(
        "<b>Descripción de Procesos Actuales:</b> En el restaurante, el cliente es atendido por el mesero quien transcribe manualmente la orden en una comanda. "
        "Posteriormente, el papel se traslada físicamente a la cocina, donde los cocineros acumulan hojas en una barra, provocando extravíos o preparaciones "
        "desordenadas. Al momento del cobro, el cajero debe ingresar manualmente cada ítem en una calculadora, consultar la tasa cambiaria del día en una pizarra "
        "y emitir una nota física. El balance de caja nocturno requiere hasta dos horas de cuadre manual con frecuente disparidad entre el efectivo y los comprobantes.",
        indent=True, space_after=6
    )
    add_p(
        "<b>Estudio de Factibilidad:</b>",
        bold=True, indent=True, space_after=3
    )
    add_p(
        "• <i>Factibilidad Técnica:</i> El restaurante cuenta con dos equipos de cómputo en mostrador, tabletas estándar para salón y conexión local WiFi. "
        "El backend FastAPI y la base relacional operan óptimamente con un consumo de memoria inferior a 150 MB en servidores locales o en la nube (Render).",
        indent=True, space_after=3
    )
    add_p(
        "• <i>Factibilidad Operativa:</i> La curva de aprendizaje del sistema es reducida debido al diseño de botones táctiles amplios Toon UI. El personal expresó "
        "un 93% de aceptación para la adopción de la herramienta informática.",
        indent=True, space_after=3
    )
    add_p(
        "• <i>Factibilidad Económica:</i> Dado que el desarrollo se realizó con herramientas de código abierto (Python, FastAPI, SQLite, PostgreSQL, HTML5/CSS3), "
        "no existen costos de licencias de software propietario. La inversión se limitó a periféricos estándar (impresora térmica USB y soporte para tableta).",
        indent=True, space_after=8
    )

    # FASE II
    add_sub_title("4.3. Fase II: Determinación de Requerimientos de Información", level=1)
    add_p(
        "Siguiendo los lineamientos de Kendall & Kendall, se clasificaron rigurosamente los requerimientos de información en tres vertientes:",
        indent=True, space_after=4
    )
    add_p("• <b>Requerimientos de Entrada:</b> Credenciales de acceso; datos de categorías y productos con precio USD/VES y foto; asignación de mesa; selección de modificadores y extras; referencia bancaria de Pago Móvil o tarjeta; motivo y parámetros para creación de copias de seguridad; filtros de consulta de logs y auditoría.", indent=True, space_after=3)
    add_p("• <b>Requerimientos de Almacenamiento:</b> Entidades relacionales normalizadas para usuarios, roles, pedidos, detalles de pedido, mesas, turnos de caja, inventario; tabla indexada de <code>Auditoria</code> con campos JSON para estados previos y nuevos; archivos físicos rotativos de logs (<code>donde_david.log</code> y <code>donde_david_errors.log</code>); directorio de respaldos con archivos <code>.db</code> / <code>.dump</code> y manifiestos de metadatos criptográficos <code>.meta.json</code>.", indent=True, space_after=3)
    add_p("• <b>Requerimientos de Salida:</b> Pantalla de comanda táctil POS; monitor de cocina KDS con tarjetas de orden clasificadas por antigüedad; ticket digital y recibo de cobro; reporte de cierre de caja por turno; consola interactiva de logs de servidor con métricas de tasa de error (<code>error_rate_pct</code>); visor modal de diferencias JSON de auditoría; archivo descargable en formato CSV con historial de auditoría y descarga de backups protegidos por hash SHA-256.", indent=True, space_after=8)

    # FASE III
    add_sub_title("4.4. Fase III: Análisis de las Necesidades del Sistema", level=1)
    add_p(
        "<b>Descripción del Software Propuesto:</b> El software 'Dónde David' opera como una plataforma cliente-servidor basada en web. "
        "El servidor expone una API REST modularizada con documentación interactiva Swagger/OpenAPI en la ruta <code>/docs</code>, securizada "
        "mediante tokens JWT y complementada con un router de WebSockets que transmite eventos instantáneos sin recarga de página (polling).",
        indent=True, space_after=6
    )
    add_p(
        "<b>Descripción Específica del Sistema Propuesto:</b> El sistema articula nueve módulos especializados: Autenticación, Administración, "
        "Punto de Venta Táctil (POS), Monitor de Cocina (KDS), Módulo de Meseros, Control de Caja, Observabilidad de Logs, Pistas de Auditoría y "
        "Gestor de Respaldos (DR). Toda la lógica crítica se encuentra aislada en la capa de servicios (<code>app/services/</code>), garantizando "
        "que los controladores HTTP permanezcan limpios y desacoplados de la base de datos.",
        indent=True, space_after=6
    )
    add_p(
        "<b>Análisis Costo - Beneficio:</b> La inversión en periféricos y puesta en marcha se estimó en 240 USD. Por su parte, la reducción de errores "
        "en comandas (estimada en 60 USD mensuales) y el ahorro en horas de cuadre de caja (estimado en 80 USD mensuales) generan una tasa de retorno "
        "de la inversión en menos de dos meses de operatividad continua.",
        indent=True, space_after=8
    )

    # FASE IV
    add_sub_title("4.5. Fase IV: Diseño del Sistema Recomendado", level=1)
    add_p(
        "<b>Carta Estructurada y Diseño Modular:</b> La arquitectura del backend se organizó en paquetes modulares con responsabilidades estrictas:",
        indent=True, space_after=4
    )
    
    headers_mod = ["Módulo / Archivo", "Capa Arquitectónica", "Función Principal"]
    rows_mod = [
        ["admin_auditoria.py", "API Controller (REST)", "Endpoints de consulta paginada, filtros por acción/recurso y exportación CSV."],
        ["admin_logs.py", "API Controller (REST)", "Endpoints para lectura en tiempo real de logs, KPIs y vaciado controlado."],
        ["admin_backups.py", "API Controller (REST)", "Gestión de ciclo de vida de copias: crear, listar, restaurar y eliminar."],
        ["logging_middleware.py", "Core Middleware", "Intercepta peticiones HTTP, captura latencia en ms, IP y registra trazas."],
        ["logging_config.py", "Core Configuration", "Configura RotatingFileHandlers para canales operativo y crítico (5MBx5)."],
        ["audit_service.py", "Domain Service", "Lógica de persistencia inmutable fail-safe y exportador estructurado CSV."],
        ["log_service.py", "Domain Service", "Algoritmo de tail inverso sobre disco y cálculo analítico de error_rate_pct."],
        ["backup_service.py", "Domain Service", "Motor dual (SQLite Hot Backup / PostgreSQL), cálculo de hash SHA-256 y retención 15."],
        ["auditoria.py", "Relational Model", "Entidad ORM con índices en fecha, usuario, acción y almacenamiento JSON de diffs."],
    ]
    add_table_custom(headers_mod, rows_mod, [Inches(2.0), Inches(1.8), Inches(3.2)])

    add_p(
        "<b>Normalización en Tercera Forma Normal (3FN):</b> El modelo relacional fue sometido al proceso riguroso de normalización. "
        "Todas las tablas cumplen la 1FN (atributos atómicos y clave primaria), 2FN (dependencia funcional completa de la clave) y 3FN "
        "(eliminación de dependencias transitivas). La tabla <code>auditoria</code> fue desacoplada de cualquier entidad operativa, relacionándose "
        "con <code>usuarios</code> mediante clave foránea con borrado restringido (RESTRICT).",
        indent=True, space_after=6
    )

    add_p(
        "<b>Diccionario de Datos: Estructura de la Tabla <code>auditoria</code>:</b>",
        bold=True, indent=True, space_after=3
    )
    headers_dict = ["Columna", "Tipo de Dato", "Restricciones", "Descripción"]
    rows_dict = [
        ["id", "INTEGER", "PK, Autoincremental", "Identificador único secuencial del evento de auditoría."],
        ["accion", "VARCHAR(50)", "NOT NULL, Indexado", "Tipo de operación ejecutada (ej. LOGIN_SUCCESS, USER_CREATE)."],
        ["recurso", "VARCHAR(50)", "NOT NULL, Indexado", "Entidad afectada (USUARIO, PEDIDO, BACKUP, CONFIGURACION)."],
        ["recurso_id", "VARCHAR(50)", "NULLABLE", "Identificador del registro específico intervenido."],
        ["usuario", "VARCHAR(50)", "NOT NULL, Indexado", "Nombre de usuario que realizó o solicitó la acción."],
        ["usuario_id", "INTEGER", "FK (usuarios.id), NULL", "Vínculo referencial a la cuenta de usuario activa."],
        ["ip_address", "VARCHAR(45)", "NULLABLE", "Dirección IP (IPv4/IPv6) de origen de la solicitud HTTP."],
        ["detalle", "TEXT", "NULLABLE", "Descripción legible y contextual del evento acontecido."],
        ["datos_previos", "TEXT (JSON)", "NULLABLE", "Snapshot JSON del estado de la entidad antes de modificarse."],
        ["datos_nuevos", "TEXT (JSON)", "NULLABLE", "Snapshot JSON del estado de la entidad tras la operación."],
        ["fecha", "DATETIME", "NOT NULL, Default UTC", "Marca de tiempo precisa indexada de la transacción."],
    ]
    add_table_custom(headers_dict, rows_dict, [Inches(1.2), Inches(1.3), Inches(1.6), Inches(2.9)])

    add_p(
        "<b>Seguridad del Sistema:</b>",
        bold=True, indent=True, space_after=3
    )
    add_p("• <i>Seguridad Lógica:</i> Autenticación basada en JWT con expiración estricta; cifrado bcrypt de contraseñas; autorización RBAC en backend en todas las rutas sensibles; validación de integridad criptográfica con hashes SHA-256 en cada backup; protocolo de seguridad con Safety Checkpoints antes de aplicar restauraciones; y rotación física controlada de archivos de log con separación de eventos críticos.", indent=True, space_after=3)
    add_p("• <i>Seguridad Física:</i> Restricción de acceso al servidor central mediante credenciales del sistema operativo; aislamiento de terminales POS en red local protegida por cortafuegos; y almacenamiento de respaldos en soportes externos redundantes protegidos contra cortes de energía.", indent=True, space_after=8)

    # FASE V
    add_sub_title("4.6. Fase V: Desarrollo y Documentación del Software", level=1)
    add_p(
        "<b>Descripción del Entorno de Programación:</b> El backend se implementó bajo Python 3.11 sobre entorno virtual pip, empleando FastAPI 0.115, "
        "Uvicorn como servidor ASGI, SQLAlchemy 2.0 y Alembic para el versionado de base de datos. En el frontend se prescindió deliberadamente de "
        "frameworks sobrecargados, utilizándose Vanilla JavaScript (ES6+), HTML5 semántico y CSS3 Toon UI estructurado en utilidades atómicas "
        "(<code>utilities.css</code>) y estilos de página (<code>admin-index.css</code>), logrando una velocidad de carga instantánea.",
        indent=True, space_after=6
    )
    add_p(
        "<b>Diseño de Pantallas e Interfaces:</b> Se diseñaron interfaces interactivas para cada rol operativo:",
        indent=True, space_after=4
    )
    add_p("1. <b>Pantalla POS Touch (Caja y Meseros):</b> Disposición de catálogo por categorías superiores, cuadrícula de platos con botones táctiles grandes, panel lateral de comanda con totales en tiempo real en USD y Bs, y modal de cierre de venta.", indent=True, space_after=3)
    add_p("2. <b>Pantalla de Monitor de Cocina (KDS):</b> Tarjetas ordenadas cronológicamente con temporizador visual que cambia de color según el tiempo de espera del pedido y botones táctiles para avanzar a 'En Preparación' y 'Listo'.", indent=True, space_after=3)
    add_p("3. <b>Panel de Auditoría del Sistema (Admin):</b> Interfaz con selector de filtros por acción y recurso, buscador reactivo, tabla de eventos con badges de colores y botón de inspección modal para contrastar las diferencias JSON (datos_previos vs datos_nuevos).", indent=True, space_after=3)
    add_p("4. <b>Consola de Logs de Servidor (Admin):</b> Ventana simulada de terminal con coloreado de sintaxis según nivel de severidad, tarjetas de métricas en tiempo real (eventos, errores, tasa de error % y latencia ms), interruptor de auto-refresco a 5 segundos y botones de descarga directa y depuración.", indent=True, space_after=3)
    add_p("5. <b>Gestor de Copias de Seguridad (Admin):</b> Indicador de motor de base de datos activo, tabla descriptiva con fecha, tamaño formateado, hash SHA-256 truncado con tooltip, y botones protegidos para Crear Respaldo, Descargar, Restaurar y Eliminar.", indent=True, space_after=8)

    # FASE VI
    add_sub_title("4.7. Fase VI: Pruebas y Mantenimiento del Sistema", level=1)
    add_p(
        "<b>Plan de Pruebas y Verificación Automatizada:</b> La estabilidad del sistema se evaluó a través de tres suites de pruebas unitarias "
        "y de integración ejecutadas con <code>pytest</code>, sumadas a una prueba de validación E2E completa del ciclo de pedidos:",
        indent=True, space_after=4
    )

    headers_test = ["Suite de Pruebas", "Alcance Evaluado", "Casos", "Resultado", "Tiempo"]
    rows_test = [
        ["test_audit_logs_backups.py", "APIs de Logs, Auditoría, Backups, Hashes SHA-256, Rotación y Safety Checkpoint.", "9", "Aprobado (100%)", "7.33 s"],
        ["test_frontend_styles.py", "Cumplimiento estricto de cero inline styles y validez de clases CSS en todos los HTML.", "2", "Aprobado (100%)", "0.47 s"],
        ["tests/ (Suite Oficial)", "Lógica de negocio: pedidos, catálogo, inventario, mesas, turnos y promociones.", "51", "Aprobado (100%)", "26.89 s"],
        ["test_api.py (E2E Script)", "Flujo completo de comanda: login, creación de pedido, cobro y visualización KDS.", "9", "Aprobado (100%)", "0.91 s"],
    ]
    add_table_custom(headers_test, rows_test, [Inches(1.8), Inches(2.7), Inches(0.7), Inches(1.1), Inches(0.7)])

    add_p(
        "<b>Total de Pruebas Automatizadas Exitosas: 62 Casos Aprobados (0 fallas, 0 errores, 0 regresiones).</b>",
        bold=True, indent=True, space_after=6
    )
    add_p(
        "<b>Plan de Mantenimiento Preventivo y Correctivo:</b> El protocolo de mantenimiento establece la revisión quincenal de los logs "
        "de error (<code>donde_david_errors.log</code>) mediante la consola administrativa, la verificación de integridad mensual de los archivos "
        "de respaldo cotejando sus firmas SHA-256 y la aplicación periódica de actualizaciones de dependencias de seguridad de Python vía pip.",
        indent=True, space_after=12
    )

    # ==========================================
    # CAPÍTULO V: CONCLUSIONES Y RECOMENDACIONES
    # ==========================================
    add_cap_title("V", "CONCLUSIONES Y RECOMENDACIONES")

    add_sub_title("5.1. Conclusiones", level=1)
    add_p(
        "Una vez culminadas las fases de diagnóstico, diseño, desarrollo, robustecimiento de seguridad y pruebas del Sistema Web Integral "
        "para el restaurante “Donde David - Fresh & Tasty!” C.A., se formulan las siguientes conclusiones basadas en el cumplimiento de los objetivos:",
        indent=True, space_after=6
    )
    add_p(
        "1. Se diagnosticaron exitosamente las deficiencias de los procesos tradicionales de comanda y cobro manual, evidenciando retrasos de "
        "hasta 25 minutos en horas pico y discrepancias constantes en el cuadre de caja nocturno.",
        indent=True, space_after=4
    )
    add_p(
        "2. Se identificaron y documentaron los requerimientos de información, transformándolos en especificaciones formales bajo la metodología "
        "de Kendall & Kendall, asegurando una arquitectura balanceada entre funcionalidad y rendimiento.",
        indent=True, space_after=4
    )
    add_p(
        "3. Se diseñó e implementó un modelo de datos en Tercera Forma Normal (3FN), desacoplado y compatible de forma transparente con SQLite en "
        "entornos locales de prueba y PostgreSQL en entornos productivos escalables.",
        indent=True, space_after=4
    )
    add_p(
        "4. Se desarrolló el módulo POS Touch con una interfaz visual intuitiva basada en el sistema Toon UI, eliminando por completo los estilos "
        "en línea conforme a las normas de buenas prácticas web y facilitando la operación táctil fluida.",
        indent=True, space_after=4
    )
    add_p(
        "5. Se integraron con éxito los tres módulos críticos de gobernanza de producción: el sistema de observabilidad y logging continuo con "
        "telemetría de latencias HTTP; la pista de auditoría forense inmutable con captura de diferencias JSON; y el motor de respaldos en caliente "
        "con comprobación de integridad criptográfica SHA-256 y salvaguardas de seguridad.",
        indent=True, space_after=4
    )
    add_p(
        "6. La ejecución íntegra del plan de pruebas certificó la aprobación del 100% de los 62 casos de prueba automatizados, confirmando que "
        "la plataforma está completamente madura y lista para su pase a producción sin riesgos de estabilidad o vulnerabilidad.",
        indent=True, space_after=10
    )

    add_sub_title("5.2. Recomendaciones", level=1)
    add_p(
        "Con el propósito de garantizar la máxima longevidad y eficiencia del sistema en el entorno comercial, se recomienda:",
        indent=True, space_after=6
    )
    add_p("1. <b>Capacitación del Personal:</b> Desarrollar jornadas breves de adiestramiento con cajeros y meseros para familiarizarlos plenamente con las funciones táctiles y el manejo de modificadores del menú en el POS.", indent=True, space_after=4)
    add_p("2. <b>Monitoreo Activo de la Consola de Logs:</b> Supervisar periódicamente la tasa de error (<code>error_rate_pct</code>) y la latencia media desde el panel administrativo para detectar anomalías de conectividad de forma temprana.", indent=True, space_after=4)
    add_p("3. <b>Custodia Externa de Respaldos:</b> Establecer la descarga quincenal de los archivos de respaldo y sus manifiestos <code>.meta.json</code> hacia una unidad de almacenamiento físico externa fuera del local comercial.", indent=True, space_after=4)
    add_p("4. <b>Rotación Periódica de Credenciales:</b> Modificar cada 90 días las claves maestras de administrador y la variable <code>SECRET_KEY</code> del archivo de configuración <code>.env</code>.", indent=True, space_after=4)
    add_p("5. <b>Automatización del Respaldo Nocturno:</b> Configurar una tarea programada (Cron Job en Linux o Programador de Tareas en Windows) que invoque automáticamente el endpoint de creación de backups a las 03:00 AM.", indent=True, space_after=10)

    # ==========================================
    # REFERENCIAS BIBLIOGRÁFICAS
    # ==========================================
    doc.add_page_break()
    p_ref_t = doc.add_paragraph()
    p_ref_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ref_t.paragraph_format.space_before = Pt(28)
    p_ref_t.paragraph_format.space_after = Pt(18)
    p_ref_t.paragraph_format.first_line_indent = Cm(0)
    p_ref_t.add_run("REFERENCIAS BIBLIOGRÁFICAS").bold = True

    referencias = [
        "Barrionuevo Ochoa, D. (2024). Sistema de Gestión de Pedidos y Control de Ventas para Establecimientos Gastronómicos. Trabajo Especial de Grado, Universidad Central de Ecuador.",
        "Beyer, B., Jones, C., Petoff, J., y Murphy, N. (2018). Site Reliability Engineering: How Google Runs Production Systems. O'Reilly Media.",
        "Constitución de la República Bolivariana de Venezuela. (1999). Gaceta Oficial de la República Bolivariana de Venezuela Nº 36.860. Caracas, Venezuela.",
        "García Requena, J., y Gómez Marcano, L. (2022). Desarrollo de una Aplicación Web para el Control Administrativo de Pedidos y Clientes en el Sector Gastronómico. Trabajo Especial de Grado, Universidad de Oriente, Barcelona.",
        "González, M., Marín, R., y Uzcátegui, P. (2023). Sistema de Información Web para la Gestión de Ventas, Inventario y Caja en Empresas de Servicios de Alimentos. Trabajo Especial de Grado, Instituto Universitario de Tecnología para la Informática (IUTEPI), Valencia.",
        "Instituto Universitario de Tecnología para la Informática (IUTEPI). (2023). Normas para la Elaboración y Presentación del Trabajo Especial de Grado en Análisis de Sistemas. Coordinación de Trabajo Especial de Grado, Valencia, Venezuela.",
        "ISO/IEC 25010. (2023). Systems and Software Engineering — Systems and Software Quality Requirements and Evaluation (SQuaRE) — Product Quality Model. International Organization for Standardization.",
        "Kendall, K. E., y Kendall, J. E. (2019). Análisis y Diseño de Sistemas (8va ed.). Pearson Educación.",
        "Laudon, K. C., y Laudon, J. P. (2022). Sistemas de Información Gerencial: Administración de la Empresa Digital (16va ed.). Pearson Educación.",
        "Ley de Mensajes de Datos y Firmas Electrónicas. (2001). Gaceta Oficial de la República Bolivariana de Venezuela Nº 37.148. Caracas, Venezuela.",
        "Ley Especial contra los Delitos Informáticos. (2001). Gaceta Oficial de la República Bolivariana de Venezuela Nº 37.313. Caracas, Venezuela.",
        "Maytan Quispe, R. (2023). Plataforma Web para la Automatización de Procesos de Comanda y Facturación en Restaurantes. Trabajo Especial de Grado, Universidad Católica Los Ángeles, Chimbote.",
        "Morlés, V. (1997). Planeamiento y Análisis de Investigaciones (3ra ed.). Ediciones El Dorado, Caracas.",
        "Pressman, R. S., y Maxim, B. R. (2020). Ingeniería del Software: Un Enfoque Práctico (9na ed.). McGraw-Hill Interamericana.",
        "Stallings, W. (2018). Seguridad en las Comunicaciones y en las Redes de Computadoras (5ta ed.). Pearson Educación.",
        "Tanenbaum, A. S., y Wetherall, D. J. (2021). Redes de Computadoras (6ta ed.). Pearson Educación.",
    ]
    for ref in referencias:
        p_ref = doc.add_paragraph()
        p_ref.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_ref.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        p_ref.paragraph_format.first_line_indent = Cm(-1.25)
        p_ref.paragraph_format.left_indent = Cm(1.25)
        p_ref.paragraph_format.space_after = Pt(6)
        p_ref.add_run(ref)

    # ==========================================
    # ANEXOS
    # ==========================================
    doc.add_page_break()
    p_anx_t = doc.add_paragraph()
    p_anx_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_anx_t.paragraph_format.space_before = Pt(28)
    p_anx_t.paragraph_format.space_after = Pt(18)
    p_anx_t.paragraph_format.first_line_indent = Cm(0)
    p_anx_t.add_run("ANEXOS").bold = True

    add_sub_title("ANEXO A: Instrumento de Recolección de Datos - Cuestionario de Usabilidad y Diagnóstico", level=1)
    cuestionario_items = [
        "1. ¿Considera que el método manual actual de toma de pedidos genera demoras o equivocaciones en cocina?",
        "2. ¿Considera indispensable contar con un Punto de Venta Táctil (POS Touch) con botones grandes y catálogo fotográfico?",
        "3. ¿Estima conveniente que la tasa de cambio oficial (Bs/USD) se actualice de forma automatizada al momento de cobrar?",
        "4. ¿Considera relevante que el sistema registre auditorías detalladas de quién modifica precios, anula pedidos o crea usuarios?",
        "5. ¿Cree necesario que el servidor cuente con una consola de logs en vivo para diagnosticar incidencias técnicas?",
        "6. ¿Considera prioritario disponer de copias de seguridad automáticas con verificación criptográfica para prevenir pérdida de datos?",
    ]
    for ci in cuestionario_items:
        add_p(ci, indent=True, space_after=3)

    add_sub_title("ANEXO B: Matriz Oficial de Resultados de Pruebas Automatizadas del Sistema", level=1)
    headers_anx_b = ["Módulo / Archivo de Prueba", "Casos Evaluados", "Criterio de Aprobación", "Estado Final"]
    rows_anx_b = [
        ["tests/test_audit_logs_backups.py", "9 pruebas unitarias", "APIs de logs, auditoría forense, creación y restauración de backups con SHA-256.", "APROBADO (100%)"],
        ["tests/test_frontend_styles.py", "2 pruebas visuales", "0 atributos style inline y 0 etiquetas <style> en todas las vistas HTML.", "APROBADO (100%)"],
        ["tests/ (Suite de Dominio)", "51 pruebas de backend", "Flujos de pedidos, mesas, fidelidad, promociones, turnos y catálogo.", "APROBADO (100%)"],
        ["backend/scripts/test_api.py", "9 pasos de integración", "Flujo E2E desde login hasta visualización en monitor de cocina KDS.", "APROBADO (100%)"],
        ["TOTAL ACUMULADO", "62 Casos de Prueba", "Conformidad total de especificaciones para pase a producción.", "100% EXITOSO"],
    ]
    add_table_custom(headers_anx_b, rows_anx_b, [Inches(2.2), Inches(1.5), Inches(2.3), Inches(1.0)])

    add_sub_title("ANEXO C: Guía de Despliegue y Puesta en Marcha en Producción", level=1)
    add_p(
        "Para desplegar el sistema en servidores Linux de producción (Ubuntu/Debian con Nginx y PostgreSQL), se deben seguir los siguientes pasos:",
        indent=True, space_after=4
    )
    add_p("1. Configurar variables de entorno seguras en el archivo <code>.env</code> (SECRET_KEY, DATABASE_URL de PostgreSQL, ALLOWED_ORIGINS).", indent=True, space_after=3)
    add_p("2. Ejecutar las migraciones de base de datos con el comando <code>alembic upgrade head</code> para sincronizar el esquema relacional.", indent=True, space_after=3)
    add_p("3. Iniciar el servidor ASGI con Gunicorn: <code>gunicorn backend.app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000</code>.", indent=True, space_after=3)
    add_p("4. Configurar el proxy inverso Nginx con certificado SSL Let's Encrypt y cabeceras para soporte de WebSockets.", indent=True, space_after=3)
    add_p("5. Programar el Cron Job de respaldo automático diario a las 03:00 AM invocando el endpoint seguro <code>POST /api/v1/admin/backups/crear</code>.", indent=True, space_after=6)

    # Guardar documento
    doc.save(output_path)
    print(f"Documento Word (.docx) generado exitosamente en: {output_path}")


if __name__ == "__main__":
    target_docx = os.path.abspath("TRABAJO_ESPECIAL_DE_GRADO_DONDE_DAVID.docx")
    create_thesis_document(target_docx)
