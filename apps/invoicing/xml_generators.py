from lxml import etree
from datetime import datetime
from decimal import Decimal

class XMLGenerator:
    def __init__(self):
        self.namespaces = {
            None: "http://www.sat.gob.mx/cfd/3",
            'xsi': "http://www.w3.org/2001/XMLSchema-instance"
        }
    
    def generar_xml_factura(self, invoice):
        """Genera el XML de la factura según especificaciones del SRI"""
        
        # Elemento raíz
        factura = etree.Element("factura", 
                               id="comprobante",
                               version="1.1.0")
        
        # Información tributaria
        info_tributaria = etree.SubElement(factura, "infoTributaria")
        
        etree.SubElement(info_tributaria, "ambiente").text = "1" if invoice.company.sri_config.environment == 'test' else "2"
        etree.SubElement(info_tributaria, "tipoEmision").text = "1"
        etree.SubElement(info_tributaria, "razonSocial").text = invoice.company.razon_social
        etree.SubElement(info_tributaria, "nombreComercial").text = invoice.company.nombre_comercial or invoice.company.razon_social
        etree.SubElement(info_tributaria, "ruc").text = invoice.company.ruc
        etree.SubElement(info_tributaria, "claveAcceso").text = invoice.clave_acceso
        etree.SubElement(info_tributaria, "codDoc").text = "01"  # Factura
        etree.SubElement(info_tributaria, "estab").text = invoice.establecimiento
        etree.SubElement(info_tributaria, "ptoEmi").text = invoice.punto_emision
        etree.SubElement(info_tributaria, "secuencial").text = invoice.secuencial
        etree.SubElement(info_tributaria, "dirMatriz").text = invoice.company.direccion
        
        # Información de la factura
        info_factura = etree.SubElement(factura, "infoFactura")
        
        etree.SubElement(info_factura, "fechaEmision").text = invoice.fecha_emision.strftime('%d/%m/%Y')
        etree.SubElement(info_factura, "dirEstablecimiento").text = invoice.company.direccion
        
        if invoice.company.contribuyente_especial:
            etree.SubElement(info_factura, "contribuyenteEspecial").text = invoice.company.contribuyente_especial
        
        etree.SubElement(info_factura, "obligadoContabilidad").text = "SI" if invoice.company.obligado_contabilidad else "NO"
        etree.SubElement(info_factura, "tipoIdentificacionComprador").text = invoice.customer.tipo_identificacion
        etree.SubElement(info_factura, "razonSocialComprador").text = invoice.customer.razon_social
        etree.SubElement(info_factura, "identificacionComprador").text = invoice.customer.identificacion
        
        if invoice.customer.direccion:
            etree.SubElement(info_factura, "direccionComprador").text = invoice.customer.direccion
        
        etree.SubElement(info_factura, "totalSinImpuestos").text = str(invoice.subtotal_sin_impuestos)
        etree.SubElement(info_factura, "totalDescuento").text = "0.00"
        
        # Total con impuestos
        total_con_impuestos = etree.SubElement(info_factura, "totalConImpuestos")
        
        # IVA 0%
        if invoice.subtotal_0 > 0:
            total_impuesto = etree.SubElement(total_con_impuestos, "totalImpuesto")
            etree.SubElement(total_impuesto, "codigo").text = "2"
            etree.SubElement(total_impuesto, "codigoPorcentaje").text = "0"
            etree.SubElement(total_impuesto, "baseImponible").text = str(invoice.subtotal_0)
            etree.SubElement(total_impuesto, "valor").text = "0.00"
        
        # IVA 12%
        if invoice.subtotal_12 > 0:
            total_impuesto = etree.SubElement(total_con_impuestos, "totalImpuesto")
            etree.SubElement(total_impuesto, "codigo").text = "2"
            etree.SubElement(total_impuesto, "codigoPorcentaje").text = "2"
            etree.SubElement(total_impuesto, "baseImponible").text = str(invoice.subtotal_12)
            etree.SubElement(total_impuesto, "valor").text = str(invoice.valor_iva)
        
        etree.SubElement(info_factura, "propina").text = str(invoice.propina)
        etree.SubElement(info_factura, "importeTotal").text = str(invoice.importe_total)
        etree.SubElement(info_factura, "moneda").text = "DOLAR"
        
        # Formas de pago
        pagos = etree.SubElement(info_factura, "pagos")
        for pago in invoice.invoicepayment_set.all():
            pago_element = etree.SubElement(pagos, "pago")
            etree.SubElement(pago_element, "formaPago").text = pago.forma_pago
            etree.SubElement(pago_element, "total").text = str(pago.valor)
            if pago.plazo > 0:
                etree.SubElement(pago_element, "plazo").text = str(pago.plazo)
                etree.SubElement(pago_element, "unidadTiempo").text = pago.unidad_tiempo
        
        # Detalles
        detalles = etree.SubElement(factura, "detalles")
        
        for detalle in invoice.invoicedetail_set.all():
            detalle_element = etree.SubElement(detalles, "detalle")
            
            etree.SubElement(detalle_element, "codigoPrincipal").text = detalle.codigo_principal
            if detalle.codigo_auxiliar:
                etree.SubElement(detalle_element, "codigoAuxiliar").text = detalle.codigo_auxiliar
            
            etree.SubElement(detalle_element, "descripcion").text = detalle.descripcion
            etree.SubElement(detalle_element, "cantidad").text = str(detalle.cantidad)
            etree.SubElement(detalle_element, "precioUnitario").text = str(detalle.precio_unitario)
            etree.SubElement(detalle_element, "descuento").text = str(detalle.descuento)
            etree.SubElement(detalle_element, "precioTotalSinImpuesto").text = str(detalle.precio_total_sin_impuesto)
            
            # Impuestos del detalle
            impuestos = etree.SubElement(detalle_element, "impuestos")
            
            # IVA
            impuesto = etree.SubElement(impuestos, "impuesto")
            etree.SubElement(impuesto, "codigo").text = "2"
            codigo_porcentaje = "0" if detalle.porcentaje_iva == 0 else "2"
            etree.SubElement(impuesto, "codigoPorcentaje").text = codigo_porcentaje
            etree.SubElement(impuesto, "tarifa").text = str(detalle.porcentaje_iva)
            etree.SubElement(impuesto, "baseImponible").text = str(detalle.precio_total_sin_impuesto)
            etree.SubElement(impuesto, "valor").text = str(detalle.valor_iva)
            
            # ICE (si aplica)
            if detalle.porcentaje_ice > 0:
                impuesto_ice = etree.SubElement(impuestos, "impuesto")
                etree.SubElement(impuesto_ice, "codigo").text = "3"
                etree.SubElement(impuesto_ice, "codigoPorcentaje").text = "3"
                etree.SubElement(impuesto_ice, "tarifa").text = str(detalle.porcentaje_ice)
                etree.SubElement(impuesto_ice, "baseImponible").text = str(detalle.precio_total_sin_impuesto)
                etree.SubElement(impuesto_ice, "valor").text = str(detalle.valor_ice)
        
        # Información adicional
        info_adicional = etree.SubElement(factura, "infoAdicional")
        
        if invoice.customer.email:
            campo_adicional = etree.SubElement(info_adicional, "campoAdicional", nombre="Email")
            campo_adicional.text = invoice.customer.email
        
        if invoice.customer.telefono:
            campo_adicional = etree.SubElement(info_adicional, "campoAdicional", nombre="Teléfono")
            campo_adicional.text = invoice.customer.telefono
        
        if invoice.observaciones:
            campo_adicional = etree.SubElement(info_adicional, "campoAdicional", nombre="Observaciones")
            campo_adicional.text = invoice.observaciones
        
        # Convertir a string XML
        xml_string = etree.tostring(factura, 
                                   pretty_print=True, 
                                   xml_declaration=True, 
                                   encoding='UTF-8').decode('utf-8')
        
        return xml_string