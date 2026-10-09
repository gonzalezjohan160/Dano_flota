"""Pruebas de regresión de los hallazgos altos y de los cambios preventivos.

Se ejecutan sin SQL Server: la conexión se reemplaza por una simulada que
registra las consultas.
"""
import importlib.util
import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("SECRET_KEY", "hallazgos-test-only")
os.environ.setdefault("MEDIA_DIR", tempfile.mkdtemp(prefix="dano-flota-hallazgos-"))
sys.path.insert(0, str(PROJECT_DIR / "backend"))
if "pyodbc" not in sys.modules and importlib.util.find_spec("pyodbc") is None:
    sys.modules["pyodbc"] = types.ModuleType("pyodbc")

CONSULTAS = []


class CursorSimulado:
    description = [("c",)]
    rowcount = 1

    def __init__(self, filas=None):
        self.filas = list(filas or [])

    def execute(self, sql, *args):
        CONSULTAS.append((sql, args))
        return self

    def fetchone(self):
        return self.filas.pop(0) if self.filas else None

    def fetchall(self):
        return []

    def nextset(self):
        return False

    def close(self):
        pass


class ConexionSimulada:
    def __init__(self, filas=None):
        self.filas = filas
        self.commits = 0

    def cursor(self):
        return CursorSimulado(self.filas)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


class CursorGlobal(CursorSimulado):
    def execute(self, sql, *args):
        return self

    def fetchone(self):
        return (0,)


