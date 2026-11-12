"""Flujo del caso entre Operaciones, Mantenimiento, Seguridad Vial y RRLL.

Decide cuándo un caso necesita a Relaciones Laborales, qué procesos quedan
pendientes por decisión de RRLL, cuándo el caso se cierra solo y en qué estado
lo ve RRLL en su exportación.
"""
from modelos import casos as modelo_casos

PROCESOS_PENDIENTES_RRLL = (
    "MANTENIMIENTO",
    "OPERACIONES",
    "SEGURIDAD VIAL",
    "COMITE",
    "COMPLETO",
)


def normalizar_procesos_pendientes(valor, validar=True):
    """Normaliza la selección múltiple de Pendiente_proceso y valida COMPLETO."""
    procesos = {
        parte.strip().upper()
        for parte in (valor or "").split(",")
        if parte.strip()
    }
    if validar:
        desconocidos = procesos.difference(PROCESOS_PENDIENTES_RRLL)
        if desconocidos:
            raise ValueError("El proceso pendiente seleccionado no es válido.")
        if "COMPLETO" in procesos and len(procesos) > 1:
            raise ValueError("COMPLETO no puede combinarse con otros procesos pendientes.")

    return ", ".join(proceso for proceso in PROCESOS_PENDIENTES_RRLL if proceso in procesos), procesos


def caso_en_comite(pendiente_proceso, caso_cerrado=False):
    """El estado de comite depende del ultimo seguimiento de un caso abierto."""
    _, procesos = normalizar_procesos_pendientes(pendiente_proceso, validar=False)
    return not caso_cerrado and "COMITE" in procesos


def evento_pendiente_para_modulo(evento, modulo):
    """Indica si un evento RRLL debe mostrarse al módulo pendiente indicado."""
    proceso_modulo = {
        "Operaciones": "OPERACIONES",
        "Mtto": "MANTENIMIENTO",
        "Svial": "SEGURIDAD VIAL",
    }.get(modulo)
    if not proceso_modulo:
        return False

    _, procesos = normalizar_procesos_pendientes(
        evento.get("Pendiente_proceso"), validar=False
    )
    return proceso_modulo in procesos


def requiere_relaciones_laborales(responsabilidad, conciliacion):
    return not (
        responsabilidad == "NO APLICA"
        or (responsabilidad == "SI" and conciliacion == "SI")
    )


def cerrar_caso_automaticamente(cursor, codigo, usuario, permitir_cierre=True):
    """Cierra el caso cuando hayan finalizado todas las gestiones requeridas."""
    fila = modelo_casos.buscar_estado_de_gestiones(cursor, codigo)
    if not fila:
        return

    responsabilidad, conciliacion, estado_oper, estado_mtto, estado_svial, tiene_ot, estado_laboral = fila
    gestiones_iniciales_completas = estado_oper == 1 and estado_mtto == 1 and estado_svial == 1
    if not gestiones_iniciales_completas:
        return

    # Solo estos dos desenlaces terminan en Operaciones. Los demás llegan
    # a Relaciones Laborales: costo > $2M, no aceptación, no conciliación
    # o reincidencia (la conciliación queda vacía por la regla vigente).
    requiere_laboral = requiere_relaciones_laborales(responsabilidad, conciliacion)
    if requiere_laboral and not tiene_ot:
        modelo_casos.marcar_mantenimiento_pendiente_de_ot(cursor, codigo)
        return
    if not permitir_cierre:
        return
    puede_cerrar = not requiere_laboral or estado_laboral == 1
    if not puede_cerrar:
        return
    modelo_casos.marcar_caso_cerrado(cursor, codigo)


def estado_rrll_para_exportacion(registro):
    """PENDIENTE, GESTIONADO o CERRADO según las gestiones del caso; None si el
    caso no le corresponde a RRLL."""
    caso_cerrado = bool(registro.get("estado_caso"))
    cerrado_por_laboral = bool(registro.get("cerrado_por_laboral"))

    estado_oper = bool(registro.get("estado_oper"))
    estado_mtto = bool(registro.get("estado_mtto"))
    estado_svial = bool(registro.get("estado_svial"))
    tiene_ot = bool(registro.get("tiene_ot"))

    pendiente_proceso = str(
        registro.get("pendiente_proceso_actual") or ""
    ).strip().upper()

    # =========================
    # CERRADOS
    # =========================
    if caso_cerrado and cerrado_por_laboral:
        return "CERRADO"

    if caso_en_comite(pendiente_proceso, caso_cerrado):
        return "COMITE"

    # =========================
    # GESTIONADOS
    # =========================
    if (
        not caso_cerrado
        and estado_oper
        and estado_mtto
        and estado_svial
        and pendiente_proceso == "COMPLETO"
    ):
        return "GESTIONADO"

    # =========================
    # PENDIENTES
    # =========================
    if (
        not caso_cerrado
        and estado_oper
        and estado_mtto
        and estado_svial
        and tiene_ot
        and pendiente_proceso != "COMPLETO"
    ):
        return "PENDIENTE"

    # Si no cumple ninguna condición de RRLL,
    # no debe aparecer en la exportación.
    return None
