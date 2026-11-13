"""Publicación de archivos completos sin reemplazar un corte existente."""

import os


def publicar(origen, destino):
    if os.name == "nt":
        origen.rename(destino)
    else:
        os.link(origen, destino)
