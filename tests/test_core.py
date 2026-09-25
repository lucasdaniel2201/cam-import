"""Testes do core de importacao (zabbix_web_batch_import.py).

Cobrem as funcoes puras que ja causaram ou poderiam causar bugs reais:
normalizacao de nome, interpretacao da resposta do Zabbix e montagem do
formulario de criacao do host.
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import zabbix_web_batch_import as core  # noqa: E402


def make_args(**overrides) -> SimpleNamespace:
    base = {
        "host_prefix": "",
        "host_suffix": "",
        "visible_name_prefix": "",
        "visible_name_suffix": "",
        "template_id": ["10001"],
        "group_id": ["1"],
        "proxy_id": "2",
        "port": "10051",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def make_record(**overrides) -> core.CameraRecord:
    base = {
        "csv_index": 1,
        "name": "CAM-TESTE-01",
        "vendor": "Hikvision",
        "model": "DS-2CD2043G2-I",
        "firmware": "1.0.0",
        "ip": "10.0.0.10",
        "mac_address": "AA-BB-CC-DD-EE-FF",
    }
    base.update(overrides)
    return core.CameraRecord(**base)


class TestNormalizeZabbixName(unittest.TestCase):
    def test_remove_acentos(self):
        self.assertEqual(core.normalize_zabbix_name("Câmera São Paulo"), "Camera Sao Paulo")

    def test_remove_cedilha_e_til(self):
        self.assertEqual(core.normalize_zabbix_name("Ação Bênção"), "Acao Bencao")

    def test_barra_vira_hifen(self):
        self.assertEqual(core.normalize_zabbix_name("A/B"), "A-B")
        self.assertEqual(core.normalize_zabbix_name("A\\B"), "A-B")
        self.assertEqual(core.normalize_zabbix_name("A//B"), "A-B")

    def test_remove_caracteres_invalidos(self):
        # parenteses, virgula e dois-pontos nao sao aceitos pelo Zabbix
        self.assertEqual(core.normalize_zabbix_name("CAM (1), fundo"), "CAM 1 fundo")

    def test_preserva_caracteres_permitidos(self):
        self.assertEqual(core.normalize_zabbix_name("CAM-A_1.2 x"), "CAM-A_1.2 x")

    def test_colapsa_espacos(self):
        self.assertEqual(core.normalize_zabbix_name("  CAM   01  "), "CAM 01")

    def test_texto_vazio(self):
        self.assertEqual(core.normalize_zabbix_name(""), "")

    def test_apenas_invalidos_vira_vazio(self):
        self.assertEqual(core.normalize_zabbix_name("()[]{}"), "")

    def test_nome_longo_com_hifens(self):
        self.assertEqual(
            core.normalize_zabbix_name("CAM-ENTRADA-PRINCIPAL-BLOCO-A"),
            "CAM-ENTRADA-PRINCIPAL-BLOCO-A",
        )


class TestParseResult(unittest.TestCase):
    def test_sucesso(self):
        status, message = core.parse_result({"success": {"title": "Host added"}})
        self.assertEqual(status, "created")
        self.assertEqual(message, "Host added")

    def test_sucesso_sem_titulo_usa_padrao(self):
        status, message = core.parse_result({"success": {}})
        self.assertEqual(status, "created")
        self.assertEqual(message, "Host added")

    def test_erro_com_mensagens(self):
        payload = {"error": {"title": "Erro", "messages": ["Campo X invalido"]}}
        status, message = core.parse_result(payload)
        self.assertEqual(status, "error")
        self.assertEqual(message, "Campo X invalido")

    def test_erro_junta_multiplas_mensagens(self):
        payload = {"error": {"title": "Erro", "messages": ["Um", "Dois"]}}
        _status, message = core.parse_result(payload)
        self.assertEqual(message, "Um | Dois")

    def test_host_ja_existe_em_ingles(self):
        payload = {"error": {"title": "Erro", "messages": ["Host already exists"]}}
        status, _message = core.parse_result(payload)
        self.assertEqual(status, "exists")

    def test_host_ja_existe_com_acento(self):
        payload = {"error": {"title": "Erro", "messages": ["Já existe um host com este nome"]}}
        status, _message = core.parse_result(payload)
        self.assertEqual(status, "exists")

    def test_resposta_inesperada(self):
        status, message = core.parse_result({})
        self.assertEqual(status, "error")
        self.assertIn("success/error", message)


class TestCameraRecord(unittest.TestCase):
    def test_descricao_e_tags_tem_padrao(self):
        record = make_record()
        self.assertEqual(record.description, "")
        self.assertEqual(record.tags, [])

    def test_nao_existe_mais_coluna_server(self):
        self.assertFalse(hasattr(make_record(), "server"))


class TestBuildFormData(unittest.TestCase):
    def _form(self, record=None, args=None) -> list[tuple[str, str]]:
        return core.build_form_data("TOKEN", record or make_record(), args or make_args())

    def test_campos_basicos(self):
        form = dict(self._form())
        self.assertEqual(form["_csrf_token"], "TOKEN")
        self.assertEqual(form["host"], "CAM-TESTE-01")
        self.assertEqual(form["visiblename"], "CAM-TESTE-01")

    def test_prefixo_e_sufixo(self):
        args = make_args(host_prefix="CAM - ", host_suffix=" - v1")
        form = dict(self._form(args=args))
        self.assertEqual(form["host"], "CAM - CAM-TESTE-01 - v1")

    def test_grupos_e_templates_repetidos(self):
        args = make_args(group_id=["1", "2"], template_id=["10001", "10002"])
        form = self._form(args=args)
        self.assertEqual([v for k, v in form if k == "groups[]"], ["1", "2"])
        self.assertEqual([v for k, v in form if k == "add_templates[]"], ["10001", "10002"])

    def test_interface_usa_porta_e_ip(self):
        form = dict(self._form())
        self.assertEqual(form["interfaces[1][ip]"], "10.0.0.10")
        self.assertEqual(form["interfaces[1][port]"], "10051")

    def test_proxy_presente_quando_informado(self):
        form = dict(self._form(args=make_args(proxy_id="2")))
        self.assertEqual(form["proxy_hostid"], "2")

    def test_proxy_omitido_quando_vazio(self):
        form = dict(self._form(args=make_args(proxy_id="")))
        self.assertNotIn("proxy_hostid", form)

    def test_descricao_enviada_quando_presente(self):
        record = make_record(description="Camera do portao principal")
        form = dict(self._form(record=record))
        self.assertEqual(form["description"], "Camera do portao principal")

    def test_descricao_omitida_quando_vazia(self):
        self.assertNotIn("description", dict(self._form()))

    def test_tags_enviadas_em_indices(self):
        record = make_record(tags=[("site", "MATRIZ"), ("andar", "2")])
        form = dict(self._form(record=record))
        self.assertEqual(form["tags[0][tag]"], "site")
        self.assertEqual(form["tags[0][value]"], "MATRIZ")
        self.assertEqual(form["tags[1][tag]"], "andar")
        self.assertEqual(form["tags[1][value]"], "2")

    def test_sem_tags_quando_lista_vazia(self):
        form = self._form()
        self.assertFalse([k for k, _v in form if k.startswith("tags[")])

    def test_nao_envia_mais_notes_do_servidor(self):
        form = self._form()
        self.assertNotIn("host_inventory[notes]", [k for k, _v in form])

    def test_nome_do_host_e_normalizado(self):
        record = make_record(name="Câmera São João (fundo)")
        form = dict(self._form(record=record))
        self.assertEqual(form["host"], "Camera Sao Joao fundo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
