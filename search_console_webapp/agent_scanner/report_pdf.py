# -*- coding: utf-8 -*-
"""Informe PDF del Agent-Ready Scanner (reportlab, ya en las deps de la app).

Diseñado para el flujo real: un CMO lo lee y se lo pasa a su equipo técnico.
Estructura:
  1. Portada con veredicto y score
  2. Resumen ejecutivo (qué significa, el viaje del agente, quick wins)
  3. Comparativa con competidores
  4. Plan de acción por prioridad (qué falla / por qué importa / cómo se arregla)
  5. Anexo técnico (evidencia de cada check, para el equipo técnico)
  6. Metodología y fiabilidad
"""
from io import BytesIO

# Los nombres de categoría viven en catalog.py, que es la fuente de verdad
# del catálogo de factores. Tenerlos duplicados en tres módulos era pedir
# que se desincronizaran al renombrar una categoría.
from .catalog import CATEGORIES as CAT_NAMES
IMPORD = {"Crítico": 0, "Alto": 1, "Alto (apuesta de futuro)": 1,
          "Alto (ventana de oportunidad)": 1, "Medio": 2, "Medio (creciente)": 2,
          "Bajo": 3, "Bajo (hoy)": 3, "Diagnóstico": 4}
TIERS = [(0, "Crítico", "Está frenando a los agentes hoy. Arreglar lo primero."),
         (1, "Importante", "Alto impacto en visibilidad y capacidad de ser usado."),
         (2, "Mejoras recomendadas", "Suman puntos y pulen la experiencia del agente."),
         (3, "Menor", "Poca urgencia: para cuando el resto esté hecho.")]


