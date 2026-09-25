"""Testes de credenciais: nada de senha em disco, pedido no terminal.

Protege a decisao de nao guardar credenciais em arquivo (.env) e garante que os
CLIs pedem usuario/senha no terminal.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_batches  # noqa: E402


class TestSemArquivoDeCredenciais(unittest.TestCase):
    def test_nao_existe_env(self):
        self.assertFalse((ROOT / ".env").exists())
        self.assertFalse((ROOT / ".env.example").exists())

    def test_nenhum_script_usa_dotenv(self):
        for script in ROOT.glob("*.py"):
            with self.subTest(script=script.name):
                self.assertNotIn("dotenv", script.read_text(encoding="utf-8"))

    def test_nenhuma_senha_embutida_no_codigo(self):
        """Nenhum .py deve conter password= seguido de string literal."""
        import re

        padrao = re.compile(r"""password\s*[=:]\s*["'][^"']+["']""")
        for script in list(ROOT.glob("*.py")) + list((ROOT / "app").glob("*.py")):
            with self.subTest(script=script.name):
                for linha in script.read_text(encoding="utf-8").splitlines():
                    if linha.strip().startswith("#"):
                        continue
                    self.assertIsNone(
                        padrao.search(linha),
                        f"credencial embutida em {script.name}: {linha.strip()}",
                    )


class TestAskCredentials(unittest.TestCase):
    def test_le_usuario_e_senha(self):
        with mock.patch("builtins.input", return_value="  lucas.daniel  "):
            with mock.patch("run_batches.getpass.getpass", return_value="segredo"):
                username, password = run_batches.ask_credentials()
        self.assertEqual(username, "lucas.daniel")
        self.assertEqual(password, "segredo")

    def test_senha_vem_do_getpass_nao_do_input(self):
        """A senha nao pode ser pedida com input() (ficaria visivel na tela)."""
        with mock.patch("builtins.input", return_value="usuario") as fake_input:
            with mock.patch("run_batches.getpass.getpass", return_value="s") as fake_getpass:
                run_batches.ask_credentials()
        self.assertEqual(fake_input.call_count, 1)  # so o usuario
        self.assertEqual(fake_getpass.call_count, 1)  # a senha


class TestMainAbortaSemCredenciais(unittest.TestCase):
    def _run_main(self, username: str, password: str) -> int:
        with mock.patch("sys.argv", ["run_batches.py"]):
            with mock.patch("run_batches.ask_credentials", return_value=(username, password)):
                return run_batches.main()

    def test_usuario_vazio_aborta(self):
        self.assertEqual(self._run_main("", "senha"), 2)

    def test_senha_vazia_aborta(self):
        self.assertEqual(self._run_main("usuario", ""), 2)

    def test_help_nao_pede_credenciais(self):
        """--help deve sair antes de qualquer pedido de credencial."""
        with mock.patch("run_batches.ask_credentials") as fake:
            with mock.patch("sys.argv", ["run_batches.py", "--help"]):
                with self.assertRaises(SystemExit) as ctx:
                    run_batches.main()
        self.assertEqual(ctx.exception.code, 0)
        fake.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
