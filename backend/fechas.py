"""Lectura y validación de las fechas que llegan en los filtros de las pantallas.

Todas usan el formato de los campos <input type="date">: AAAA-MM-DD. Una fecha
mal formada lanza FechaInvalida, que las vistas responden con 400 y su mensaje.
"""
from datetime import datetime


class FechaInvalida(ValueError):
    """Fecha con formato incorrecto; el mensaje se puede mostrar al usuario."""


def parse_fecha(texto, nombre):
    """Convierte 'AAAA-MM-DD' en date; vacío o None devuelve None."""
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise FechaInvalida(f"La fecha de {nombre} no es válida. Use el formato AAAA-MM-DD.") from None


def leer_rango_fechas(args, campo_inicio="fecha_inicio", campo_fin="fecha_fin"):
    """Lee el rango (inicio, fin) de los parámetros y valida que inicio <= fin."""
    inicio = parse_fecha(args.get(campo_inicio), "inicio")
    fin = parse_fecha(args.get(campo_fin), "fin")
    if inicio and fin and inicio > fin:
        raise FechaInvalida("La fecha de inicio no puede ser posterior a la fecha de fin.")
    return inicio, fin
