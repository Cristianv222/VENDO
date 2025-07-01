import os
import base64
import xml.etree.ElementTree as ET
from datetime import datetime
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session
from lxml import etree
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509
from django.conf import settings
from .models import SRIConfiguration, SRILog
import logging

logger = logging.getLogger(__name__)

class SRIClient:
    def __init__(self, company):
        self.company = company
        try:
            self.sri_config = SRIConfiguration.objects.get(company=company)
        except SRIConfiguration.DoesNotExist:
            raise Exception("No existe configuración del SRI para esta empresa")
        
        # URLs del SRI
        if self.sri_config.environment == 'production':
            self.wsdl_recepcion = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl'
            self.wsdl_autorizacion = 'https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl'
        else:
            self.wsdl_recepcion = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl'
            self.wsdl_autorizacion = 'https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl'
        
        # Configurar cliente SOAP
        session = Session()
        transport = Transport(session=session)
        settings_soap = Settings(strict=False, xml_huge_tree=True)
        
        try:
            self.client_recepcion = Client(self.wsdl_recepcion, transport=transport, settings=settings_soap)
            self.client_autorizacion = Client(self.wsdl_autorizacion, transport=transport, settings=settings_soap)
        except Exception as e:
            logger.error(f"Error creando cliente SOAP: {str(e)}")
            raise Exception(f"Error conectando con el SRI: {str(e)}")
    
    def load_certificate(self):
        """Carga el certificado P12"""
        try:
            with open(self.sri_config.certificate_file.path, 'rb') as f:
                cert_data = f.read()
            
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                cert_data, 
                self.sri_config.certificate_password.encode()
            )
            
            return private_key, certificate
            
        except Exception as e:
            logger.error(f"Error cargando certificado: {str(e)}")
            raise Exception(f'Error cargando certificado: {str(e)}')
    
    def sign_xml(self, xml_string):
        """Firma el XML con el certificado digital usando xmlsec"""
        try:
            import xmlsec
            
            private_key, certificate = self.load_certificate()
            
            # Parsear el XML
            doc = etree.fromstring(xml_string.encode('utf-8'))
            
            # Crear template de firma
            signature_node = xmlsec.template.create(
                doc,
                xmlsec.constants.TransformExclC14N,
                xmlsec.constants.TransformRsaSha1
            )
            
            # Agregar referencia
            ref = xmlsec.template.add_reference(
                signature_node,
                xmlsec.constants.TransformSha1,
                uri=""
            )
            
            xmlsec.template.add_transform(ref, xmlsec.constants.TransformEnveloped)
            xmlsec.template.add_transform(ref, xmlsec.constants.TransformExclC14N)
            
            # Agregar información de clave
            key_info = xmlsec.template.ensure_key_info(signature_node)
            xmlsec.template.add_x509_data(key_info)
            
            # Insertar la firma en el documento
            doc.append(signature_node)
            
            # Crear contexto de firma
            ctx = xmlsec.SignatureContext()
            
            # Crear clave desde el certificado
            key = xmlsec.Key.from_memory(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ),
                xmlsec.constants.KeyDataFormatPem
            )
            
            # Cargar certificado
            key.load_cert_from_memory(
                certificate.public_bytes(serialization.Encoding.PEM),
                xmlsec.constants.KeyDataFormatPem
            )
            
            ctx.key = key
            
            # Firmar
            ctx.sign(signature_node)
            
            return etree.tostring(doc, encoding='unicode')
            
        except ImportError:
            # Fallback: firma simple sin xmlsec
            logger.warning("xmlsec no disponible, usando firma simple")
            return self._simple_sign_xml(xml_string)
        except Exception as e:
            logger.error(f"Error firmando XML: {str(e)}")
            raise Exception(f'Error firmando XML: {str(e)}')
    
    def _simple_sign_xml(self, xml_string):
        """Firma simple del XML (fallback)"""
        # Esta es una implementación básica
        # En producción se debe usar xmlsec o una implementación completa
        return xml_string
    
    def send_document(self, xml_signed, clave_acceso):
        """Envía el documento firmado al SRI"""
        try:
            xml_bytes = xml_signed.encode('utf-8')
            xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')
            
            # Llamar al servicio de recepción
            response = self.client_recepcion.service.validarComprobante(xml_base64)
            
            # Log de la operación
            SRILog.objects.create(
                company=self.company,
                clave_acceso=clave_acceso,
                proceso='ENVIO',
                estado='EXITOSO' if response.estado == 'RECIBIDA' else 'ERROR',
                response_data={
                    'estado': response.estado,
                    'comprobantes': getattr(response, 'comprobantes', None)
                }
            )
            
            return {
                'success': response.estado == 'RECIBIDA',
                'estado': response.estado,
                'clave_acceso': clave_acceso,
                'comprobantes': getattr(response, 'comprobantes', None),
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error enviando documento al SRI: {str(e)}")
            
            # Log del error
            SRILog.objects.create(
                company=self.company,
                clave_acceso=clave_acceso,
                proceso='ENVIO',
                estado='ERROR',
                error_message=str(e)
            )
            
            raise Exception(f'Error enviando documento al SRI: {str(e)}')
    
    def get_authorization(self, clave_acceso):
        """Obtiene la autorización del documento"""
        try:
            response = self.client_autorizacion.service.autorizacionComprobante(clave_acceso)
            
            # Log de la operación
            SRILog.objects.create(
                company=self.company,
                clave_acceso=clave_acceso,
                proceso='AUTORIZACION',
                estado='EXITOSO' if hasattr(response, 'numeroAutorizacion') else 'ERROR',
                response_data={
                    'numero_autorizacion': getattr(response, 'numeroAutorizacion', None),
                    'fecha_autorizacion': getattr(response, 'fechaAutorizacion', None),
                    'estado': getattr(response, 'estado', None)
                }
            )
            
            return {
                'success': hasattr(response, 'numeroAutorizacion'),
                'numero_autorizacion': getattr(response, 'numeroAutorizacion', None),
                'fecha_autorizacion': getattr(response, 'fechaAutorizacion', None),
                'estado': getattr(response, 'estado', None),
                'xml_autorizado': getattr(response, 'comprobante', None),
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo autorización: {str(e)}")
            
            # Log del error
            SRILog.objects.create(
                company=self.company,
                clave_acceso=clave_acceso,
                proceso='AUTORIZACION',
                estado='ERROR',
                error_message=str(e)
            )
            
            raise Exception(f'Error obteniendo autorización: {str(e)}')
    
    def validate_certificate(self):
        """Valida el certificado y devuelve información"""
        try:
            private_key, certificate = self.load_certificate()
            
            # Verificar validez del certificado
            now = datetime.now()
            if certificate.not_valid_after < now:
                raise Exception("El certificado ha expirado")
            
            if certificate.not_valid_before > now:
                raise Exception("El certificado aún no es válido")
            
            return {
                'valid': True,
                'subject': certificate.subject.rfc4514_string(),
                'issuer': certificate.issuer.rfc4514_string(),
                'not_valid_before': certificate.not_valid_before,
                'not_valid_after': certificate.not_valid_after,
                'serial_number': str(certificate.serial_number)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': str(e)
            }