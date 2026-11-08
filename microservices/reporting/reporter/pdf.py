"""Mise en page du planning hebdomadaire au format PDF (ReportLab)."""

from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .stats import PARIS, Report

DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
DAYS_SHORT = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.']
MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
          'août', 'septembre', 'octobre', 'novembre', 'décembre']

INK = colors.HexColor('#1f2937')
MUTED = colors.HexColor('#6b7280')
LINE = colors.HexColor('#d1d5db')
HEADER_BG = colors.HexColor('#1f2937')
ZEBRA = colors.HexColor('#f9fafb')
ALERT_BG = colors.HexColor('#fde2e1')
ALERT_INK = colors.HexColor('#b91c1c')
WARN_BG = colors.HexColor('#fef3c7')


def long_date(d: date) -> str:
    return f'{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}'


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle('t', parent=base['Title'], fontSize=20, leading=24,
                                textColor=INK, alignment=0, spaceAfter=2),
        'subtitle': ParagraphStyle('s', parent=base['Normal'], fontSize=11, textColor=MUTED),
        'h2': ParagraphStyle('h2', parent=base['Heading2'], fontSize=13, textColor=INK,
                             spaceBefore=10, spaceAfter=6),
        'cell': ParagraphStyle('c', parent=base['Normal'], fontSize=8.5, leading=10.5, textColor=INK),
        'kpi_value': ParagraphStyle('kv', parent=base['Normal'], fontSize=18, leading=22,
                                    textColor=INK, alignment=TA_CENTER, fontName='Helvetica-Bold'),
        'kpi_label': ParagraphStyle('kl', parent=base['Normal'], fontSize=8.5, textColor=MUTED,
                                    alignment=TA_CENTER),
        'empty': ParagraphStyle('e', parent=base['Normal'], fontSize=10, textColor=MUTED),
    }


def _table_style(header_rows=1):
    return [
        ('BACKGROUND', (0, 0), (-1, header_rows - 1), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), colors.white),
        ('FONTNAME', (0, 0), (-1, header_rows - 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]


def _kpis(report: Report, st):
    coverage = f'{report.coverage * 100:.0f} %'
    cells = [
        (str(len(report.shifts)), 'créneaux'),
        (str(report.total_assignments), 'affectations'),
        (coverage, 'couverture des effectifs minimum'),
        (str(len(report.understaffed)), 'créneaux en sous-effectif'),
    ]
    table = Table(
        [[Paragraph(v, st['kpi_value']) for v, _ in cells],
         [Paragraph(label, st['kpi_label']) for _, label in cells]],
        colWidths=[66 * mm] * 4,
    )
    style = [
        ('BOX', (0, 0), (-1, -1), 0.6, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ('LINEAFTER', (0, 0), (-2, -1), 0.4, LINE),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]
    if report.understaffed:
        style.append(('TEXTCOLOR', (3, 0), (3, 0), ALERT_INK))
    table.setStyle(TableStyle(style))
    return table


def _planning_table(report: Report, st):
    rows = [['Jour', 'Horaire', 'Garde', 'Service / unité', 'Soignants', 'Effectif']]
    style = _table_style()
    for i, s in enumerate(report.shifts, start=1):
        staff = ', '.join(s.staff_names) if s.staff_names else '<font color="#b91c1c">Non pourvu</font>'
        rows.append([
            f'{DAYS_SHORT[s.start.weekday()]} {s.start:%d/%m}',
            f'{s.start:%H:%M} – {s.end:%H:%M}',
            s.shift_type + (' (nuit)' if s.is_night else ''),
            Paragraph(escape(f'{s.service} / {s.care_unit}'), st['cell']),
            Paragraph(staff if not s.staff_names else escape(staff), st['cell']),
            f'{s.assigned} / {s.min_staff}',
        ])
        if s.understaffed:
            style += [('BACKGROUND', (0, i), (-1, i), ALERT_BG), ('TEXTCOLOR', (5, i), (5, i), ALERT_INK)]
        elif i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    table = Table(rows, colWidths=[22 * mm, 28 * mm, 34 * mm, 62 * mm, 98 * mm, 20 * mm],
                  repeatRows=1)
    style.append(('ALIGN', (5, 0), (5, -1), 'CENTER'))
    table.setStyle(TableStyle(style))
    return table


def _staff_table(report: Report, st):
    rows = [['Soignant', 'Gardes', 'Heures', 'Plafond hebdo', 'Charge', 'Nuits', 'Week-end']]
    style = _table_style()
    for i, p in enumerate(report.staff, start=1):
        load = f'{p.load * 100:.0f} %' if p.load is not None else '—'
        rows.append([
            Paragraph(escape(p.name), st['cell']), p.shifts, f'{p.hours} h',
            f'{p.max_hours} h' if p.max_hours else 'sans contrat', load, p.nights, p.weekends,
        ])
        if p.overloaded:
            style.append(('BACKGROUND', (0, i), (-1, i), WARN_BG))
        elif i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), ZEBRA))
    style.append(('ALIGN', (1, 0), (-1, -1), 'CENTER'))
    table = Table(rows, colWidths=[70 * mm, 22 * mm, 22 * mm, 30 * mm, 22 * mm, 22 * mm, 22 * mm],
                  repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle(style))
    return table


def render_planning_pdf(report: Report, generated_at: datetime | None = None) -> bytes:
    st = _styles()
    generated_at = (generated_at or datetime.now(PARIS)).astimezone(PARIS)
    buffer = BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 8 * mm,
                          f'HospiPlan — généré le {generated_at:%d/%m/%Y à %H:%M}')
        canvas.drawRightString(doc.pagesize[0] - 15 * mm, 8 * mm, f'Page {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
        title=f'Planning du {report.week_start:%d/%m/%Y}', author='HospiPlan',
    )

    story = [
        Paragraph('Planning hebdomadaire', st['title']),
        Paragraph(f'Semaine du {long_date(report.week_start)} au {long_date(report.week_end)}',
                  st['subtitle']),
        Spacer(1, 6 * mm),
        _kpis(report, st),
        Paragraph('Planning détaillé', st['h2']),
    ]
    if report.shifts:
        story.append(_planning_table(report, st))
    else:
        story.append(Paragraph('Aucun créneau sur cette semaine.', st['empty']))

    story.append(Paragraph('Charge par soignant', st['h2']))
    if report.staff:
        story.append(_staff_table(report, st))
    else:
        story.append(Paragraph('Aucun soignant actif.', st['empty']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
