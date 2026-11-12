"""Comprobaciones básicas de la separación MVC de usuarios y tutoriales."""
import ast
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, session


PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_LOG_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc-logs-"))
os.environ.setdefault("APP_ENV", "prod")
os.environ.setdefault("SECRET_KEY", "mvc-usuarios-tutoriales-test")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-mvc-media-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))
if "pyodbc" not in sys.modules and importlib.util.find_spec("pyodbc") is None:
    sys.modules["pyodbc"] = types.ModuleType("pyodbc")


class CursorQueFalla:
    def __init__(self):
        self.cerrado = 0

    def execute(self, *_args, **_kwargs):
        raise RuntimeError("fallo simulado de consulta")

    def close(self):
        self.cerrado += 1


class ConexionSimulada:
    def __init__(self):
        self.cursor_simulado = CursorQueFalla()
        self.cerrado = 0
        self.reversiones = 0

    def cursor(self):
        return self.cursor_simulado

    def close(self):
        self.cerrado += 1

    def rollback(self):
        self.reversiones += 1


class MigracionUsuariosTutorialesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__, template_folder=str(PROJECT_DIR / "frontend"))
        cls.app.secret_key = "solo-pruebas"
        import backend_usuarios
        import backend_permisos_roles
        import backend_profile
        import backend_tutoriales
        cls.controladores = (
            backend_usuarios,
            backend_permisos_roles,
            backend_profile,
            backend_tutoriales,
        )

    def test_conexiones_y_cursores_se_cierran_si_falla_una_consulta(self):
        import backend_usuarios
        import backend_permisos_roles
        import backend_profile
        import backend_tutoriales

        casos = (
            (backend_usuarios, backend_usuarios.crear_usuario, "POST", {
                "Nombre": "Ana", "IDusuario": "123", "username": "ana.p",
                "password": "ClaveSegura2026", "Email": "ana@empresa.co", "UF": "10",
            }, "Ingresar_crear_usuario"),
            (backend_permisos_roles, backend_permisos_roles.asignar_permisos, "GET", {},
             "Ingresar_asignar_permisos"),
            (backend_profile, backend_profile.index, "GET", {}, None),
            (backend_tutoriales, backend_tutoriales.index, "GET", {}, None),
        )
        for modulo, vista, metodo, datos, permiso in casos:
            with self.subTest(controlador=modulo.__name__):
                conexion = ConexionSimulada()
                with patch.object(modulo, "connect", return_value=conexion):
                    with self.app.test_request_context("/", method=metodo, data=datos):
                        session["usuario"] = "usuario_prueba"
                        session["permisos"] = [permiso] if permiso else []
                        if modulo is backend_usuarios:
                            with patch.object(modulo, "render_template", return_value=""):
                                vista()
                        else:
                            with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
                                vista()
                self.assertEqual(conexion.cerrado, 1)
                self.assertEqual(conexion.cursor_simulado.cerrado, 1)

    def test_los_controladores_no_contienen_consultas_sql(self):
        for modulo in self.controladores:
            arbol = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
            llamadas = [
                nodo for nodo in ast.walk(arbol)
                if isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "execute"
            ]
            self.assertEqual(llamadas, [], modulo.__name__)

    def test_los_modelos_no_importan_flask_ni_usan_sesion(self):
        for nombre in ("usuarios.py", "tutoriales.py"):
            archivo = PROJECT_DIR / "backend" / "modelos" / nombre
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            imports_flask = [
                nodo for nodo in ast.walk(arbol)
                if isinstance(nodo, ast.Import) and any(alias.name == "flask" for alias in nodo.names)
                or isinstance(nodo, ast.ImportFrom) and nodo.module == "flask"
            ]
            self.assertEqual(imports_flask, [], nombre)

    def test_los_usuarios_se_inactivan_y_no_se_borran(self):
        # El nombre de usuario es la clave foránea de quien registró cada caso y cada
        # gestión: el modelo ya no tiene cómo borrar un usuario, solo inactivarlo.
        import modelos.usuarios as modelo_usuarios
        self.assertFalse(hasattr(modelo_usuarios, "eliminar_usuario_y_sus_datos"))
        codigo = (PROJECT_DIR / "backend" / "modelos" / "usuarios.py").read_text(encoding="utf-8")
        self.assertNotIn("DELETE FROM usuario.Table_usuarios ", codigo)
        self.assertIn("UPDATE usuario.Table_usuarios SET Activo = ?", codigo)


if __name__ == "__main__":
    unittest.main()
