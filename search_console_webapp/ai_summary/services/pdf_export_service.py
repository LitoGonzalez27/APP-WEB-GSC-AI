"""
AI Visibility Summary — Executive PDF report (one-pager + competidores).

Informe ejecutivo pensado para reenviar a dirección: score con delta y
cobertura, highlights, métricas por canal, histórico del score (si existe),
ranking de competidores y top opportunities.

Identidad Clicandseo (brandbook v1.1): cabecera oscura #0A0A0B, acento
Bio-Lime #d9f9b8, paleta slate, sin gradientes. Mismo stack (reportlab)
que los exports de Manual AI y LLM Monitoring.
"""

import io
import logging
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

logger = logging.getLogger(__name__)

# Paleta brandbook
DARK = colors.HexColor('#0A0A0B')
TEXT = colors.HexColor('#0F172A')
TEXT_SECONDARY = colors.HexColor('#64748B')
BORDER = colors.HexColor('#E2E8F0')
BG_SUBTLE = colors.HexColor('#F1F5F9')
ACCENT = colors.HexColor('#d9f9b8')
ACCENT_SUBTLE = colors.HexColor('#F3FCE7')
SUCCESS = colors.HexColor('#3CB371')
ERROR = colors.HexColor('#E05252')

PERIOD_LABELS = {
    '7': 'Last 7 days', '14': 'Last 14 days', '28': 'Last 28 days',
    '30': 'Last 30 days', 'last_month': 'Last full month',
    '90': 'Last 3 months', '180': 'Last 6 months',
}

CHANNEL_LABELS = {
    'ai_overview': 'Google AI Overview',
    'ai_mode': 'Google AI Mode',
    'llm': 'LLMs (ChatGPT, Gemini...)',
}


def _style(name, **kw):
    defaults = dict(fontName='Helvetica', fontSize=9, leading=13, textColor=TEXT)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


S_TITLE = _style('title', fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.white)
S_SUBTITLE = _style('subtitle', fontSize=9, textColor=colors.HexColor('#CBD5E1'))
S_H2 = _style('h2', fontName='Helvetica-Bold', fontSize=12, leading=16, spaceBefore=14, spaceAfter=6)
S_BODY = _style('body')
S_SMALL = _style('small', fontSize=8, textColor=TEXT_SECONDARY)
S_SCORE = _style('score', fontName='Helvetica-Bold', fontSize=34, leading=36, textColor=DARK)
S_TABLE_CELL = _style('cell', fontSize=8.5, leading=11)
S_TABLE_HEAD = _style('head', fontName='Helvetica-Bold', fontSize=8, textColor=colors.white)


def _delta_text(delta, suffix=' pts'):
    if delta is None:
        return '<font color="#94A3B8">no previous period</font>'
    if abs(delta) < 0.05:
        return '<font color="#64748B">stable</font>'
    color = '#3CB371' if delta > 0 else '#E05252'
    sign = '+' if delta > 0 else ''
    return f'<font color="{color}"><b>{sign}{delta:.1f}{suffix}</b></font>'


def _pct(value):
    return f'{value:.1f}%' if value is not None else '–'


