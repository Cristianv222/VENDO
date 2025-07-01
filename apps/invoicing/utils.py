from datetime import datetime
import random

def generar_clave_acceso(fecha_emision, tipo_comprobante, ruc, ambiente, establecimiento, punto_emision, secuencial, codigo_numerico=None):
    """
    Genera la clave de acceso de 49 dígitos según especificaciones del SRI
    """
    # Fecha en formato ddmmaaaa
    fecha_str = fecha_emision.strftime('%d%m%Y')
    
    # Código numérico aleatorio de 8 dígitos si no se proporciona
    if codigo_numerico is None:
        codigo_numerico = str(random.randint(10000000, 99999999))
    else:
        codigo_numerico = str(codigo_numerico).zfill(8)
    
    # Tipo de emisión (1 = Normal)
    tipo_emision = '1'
    
    # Construir clave sin dígito verificador
    clave_sin_verificador = (
        fecha_str +                    # 8 dígitos
        tipo_comprobante +             # 2 dígitos
        ruc +                         # 13 dígitos
        ambiente +                    # 1 dígito
        establecimiento +             # 3 dígitos
        punto_emision +               # 3 dígitos
        secuencial.zfill(9) +         # 9 dígitos
        codigo_numerico +             # 8 dígitos
        tipo_emision                  # 1 dígito
    )
    
    # Calcular dígito verificador
    digito_verificador = calcular_digito_verificador(clave_sin_verificador)
    
    # Clave completa de 49 dígitos
    clave_acceso = clave_sin_verificador + str(digito_verificador)
    
    return clave_acceso

def calcular_digito_verificador(clave):
    """
    Calcula el dígito verificador usando el algoritmo módulo 11
    """
    factor = 2
    suma = 0
    
    # Recorrer de derecha a izquierda
    for i in range(len(clave) - 1, -1, -1):
        suma += int(clave[i]) * factor
        factor += 1
        if factor > 7:
            factor = 2
    
    residuo = suma % 11
    
    if residuo == 0:
        return 0
    elif residuo == 1:
        return 1
    else:
        return 11 - residuo

def generar_numero_factura(establecimiento, punto_emision, secuencial):
    """Genera el número de factura en formato 001-001-000000001"""
    return f"{establecimiento}-{punto_emision}-{str(secuencial).zfill(9)}"

def obtener_siguiente_secuencial(company, establecimiento='001', punto_emision='001'):
    """Obtiene el siguiente secuencial para una empresa"""
    from .models import Invoice
    
    ultimo_secuencial = Invoice.objects.filter(
        company=company,
        establecimiento=establecimiento,
        punto_emision=punto_emision
    ).order_by('-secuencial').first()
    
    if ultimo_secuencial:
        return str(int(ultimo_secuencial.secuencial) + 1).zfill(9)
    else:
        return '000000001'