class ConexionGlobal(ConexionSimulada):
    def cursor(self):
        return CursorGlobal()


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class HallazgosAltosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backend_interfaz
        cls.interfaz = backend_interfaz
        cls.app = backend_interfaz.Interfaz
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.app.config["PROPAGATE_EXCEPTIONS"] = False
        cls.modulos = {n: m for n, m in sys.modules.items()
                       if n.startswith("backend_") and n != "backend_interfaz" and hasattr(m, "connect")}

    def setUp(self):
        CONSULTAS.clear()
        self.parches = [
            patch.object(self.interfaz, "_validar_esquema_una_vez_por_proceso", return_value=None),
            patch.object(self.interfaz, "connect", side_effect=ConexionGlobal),
        ] + [patch.object(m, "connect", side_effect=ConexionSimulada) for m in self.modulos.values()]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def cliente(self, permisos=(), uf="10"):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s.update(usuario="prueba", usuario_id="prueba", UF=uf, permisos=list(permisos))
        return c

    # N-03 / N-04: toda ruta no pública rechaza a un usuario sin permisos -----------
    RUTAS_DE_CUALQUIER_SESION = {
        "Modulo_login.logout", "Profile.index", "Profile.cambiar_password",
        "Tutoriales.index", "Tutoriales.ver_video", "index",
    }
    PUBLICAS = {"Modulo_login.login", "Modulo_login.forgot_password", "Modulo_login.reset_password"}

    def test_toda_ruta_no_publica_exige_permiso(self):
        from flask import url_for
        sin_control = []
        for regla in self.app.url_map.iter_rules():
            ep = regla.endpoint
            if ep == "static" or ep.endswith(".static") or ep in self.PUBLICAS | self.RUTAS_DE_CUALQUIER_SESION:
                continue
            modulos = ["Operaciones", "Mtto", "Svial", "laboral"] if "modulo" in regla.arguments else [None]
            for modulo in modulos:
                valores = {a: (modulo if a == "modulo" else "agregar_oper" if a == "accion" else 1)
                           for a in regla.arguments}
                with self.app.test_request_context():
                    url = url_for(ep, **valores)
                if ep == "Modulo_unificado.descargar_archivo":
                    url += "?tipo=laboral"
                for metodo in regla.methods - {"HEAD", "OPTIONS"}:
                    CONSULTAS.clear()
                    r = self.cliente().open(url, method=metodo, data={"Id_damage_to_fleet": "1"})
                    rechazada = r.status_code in (403, 404, 405) or (
                        r.status_code == 302 and "/interfaz" in r.headers.get("Location", ""))
                    if CONSULTAS or not rechazada:
                        sin_control.append(f"{metodo} {url} -> {r.status_code}")
        self.assertEqual(sin_control, [], "Rutas sin control de permiso")

    def test_adjunto_laboral_negado_a_mantenimiento(self):
        r = self.cliente(["Ingresar_modulo__mtto"]).get("/archivo/1?tipo=laboral")
        self.assertEqual(r.headers.get("Location"), "/interfaz")
        self.assertEqual(CONSULTAS, [])

    # Cambio 6: CSP estricta en todas las páginas ------------------------------------
    def test_csp_sin_unsafe_inline_en_todas_las_paginas(self):
        for url, permiso in [("/", None), ("/Capturador/", "Ingresar_captur_danos"),
                             ("/Capturador_rep/", "Ingresar_captur_reparaciones"),
                             ("/Videos/Tutoriales", None), ("/Operaciones", "Ingresar_modulo__oper")]:
            r = self.cliente([permiso] if permiso else []).get(url)
            csp = r.headers["Content-Security-Policy"]
            script_src = next(d for d in csp.split(";") if d.strip().startswith("script-src "))
            self.assertNotIn("'unsafe-inline'", script_src, url)
            self.assertIn("'nonce-", script_src, url)
            self.assertIn("script-src-attr 'none'", csp, url)

    def test_plantillas_sin_javascript_en_linea(self):
        for plantilla in (PROJECT_DIR / "frontend").glob("*.html"):
            html = plantilla.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\son[a-z]+\s*=\s*[\"']", html), f"manejador on*= en {plantilla.name}")
            self.assertNotIn("javascript:", html, plantilla.name)
            for etiqueta in re.findall(r"<script\b[^>]*>", html):
                permitido = "src=" in etiqueta or "application/json" in etiqueta or "nonce=" in etiqueta
                self.assertTrue(permitido, f"script en línea sin nonce en {plantilla.name}: {etiqueta}")
            for etiqueta in re.findall(r"<(?:script|link)\b[^>]*https://[^>]*>", html):
                self.assertIn("integrity=", etiqueta, f"CDN sin SRI en {plantilla.name}")

    # Cambio 4: el enlace de recuperación no depende del Host -----------------------
    def test_enlace_recuperacion_ignora_cabecera_host(self):
        import backend_login
        enviados = []
        with patch.dict(os.environ, {"APP_BASE_URL": "https://gfd.emasivosas.com.co"}), \
                patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([(7,)])), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            self.app.test_client().post("/forgot-password", data={"email": "a@b.co"},
                                        headers={"Host": "atacante.example"})
        self.assertEqual(len(enviados), 1)
        self.assertTrue(enviados[0].startswith("https://gfd.emasivosas.com.co/reset-password/"))
        self.assertNotIn("atacante", enviados[0])

    def test_sin_app_base_url_no_se_envia_correo(self):
        import backend_login
        enviados = []
        with patch.dict(os.environ, {"APP_BASE_URL": ""}), \
                patch.object(backend_login, "connect", side_effect=lambda: ConexionSimulada([(7,)])), \
                patch.object(backend_login, "enviar_email", side_effect=lambda d, l: enviados.append(l)):
            r = self.app.test_client().post("/forgot-password", data={"email": "a@b.co"})
        self.assertEqual(enviados, [])
        self.assertEqual(r.status_code, 302)  # mismo mensaje neutro para el usuario

    # Cambio 5: crear no sobrescribe; editar exige permiso de administración ----------
    DATOS_USUARIO = {"Nombre": "Ana", "IDusuario": "123", "username": "ana.p",
                     "password": "ClaveSegura2026", "UF": "10", "Email": "ana@empresa.co"}

    def test_crear_no_modifica_usuario_existente(self):
        import backend_usuarios
        with patch.object(backend_usuarios, "connect", side_effect=lambda: ConexionSimulada([(1,)])):
            self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=self.DATOS_USUARIO)
        self.assertFalse(any(re.match(r"\s*(UPDATE|INSERT)", sql) for sql, _ in CONSULTAS), CONSULTAS)

    def test_crear_rechaza_contrasena_debil(self):
        datos = dict(self.DATOS_USUARIO, password="123")
        self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=datos)
        self.assertEqual(CONSULTAS, [])

    def test_crear_obliga_cambio_de_contrasena(self):
        self.cliente(["Ingresar_crear_usuario"]).post("/Modulo_usuario/", data=self.DATOS_USUARIO)
        insert = [sql for sql, _ in CONSULTAS if "INSERT INTO Table_usuarios" in sql]
        self.assertEqual(len(insert), 1)
        self.assertIn("Cambio_password_obligatorio", insert[0])

    def test_editar_exige_permiso_de_administracion(self):
        r = self.cliente(["Ingresar_crear_usuario"]).post(
            "/Modulo_usuario/editar", data={"IDusuario": "123", "password": "ClaveSegura2026"})
        self.assertEqual(r.headers.get("Location"), "/interfaz")
        self.assertEqual(CONSULTAS, [])

    def test_editar_no_toca_activo_y_fuerza_cambio_si_asigna_clave(self):
        import backend_usuarios
        with patch.object(backend_usuarios, "connect", side_effect=lambda: ConexionSimulada([("ana.p",)])):
            self.cliente(["Ingresar_crear_usuario", "Ingresar_asignar_permisos"]).post(
                "/Modulo_usuario/editar", data={"IDusuario": "123", "password": "ClaveSegura2026"})
        update = [sql for sql, _ in CONSULTAS if sql.strip().startswith("UPDATE Table_usuarios")]
        self.assertEqual(len(update), 1)
        self.assertNotIn("Activo", update[0])
        self.assertIn("Cambio_password_obligatorio", update[0])

    # Cambio 2: geocodificador con TLS verificado y timeout --------------------------
    def test_geocodificador_valida_tls_y_usa_timeout(self):
        import backend_capturador
        with patch.object(backend_capturador.requests, "get") as get:
            get.return_value.json.return_value = {"candidates": []}
            self.cliente(["Ingresar_captur_danos"]).get("/Capturador/geocode?q=calle 1")
        _, kwargs = get.call_args
        self.assertNotIn("verify", kwargs)
        self.assertIn("timeout", kwargs)

    # Cambio 3: el módulo no se interpola como valor en el SQL -----------------------
    def test_listado_no_interpola_modulo_en_sql(self):
        for modulo, permiso in [("laboral", "Ingresar_modulo__laboral"), ("Mtto", "Ingresar_modulo__mtto")]:
            CONSULTAS.clear()
            self.cliente([permiso]).get(f"/{modulo}")
            sql = " ".join(s for s, _ in CONSULTAS)
            self.assertNotIn(f"'{modulo}'", sql)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(importlib.util.find_spec("flask_wtf"), "Flask-WTF no está instalado")
