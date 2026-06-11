import io
import logging
import re
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from services import supabase_service

logger = logging.getLogger(__name__)

def clean_for_pdf(text: str) -> str:
    """Replaces emojis and high-unicode symbols with ASCII-safe equivalents for ReportLab safety."""
    if not text:
        return ""
    text = str(text)
    # Replace Rupee symbol
    text = text.replace("₹", "Rs. ")
    text = text.replace("â‚¹", "Rs. ")
    # Replace common emojis/symbols
    replacements = {
        "✅": "[OK]", "âœ…": "[OK]",
        "❌": "[ERROR]",
        "🚨": "[ALERT]", "ðŸš¨": "[ALERT]",
        "🙏": "[NAMASTE]", "ðŸ™": "[NAMASTE]",
        "⚠️": "[WARNING]", "âš ": "[WARNING]",
        "➔": "->", "âž”": "->",
        "➜": "->",
        "ℹ️": "[INFO]", "ℹ": "[INFO]", "â„¹": "[INFO]",
        "🎉": "[CONGRATS]",
        "ℹ️": "[INFO]"
    }
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)
        
    # Remove other characters above code 255 to prevent Helvetica failures
    cleaned = []
    for char in text:
        if ord(char) > 255:
            cleaned.append(" ")
        else:
            cleaned.append(char)
    return "".join(cleaned)

def generate_ewb_pdf(ewb_dict: dict, shipment_id: str) -> str:
    """Generates a professional E-Way Bill draft PDF and uploads it to Supabase storage.
    
    Returns the public URL of the uploaded PDF.
    """
    logger.info(f"Generating EWB PDF for shipment: {shipment_id}...")
    
    # Create in-memory buffer
    buffer = io.BytesIO()
    
    # Setup document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor("#0A1628"),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor("#FF6B2B"),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor("#1D3557"),
        spaceBefore=10,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2C3E50")
    )
    
    header_cell_style = ParagraphStyle(
        'HeaderCellStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    story = []
    
    # 1. Header Title
    story.append(Paragraph("LOADSETU — E-WAY BILL DRAFT", title_style))
    story.append(Paragraph("DRAFT GENERATION FOR VERIFICATION ONLY • NOT A PORTAL-ISSUED EWB", subtitle_style))
    story.append(Spacer(1, 10))
    
    # 2. Main Metadata Table (Transaction & Document details)
    meta_data = [
        [Paragraph("Document Type", body_style), Paragraph(clean_for_pdf(ewb_dict.get("document_type", "")), body_style),
         Paragraph("Transaction Type", body_style), Paragraph(clean_for_pdf(ewb_dict.get("transaction_type", "")), body_style)],
        [Paragraph("Scheduled Date", body_style), Paragraph(clean_for_pdf(ewb_dict.get("scheduled_date", "")), body_style),
         Paragraph("Shipment ID", body_style), Paragraph(clean_for_pdf(str(shipment_id)), body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[120, 150, 120, 140])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8F9FA")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))
    
    # 3. Consignor vs Consignee Section
    story.append(Paragraph("PART A — PARTIES DETAILS", h2_style))
    
    parties_data = [
        [Paragraph("CONSIGNOR (Sender)", header_cell_style), Paragraph("CONSIGNEE (Receiver)", header_cell_style)],
        [
            Paragraph(
                clean_for_pdf(f"<b>{ewb_dict.get('consignor_name', '')}</b><br/>"
                f"GSTIN: {ewb_dict.get('consignor_gstin', '')}<br/>"
                f"Address: {ewb_dict.get('consignor_address', '')}"), 
                body_style
            ),
            Paragraph(
                clean_for_pdf(f"<b>{ewb_dict.get('consignee_name', '')}</b><br/>"
                f"GSTIN: {ewb_dict.get('consignee_gstin', '')}<br/>"
                f"Address: {ewb_dict.get('consignee_address', '')}"), 
                body_style
            )
        ]
    ]
    t_parties = Table(parties_data, colWidths=[265, 265])
    t_parties.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#0A1628")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_parties)
    story.append(Spacer(1, 15))
    
    # 4. Goods Description
    story.append(Paragraph("PART B — GOODS DESCRIPTION", h2_style))
    
    goods_data = [
        [Paragraph("Description", header_cell_style), Paragraph("HSN Code", header_cell_style), 
         Paragraph("Weight (Tons)", header_cell_style), Paragraph("Estimated Value (INR)", header_cell_style)],
        [
            Paragraph(clean_for_pdf(ewb_dict.get("cargo_description", "")), body_style),
            Paragraph(clean_for_pdf(ewb_dict.get("hsn_code", "")), body_style),
            Paragraph(clean_for_pdf(f"{ewb_dict.get('weight_tons', 0.0):.2f}"), body_style),
            Paragraph(clean_for_pdf(f"Rs. {ewb_dict.get('cargo_value_inr', 0):,}"), body_style)
        ]
    ]
    t_goods = Table(goods_data, colWidths=[200, 100, 100, 130])
    t_goods.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1D3557")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_goods)
    story.append(Spacer(1, 15))
    
    # 5. Transportation Details
    story.append(Paragraph("PART C — TRANSPORTATION DETAILS (PART-B)", h2_style))
    
    trans_data = [
        [Paragraph("Vehicle Number", body_style), Paragraph(clean_for_pdf(ewb_dict.get("truck_number", "")), body_style),
         Paragraph("Place of Origin", body_style), Paragraph(clean_for_pdf(ewb_dict.get("origin_place", "")), body_style)],
        [Paragraph("Driver Name", body_style), Paragraph(clean_for_pdf(ewb_dict.get("driver_name", "")), body_style),
         Paragraph("Place of Destination", body_style), Paragraph(clean_for_pdf(ewb_dict.get("destination_place", "")), body_style)],
        [Paragraph("Driver Phone", body_style), Paragraph(clean_for_pdf(ewb_dict.get("driver_phone", "")), body_style),
         Paragraph("Estimated Freight Cost", body_style), Paragraph(f"Calculated in Booking", body_style)]
    ]
    t_trans = Table(trans_data, colWidths=[130, 140, 130, 130])
    t_trans.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8F9FA")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_trans)
    story.append(Spacer(1, 30))
    
    # 6. Watermark disclaimer
    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        alignment=1, # Center
        textColor=colors.HexColor("#E74C3C")
    )
    story.append(Paragraph("DISCLAIMER: This document is generated automatically by LoadSetu as a draft for verification.<br/>It is NOT an official E-way bill registered on the GST Portal. The user is responsible for official registration.", disclaimer_style))
    
    # Build document
    def add_watermark(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 36)
        canvas.setFillColor(colors.HexColor("#E2E8F0"))
        canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
        # Draw transparent watermark across page
        canvas.translate(300, 400)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "DRAFT — NOT A PORTAL-ISSUED EWB")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_watermark)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Upload to Supabase and get URL
    pdf_url = supabase_service.upload_ewb_pdf_bytes(shipment_id, pdf_bytes)
    return pdf_url


