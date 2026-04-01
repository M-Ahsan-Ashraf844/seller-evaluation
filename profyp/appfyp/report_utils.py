"""
report_utils.py
---------------
Seller Performance PDF Report Generator
Drop this file into your Django app (e.g. appfyp/report_utils.py).

Usage in views.py:
    from appfyp.report_utils import generate_seller_pdf_report

    def seller_report_view(request, seller_id):
        seller = get_object_or_404(Seller, pk=seller_id)
        return generate_seller_pdf_report(seller)
"""

from io import BytesIO
from datetime import date

from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)


# ── Colour palette ────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor("#1a3c5e")   # dark navy
ACCENT    = colors.HexColor("#2e86de")   # blue
SUCCESS   = colors.HexColor("#27ae60")   # green
WARNING   = colors.HexColor("#e67e22")   # orange
DANGER    = colors.HexColor("#e74c3c")   # red
LIGHT_BG  = colors.HexColor("#f0f4f8")   # very light blue-grey
MID_GREY  = colors.HexColor("#7f8c8d")
WHITE     = colors.white
BLACK     = colors.black


def _styles():
    base = getSampleStyleSheet()
    custom = {
        "ReportTitle": ParagraphStyle(
            "ReportTitle", parent=base["Title"],
            fontSize=22, textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=4, fontName="Helvetica-Bold"
        ),
        "ReportSubtitle": ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"],
            fontSize=10, textColor=colors.HexColor("#dce6f0"),
            alignment=TA_CENTER, spaceAfter=0
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"],
            fontSize=13, textColor=PRIMARY, fontName="Helvetica-Bold",
            spaceBefore=14, spaceAfter=6,
            borderPad=4
        ),
        "MetricLabel": ParagraphStyle(
            "MetricLabel", parent=base["Normal"],
            fontSize=9, textColor=MID_GREY, fontName="Helvetica"
        ),
        "MetricValue": ParagraphStyle(
            "MetricValue", parent=base["Normal"],
            fontSize=18, textColor=PRIMARY, fontName="Helvetica-Bold",
            alignment=TA_CENTER
        ),
        "MetricUnit": ParagraphStyle(
            "MetricUnit", parent=base["Normal"],
            fontSize=8, textColor=MID_GREY, alignment=TA_CENTER
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=9, textColor=BLACK, leading=14
        ),
        "Footer": ParagraphStyle(
            "Footer", parent=base["Normal"],
            fontSize=8, textColor=MID_GREY, alignment=TA_CENTER
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader", parent=base["Normal"],
            fontSize=9, textColor=WHITE, fontName="Helvetica-Bold",
            alignment=TA_CENTER
        ),
    }
    return {**{k: base[k] for k in base.byName}, **custom}


def _score_color(score: float) -> colors.Color:
    if score >= 80:
        return SUCCESS
    if score >= 60:
        return WARNING
    return DANGER


def _star_string(rating: float) -> str:
    full  = int(rating)
    half  = 1 if (rating - full) >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + ("½" if half else "") + "☆" * empty


