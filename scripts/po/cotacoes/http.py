"""Única camada de rede do motor. Tudo que busca cotação passa por buscar_json."""
import json
import socket
import urllib.error
import urllib.request

from po.cotacoes.tipos import RespostaInvalida, SemRede

UA = {"User-Agent": "Mozilla/5.0 (PatrimonioOS)"}


def buscar_json(url: str, timeout: float = 15.0, headers: dict | None = None):
    """GET url e devolve o JSON. SemRede se não alcançou a fonte; RespostaInvalida se
    alcançou mas a resposta não serve (HTTP de erro, corpo não-JSON)."""
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = resp.read()
    except urllib.error.HTTPError as e:
        raise RespostaInvalida(f"HTTP {e.code}") from e
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
        raise SemRede(str(e)) from e
    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RespostaInvalida(f"resposta não é JSON ({e})") from e
