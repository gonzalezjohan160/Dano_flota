import unittest
import sys
from pathlib import Path

from flask import Flask

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from backend_security import usuario_puede_acceder_uf, ufs_autorizadas_sesion


class UfAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-only"
        self.context = self.app.test_request_context("/")
        self.context.push()
        self.addCleanup(self.context.pop)

    def test_individual_uf_is_limited_to_own_records(self):
        from flask import session

        session["UF"] = "10"
        self.assertEqual(ufs_autorizadas_sesion(), (10,))
        self.assertTrue(usuario_puede_acceder_uf(10))
        self.assertFalse(usuario_puede_acceder_uf("16"))

    def test_transversal_is_limited_to_ufs_10_and_16(self):
        from flask import session

        session["UF"] = "TRANSVERSAL"
        self.assertEqual(ufs_autorizadas_sesion(), (10, 16))
        self.assertTrue(usuario_puede_acceder_uf("10"))
        self.assertTrue(usuario_puede_acceder_uf(16))
        self.assertFalse(usuario_puede_acceder_uf("20"))

    def test_missing_or_invalid_uf_denies_access(self):
        from flask import session

        for value in (None, "", "0", "20", "invalid"):
            session.pop("UF", None)
            if value is not None:
                session["UF"] = value
            self.assertEqual(ufs_autorizadas_sesion(), ())
            self.assertFalse(usuario_puede_acceder_uf("10"))
        session["UF"] = "10"
        self.assertFalse(usuario_puede_acceder_uf(None))
        self.assertFalse(usuario_puede_acceder_uf("20"))


if __name__ == "__main__":
    unittest.main()
