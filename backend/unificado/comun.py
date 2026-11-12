"""Utilidades de los controladores del módulo unificado (sin SQL).

Acceso al módulo, configuración pública para el navegador, validación de
adjuntos y lectura de valores en pesos.
"""
from flask import abort, jsonify, request, session

from attachment_security import AttachmentValidationError, validate_uploads
from unificado.configuracion import MODULOS
from servicios.montos import leer_valor_monetario as leer_valor_monetario


def validar_adjuntos_de_solicitud():
    try:
        validate_uploads(request.files.getlist("archivos"))
    except AttachmentValidationError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    return None


def config_publica_modulo(modulo):
    """Config del módulo, apta para mandar al frontend como JSON."""
    cfg = MODULOS[modulo]
    return {
        "modulo": modulo,
        "titulo": cfg["titulo"],
        "tipo": cfg["tipo"],
        "campoPrincipalLabel": cfg["campo_principal_label"],
        "propia": cfg["propia"],
        "seccionesVisibles": cfg["secciones_visibles"],
        "mostrarRevision": cfg["mostrar_revision"],
        "mostrarObservaciones": cfg["mostrar_observaciones"],
        "puedeReabrirCaso": {
            "Operaciones": "Reabrir_caso_oper",
            "laboral": "Reabrir_caso_rr_ll",
        }.get(modulo) in session.get("permisos", []),
    }


def verificar_acceso_modulo(modulo):
 
    if modulo not in MODULOS:
        abort(404)

    permisos = session.get("permisos", [])
    permiso_requerido = MODULOS[modulo]["permiso"]

    if permiso_requerido not in permisos:
        abort(403)