def build_pdf(data):
    """Devuelve un BytesIO con el PDF del informe."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    LIMA = colors.HexColor("#7BA428")      # acento legible sobre blanco
    DARK = colors.HexColor("#0F172A")
    GREY = colors.HexColor("#64748B")
    LIGHT = colors.HexColor("#E2E8F0")
    OK = colors.HexColor("#2E8B57")
    WARN = colors.HexColor("#C77700")
    BAD = colors.HexColor("#C0392B")

    client = data.get("client") or {}
    comps = [c for c in (data.get("competitors") or []) if "error" not in c]
    audits = [client] + comps
    host = client.get("host", "—")
    # lo usan varias secciones (resumen, plan de acción, anexo): vive aquí
    checks = client.get("checks") or []

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Title"], fontName="Helvetica-Bold",
                        fontSize=24, leading=28, textColor=DARK, alignment=TA_LEFT, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=ss["Heading1"], fontName="Helvetica-Bold",
                        fontSize=15, leading=19, textColor=DARK, spaceBefore=16, spaceAfter=8)
    H3 = ParagraphStyle("H3", parent=ss["Heading2"], fontName="Helvetica-Bold",
                        fontSize=11.5, leading=15, textColor=DARK, spaceBefore=10, spaceAfter=4)
    BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontName="Helvetica",
                          fontSize=9.5, leading=14, textColor=DARK, spaceAfter=6)
    MUTED = ParagraphStyle("MUTED", parent=BODY, textColor=GREY, fontSize=8.5, leading=12)
    LEAD = ParagraphStyle("LEAD", parent=BODY, fontSize=11, leading=16)
    MONO = ParagraphStyle("MONO", parent=BODY, fontName="Courier", fontSize=7.5, leading=10,
                          textColor=GREY)
    CENTER = ParagraphStyle("C", parent=BODY, alignment=TA_CENTER)

    def esc(s):
        return (str(s if s is not None else "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def color_for(pct):
        return BAD if pct < 25 else colors.HexColor("#D97706") if pct < 50 \
            else colors.HexColor("#B8A20B") if pct < 75 else OK

    # --- helpers gráficos (reportlab shapes): barras y donut, nada de texto plano
    from reportlab.graphics.shapes import Circle, Drawing, Rect, String, Wedge

    def bar(pct, width=6.2 * cm, height=0.42 * cm, col=None):
        """Barra de progreso con fondo, relleno y % al final."""
        d = Drawing(width + 1.3 * cm, height)
        col = col or color_for(pct)
        d.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#EEF2F7"),
                   strokeColor=None, rx=height / 2, ry=height / 2))
        w = max(width * pct / 100.0, 1)
        d.add(Rect(0, 0, w, height, fillColor=col, strokeColor=None,
                   rx=height / 2, ry=height / 2))
        d.add(String(width + 0.2 * cm, height / 2 - 3.2, f"{pct}%",
                     fontName="Helvetica-Bold", fontSize=8.5, fillColor=DARK))
        return d

    def donut(pct, size=3.4 * cm):
        """Donut del score global, coloreado por nivel."""
        d = Drawing(size, size)
        r, cx, cy = size / 2, size / 2, size / 2
        col = color_for(pct)
        d.add(Circle(cx, cy, r, fillColor=colors.HexColor("#EEF2F7"), strokeColor=None))
        ang = max(min(pct, 100), 0) * 3.6
        if ang > 0:
            d.add(Wedge(cx, cy, r, 90 - ang, 90, fillColor=col, strokeColor=None))
        d.add(Circle(cx, cy, r * 0.68, fillColor=colors.white, strokeColor=None))
        d.add(String(cx, cy + 1, f"{pct:g}", fontName="Helvetica-Bold", fontSize=21,
                     fillColor=DARK, textAnchor="middle"))
        d.add(String(cx, cy - 11, "de 100", fontName="Helvetica", fontSize=7,
                     fillColor=GREY, textAnchor="middle"))
        return d

    def chip(text, col):
        """Etiqueta de color (impacto, estado…) como mini-tabla."""
        t = Table([[Paragraph(f'<font color="{col.hexval()}" size="7.5"><b>{esc(text)}</b></font>',
                              BODY)]], colWidths=[3.1 * cm])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.7, col), ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    story = []

    def seccion_portada():
        lvl = client.get("level") or {}
        score = client.get("score", 0)
        lvl_color = BAD if score <= 25 else WARN if score <= 50 else colors.HexColor("#B8860B") if score <= 75 else OK
        story.append(Spacer(1, 1.2 * cm))
        story.append(Paragraph("CLICANDSEO · AGENT READINESS", ParagraphStyle(
            "kick", parent=MUTED, fontName="Helvetica-Bold", fontSize=9, textColor=LIMA)))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Auditoría de preparación para la era agéntica", H1))
        story.append(Paragraph(f"<b>{esc(host)}</b> · {esc(data.get('generated', '')[:10])}", LEAD))
        story.append(Spacer(1, 0.8 * cm))

        lvl_color = color_for(score)
        etapas_txt = []
        for _k, label, cs in [("leer", "¿Te leen?", ["C1", "C2"]),
                              ("entender", "¿Te entienden?", ["C3", "C4", "C5"]),
                              ("usar", "¿Pueden usarte?", ["C6", "C7"])]:
            vals = [client["category_scores"][c] for c in cs
                    if c in (client.get("category_scores") or {})]
            if vals:
                etapas_txt.append(f"{label} <b>{round(sum(vals)/len(vals)*100)}%</b>")

        verdict = Table([[
            donut(score),
            Paragraph(f'<b><font size="14" color="{lvl_color.hexval()}">{esc(lvl.get("name",""))}</font></b><br/>'
                      f'<font size="9.5" color="#0F172A">{esc(lvl.get("msg",""))}</font><br/><br/>'
                      f'<font size="8.5" color="#64748B">{" &nbsp;·&nbsp; ".join(etapas_txt)}</font>', BODY),
        ]], colWidths=[4.6 * cm, 11.4 * cm])
        verdict.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFBFC")),
            ("LINEAFTER", (0, 0), (0, 0), 0.8, LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12), ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(verdict)

        # Aviso de fidelidad: si el sitio bloqueó nuestro acceso, el PDF NO puede
        # salir con aspecto de dato firme. Este aviso replica el de la web; sin él,
        # la vía de exportación (la que viaja sola, sin nadie que la matice) era la
        # única sin guardarraíl.
        def _aviso_fiabilidad(dom, etiqueta):
            deg = dom.get("acceso_degradado")
            if dom.get("score_fiable", True) or not deg:
                return None
            warn_tbl = Table([[Paragraph(
                f'<b><font color="{BAD.hexval()}" size="11">⚠ PUNTUACIÓN NO FIABLE — '
                f'no usar este informe como dato firme</font></b><br/>'
                f'<font size="9">{esc(etiqueta)}: {esc(deg.get("motivo", ""))}. '
                f'Se han marcado <b>{deg.get("degradados", 0)}</b> factores como '
                f'«no verificable» en lugar de contarlos como fallo. La puntuación '
                f'cubre solo lo que sí pudo comprobarse: repite el análisis más tarde '
                f'o desde otra red antes de tomar decisiones con estos datos.</font>', BODY)]],
                colWidths=[16 * cm])
            warn_tbl.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 1.2, BAD),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDF1F1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]))
            return warn_tbl

        avisos = [w for w in
                  [_aviso_fiabilidad(client, "Tu dominio")]
                  + [_aviso_fiabilidad(comp, comp.get("host", "competidor"))
                     for comp in (data.get("competitors") or [])]
                  if w is not None]
        for w in avisos:
            story.append(Spacer(1, 0.4 * cm))
            story.append(w)

        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            "Este informe mide si los sistemas de IA pueden <b>leer</b> tu web, <b>entenderla</b> "
            "sin equivocarse y <b>actuar</b> en ella (comprar, reservar, contactar). No es SEO "
            "clásico: es la capa que determina si tu marca existe cuando un agente de IA hace el trabajo "
            "por el usuario.", BODY))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            "<b>Cómo usar este documento:</b> las secciones 1–3 son de decisión (para dirección/marketing). "
            "El <b>Anexo técnico</b> del final contiene la evidencia bruta de cada comprobación, pensado "
            "para pasárselo directamente al equipo técnico o a la agencia.", MUTED))

    def seccion_resumen():
        story.append(PageBreak())
        story.append(Paragraph("1. Resumen ejecutivo", H2))

        cats = [(c, client["category_scores"][c]) for c in CAT_NAMES
                if c in (client.get("category_scores") or {})]
        rows = [[Paragraph('<b><font color="white" size="9">CATEGORÍA</font></b>', BODY),
                 Paragraph('<b><font color="white" size="9">PUNTUACIÓN</font></b>', BODY),
                 Paragraph('<b><font color="white" size="9">ESTADO</font></b>', BODY)]]
        style = [("BACKGROUND", (0, 0), (-1, 0), DARK),
                 ("FONTSIZE", (0, 0), (-1, -1), 9),
                 ("LINEBELOW", (0, 0), (-1, -1), 0.4, LIGHT),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
        for i, (c, v) in enumerate(cats, start=1):
            pct = round(v * 100)
            estado = "Fuerte" if pct >= 75 else "Mejorable" if pct >= 50 else "Flojo" if pct >= 25 else "Crítico"
            col = color_for(pct)
            rows.append([Paragraph(f"<b>{c}</b> · {CAT_NAMES[c]}", BODY), bar(pct),
                         Paragraph(f'<font color="{col.hexval()}"><b>{estado}</b></font>', BODY)])
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFBFC")))
        t = Table(rows, colWidths=[6.1 * cm, 7.3 * cm, 2.6 * cm])
        t.setStyle(TableStyle(style))
        story.append(t)

        # continuum
        stages = [("¿Te leen?", ["C1", "C2"]), ("¿Te entienden?", ["C3", "C4", "C5"]),
                  ("¿Pueden usarte?", ["C6", "C7"])]
        srow, hrow = [], []
        for name, cs in stages:
            vals = [client["category_scores"][c] for c in cs if c in (client.get("category_scores") or {})]
            if not vals:
                continue
            p = round(sum(vals) / len(vals) * 100)
            hrow.append(Paragraph(f"<b>{name}</b>", CENTER))
            srow.append(Paragraph(f'<font size="18"><b>{p}%</b></font>', CENTER))
        if hrow:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph("El viaje del agente por tu web", H3))
            ct = Table([hrow, srow], colWidths=[16 * cm / len(hrow)] * len(hrow))
            ct.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LIGHT),
                                    ("INNERGRID", (0, 0), (-1, -1), 0.5, LIGHT),
                                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            story.append(ct)
            story.append(Paragraph(
                "Un agente primero tiene que poder leerte, luego entenderte sin equivocarse, y solo "
                "entonces puede usarte. La cadena se rompe en el eslabón más débil.", MUTED))

        n_ok = sum(1 for c in checks if c.get("score") == 1)
        n_part = sum(1 for c in checks if c.get("score") not in (None, 0, 1))
        n_bad = sum(1 for c in checks if c.get("score") == 0)
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            f"De <b>{len(checks)} comprobaciones</b>: <font color='{OK.hexval()}'><b>{n_ok} se cumplen</b></font>, "
            f"<font color='{WARN.hexval()}'><b>{n_part} a medias</b></font> y "
            f"<font color='{BAD.hexval()}'><b>{n_bad} fallan</b></font>.", BODY))
        for pen, val in (client.get("penalties") or []):
            story.append(Paragraph(f"⚠ Penalización aplicada: {esc(pen)} ({val} puntos)", MUTED))

        quick = [c for c in checks if c.get("advice") and c.get("score") is not None
                 and c["score"] < 1 and c["advice"].get("esfuerzo") == "Bajo"
                 and IMPORD.get(c["advice"].get("impacto"), 3) <= 2]
        if quick:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph("Por dónde empezar (quick wins: alto impacto, poco esfuerzo)", H3))
            for c in quick[:5]:
                story.append(Paragraph(f"• <b>{esc(c['advice']['titulo'])}</b> — {esc(c['advice']['como'])}", BODY))

    def seccion_comparativa():
        if comps:
            story.append(PageBreak())
            story.append(Paragraph("2. Comparativa con la competencia", H2))
            story.append(Paragraph("Mismos checks, mismos pesos, misma vara de medir para todos los dominios.", BODY))
            head = ["Categoría"] + [a.get("host", "?") for a in audits]
            rows = [head]
            for c in CAT_NAMES:
                if not any(c in (a.get("category_scores") or {}) for a in audits):
                    continue
                row = [f"{c} · {CAT_NAMES[c]}"]
                for a in audits:
                    v = (a.get("category_scores") or {}).get(c)
                    row.append(f"{round(v*100)}%" if v is not None else "n/a")
                rows.append(row)
            rows.append(["PUNTUACIÓN GLOBAL"] + [str(a.get("score", "—")) for a in audits])
            w = [7 * cm] + [(9 * cm) / len(audits)] * len(audits)
            ct = Table(rows, colWidths=w)
            heat = [("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
            # mapa de calor: cada celda coloreada según su valor
            for ri in range(1, len(rows) - 1):
                for ci in range(1, len(rows[ri])):
                    txt = rows[ri][ci]
                    if txt.endswith("%"):
                        p = int(txt[:-1])
                        tone = (colors.HexColor("#FDECEA") if p < 25 else
                                colors.HexColor("#FEF0E2") if p < 50 else
                                colors.HexColor("#FBF7E0") if p < 75 else
                                colors.HexColor("#E9F5EE"))
                        heat.append(("BACKGROUND", (ci, ri), (ci, ri), tone))
                        heat.append(("TEXTCOLOR", (ci, ri), (ci, ri), color_for(p)))
            ct.setStyle(TableStyle(heat))
            story.append(ct)
            story.append(Spacer(1, 0.3 * cm))
            gaps = []
            for c in CAT_NAMES:
                mine = (client.get("category_scores") or {}).get(c)
                if mine is None:
                    continue
                for comp in comps:
                    v = (comp.get("category_scores") or {}).get(c)
                    if v is not None and v - mine >= 0.15:
                        gaps.append(f"• <b>{c} · {CAT_NAMES[c]}</b>: {esc(comp.get('host'))} te saca "
                                    f"{round((v-mine)*100)} puntos ({round(v*100)}% vs tu {round(mine*100)}%).")
            story.append(Paragraph("Dónde te sacan ventaja", H3))
            if gaps:
                for g in gaps:
                    story.append(Paragraph(g, BODY))
            else:
                story.append(Paragraph("Sin brechas relevantes: ninguna categoría con desventaja ≥15 puntos.", BODY))

    def seccion_plan_de_accion():
        story.append(PageBreak())
        story.append(Paragraph("3. Plan de acción priorizado", H2))
        story.append(Paragraph(
            "Cada punto explica <b>qué falla</b>, <b>por qué le importa al negocio</b> y "
            "<b>cómo se arregla</b> (esta última línea es la que puede ir directa al equipo técnico).", BODY))
        items = [c for c in checks if c.get("advice") and c.get("score") is not None and c["score"] < 1]
        for ord_, tier_name, tier_desc in TIERS:
            tier_items = [c for c in items if min(IMPORD.get(c["advice"].get("impacto"), 3), 3) == ord_]
            if not tier_items:
                continue
            tier_col = [BAD, colors.HexColor("#D97706"), colors.HexColor("#B8A20B"), GREY][ord_]
            story.append(Spacer(1, 0.35 * cm))
            # cabecera de prioridad con banda de color
            th = Table([[Paragraph(
                f'<font color="white" size="10.5"><b>&nbsp;{esc(tier_name).upper()} · {len(tier_items)}</b></font>'
                f'<font color="white" size="8">&nbsp;&nbsp;{esc(tier_desc)}</font>', BODY)]],
                colWidths=[16 * cm])
            th.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tier_col),
                                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story.append(th)
            story.append(Spacer(1, 0.2 * cm))
            for c in tier_items:
                a = c["advice"]
                meta = Table([[chip(f"Impacto {a['impacto']}", tier_col),
                               chip(f"Esfuerzo {a['esfuerzo']}", GREY),
                               Paragraph(f"<font color='#94A3B8' size='7.5'>check {esc(c['id'])}</font>", MUTED)]],
                             colWidths=[3.3 * cm, 3.3 * cm, 3 * cm])
                meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                          ("TOPPADDING", (0, 0), (-1, -1), 0),
                                          ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                          ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
                card = Table([[Paragraph(f"<b>{esc(a['titulo'])}</b>", BODY)],
                              [meta],
                              [Paragraph(f"<font color='#64748B'><b>POR QUÉ IMPORTA</b></font><br/>{esc(a['por_que'])}", BODY)],
                              [Paragraph(f"<font color='#64748B'><b>CÓMO SE ARREGLA</b></font><br/>{esc(a['como'])}", BODY)]],
                             colWidths=[16 * cm])
                card.setStyle(TableStyle([
                    ("LINEBEFORE", (0, 0), (0, -1), 2, tier_col),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFBFC")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(KeepTogether([card, Spacer(1, 0.28 * cm)]))

    def seccion_anexo_tecnico():
        story.append(PageBreak())
        story.append(Paragraph("4. Anexo técnico — evidencia de cada comprobación", H2))
        story.append(Paragraph(
            "Para el equipo técnico: resultado y evidencia bruta de las "
            f"{len(checks)} comprobaciones sobre {esc(host)}.", BODY))
        rows = [["Check", "Resultado", "Evidencia"]]
        for c in checks:
            s = c.get("score")
            res = "CUMPLE" if s == 1 else "PARCIAL" if (s or 0) > 0 else "FALLA" if s == 0 else "N/A"
            rows.append([Paragraph(f"<b>{esc(c['id'])}</b> {esc(c['name'])}", MUTED),
                         Paragraph(res, MUTED),
                         Paragraph(esc(c.get("evidence", ""))[:300], MONO)])
        at = Table(rows, colWidths=[4.6 * cm, 1.9 * cm, 9.5 * cm], repeatRows=1)
        at.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(at)

        # pruebas agénticas
        at_data = client.get("agent_tests") or {}
        if at_data.get("agents"):
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Prueba con agentes de IA reales (check 6.3)", H3))
            story.append(Paragraph(
                f"Tarea de tipología <b>{esc(at_data.get('typology'))}</b>. Cada agente controla un "
                "navegador real e intenta completarla. Nunca se pagan compras ni se crean cuentas.", BODY))
            for name, r in at_data["agents"].items():
                story.append(Paragraph(
                    f"• <b>{esc(name)}</b>: {esc(str(r.get('outcome','')).replace('_',' '))}"
                    f"{' · ' + str(r.get('steps')) + ' pasos' if r.get('steps') else ''} — "
                    f"{esc(r.get('detail',''))[:220]}", BODY))

    def seccion_metodologia():
        story.append(PageBreak())
        story.append(Paragraph("5. Metodología y fiabilidad", H2))
        story.append(Paragraph(
            f"Tipología detectada: <b>{esc(client.get('typology'))}</b>. "
            f"Framework: {esc(data.get('framework_version',''))}.", BODY))
        cov = client.get("coverage") or {}
        story.append(Paragraph(
            f"Cobertura del muestreo: {cov.get('sampled_ok','?')}/{cov.get('sampled','?')} páginas "
            f"accesibles de {cov.get('sitemap_urls','?')} URLs del sitemap. El muestreo es "
            "representativo (hasta 2 páginas por plantilla), no exhaustivo.", BODY))
        trail = client.get("trail") or []
        if trail:
            story.append(Paragraph("Procesos ejecutados y su resultado", H3))
            rows = [["Proceso", "Estado", "Detalle"]]
            for t in trail:
                rows.append([Paragraph(esc(t.get("step")), MUTED),
                             Paragraph(esc(t.get("status")).upper(), MUTED),
                             Paragraph(esc(t.get("detail", ""))[:220], MONO)])
            tt = Table(rows, colWidths=[4.4 * cm, 2 * cm, 9.6 * cm], repeatRows=1)
            tt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, LIGHT), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tt)
            story.append(Paragraph(
                "OK = ejecutado con evidencia · WARN = evidencia degradada · FAIL = el proceso no obtuvo "
                "evidencia · SKIPPED = desactivado. Un 404 del sitio es un hallazgo, no un fallo del análisis.", MUTED))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(
            "El campo agéntico evoluciona por trimestres: se recomienda repetir esta auditoría cada 90 días.", MUTED))


    # Orden del documento. Cada sección es autónoma y comparte estilos y
    # helpers por closure; añadir o reordenar una es tocar solo esta lista.
    for seccion in (seccion_portada, seccion_resumen, seccion_comparativa,
                    seccion_plan_de_accion, seccion_anexo_tecnico,
                    seccion_metodologia):
        seccion()

    # ---------------------------------------------------------------- render
    buf = BytesIO()
    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(2 * cm, 1.2 * cm, f"Clicandseo · Agent Readiness · {host}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title=f"Agent Readiness · {host}", author="Clicandseo")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
