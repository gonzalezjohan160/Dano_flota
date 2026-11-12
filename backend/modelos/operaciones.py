"""Consultas exclusivas del módulo de Operaciones.

Edición del evento, consulta de operador, eliminación lógica, reincidencia del
operador y registro de la gestión de Operaciones (proceso.table_info_oper),
incluido el cierre por conciliación que se guarda en proceso.table_info_labora.
"""
from modelos.flota import buscar_fila_del_conductor as buscar_nombre_del_operador
from modelos.laboral import crear_cierre as crear_cierre_laboral
from modelos.casos import CASO_CON_MOVIL
from modelos.casos import buscar_caso_completo as buscar_caso_completo

TABLA_CASO = "flota.table_damage_to_fleet"
TABLA_GESTION = "proceso.table_info_oper"
TABLA_CIERRE = "proceso.table_info_labora"

# Campo que Operaciones puede corregir desde "Editar" -> columna de flota.table_damage_to_fleet. El
# nombre de la columna se escribe en el UPDATE, así que solo se aceptan los de aquí.
# La UF y la tipología no están: son las del móvil.
CAMPOS_EDITABLES_DEL_CASO = {
    "Fecha_evento": "Fecha_evento", "Movil": "Movil", "Codigo": "Codigo",
    "Nombre": "Nombre", "Area": "Area", "Ruta": "Ruta", "Direccion": "Direccion",
    "Version_libre": "version_libre", "Parte_afectada": "parte_afectada",
    "Dano_ocasionado": "Dano_ocasionado", "Zona_dano": "Zona_dano",
    "Centro_operaciones": "Centro_operaciones",
}

# Campo de la gestión de Operaciones -> columna (para la auditoría de correcciones).
COLUMNAS_DE_LA_GESTION = {
    "Observaciones_operaciones": "Observaciones_operaciones", "Usuario_registro_oper": "Usuario_registro_oper",
    "responsabilidad_operador": "responsabilidad_operador", "conciliacion": "conciliacion",
    "costo_oper": "costo_oper",
}


# ------------------------------------------------------------- el caso ---


def actualizar_campo_del_caso(cursor, id_caso, campo, valor):
    """Cambia una columna del caso. 'campo' debe estar en CAMPOS_EDITABLES_DEL_CASO."""
    if campo not in CAMPOS_EDITABLES_DEL_CASO:
        raise ValueError(f"El campo {campo!r} no se puede editar.")
    columna = CAMPOS_EDITABLES_DEL_CASO[campo]
    cursor.execute(f"UPDATE flota.table_damage_to_fleet SET {columna} = ? WHERE Id_damage = ?", (valor, id_caso))


# ---------------------------------------------------------- eliminación ---

def buscar_estado_para_eliminar(cursor, id_caso):
    """Fila (eliminado, UF, cerrado) del caso, o None si no existe."""
    cursor.execute(f"""
            SELECT d.eliminado, CAST(m.UF AS varchar(3)), d.estado_caso
            FROM {CASO_CON_MOVIL}
            WHERE d.Id_damage = ?
        """, [id_caso])
    return cursor.fetchone()


def registrar_eliminacion(cursor, id_caso, usuario, fecha, motivo):
    """Deja en la auditoría quién eliminó el caso, cuándo y por qué."""
    cursor.execute("""
            INSERT INTO proceso.table_auditoria_correcciones
                (Id_damage, Tabla_Afectada, usuario_id, Fecha_Modificacion, Motivo_modificacion)
            VALUES (?, ?, ?, ?, ?)
        """, (id_caso, TABLA_CASO, usuario, fecha, motivo))


def marcar_caso_eliminado(cursor, id_caso):
    """Borrado lógico. Devuelve cuántas filas cambió (0 si ya estaba eliminado)."""
    cursor.execute("""
            UPDATE flota.table_damage_to_fleet
            SET eliminado = 1
            WHERE Id_damage = ? AND eliminado = 0
        """, [id_caso])
    return cursor.rowcount


# ---------------------------------------------------------- reincidencia ---

def buscar_operador_y_fecha_del_caso(cursor, id_caso):
    """Fila (codigo_operador, fecha_evento) del caso, o None."""
    cursor.execute("""
        SELECT Codigo, Fecha_evento
        FROM flota.v_BD6_table_damage_to_fleet
        WHERE Id_damage = ?
    """, [id_caso])
    return cursor.fetchone()


