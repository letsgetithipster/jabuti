"""Ingestão a partir de resposta de provider de open finance, em contraste com documento baixado.

O contrato dos campos vem da especificação do Open Finance Brasil, nunca do formato que um
provider devolve: provider é adaptador, não é o tipo. Nenhum campo de `dados/` pode ter nome
ou semântica herdada de fornecedor.

Três coisas são obrigatórias aqui e não eram na ingestão de documento, porque documento baixado
é prova de si mesmo e resposta de API não é:

1. O payload cru vira artefato. Se o número não é reproduzível amanhã, o payload é a única prova.
2. A data de referência do provider é gravada separada da data de importação.
3. O status de sincronização é precondição, não linha de relatório.
"""
import json
import re
from pathlib import Path

from po.ingestao.artefatos import caminho_datado_livre

# Só este status conta como "sincronizou". Qualquer outro, inclusive desconhecido, para a rodada:
# o vocabulário é do provider e muda sem aviso, e tratar desconhecido como OK é como tratar
# lista vazia como zero.
#
# Medido em 12/09/2026 contra o MCP da Finnest: o valor é "CONNECTED", não "OK". "OK" era palpite
# de quem escreveu a precondição antes de existir resposta para olhar, e o palpite é pior que o
# erro comum — ele reprova TODA conexão saudável, e a rodada aborta sempre, com uma frase dizendo
# ao usuário para reconectar uma conta que está conectada. Vocabulário conhecido, e o que cada um
# significa, está em docs/provider-finnest.md.
STATUS_OK = "CONNECTED"

# Nome de provider entra no CAMINHO do artefato, então ele é slug, não texto livre.
SLUG_PROVIDER = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def arquivar_payload(raiz: str | Path, provider: str, bruto: dict, hoje) -> Path:
    """Grava a resposta crua em logs/importacoes/AAAA-MM-DD-<provider>.json e devolve o caminho.

    Duas rodadas no mesmo dia não se sobrescrevem: a segunda sincronização é outro evento e
    outra prova, do mesmo jeito que duas importações do mesmo extrato são dois logs.

    `bruto` é o objeto que saiu de `json.loads` da resposta, logo serializável por construção —
    o mesmo raciocínio de contrato que vale para `conciliar_resposta`. Quem chama trata
    `ValueError`: se o payload não pode ser arquivado, a rodada **aborta**, porque ele é a única
    prova do número, e ingerir dado cuja prova se perdeu é pior que não ingerir.
    """
    if not SLUG_PROVIDER.match(provider or ""):
        raise ValueError(
            f"nome de provider inválido: {provider!r}. Use minúsculas, dígitos e hífen (ex.: "
            "'finnest'). O nome entra no caminho do artefato, e um separador ali faria o payload "
            "cair fora de logs/importacoes/, onde ninguém o encontraria depois")
    caminho = caminho_datado_livre(Path(raiz) / "logs" / "importacoes",
                                   f"{hoje.isoformat()}-{provider}", ".json")
    caminho.write_text(json.dumps(bruto, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    return caminho


def conferir_status(conexoes: list[dict]) -> list[str]:
    """Erros de sincronização, um por conexão degradada. Lista vazia = tudo sincronizado.

    Precondição da ingestão, não informação do relatório: conta que parou de sincronizar devolve
    lista vazia SEM erro, e o patrimônio encolhe em silêncio. Lacuna nunca é zero.

    `conexoes` vem da resposta do provider, que é a entrada menos confiável do sistema: aqui nada
    levanta, tudo vira frase. Conexão cujo status não dá para ler não é conexão sincronizada, e
    cai na mesma regra do status desconhecido.
    """
    if not conexoes or not isinstance(conexoes, list):
        return ["nenhuma conexão de open finance configurada — conecte uma conta antes de importar"]
    erros = []
    for i, c in enumerate(conexoes, start=1):
        if not isinstance(c, dict):
            erros.append(f"conexão {i} veio como {type(c).__name__}, não como objeto com status — "
                         "resposta do provider fora do formato esperado; não dá para afirmar que "
                         "essa conta sincronizou, e conta não confirmada não entra na rodada")
            continue
        status = c.get("status")
        if status != STATUS_OK:
            # `name` está na chain porque é a chave que o provider realmente usa (medido em
            # 12/09/2026); sem ela a frase cai no `id` e manda o usuário reconectar um UUID.
            nome = c.get("nome") or c.get("name") or c.get("id") or f"(sem nome, posição {i})"
            if not isinstance(nome, str):
                nome = f"(nome ilegível, posição {i})"
            erros.append(f"conexão {nome} com status {status!r} em vez de {STATUS_OK!r} — "
                         "reconecte no app do provider antes de importar; conta fora do ar "
                         "devolve lista vazia sem erro e some da sua carteira em silêncio")
    return erros
