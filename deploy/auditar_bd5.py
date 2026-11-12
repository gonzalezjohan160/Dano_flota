"""Revision BD-5 de solo lectura; no aplica migraciones ni modifica registros."""
import json
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from config import connect

TABLAS = (
    "table_info_oper", "table_info_mtto", "table_info_svial", "table_info_labora",
    "gestion_operaciones", "gestion_mantenimiento", "gestion_seguridad_vial", "cierre_laboral",
)


def revisar():
    resultado = {"tablas": []}
    with closing(connect()) as conexion, closing(conexion.cursor()) as cursor:
        conexion.timeout = 20
        cursor.execute("SELECT DB_NAME(), HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'VIEW DEFINITION')")
        resultado["base"], resultado["puede_ver_definicion"] = tuple(cursor.fetchone())
        cursor.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('proceso')")
        existentes = {fila[0] for fila in cursor.fetchall()}
        for tabla in TABLAS:
            if tabla not in existentes:
                continue
            nombre = f"proceso.{tabla}"
            cursor.execute("SELECT name,is_nullable FROM sys.columns WHERE object_id=OBJECT_ID(?) AND name IN ('Id_damage','caso_id')", nombre)
            columnas = [tuple(fila) for fila in cursor.fetchall()]
            if len(columnas) != 1:
                resultado["tablas"].append({"tabla": nombre, "error": "FK del caso ambigua o ausente"})
                continue
            columna, nullable = columnas[0]
            dato = {"tabla": nombre, "columna_caso": columna, "permite_null": bool(nullable)}
            cursor.execute(f"SELECT COUNT_BIG(*), SUM(CASE WHEN [{columna}] IS NULL THEN 1 ELSE 0 END) FROM [proceso].[{tabla}]")
            dato["filas"], dato["fk_nulas"] = tuple(cursor.fetchone())
            cursor.execute(f"SELECT COUNT_BIG(*) FROM (SELECT [{columna}] FROM [proceso].[{tabla}] GROUP BY [{columna}] HAVING COUNT_BIG(*)>1) d")
            dato["casos_duplicados"] = cursor.fetchone()[0]
            cursor.execute(f"SELECT TOP (50) [{columna}],COUNT_BIG(*) FROM [proceso].[{tabla}] GROUP BY [{columna}] HAVING COUNT_BIG(*)>1 ORDER BY [{columna}]")
            dato["duplicados_hasta_50"] = [tuple(fila) for fila in cursor.fetchall()]
            cursor.execute(f"SELECT COUNT_BIG(*) FROM [proceso].[{tabla}] WHERE [{columna}] = 6")
            dato["filas_caso_6"] = cursor.fetchone()[0]
            cursor.execute("""SELECT i.name, i.is_disabled, i.has_filter, i.filter_definition,
                              ic.key_ordinal, c.name
                              FROM sys.indexes i
                              JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
                              JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                              WHERE i.object_id=OBJECT_ID(?) AND i.is_unique=1 AND ic.key_ordinal>0
                              ORDER BY i.name,ic.key_ordinal""", nombre)
            dato["indices_unicos"] = [tuple(fila) for fila in cursor.fetchall()]
            cursor.execute("""SELECT fk.name,fk.is_disabled,fk.is_not_trusted,pc.name,rs.name,rt.name,rc.name
                              FROM sys.foreign_keys fk
                              JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
                              JOIN sys.columns pc ON pc.object_id=fkc.parent_object_id AND pc.column_id=fkc.parent_column_id
                              JOIN sys.tables rt ON rt.object_id=fkc.referenced_object_id
                              JOIN sys.schemas rs ON rs.schema_id=rt.schema_id
                              JOIN sys.columns rc ON rc.object_id=fkc.referenced_object_id AND rc.column_id=fkc.referenced_column_id
                              WHERE fk.parent_object_id=OBJECT_ID(?) AND pc.name=?""", nombre, columna)
            dato["relaciones_caso"] = [tuple(fila) for fila in cursor.fetchall()]
            resultado["tablas"].append(dato)
        cursor.execute("SELECT OBJECT_ID('dbo.SchemaMigrations', 'U')")
        if cursor.fetchone()[0] is not None:
            cursor.execute("SELECT Version,FileName FROM dbo.SchemaMigrations ORDER BY Version")
            resultado["migraciones_aplicadas"] = [tuple(fila) for fila in cursor.fetchall()]
        conexion.rollback()
    return resultado


if __name__ == "__main__":
    print(json.dumps(revisar(), ensure_ascii=False, indent=2))