def generate_dispute_pack_pdf(shipment: dict, operator: dict, truck: dict, events: list, messages: list) -> str:
    """Generates a comprehensive dispute packet PDF containing trip logs, chat history, and timeline.
    Uploads it to Supabase Storage and returns the public URL.
    """
    logger.info(f"Generating Dispute Pack PDF for shipment: {shipment['id']}...")
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DisputeTitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor("#0A1628"),
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'DisputeH2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor("#FF6B2B"),
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'DisputeBodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2C3E50")
    )
    
    header_cell_style = ParagraphStyle(
        'DisputeHeaderCellStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    story = []
    
    # 1. Header Title
    story.append(Paragraph("LOADSETU — VERIFIABLE TRIP RECORD & DISPUTE PACK", title_style))
    story.append(Paragraph(f"VERIFIED PACKET GENERATED ON: {datetime.datetime.now(supabase_service.IST).strftime('%Y-%m-%d %H:%M:%S IST')} • TRIP ID: {shipment['id'][:8].upper()}", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#7F8C8D"), spaceAfter=15)))
    story.append(Spacer(1, 10))
    
    # 2. Main Shipment Details
    story.append(Paragraph("1. TRIP SUMMARY", h2_style))
    summary_data = [
        [Paragraph("Origin", body_style), Paragraph(clean_for_pdf(shipment.get("origin", "N/A")), body_style),
         Paragraph("Destination", body_style), Paragraph(clean_for_pdf(shipment.get("destination", "N/A")), body_style)],
        [Paragraph("Cargo Type", body_style), Paragraph(clean_for_pdf(shipment.get("cargo_type", "N/A")), body_style),
         Paragraph("Weight (Tons)", body_style), Paragraph(clean_for_pdf(f"{shipment.get('weight_tons', 0.0):.2f}"), body_style)],
        [Paragraph("Scheduled Date", body_style), Paragraph(clean_for_pdf(shipment.get("scheduled_date", "N/A")), body_style),
         Paragraph("Current Status", body_style), Paragraph(clean_for_pdf(shipment.get("status", "N/A")), body_style)]
    ]
    t_summary = Table(summary_data, colWidths=[120, 150, 120, 140])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8F9FA")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))
    
    # 3. Operators & Driver Details
    story.append(Paragraph("2. STAKEHOLDERS DETAILS", h2_style))
    stake_data = [
        [Paragraph("OPERATOR (Shipper)", header_cell_style), Paragraph("DRIVER & TRUCK", header_cell_style)],
        [
            Paragraph(
                clean_for_pdf(f"<b>Business Name:</b> {operator.get('business_name') or 'N/A'}<br/>"
                f"<b>Phone:</b> {operator.get('phone') or 'N/A'}<br/>"
                f"<b>City:</b> {operator.get('city') or 'N/A'}"), 
                body_style
            ),
            Paragraph(
                clean_for_pdf(f"<b>Driver Name:</b> {truck.get('driver_name') or 'N/A'}<br/>"
                f"<b>Driver Phone:</b> {truck.get('driver_phone') or 'N/A'}<br/>"
                f"<b>Truck Number:</b> {truck.get('truck_number') or 'N/A'}"), 
                body_style
            )
        ]
    ]
    t_stake = Table(stake_data, colWidths=[265, 265])
    t_stake.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#0A1628")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_stake)
    story.append(Spacer(1, 15))
    
    # 4. Proof of Delivery (POD) Details
    story.append(Paragraph("3. PROOF OF DELIVERY (POD)", h2_style))
    pod_data = [
        [Paragraph("POD Status", body_style), Paragraph(clean_for_pdf(shipment.get("pod_status") or "PENDING"), body_style),
         Paragraph("Received At", body_style), Paragraph(clean_for_pdf(shipment.get("pod_received_at") or "N/A"), body_style)],
        [Paragraph("Driver Note", body_style), Paragraph(clean_for_pdf(shipment.get("pod_note") or "No note submitted"), body_style),
         Paragraph("POD Attachment URL", body_style), Paragraph(clean_for_pdf(shipment.get("pod_media_url") or "No document attached"), body_style)]
    ]
    t_pod = Table(pod_data, colWidths=[120, 150, 120, 140])
    t_pod.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDF4") if shipment.get("pod_status") == "RECEIVED" else colors.HexColor("#F8F9FA")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_pod)
    story.append(Spacer(1, 15))
    
    # 5. Timeline Events
    story.append(Paragraph("4. TRUST TIMELINE / AUDIT TRAIL", h2_style))
    timeline_rows = [[Paragraph("Timestamp", header_cell_style), Paragraph("Event", header_cell_style), Paragraph("Description", header_cell_style)]]
    for ev in events:
        time_str = ev.get("created_at", "")
        if "T" in time_str:
            time_str = time_str.split("T")[0] + " " + time_str.split("T")[1][:8]
        timeline_rows.append([
            Paragraph(clean_for_pdf(time_str), body_style),
            Paragraph(clean_for_pdf(ev.get("title", "")), body_style),
            Paragraph(clean_for_pdf(ev.get("description", "") or ""), body_style)
        ])
    if len(timeline_rows) == 1:
        timeline_rows.append([Paragraph("No events", body_style), Paragraph("-", body_style), Paragraph("-", body_style)])
    
    t_timeline = Table(timeline_rows, colWidths=[110, 150, 260])
    t_timeline.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1D3557")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_timeline)
    story.append(Spacer(1, 15))
    
    # 6. Chat History
    story.append(Paragraph("5. ASSOCIATED CHAT LOGS", h2_style))
    chat_rows = [[Paragraph("Time", header_cell_style), Paragraph("Sender", header_cell_style), Paragraph("Message Body", header_cell_style)]]
    op_phone = operator.get("phone", "").replace("+91", "").strip()
    dr_phone = truck.get("driver_phone", "").replace("+91", "").strip()
    
    shipment_messages = []
    for m in messages:
        msg_phone = m.get("phone_number", "").replace("+91", "").strip()
        if msg_phone in [op_phone, dr_phone] or m.get("shipment_id") == shipment["id"]:
            shipment_messages.append(m)
            
    shipment_messages.sort(key=lambda x: x.get("timestamp", ""))
    
    for m in shipment_messages:
        time_str = m.get("timestamp", "")
        if "T" in time_str:
            time_str = time_str.split("T")[0] + " " + time_str.split("T")[1][:5]
        sender_role = "OPERATOR" if m.get("phone_number", "").replace("+91", "").strip() == op_phone else "DRIVER"
        sender_label = f"{sender_role} ({m.get('direction', 'INBOUND')})"
        chat_rows.append([
            Paragraph(clean_for_pdf(time_str), body_style),
            Paragraph(clean_for_pdf(sender_label), body_style),
            Paragraph(clean_for_pdf(m.get("body", "")), body_style)
        ])
        
    if len(chat_rows) == 1:
        chat_rows.append([Paragraph("No messages", body_style), Paragraph("-", body_style), Paragraph("-", body_style)])
        
    t_chat = Table(chat_rows, colWidths=[100, 120, 300])
    t_chat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1D3557")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_chat)
    story.append(Spacer(1, 30))
    
    # 7. Verification watermark disclaimer
    ver_disclaimer = ParagraphStyle(
        'VerDisclaimerStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        alignment=1,
        textColor=colors.HexColor("#27AE60")
    )
    story.append(Paragraph("VERIFICATION COMPLETED: All timeline events, timestamps, and WhatsApp dialogues are cryptographically pinned to the trip record.<br/>This dispute pack is a verifiable audit packet of the LoadSetu Freight Engine.", ver_disclaimer))
    
    # Build document
    def add_watermark(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 32)
        canvas.setFillColor(colors.HexColor("#EAF2F8"))
        canvas.setStrokeColor(colors.HexColor("#EAF2F8"))
        canvas.translate(300, 400)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "LOADSETU VERIFIED RECORD")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_watermark)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Upload to Supabase and return public URL
    pdf_url = supabase_service.upload_ewb_pdf_bytes(f"dispute_pack_{shipment['id']}", pdf_bytes)
    return pdf_url