class AiSummaryPdfExportService:
    """Genera el informe ejecutivo en PDF de una marca."""

    def build(self, brand: dict, summary: dict, history: list) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=16 * mm, rightMargin=16 * mm,
            topMargin=42 * mm, bottomMargin=16 * mm,
            title=f"AI Visibility Report — {brand['brand_name']}",
        )

        story = []
        story += self._score_block(summary)
        story += self._highlights_block(summary)
        story += self._channels_block(summary)
        story += self._history_block(history)
        story += self._competitors_block(brand, summary)
        story += self._opportunities_block(summary)

        header = self._page_decorator(brand, summary)
        doc.build(story, onFirstPage=header, onLaterPages=header)
        buffer.seek(0)
        return buffer

    # ------------------------------------------------------------------
    # Cabecera y pie de página
    # ------------------------------------------------------------------

    def _page_decorator(self, brand, summary):
        period_label = PERIOD_LABELS.get(summary.get('period'), summary.get('period'))
        generated = datetime.now().strftime('%d %b %Y')

        def draw(canvas, doc):
            width, height = A4
            # Banda superior oscura
            canvas.saveState()
            canvas.setFillColor(DARK)
            canvas.rect(0, height - 34 * mm, width, 34 * mm, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 17)
            canvas.drawString(16 * mm, height - 16 * mm, 'AI Visibility Report')
            canvas.setFillColor(ACCENT)
            canvas.setFont('Helvetica-Bold', 12)
            canvas.drawString(16 * mm, height - 23 * mm, brand['brand_name'][:60])
            canvas.setFillColor(colors.HexColor('#CBD5E1'))
            canvas.setFont('Helvetica', 8.5)
            canvas.drawString(16 * mm, height - 29 * mm,
                              f"{brand['brand_domain']}  ·  {period_label}  ·  Generated {generated}")
            canvas.setFont('Helvetica-Bold', 10)
            canvas.setFillColor(colors.white)
            canvas.drawRightString(width - 16 * mm, height - 16 * mm, 'Clicandseo')
            # Pie
            canvas.setFillColor(TEXT_SECONDARY)
            canvas.setFont('Helvetica', 7.5)
            canvas.drawString(16 * mm, 9 * mm, 'Generated by Clicandseo · AI Visibility Summary')
            canvas.drawRightString(width - 16 * mm, 9 * mm, f'Page {canvas.getPageNumber()}')
            canvas.restoreState()

        return draw

    # ------------------------------------------------------------------
    # Bloques
    # ------------------------------------------------------------------

    def _score_block(self, summary):
        score = summary.get('score') or {}
        value = score.get('value')
        used = score.get('channels_used') or []
        missing = score.get('channels_missing') or []
        coverage = (f"Based on {len(used)} of {len(used) + len(missing)} channels: "
                    + ', '.join(CHANNEL_LABELS.get(c, c) for c in used)) if used else 'No data in this period'

        score_cell = [
            Paragraph('AI VISIBILITY SCORE', _style('sl', fontSize=8, textColor=TEXT_SECONDARY)),
            Spacer(0, 2),
            Paragraph('–' if value is None else f'{value:.1f}', S_SCORE),
            Spacer(0, 2),
            Paragraph(_delta_text(score.get('delta')) + ' vs previous period', S_TABLE_CELL),
            Spacer(0, 2),
            Paragraph(escape(coverage), S_SMALL),
        ]
        table = Table([[score_cell]], colWidths=[178 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), ACCENT_SUBTLE),
            ('BOX', (0, 0), (-1, -1), 0.75, BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        return [table]

    def _highlights_block(self, summary):
        highlights = summary.get('highlights') or []
        if not highlights:
            return []
        icons = {'positive': '▲', 'negative': '▼', 'neutral': '◆', 'info': '·'}
        icon_colors = {'positive': '#3CB371', 'negative': '#E05252',
                       'neutral': '#64748B', 'info': '#94A3B8'}
        flow = [Paragraph('Key takeaways', S_H2)]
        for h in highlights:
            severity = h.get('severity', 'info')
            flow.append(Paragraph(
                f'<font color="{icon_colors.get(severity, "#94A3B8")}">{icons.get(severity, "·")}</font>  '
                + escape(h.get('text', '')),
                _style('hl', fontSize=9.5, leading=14, spaceAfter=2)))
        return flow

    def _channels_block(self, summary):
        channels = summary.get('channels') or {}
        rows = [[Paragraph(h, S_TABLE_HEAD) for h in
                 ['Channel', 'Visibility', 'Trend', 'Avg position', 'Notes']]]
        for key, label in CHANNEL_LABELS.items():
            ch = channels.get(key) or {}
            if not ch.get('available'):
                note = 'Not monitored' if not ch.get('project_id') else 'No data in this period'
                rows.append([Paragraph(escape(label), S_TABLE_CELL),
                             Paragraph('–', S_TABLE_CELL), Paragraph('–', S_TABLE_CELL),
                             Paragraph('–', S_TABLE_CELL),
                             Paragraph(f'<font color="#94A3B8">{note}</font>', S_TABLE_CELL)])
                continue
            extras = ch.get('extras') or {}
            notes = []
            if key == 'ai_overview' and extras.get('aio_weight_pct') is not None:
                notes.append(f"Keywords with AIO: {_pct(extras['aio_weight_pct'])}")
            if key == 'llm':
                if extras.get('share_of_voice') is not None:
                    notes.append(f"Share of Voice: {_pct(extras['share_of_voice'])}")
                sentiment = extras.get('sentiment') or {}
                if sentiment.get('positive') is not None:
                    notes.append(f"Sentiment: {sentiment['positive']:.0f}% positive")
            rows.append([
                Paragraph(escape(label), S_TABLE_CELL),
                Paragraph(f"<b>{_pct(ch.get('visibility_pct'))}</b>", S_TABLE_CELL),
                Paragraph(_delta_text(ch.get('visibility_delta')), S_TABLE_CELL),
                Paragraph(f"#{ch['avg_position']:.1f}" if ch.get('avg_position') is not None else '–', S_TABLE_CELL),
                Paragraph(escape(' · '.join(notes)) or '–', S_TABLE_CELL),
            ])
        table = Table(rows, colWidths=[48 * mm, 22 * mm, 30 * mm, 24 * mm, 54 * mm], repeatRows=1)
        table.setStyle(self._table_style())
        return [Paragraph('Channel performance', S_H2), table]

    def _history_block(self, history):
        if not history or len(history) < 2:
            return []
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.charts.lineplots import LinePlot

        points = [(i, h['score']) for i, h in enumerate(history)]
        drawing = Drawing(178 * mm, 42 * mm)
        plot = LinePlot()
        plot.x, plot.y = 8, 8
        plot.width, plot.height = 178 * mm - 20, 42 * mm - 16
        plot.data = [points]
        plot.lines[0].strokeColor = DARK
        plot.lines[0].strokeWidth = 1.6
        plot.xValueAxis.visible = False
        plot.yValueAxis.valueMin = 0
        plot.yValueAxis.valueMax = 100
        plot.yValueAxis.valueStep = 25
        plot.yValueAxis.labels.fontSize = 6.5
        plot.yValueAxis.strokeColor = BORDER
        drawing.add(plot)

        first, last = history[0], history[-1]
        caption = (f"{first['date']} → {last['date']} · "
                   f"{first['score']:.1f} → {last['score']:.1f}")
        return [Paragraph('Score history (last 6 months)', S_H2), drawing,
                Paragraph(escape(caption), S_SMALL)]

    def _competitors_block(self, brand, summary):
        competitors = summary.get('competitors_unified') or []
        if not competitors:
            return []
        rows = [[Paragraph(h, S_TABLE_HEAD) for h in
                 ['#', 'Domain', 'AI Overview', 'AI Mode', 'LLMs (SoV)', 'Avg']]]
        brand_row_index = None
        for i, c in enumerate(competitors[:12]):
            ch = c.get('channels') or {}
            name = escape(c.get('domain', ''))
            if c.get('is_brand'):
                name = f'<b>{name}</b> <font color="#3CB371"><b>YOU</b></font>'
                brand_row_index = i + 1
            rows.append([
                Paragraph(str(c.get('rank', i + 1)), S_TABLE_CELL),
                Paragraph(name, S_TABLE_CELL),
                Paragraph(_pct(ch.get('ai_overview')), S_TABLE_CELL),
                Paragraph(_pct(ch.get('ai_mode')), S_TABLE_CELL),
                Paragraph(_pct(ch.get('llm')), S_TABLE_CELL),
                Paragraph(f"<b>{_pct(c.get('avg_visibility'))}</b>", S_TABLE_CELL),
            ])
        table = Table(rows, colWidths=[10 * mm, 74 * mm, 25 * mm, 21 * mm, 25 * mm, 23 * mm], repeatRows=1)
        style = self._table_style()
        if brand_row_index is not None:
            style.add('BACKGROUND', (0, brand_row_index), (-1, brand_row_index), ACCENT_SUBTLE)
        table.setStyle(style)
        return [Paragraph('Who owns AI visibility in your market', S_H2), table]

    def _opportunities_block(self, summary):
        opportunities = summary.get('opportunities') or {}
        aio, llm = opportunities.get('aio') or [], opportunities.get('llm') or []
        if not aio and not llm:
            return []
        flow = [Paragraph('Top opportunities — where competitors show up and you don\'t', S_H2)]
        for item in aio:
            competitors = ', '.join(escape(c) for c in item.get('competitors', []))
            flow.append(Paragraph(
                f'<b>AI Overview</b> · "{escape(item["keyword"])}" — cited: {competitors}',
                _style('op', fontSize=9, leading=13, spaceAfter=2)))
        for item in llm:
            competitors = ', '.join(escape(c) for c in item.get('competitors', []))
            prompt = item['prompt'][:90] + ('…' if len(item['prompt']) > 90 else '')
            flow.append(Paragraph(
                f'<b>LLMs</b> · "{escape(prompt)}" — mentioned: {competitors}',
                _style('op2', fontSize=9, leading=13, spaceAfter=2)))
        return flow

    @staticmethod
    def _table_style():
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_SUBTLE]),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ])
