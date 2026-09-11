"""Única camada de rede do motor. Tudo que busca cotação passa por buscar_json."""
import http.client
import json
import time
import urllib.error
import urllib.request

from po.cotacoes.tipos import RespostaInvalida, SemRede

UA = {"User-Agent": "Mozilla/5.0 (mesa-propria)"}
TENTATIVAS = 2           # a fonte pública responde 429 em rajada; uma segunda chance basta
PAUSA_RETENTATIVA = 2.0  # segundos
TRANSITORIOS = {429, 500, 502, 503, 504}


def _constante_nao_numerica(c):
    raise RespostaInvalida(f"resposta com {c} (não é número): a fonte não devolveu preço utilizável")


def buscar_json(url: str, timeout: float = 15.0, headers: dict | None = None, dormir=time.sleep):
    """GET url e devolve o JSON. SemRede se não alcançou a fonte (rede, DNS, conexão cortada);
    RespostaInvalida se alcançou mas a resposta não serve (HTTP de erro, corpo não-JSON,
    NaN/Infinity). HTTP transitório (429, 5xx) é tentado de novo uma vez antes de desistir."""
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                corpo = resp.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in TRANSITORIOS and tentativa < TENTATIVAS:
                dormir(PAUSA_RETENTATIVA)
                continue
            detalhe = _detalhe(e)
            raise RespostaInvalida(f"HTTP {e.code}" + (f": {detalhe}" if detalhe else "")) from e
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            raise SemRede(str(e)) from e
    else:
        raise SemRede(f"esgotou {TENTATIVAS} tentativas sem obter resposta")
    try:
        return json.loads(corpo.decode("utf-8"), parse_constant=_constante_nao_numerica)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise RespostaInvalida(f"resposta não é JSON ({e})") from e


def _detalhe(e: urllib.error.HTTPError) -> str:
    """Corpo do erro HTTP, quando a fonte explica o motivo (o yahoo diz 'symbol may be delisted')."""
    try:
        return e.read().decode("utf-8", errors="replace").strip()[:120]
    except (OSError, ValueError):
        return ""