def contar_antecedentes_con_responsabilidad(cursor, codigo_operador, id_caso, fecha_evento):
    """Casos del mismo operador, con responsabilidad SI, en los 2 meses anteriores
    al evento (sin contar el caso actual)."""
    cursor.execute("""
        SELECT COUNT(DISTINCT d.Id_damage)
        FROM proceso.v_BD6_table_info_oper o
        JOIN flota.v_BD6_table_damage_to_fleet d ON d.Id_damage = o.Id_damage
        WHERE d.Codigo = ?
          AND d.Id_damage <> ?
          AND o.responsabilidad_operador = 'SI'
          AND d.Fecha_evento >= DATEADD(month, -2, ?)
          AND d.Fecha_evento <= ?
    """, [codigo_operador, id_caso, fecha_evento, fecha_evento])
    return cursor.fetchone()[0]


# ------------------------------------------------ gestión de Operaciones ---

def bloquear_gestion_anterior(cursor, id_caso):
    """Gestión de Operaciones ya registrada, bloqueada hasta el commit para que
    un reenvío no cree un segundo registro. Fila de 5 columnas o None."""
    cursor.execute("""
            SELECT Observaciones_operaciones, usuario_id,
                   responsabilidad_operador,
                   conciliacion, costo_oper
            FROM proceso.v_BD6_table_info_oper WITH (UPDLOCK, HOLDLOCK)
            WHERE Id_damage = ?
        """, [id_caso])
    return cursor.fetchone()


def actualizar_gestion(cursor, id_caso, valores):
    """Reemplaza la gestión de Operaciones y la marca como hecha.

    valores: (observaciones, usuario, responsabilidad_operador, conciliacion, costo_oper).
    """
    cursor.execute("""
                UPDATE proceso.table_info_oper
                SET Observaciones_operaciones = ?,
                    usuario_id = ?,
                    responsabilidad_operador = NULLIF(?, ''),
                    conciliacion = NULLIF(?, ''),
                    costo_oper = ?,
                    estado_oper = 1
                WHERE Id_damage = ?
            """, tuple(valores) + (id_caso,))


def crear_gestion(cursor, id_caso, valores):
    """Inserta la gestión de Operaciones, ya marcada como hecha (mismos valores que actualizar_gestion)."""
    cursor.execute("""
                INSERT INTO proceso.table_info_oper
                    (Id_damage, Observaciones_operaciones, usuario_id,
                     responsabilidad_operador,
                     conciliacion, costo_oper, estado_oper)
                VALUES (?, ?, ?, NULLIF(?, ''), NULLIF(?, ''), ?, 1)
            """, (id_caso,) + tuple(valores))


def existe_registro_laboral(cursor, id_caso):
    """True si el caso ya tiene cierre en proceso.table_info_labora."""
    cursor.execute(
        "SELECT Id_damage FROM proceso.v_BD6_table_info_labora WHERE Id_damage = ?",
        [id_caso]
    )
    return cursor.fetchone() is not None


def actualizar_cierre_laboral(cursor, id_caso, valor_conciliado, tipo_cerrado):
    """Guarda el cierre decidido en Operaciones en la fila de RRLL que ya existe."""
    cursor.execute("""
                    UPDATE proceso.table_info_labora SET Valor_conciliado = ?, Tipo_cerrado = NULLIF(?, '')
                    WHERE Id_damage = ?
                """, (valor_conciliado, tipo_cerrado, id_caso))


def buscar_cierre_previo_de_operaciones(cursor, id_caso):
    """Fila (tipo_cierre, valor_conciliado) de un cierre hecho desde Operaciones,
    es decir, sin historial en RRLL (proceso.table_info_laboral_mult). None si no hay."""
    cursor.execute("""
                SELECT Tipo_cerrado, Valor_conciliado
                FROM proceso.v_BD6_table_info_labora l
                WHERE l.Id_damage = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM proceso.v_BD6_table_info_laboral_mult lm
                      WHERE lm.Id_damage = l.Id_damage
                  )
            """, [id_caso])
    return cursor.fetchone()


def retirar_cierre_laboral(cursor, id_caso):
    """Quita el cierre de RRLL del caso."""
    cursor.execute("DELETE FROM proceso.table_info_labora WHERE Id_damage = ?", [id_caso])
