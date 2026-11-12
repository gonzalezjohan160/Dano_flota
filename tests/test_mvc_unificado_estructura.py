"""División del módulo unificado: capas, tamaño de archivos, plantillas y JavaScript.

Pruebas estáticas (leen el código): no ejecutan la aplicación ni usan base de datos.
"""
import ast
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BACKEND = RAIZ / "backend"
JS = RAIZ / "Static" / "Script" / "Modulo_unificado"
PARCIALES = RAIZ / "frontend" / "parciales" / "modulo_unificado"
PLANTILLA = RAIZ / "frontend" / "Modulo_unificado.html"

CONTROLADORES = [BACKEND / "backend_unificado.py", *sorted((BACKEND / "unificado").glob("*.py"))]
MODELOS = [BACKEND / "modelos" / f"{n}.py" for n in (
    "casos", "archivos", "bandeja", "detalle_caso", "mantenimiento", "seguridad_vial", "laboral",
    "operaciones", "auditoria")]
SERVICIOS = sorted((BACKEND / "servicios").glob("*.py"))
SQL = re.compile(r"\b(SELECT\s|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)")
ORDEN_JS = ["configuracion", "utilidades", "filtros", "tabla", "detalle", "edicion_evento", "adjuntos",
            "formulario", "formulario_campos", "flujo_operaciones", "validacion", "envio", "inicio"]
# Ids que el JS crea al vuelo (edición del evento) u opcionales con "?." (ya era así antes).
IDS_DINAMICOS = {"btnCerrarCaso", "btn_reabrir_evento", "evento_area", "evento_centro", "evento_codigo",
                 "evento_dano", "evento_direccion", "evento_fecha", "evento_movil", "evento_nombre",
                 "evento_parte", "evento_ruta", "evento_tipologia", "evento_uf", "evento_version", "evento_zona"}


def leer(ruta):
    return ruta.read_text(encoding="utf-8")


def plantillas():
    return [PLANTILLA, *sorted(PARCIALES.glob("*.html"))]


