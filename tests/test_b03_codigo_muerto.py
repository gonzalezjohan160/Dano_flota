"""B-03: el backend no tiene imports ni variables sin uso (pyflakes sin avisos)."""
import importlib.util
import io
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("pyflakes"),
                     "pyflakes no está instalado (pip install -r requirements-dev.txt)")
class CodigoMuertoTests(unittest.TestCase):
    def test_pyflakes_sin_avisos(self):
        from pyflakes.api import checkRecursive
        from pyflakes.reporter import Reporter

        salida = io.StringIO()
        rutas = [str(PROJECT_DIR / "backend"), str(PROJECT_DIR / "wsgi.py"),
                 str(PROJECT_DIR / "gunicorn.conf.py")]
        avisos = checkRecursive(rutas, Reporter(salida, salida))
        self.assertEqual(avisos, 0, "\n" + salida.getvalue())


if __name__ == "__main__":
    unittest.main()
