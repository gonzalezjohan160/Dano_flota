"""Sincroniza altas, cambios de nombre y retiros de operadores."""
from contextlib import closing

from modelos import sincronizacion_operadores as modelo
from repositories.sesiones import sesion_bd


def sincronizar_operadores():
    with sesion_bd(transaccional=True) as conexion, closing(conexion.cursor()) as cursor:
        conflictos = modelo.validar_fuente(cursor)
        tabla = modelo.tabla_destino(cursor)
        operadores_nuevos = modelo.listar_operadores_nuevos(cursor, tabla)
        operadores_retirados = modelo.listar_operadores_retirados(cursor, tabla)
        actualizados = modelo.actualizar_nombres(cursor, tabla)

        for operador in operadores_nuevos:
            modelo.insertar_operador(cursor, tabla, operador.code, operador.name)
        eliminados = sum(
            modelo.eliminar_operador(cursor, tabla, operador.Codigo_OBZ)
            for operador in operadores_retirados
        )

    return len(operadores_nuevos), actualizados, eliminados, conflictos