class CapasDelModuloUnificadoTests(unittest.TestCase):
    def test_controladores_no_contienen_sql_ni_ejecutan_consultas(self):
        for ruta in CONTROLADORES:
            arbol = ast.parse(leer(ruta))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                    self.assertIsNone(SQL.search(nodo.value), f"{ruta.name}: {nodo.value[:60]!r}")
                if isinstance(nodo, ast.Attribute):
                    self.assertNotEqual(nodo.attr, "execute", ruta.name)

    def test_modelos_y_servicios_no_usan_flask_ni_manejan_la_conexion(self):
        for ruta in MODELOS + SERVICIOS:
            arbol = ast.parse(leer(ruta))
            importados = {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
            importados |= {n.module.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertFalse(importados & {"flask", "werkzeug", "config"}, ruta.name)
            nombres = {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}
            self.assertFalse(nombres & {"request", "session", "connect"}, ruta.name)
            metodos = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
            self.assertFalse(metodos & {"commit", "rollback", "close"}, ruta.name)

    def test_controladores_cierran_conexion_y_cursor_con_closing(self):
        def es_llamada(nodo, nombre):
            return isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", getattr(nodo.func, "id", None)) == nombre

        for ruta in CONTROLADORES:
            arbol = ast.parse(leer(ruta))
            conexiones = [n for n in ast.walk(arbol) if es_llamada(n, "connect")]
            protegidas = 0
            for bloque in (n for n in ast.walk(arbol) if isinstance(n, ast.With)):
                expresiones = [item.context_expr for item in bloque.items]
                if len(expresiones) == 2 and all(es_llamada(e, "closing") for e in expresiones) \
                        and es_llamada(expresiones[0].args[0], "connect") and es_llamada(expresiones[1].args[0], "cursor"):
                    protegidas += 1
            self.assertEqual(protegidas, len(conexiones), ruta.name)

    def test_ningun_archivo_nuevo_o_modificado_supera_350_lineas(self):
        archivos = CONTROLADORES + MODELOS + SERVICIOS + plantillas() + sorted(JS.glob("*.js")) + [
            RAIZ / "tests" / "test_mvc_unificado_rutas.py", RAIZ / "tests" / "test_mvc_unificado_estructura.py",
            RAIZ / "tests" / "test_mvc_operaciones.py", RAIZ / "tests" / "test_n08_attachments.py",
            RAIZ / "Static" / "Style" / "Style_modulo_unificado.css"]
        for ruta in archivos:
            with self.subTest(archivo=ruta.name):
                self.assertLessEqual(len(leer(ruta).splitlines()), 350)


class PlantillasYJavaScriptTests(unittest.TestCase):
    def test_plantilla_incluye_cada_parcial_una_vez(self):
        incluidos = re.findall(r'\{% include "parciales/modulo_unificado/(\w+\.html)" %\}',
                               "".join(leer(p) for p in plantillas()))
        self.assertEqual(sorted(incluidos), sorted(p.name for p in PARCIALES.glob("*.html")))
        self.assertEqual(len(incluidos), len(set(incluidos)))

    def test_plantillas_respetan_la_csp(self):
        for ruta in plantillas():
            texto = re.sub(r"<!--.*?-->|\{#.*?#\}", "", leer(ruta), flags=re.S)
            with self.subTest(plantilla=ruta.name):
                self.assertNotIn("<style", texto)
                self.assertIsNone(re.search(r"\son[a-z]+\s*=", texto))
                for etiqueta in re.findall(r"<script\b[^>]*>", texto):
                    self.assertRegex(etiqueta, r'\ssrc=|type="application/json"')

    def test_scripts_se_cargan_en_orden_y_una_sola_vez(self):
        cargados = re.findall(r"Script/(?:Modulo_unificado/)?(\w+)\.js", leer(PARCIALES / "_scripts.html"))
        self.assertEqual(cargados, ["Script_utils"] + ORDEN_JS)
        self.assertEqual(sorted(ORDEN_JS), sorted(p.stem for p in JS.glob("*.js")))
        self.assertFalse((RAIZ / "Static" / "Script" / "Script_oper.js").exists())

    def test_inicio_arranca_cada_parte_en_orden(self):
        definidas = []
        for nombre in ORDEN_JS:
            propias = re.findall(r"^function (iniciar\w+)\(\)", leer(JS / f"{nombre}.js"), re.M)
            self.assertEqual(len(propias), 1, nombre)
            definidas += propias
        llamadas = re.findall(r"^    (iniciar\w+)\(\);", leer(JS / "inicio.js"), re.M)
        self.assertEqual(llamadas, definidas)

    def test_no_hay_nombres_globales_repetidos_entre_archivos(self):
        vistos = {}
        otros = [RAIZ / "Static" / "Script" / "Script_utils.js", RAIZ / "Static" / "Script" / "Script_interfaz.js"]
        for ruta in otros + [JS / f"{n}.js" for n in ORDEN_JS]:
            for nombre in re.findall(r"^(?:const|let|var|function|async function)\s+(\w+)", leer(ruta), re.M):
                self.assertNotIn(nombre, vistos, f"{nombre} en {ruta.name} y {vistos.get(nombre)}")
                vistos[nombre] = ruta.name

    def test_peticiones_post_llevan_token_csrf(self):
        for ruta in JS.glob("*.js"):
            texto = leer(ruta)
            for inicio in (m.start() for m in re.finditer(r"(?<![\w.])fetch\(", texto)):
                fragmento = texto[inicio:inicio + 400].split(");", 1)[0]
                self.assertNotRegex(fragmento, r"method:\s*[\"'](POST|PUT|DELETE)", ruta.name)
            self.assertNotIn("window.fetch(", texto, ruta.name)

    def test_los_ids_que_usa_el_javascript_existen_en_las_plantillas(self):
        html = "".join(leer(p) for p in plantillas() + [RAIZ / "frontend" / "Interfaz.html"])
        ids = set(re.findall(r'id="([^"{]+)"', html))
        usados = set()
        for ruta in JS.glob("*.js"):
            usados |= set(re.findall(r'getElementById\("([^"]+)"\)', leer(ruta)))
        self.assertEqual(usados - ids - IDS_DINAMICOS, set())

    def test_configuracion_sale_del_json_y_no_de_un_script_en_linea(self):
        self.assertIn('<script id="modulo-config-json" type="application/json">', leer(PLANTILLA))
        configuracion = leer(JS / "configuracion.js")
        self.assertIn('document.getElementById("modulo-config-json")', configuracion)
        self.assertIn("const MODULO = CFG ? CFG.modulo : null;", configuracion)


if __name__ == "__main__":
    unittest.main()
