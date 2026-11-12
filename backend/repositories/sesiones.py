"""Unico punto de apertura de conexiones para los flujos de la aplicacion."""
from contextlib import contextmanager

from conexiones import conexion_bd


def abrir_conexion(conectar=None):
    """Permite inyectar el conector sin abrir conexiones al importar el modulo."""
    if conectar is None:
        from config import connect
        conectar = connect
    return conectar()


@contextmanager
def sesion_bd(conectar=None, *, transaccional=False):
    """Presta una conexion con cierre garantizado y transaccion opcional."""
    with conexion_bd(abrir_conexion(conectar), transaccional=transaccional) as conexion:
        yield conexion
