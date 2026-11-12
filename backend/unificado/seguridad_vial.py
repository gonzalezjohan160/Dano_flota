"""Seguridad Vial: registro de su gestión (observaciones y conciliación con terceros).

La ruta es la genérica "/Svial/agregar_svial" de gestiones.py, que abre la
conexión, valida y guarda los adjuntos; aquí solo va lo propio de Seguridad Vial.
"""
from modelos import seguridad_vial as modelo_seguridad_vial


def registrar_gestion(cursor, id_registro, valores, auditar_cambio):
    """valores: [id, Observaciones_svial, usuario, conciliado_a_favor,
    valor_conciliado_terceros] (CONFIG_GESTIONES)."""
    if modelo_seguridad_vial.existe_gestion(cursor, id_registro):
        anterior = modelo_seguridad_vial.buscar_gestion(cursor, id_registro)
        for campo, viejo, nuevo in zip(
            ("observaciones", "conciliado_a_favor", "valor_conciliado_terceros"),
            anterior, (valores[1], valores[3], valores[4])
        ):
            auditar_cambio(modelo_seguridad_vial.TABLA, campo, viejo, nuevo)
        modelo_seguridad_vial.actualizar_gestion(
            cursor, id_registro, valores[1], valores[2], valores[3], valores[4])
    else:
        modelo_seguridad_vial.crear_gestion(cursor, valores)
        modelo_seguridad_vial.marcar_gestion_hecha(cursor, id_registro)
