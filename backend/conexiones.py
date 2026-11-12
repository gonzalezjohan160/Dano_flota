"""Ciclo de vida comun de conexiones; no depende de Flask ni de configuracion.

conexion_bd(c, transaccional=True) confirma al terminar y revierte ante errores.
Sin transaccional conserva los limites explicitos de commit/rollback del llamador.
El cierre se intenta siempre, incluso si falla commit, rollback o cursor.close.
"""
from contextlib import contextmanager, nullcontext
import logging

log = logging.getLogger("dano_flota")


@contextmanager
def transaccion(conexion):
    """Confirma la unidad de escritura o la revierte conservando el error original."""
    try:
        yield conexion
        conexion.commit()
    except BaseException:
        try:
            conexion.rollback()
        except Exception:
            log.exception("error_rollback_conexion")
        raise


@contextmanager
def conexion_bd(conexion, *, transaccional=False):
    error_original = False
    try:
        try:
            with transaccion(conexion) if transaccional else nullcontext():
                yield conexion
        except BaseException:
            error_original = True
            raise
    finally:
        try:
            conexion.close()
        except Exception:
            if not error_original:
                raise
            log.exception("error_cerrar_conexion")
