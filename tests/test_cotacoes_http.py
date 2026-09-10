import http.client
import io
import json
import socket
import urllib.error

import pytest

from po.cotacoes import http as po_http
from po.cotacoes.tipos import RespostaInvalida, SemRede


class _Resposta(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _urlopen(monkeypatch, efeito):
    def falso(req, timeout=None):
        resultado = efeito(req)
        if isinstance(resultado, Exception):
            raise resultado
        return _Resposta(resultado)
    monkeypatch.setattr(po_http.urllib.request, "urlopen", falso)


def _erro_http(codigo, corpo=b""):
    return urllib.error.HTTPError("u", codigo, "erro", {}, io.BytesIO(corpo))


def test_json_ok(monkeypatch):
    _urlopen(monkeypatch, lambda req: b'{"a": 1}')
    assert po_http.buscar_json("http://x") == {"a": 1}


def test_http_de_erro_vira_resposta_invalida_com_detalhe(monkeypatch):
    _urlopen(monkeypatch, lambda req: _erro_http(404, b"No data found, symbol may be delisted"))
    with pytest.raises(RespostaInvalida, match="404"):
        po_http.buscar_json("http://x")


def test_rede_caida_vira_sem_rede(monkeypatch):
    _urlopen(monkeypatch, lambda req: urllib.error.URLError(socket.gaierror("getaddrinfo failed")))
    with pytest.raises(SemRede):
        po_http.buscar_json("http://x")


def test_conexao_cortada_no_meio_do_corpo_vira_sem_rede(monkeypatch):
    _urlopen(monkeypatch, lambda req: http.client.IncompleteRead(b"parcial"))
    with pytest.raises(SemRede):
        po_http.buscar_json("http://x")


def test_corpo_nao_json_e_nao_utf8(monkeypatch):
    _urlopen(monkeypatch, lambda req: b"<html>erro</html>")
    with pytest.raises(RespostaInvalida, match="não é JSON"):
        po_http.buscar_json("http://x")
    _urlopen(monkeypatch, lambda req: b"\xff\xfe")
    with pytest.raises(RespostaInvalida):
        po_http.buscar_json("http://x")


def test_nan_no_corpo_e_recusado(monkeypatch):
    _urlopen(monkeypatch, lambda req: b'{"preco": NaN}')
    with pytest.raises(RespostaInvalida, match="NaN"):
        po_http.buscar_json("http://x")


def test_429_tenta_de_novo_uma_vez(monkeypatch):
    chamadas = []

    def efeito(req):
        chamadas.append(1)
        return b'{"ok": true}' if len(chamadas) > 1 else _erro_http(429)
    _urlopen(monkeypatch, efeito)
    dormidas = []
    assert po_http.buscar_json("http://x", dormir=dormidas.append) == {"ok": True}
    assert len(chamadas) == 2 and dormidas == [po_http.PAUSA_RETENTATIVA]


def test_429_persistente_desiste(monkeypatch):
    _urlopen(monkeypatch, lambda req: _erro_http(429))
    with pytest.raises(RespostaInvalida, match="429"):
        po_http.buscar_json("http://x", dormir=lambda s: None)


def test_user_agent_do_chamador_vence(monkeypatch):
    vistos = {}

    def efeito(req):
        vistos.update(req.headers)
        return b"{}"
    _urlopen(monkeypatch, efeito)
    po_http.buscar_json("http://x", headers={"User-Agent": "meu-agente"})
    assert vistos.get("User-agent") == "meu-agente"
