from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from django.conf import settings
import os

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Estilos personalizados
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_LEFT
        )
    
    def generate_invoice_pdf(self, invoice, xml_autorizado=None):
        """Genera el PDF de la factura"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        
        # Header con información de la empresa
        elements.append(self._create_header(invoice))
        elements.append(Spacer(1, 20))
        
        # Información de la factura y cliente
        elements.append(self._create_invoice_info(invoice))
        elements.append(Spacer(1, 20))
        
        # Tabla de detalles
        elements.append(self._create_details_table(invoice))
        elements.append(Spacer(1, 20))
        
        # Totales
        elements.append(self._create_totals_table(invoice))
        elements.append(Spacer(1, 20))
        
        # Información adicional
        if xml_autorizado:
            elements.append(self._create_authorization_info(invoice))
        
        # Footer
        elements.append(self._create_footer(invoice))
        
        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
    
    def _create_header(self, invoice):
        """Crea el header del PDF"""
        data = [
            [invoice.company.razon_social, 'FACTURA'],
            [f'RUC: {invoice.company.ruc}', f'No. {invoice.numero_factura}'],
            [invoice.company.direccion, f'Fecha: {invoice.fecha_emision.strftime("%d/%m/%Y")}'],
            [f'Teléfono: {invoice.company.telefono}', ''],
        ]
        
        table = Table(data, colWidths=[4*inch, 2*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        
        return table
    
    def _create_invoice_info(self, invoice):
        """Crea la información del cliente"""
        data = [
            ['INFORMACIÓN DEL CLIENTE', ''],
            ['Cliente:', invoice.customer.razon_social],
            ['Identificación:', invoice.customer.identificacion],
            ['Dirección:', invoice.customer.direccion or 'N/A'],
            ['Email:', invoice.customer.email or 'N/A'],
            ['Teléfono:', invoice.customer.telefono or 'N/A'],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
            ('SPAN', (0,0), (1,0)),
            ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
        ]))
        
        return table
    
    def _create_details_table(self, invoice):
        """Crea la tabla de detalles de la factura"""
        # Headers
        headers = ['Código', 'Descripción', 'Cant.', 'P. Unit.', 'Desc.', 'Subtotal', 'IVA', 'Total']
        data = [headers]
        
        # Detalles
        for detalle in invoice.invoicedetail_set.all():
            row = [
                detalle.codigo_principal,
                detalle.descripcion,
                str(detalle.cantidad),
                f'${detalle.precio_unitario:.2f}',
                f'${detalle.descuento:.2f}',
                f'${detalle.precio_total_sin_impuesto:.2f}',
                f'${detalle.valor_iva:.2f}',
                f'${detalle.precio_total_sin_impuesto + detalle.valor_iva:.2f}'
            ]
            data.append(row)
        
        table = Table(data, colWidths=[0.8*inch, 2.5*inch, 0.6*inch, 0.8*inch, 0.6*inch, 0.8*inch, 0.6*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        
        return table
    
    def _create_totals_table(self, invoice):
        """Crea la tabla de totales"""
        data = [
            ['Subtotal 0%:', f'${invoice.subtotal_0:.2f}'],
            ['Subtotal 12%:', f'${invoice.subtotal_12:.2f}'],
            ['Subtotal sin impuestos:', f'${invoice.subtotal_sin_impuestos:.2f}'],
            ['IVA 12%:', f'${invoice.valor_iva:.2f}'],
            ['ICE:', f'${invoice.valor_ice:.2f}'],
            ['Propina:', f'${invoice.propina:.2f}'],
            ['TOTAL:', f'${invoice.importe_total:.2f}'],
        ]
        
        table = Table(data, colWidths=[3*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        
        return table
    
    def _create_authorization_info(self, invoice):
        """Crea la información de autorización del SRI"""
        if invoice.numero_autorizacion:
            data = [
                ['AUTORIZACIÓN SRI', ''],
                ['Número de Autorización:', invoice.numero_autorizacion],
                ['Fecha de Autorización:', invoice.fecha_autorizacion.strftime('%d/%m/%Y %H:%M:%S') if invoice.fecha_autorizacion else 'N/A'],
                ['Clave de Acceso:', invoice.clave_acceso],
            ]
            
            table = Table(data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOX', (0,0), (-1,-1), 1, colors.black),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
                ('SPAN', (0,0), (1,0)),
                ('BACKGROUND', (0,0), (1,0), colors.lightgrey),
            ]))
            
            return table
        return Spacer(1, 0)
    
    def _create_footer(self, invoice):
        """Crea el footer del PDF"""
        footer_text = f"Factura generada electrónicamente según la normativa vigente del SRI.\n"
        footer_text += f"Esta factura tiene validez legal y constituye un documento comercial válido."
        
        footer = Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER
        ))
        
        return footer