import io
import logging
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from services import supabase_service

logger = logging.getLogger(__name__)

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
        [Paragraph("Document Type", body_style), Paragraph(ewb_dict.get("document_type", ""), body_style),
         Paragraph("Transaction Type", body_style), Paragraph(ewb_dict.get("transaction_type", ""), body_style)],
        [Paragraph("Scheduled Date", body_style), Paragraph(ewb_dict.get("scheduled_date", ""), body_style),
         Paragraph("Shipment ID", body_style), Paragraph(str(shipment_id), body_style)]
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
                f"<b>{ewb_dict.get('consignor_name', '')}</b><br/>"
                f"GSTIN: {ewb_dict.get('consignor_gstin', '')}<br/>"
                f"Address: {ewb_dict.get('consignor_address', '')}", 
                body_style
            ),
            Paragraph(
                f"<b>{ewb_dict.get('consignee_name', '')}</b><br/>"
                f"GSTIN: {ewb_dict.get('consignee_gstin', '')}<br/>"
                f"Address: {ewb_dict.get('consignee_address', '')}", 
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
            Paragraph(ewb_dict.get("cargo_description", ""), body_style),
            Paragraph(ewb_dict.get("hsn_code", ""), body_style),
            Paragraph(f"{ewb_dict.get('weight_tons', 0.0):.2f}", body_style),
            Paragraph(f"Rs. {ewb_dict.get('cargo_value_inr', 0):,}", body_style)
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
        [Paragraph("Vehicle Number", body_style), Paragraph(ewb_dict.get("truck_number", ""), body_style),
         Paragraph("Place of Origin", body_style), Paragraph(ewb_dict.get("origin_place", ""), body_style)],
        [Paragraph("Driver Name", body_style), Paragraph(ewb_dict.get("driver_name", ""), body_style),
         Paragraph("Place of Destination", body_style), Paragraph(ewb_dict.get("destination_place", ""), body_style)],
        [Paragraph("Driver Phone", body_style), Paragraph(ewb_dict.get("driver_phone", ""), body_style),
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
        canvas.drawCentredString(0, 0, "DRAFT - NOT OFFICIAL EWB")
        canvas.restoreState()
        
    doc.build(story, onFirstPage=add_watermark)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Upload to Supabase and get URL
    pdf_url = supabase_service.upload_ewb_pdf_bytes(shipment_id, pdf_bytes)
    return pdf_url
