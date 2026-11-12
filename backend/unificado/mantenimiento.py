"""Mantenimiento: registro de su gestión (costo, daño adicional, observaciones).

La ruta es la genérica "/Mtto/agregar_mtto" de gestiones.py, que abre la
conexión, valida y guarda los adjuntos; aquí solo va lo propio de Mantenimiento.
"""
from modelos import mantenimiento as modelo_mantenimiento
from servicios.flujo_caso import requiere_relaciones_laborales


def registrar_gestion(cursor, id_registro, valores, auditar_cambio):
    """valores: [id, Costo, dano_adicional, observaciones, usuario] (CONFIG_GESTIONES)."""
    # Mantenimiento puede tener un costo preliminar registrado por
    # Operaciones. En ese caso se completa la misma fila y se marca la
    # gestión, en vez de intentar crear un duplicado.
    if modelo_mantenimiento.existe_gestion(cursor, id_registro):
        anterior = modelo_mantenimiento.buscar_gestion(cursor, id_registro)
        for campo, viejo, nuevo in zip(("costo", "dano_adicional", "observaciones"), anterior, valores[1:4]):
            auditar_cambio(modelo_mantenimiento.TABLA, campo, viejo, nuevo)
        modelo_mantenimiento.actualizar_gestion(
            cursor, id_registro, valores[1], valores[2], valores[3], valores[4])
    else:
        modelo_mantenimiento.crear_gestion(cursor, valores)
        modelo_mantenimiento.marcar_gestion_hecha(cursor, id_registro)


def estado_tras_guardar(cursor, id_registro):
    """Claves extra de la respuesta: si la gestión quedó hecha y si falta la OT."""
    estado_mtto, tiene_oper, responsabilidad, conciliacion = (
        modelo_mantenimiento.buscar_estado_tras_guardar(cursor, id_registro))
    requiere_laboral = bool(tiene_oper) and requiere_relaciones_laborales(
        responsabilidad, conciliacion
    )
    return {
        "estado_mtto": bool(estado_mtto),
        "pendiente_ot": requiere_laboral and not bool(estado_mtto),
    }
