"""Consultas de la flota: vehículos (flota.table_Moviles) y operadores (flota.table_drivers).

Las usan el Capturador de daños y el de reparaciones, que antes tenían copias
idénticas de estas consultas.
"""


def buscar_tipologia_del_movil(cursor, numero_movil, ufs):
    """Fila con la tipología del móvil, solo si pertenece a una de las UF dadas.

    Devuelve la fila (tipologia,) o None si el móvil no existe en esas UF.
    """
    marcadores = ", ".join("?" for _ in ufs)
    cursor.execute(
        f"SELECT Tipologia_Movil FROM flota.table_Moviles WHERE No_Movil = ? AND UF IN ({marcadores})",
        (numero_movil, *(int(uf) for uf in ufs)),
    )
    return cursor.fetchone()


def movil_pertenece_a_uf(cursor, numero_movil, uf):
    """True si el móvil está registrado en esa UF."""
    cursor.execute(
        "SELECT 1 FROM flota.table_Moviles WHERE No_Movil = ? AND UF = ?",
        (numero_movil, int(uf)),
    )
    return cursor.fetchone() is not None


def buscar_fila_del_conductor(cursor, codigo):
    """Fila (nombre,) o None; consulta compartida por Capturador y Operaciones."""
    cursor.execute("SELECT Nombre_OBZ FROM flota.table_drivers WHERE Codigo_OBZ = ?", (codigo,))
    return cursor.fetchone()


def buscar_nombre_del_conductor(cursor, codigo):
    """Nombre del operador por codigo, o None si no existe."""
    fila = buscar_fila_del_conductor(cursor, codigo)
    return fila[0] if fila else None
