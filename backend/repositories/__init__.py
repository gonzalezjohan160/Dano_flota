"""Acceso a datos: sesiones compartidas y consultas del paquete modelos.

Los modelos reciben el cursor de la sesion para compartir una transaccion;
no abren conexiones ni dependen de Flask. Las rutas conservan sus politicas.
"""