# ── Main generator ─────────────────────────────────────────────────────────────
def generate_seller_pdf_report(seller) -> HttpResponse:
    """
    Build a PDF seller performance report and return it as an HttpResponse.
    Requires: seller has related .orders, .reviews, and .performance (via Performance model).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.2*cm,  bottomMargin=1.8*cm,
        title=f"Seller Report – {seller.name}",
        author="Seller Evaluation System"
    )

    S   = _styles()
    W   = A4[0] - 3.6*cm      # usable width
    story = []

    # ── Header Banner ──────────────────────────────────────────────────────────
    header_data = [[
        Paragraph(f"Seller Performance Report", S["ReportTitle"]),
    ]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), PRIMARY),
        ("ROUNDEDCORNERS", [8]),
        ("TOPPADDING",  (0,0), (-1,-1), 16),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING",(0,0), (-1,-1), 12),
    ]))
    story.append(header_table)

    # Subtitle row (seller name + date)
    sub_data = [[
        Paragraph(seller.name, ParagraphStyle(
            "SellerName", fontSize=14, textColor=ACCENT,
            fontName="Helvetica-Bold", alignment=TA_LEFT
        )),
        Paragraph(
            f"Generated: {date.today().strftime('%d %b %Y')}",
            ParagraphStyle("GenDate", fontSize=9, textColor=MID_GREY,
                           alignment=TA_RIGHT)
        ),
    ]]
    sub_table = Table(sub_data, colWidths=[W*0.65, W*0.35])
    sub_table.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    story.append(sub_table)
    story.append(HRFlowable(width=W, color=ACCENT, thickness=1.5, spaceAfter=10))

    # ── Pull performance object ────────────────────────────────────────────────
    try:
        perf = seller.performance
    except Exception:
        perf = None

    total_orders   = perf.total_orders      if perf else 0
    avg_rating     = float(perf.average_rating)  if perf else 0.0
    delivery_rate  = float(perf.delivery_rate)   if perf else 0.0
    return_rate    = float(perf.return_rate)     if perf else 0.0
    perf_score     = float(perf.performance_score) if perf else 0.0

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Key Performance Indicators", S["SectionHeading"]))

    score_col = _score_color(perf_score)

    def kpi_cell(label, value, unit=""):
        return [
            Paragraph(label, S["MetricLabel"]),
            Paragraph(str(value), S["MetricValue"]),
            Paragraph(unit, S["MetricUnit"]),
        ]

    kpi_data = [[
        kpi_cell("Performance Score", f"{perf_score:.1f}", "out of 100"),
        kpi_cell("Total Orders",      total_orders,         "orders"),
        kpi_cell("Avg Rating",        f"{avg_rating:.1f}",  _star_string(avg_rating)),
        kpi_cell("Delivery Rate",     f"{delivery_rate:.1f}%", "on-time"),
        kpi_cell("Return Rate",       f"{return_rate:.1f}%", "of orders"),
    ]]

    # Flatten: each card is a sub-table
    card_width = (W - 0.4*cm*4) / 5

    def make_card(label, value, unit, bg_top=LIGHT_BG):
        cell_data = [
            [Paragraph(label,  S["MetricLabel"])],
            [Paragraph(value,  S["MetricValue"])],
            [Paragraph(unit,   S["MetricUnit"])],
        ]
        t = Table(cell_data, colWidths=[card_width])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), LIGHT_BG),
            ("ROUNDEDCORNERS", [6]),
            ("TOPPADDING",   (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ("RIGHTPADDING", (0,0),(-1,-1), 6),
            ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ]))
        return t

    score_card_data = [
        [Paragraph("Performance Score", S["MetricLabel"])],
        [Paragraph(f"{perf_score:.1f}", ParagraphStyle(
            "ScoreVal", fontSize=22, textColor=score_col,
            fontName="Helvetica-Bold", alignment=TA_CENTER))],
        [Paragraph("out of 100", S["MetricUnit"])],
    ]
    score_card = Table(score_card_data, colWidths=[card_width])
    score_card.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), LIGHT_BG),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
    ]))

    kpi_row = Table([[
        score_card,
        make_card("Total Orders",   str(total_orders),            "orders"),
        make_card("Avg Rating",     f"{avg_rating:.1f}",          _star_string(avg_rating)),
        make_card("Delivery Rate",  f"{delivery_rate:.1f}%",      "delivered"),
        make_card("Return Rate",    f"{return_rate:.1f}%",        "returned"),
    ]], colWidths=[card_width]*5, hAlign="LEFT")
    kpi_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
    ]))
    story.append(kpi_row)
    story.append(Spacer(1, 14))

    # ── Score Breakdown Bar ────────────────────────────────────────────────────
    story.append(Paragraph("Performance Score Breakdown", S["SectionHeading"]))

    components = [
        ("Rating (40%)",      (avg_rating / 5.0) * 100 * 0.4,  ACCENT),
        ("Delivery (40%)",    delivery_rate * 0.4,              SUCCESS),
        ("Non-Return (20%)",  (100 - return_rate) * 0.2,       WARNING),
    ]

    bar_rows = []
    for label, contribution, col in components:
        pct = min(contribution / 100.0, 1.0)
        filled  = max(int(pct * 50), 0)
        empty   = 50 - filled
        bar_str = "█" * filled + "░" * empty

        bar_rows.append([
            Paragraph(label, S["Body"]),
            Paragraph(
                f'<font color="#{col.hexval()[1:]}"><b>{bar_str}</b></font>',
                ParagraphStyle("BarFont", fontName="Helvetica", fontSize=8)
            ),
            Paragraph(f"{contribution:.1f} pts", ParagraphStyle(
                "PtsRight", fontSize=9, alignment=TA_RIGHT, textColor=col
            )),
        ])

    bar_table = Table(bar_rows, colWidths=[W*0.25, W*0.55, W*0.20])
    bar_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), LIGHT_BG),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [LIGHT_BG, WHITE]),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("LINEBELOW",    (0,0),(-1,-2), 0.5, colors.HexColor("#dee2e6")),
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#dee2e6")),
    ]))
    story.append(bar_table)
    story.append(Spacer(1, 14))

    # ── Order Summary ─────────────────────────────────────────────────────────
    story.append(Paragraph("Order Summary", S["SectionHeading"]))

    from django.db.models import Sum, Count, Q
    orders_qs = seller.orders.all()

    delivered   = orders_qs.filter(delivery_status="Delivered").count()
    returned    = orders_qs.filter(is_returned=True).count()
    pending     = orders_qs.exclude(delivery_status="Delivered").count()
    total_rev   = orders_qs.aggregate(t=Sum("total_amount"))["t"] or 0.0
    net_rev     = orders_qs.filter(is_returned=False).aggregate(
                      t=Sum("total_amount"))["t"] or 0.0

    order_summary_data = [
        [Paragraph(h, S["TableHeader"]) for h in
         ["Metric", "Value"]],
        ["Total Orders",         str(total_orders)],
        ["Delivered Orders",     str(delivered)],
        ["Pending / Other",      str(pending)],
        ["Returned Orders",      str(returned)],
        ["Total Revenue (Rs.)",  f"{total_rev:,.2f}"],
        ["Net Revenue (Rs.)",    f"{net_rev:,.2f}"],
    ]

    ord_table = Table(order_summary_data, colWidths=[W*0.55, W*0.45])
    ord_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  PRIMARY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [LIGHT_BG, WHITE]),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1),(-1,-1), 9),
        ("TOPPADDING",    (0,0),(-1,-1), 7),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ("ALIGN",         (1,1),(-1,-1), "RIGHT"),
        ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#dee2e6")),
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#dee2e6")),
    ]))
    story.append(ord_table)
    story.append(Spacer(1, 14))

    # ── Recent Orders Table ────────────────────────────────────────────────────
    recent_orders = orders_qs.order_by("-order_date")[:10]
    if recent_orders.exists():
        story.append(Paragraph("Recent Orders (Last 10)", S["SectionHeading"]))

        ro_data = [[Paragraph(h, S["TableHeader"]) for h in
                    ["Order ID", "Date", "Amount (Rs.)", "Status", "Returned"]]]
        for o in recent_orders:
            status_color = SUCCESS if o.delivery_status == "Delivered" else WARNING
            returned_str = "Yes" if o.is_returned else "No"
            ret_color    = DANGER if o.is_returned else SUCCESS
            ro_data.append([
                Paragraph(f"#{o.pk}", S["Body"]),
                Paragraph(str(o.order_date), S["Body"]),
                Paragraph(f"{float(o.total_amount):,.2f}", ParagraphStyle(
                    "Amt", fontSize=9, alignment=TA_RIGHT)),
                Paragraph(
                    f'<font color="#{status_color.hexval()[1:]}">'
                    f'<b>{o.delivery_status}</b></font>', S["Body"]),
                Paragraph(
                    f'<font color="#{ret_color.hexval()[1:]}">'
                    f'<b>{returned_str}</b></font>', S["Body"]),
            ])

        ro_table = Table(ro_data,
                         colWidths=[W*0.12, W*0.20, W*0.22, W*0.26, W*0.20])
        ro_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0),  PRIMARY),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [LIGHT_BG, WHITE]),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#dee2e6")),
            ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ]))
        story.append(ro_table)
        story.append(Spacer(1, 14))

    # ── Reviews & Ratings ─────────────────────────────────────────────────────
    story.append(Paragraph("Reviews &amp; Ratings", S["SectionHeading"]))

    reviews_qs = seller.reviews.all()
    total_reviews = reviews_qs.count()

    # Rating distribution
    dist = {i: reviews_qs.filter(rating=i).count() for i in range(1, 6)}

    rating_dist_data = [[Paragraph(h, S["TableHeader"]) for h in
                          ["Stars", "Count", "Share"]]]
    for stars in range(5, 0, -1):
        count = dist[stars]
        share = (count / total_reviews * 100) if total_reviews else 0
        rating_dist_data.append([
            Paragraph("★" * stars, ParagraphStyle(
                "Stars", fontSize=9, textColor=WARNING)),
            Paragraph(str(count), S["Body"]),
            Paragraph(f"{share:.1f}%", S["Body"]),
        ])
    rating_dist_data.append([
        Paragraph("<b>Total</b>", S["Body"]),
        Paragraph(f"<b>{total_reviews}</b>", S["Body"]),
        Paragraph("<b>100%</b>", S["Body"]),
    ])

    # Recent reviews
    recent_reviews = reviews_qs.order_by("-review_date")[:5]
    rev_rows_data = [[Paragraph(h, S["TableHeader"]) for h in
                      ["Date", "Rating", "Comment"]]]
    for rv in recent_reviews:
        rev_rows_data.append([
            Paragraph(str(rv.review_date), S["Body"]),
            Paragraph("★" * int(rv.rating), ParagraphStyle(
                "RStars", fontSize=9, textColor=WARNING)),
            Paragraph(
                (rv.comment[:120] + "…") if len(rv.comment) > 120 else rv.comment,
                S["Body"]
            ),
        ])

    # Side-by-side: distribution left, recent right
    dist_table = Table(rating_dist_data,
                       colWidths=[W*0.13, W*0.10, W*0.11])
    dist_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  PRIMARY),
        ("ROWBACKGROUNDS",(0,1),(-1,-2), [LIGHT_BG, WHITE]),
        ("BACKGROUND",    (0,-1),(-1,-1), colors.HexColor("#dce6f0")),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("ALIGN",         (1,0),(-1,-1), "CENTER"),
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#dee2e6")),
    ]))

    rev_table = Table(rev_rows_data,
                      colWidths=[W*0.16, W*0.12, W*0.49])
    rev_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  PRIMARY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [LIGHT_BG, WHITE]),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#dee2e6")),
        ("LINEBELOW",     (0,0),(-1,-2), 0.5, colors.HexColor("#dee2e6")),
    ]))

    combined_rev = Table([[dist_table, Spacer(0.3*cm, 1), rev_table]],
                         colWidths=[W*0.36, 0.3*cm, W*0.64 - 0.3*cm])
    combined_rev.setStyle(TableStyle([
        ("VALIGN", (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 0),
        ("RIGHTPADDING", (0,0),(-1,-1), 0),
    ]))
    story.append(combined_rev)
    story.append(Spacer(1, 20))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, color=colors.HexColor("#dee2e6"),
                             thickness=0.8, spaceAfter=6))
    story.append(Paragraph(
        f"Seller Evaluation System &nbsp;|&nbsp; "
        f"Report for <b>{seller.name}</b> &nbsp;|&nbsp; "
        f"Generated on {date.today().strftime('%d %B %Y')} &nbsp;|&nbsp; "
        f"Confidential",
        S["Footer"]
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story)
    buf.seek(0)

    response = HttpResponse(buf, content_type="application/pdf")
    safe_name = seller.name.replace(" ", "_")
    response["Content-Disposition"] = (
        f'attachment; filename="seller_report_{safe_name}_{date.today()}.pdf"'
    )
    return response
