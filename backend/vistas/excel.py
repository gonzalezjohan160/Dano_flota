"""Construcción de libros de Excel a partir de datos ya consultados."""
import io

from openpyxl import Workbook


def crear_libro_excel(hojas):
    """Arma un libro .xlsx en memoria y lo devuelve listo para enviar (BytesIO).

    hojas: lista de diccionarios, uno por hoja, con:
      titulo    nombre de la pestaña
      etiqueta  valor de la primera columna "Tipo" en cada fila (p. ej. "DAÑO")
      columnas  nombres de las columnas
      filas     filas de datos, en el mismo orden que las columnas
    Si no llega ninguna hoja, el libro tiene una hoja vacía llamada "Sin datos".
    """
    libro = Workbook()
    primera_hoja = True

    for hoja in hojas:
        ws = libro.active if primera_hoja else libro.create_sheet()
        ws.title = hoja["titulo"]
        primera_hoja = False
        ws.append(["Tipo"] + list(hoja["columnas"]))
        for fila in hoja["filas"]:
            ws.append([hoja["etiqueta"]] + list(fila))

    if primera_hoja:
        libro.active.title = "Sin datos"

    salida = io.BytesIO()
    libro.save(salida)
    salida.seek(0)
    return salida