class EdicionEventoValidaListasTests(HallazgosAltosTests):
    """N-07: la edición de eventos valida Zona_dano, Dano_ocasionado y Parte_afectada."""

    FILA_ACTUAL = {"Id": 1, "UF": "10", "Movil": "Z32-7001", "Codigo": "1", "Centro_operaciones": "GAITANA",
                   "Zona_dano": "FRONTAL", "Dano_ocasionado": "VANDALISMO", "Parte_afectada": "ESPEJO"}

    def editar(self, cambios):
        import backend_unificado

        class CursorEvento(CursorSimulado):
            description = [(c,) for c in EdicionEventoValidaListasTests.FILA_ACTUAL]

            def fetchone(self):
                return tuple(EdicionEventoValidaListasTests.FILA_ACTUAL.values())

        class ConexionEvento(ConexionSimulada):
            def cursor(self):
                return CursorEvento()

        with patch.object(backend_unificado, "connect", side_effect=ConexionEvento):
            return self.cliente(["Ingresar_modulo__oper"]).post(
                "/Operaciones/actualizar_evento/1",
                json={"evento": cambios, "motivo_modificacion": "prueba"})

    def test_rechaza_zona_fuera_de_lista(self):
        r = self.editar({"Zona_dano": "<img src=x onerror=alert(1)>"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(any(s.strip().startswith("UPDATE") for s, _ in CONSULTAS))

    def test_rechaza_dano_fuera_de_lista(self):
        self.assertEqual(self.editar({"Dano_ocasionado": "OTRO"}).status_code, 400)

    def test_rechaza_parte_afectada_larga(self):
        self.assertEqual(self.editar({"Parte_afectada": "x" * 201}).status_code, 400)

    def test_acepta_valor_de_la_lista(self):
        r = self.editar({"Zona_dano": "TECHO"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
