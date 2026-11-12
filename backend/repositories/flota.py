"""Consulta de flota compartida por los dos capturadores."""
from contextlib import closing

from modelos import flota
from repositories.sesiones import sesion_bd


def consultar_tipologia(numero_movil, ufs, conectar=None):
    with sesion_bd(conectar) as conexion, closing(conexion.cursor()) as cursor:
        return flota.buscar_tipologia_del_movil(cursor, numero_movil, ufs)
