"""BD-16: lectura de tipos BIT, defaults y distribucion de estados."""
import json
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from config import connect


def revisar():
    resultado = []
    with closing(connect()) as conexion, closing(conexion.cursor()) as cursor:
        conexion.timeout = 20
        cursor.execute("""SELECT s.name,t.name,c.name,c.is_nullable,dc.name,dc.definition
                          FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id
                          JOIN sys.schemas s ON s.schema_id=t.schema_id
                          LEFT JOIN sys.default_constraints dc ON dc.object_id=c.default_object_id
                          WHERE c.system_type_id=104 ORDER BY s.name,t.name,c.column_id""")
        columnas = [tuple(fila) for fila in cursor.fetchall()]
        for esquema, tabla, columna, nullable, nombre, definicion in columnas:
            def identificador(texto):
                return "[" + texto.replace("]", "]]") + "]"

            campo = identificador(columna)
            cursor.execute(f"""SELECT COUNT_BIG(*),
                               SUM(CASE WHEN {campo} IS NULL THEN 1 ELSE 0 END),
                               SUM(CASE WHEN {campo}=0 THEN 1 ELSE 0 END),
                               SUM(CASE WHEN {campo}=1 THEN 1 ELSE 0 END)
                               FROM {identificador(esquema)}.{identificador(tabla)}""")
            filas, nulos, ceros, unos = tuple(cursor.fetchone())
            resultado.append(dict(esquema=esquema, tabla=tabla, columna=columna,
                                  permite_null=bool(nullable), default_nombre=nombre,
                                  default=definicion, filas=filas, nulos=nulos or 0,
                                  ceros=ceros or 0, unos=unos or 0))
        conexion.rollback()
    return resultado


if __name__ == "__main__":
    print(json.dumps(revisar(), ensure_ascii=False, indent=2))
