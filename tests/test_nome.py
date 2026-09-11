"""O nome do produto é Mesa Própria. O antigo (PatrimônioOS) não pode voltar por descuido:
ele aparecia até no User-Agent que o motor manda para o Yahoo e a brapi, ou seja, fora da
máquina do usuário. Guarda mecânica, no mesmo espírito de test_fixtures_nao_carregam_dado_pessoal.

Convenção de grafia: em prosa o produto é "Mesa Própria" (com acento, duas palavras); em
identificador de código, caminho ou User-Agent é "mesa-propria". O NOTICE é a única exceção
— ASCII puro hoje, então ali o nome vai sem acento ("Mesa Propria") para não misturar duas
convenções no mesmo arquivo, regra que test_notice_continua_ascii_puro torna mecânica."""
import re
import subprocess
from pathlib import Path

from po.cotacoes.http import UA

RAIZ = Path(__file__).resolve().parent.parent
ESTE_ARQUIVO = Path(__file__).resolve()
# hífen e underscore são as variantes que um rename descuidado realmente produz
# (patrimonio_os num nome de módulo, patrimônio-os num slug). Espaço fica de fora de propósito:
# "patrimônio os" é sequência que pode aparecer em prosa portuguesa legítima, e ali a guarda
# passaria a barrar commit de texto correto — ganho nulo (zero ocorrências assim hoje) por
# risco de falso positivo real.
ANTIGO = re.compile(r"patrim[oô]nio[-_]?os", re.IGNORECASE)


def _versionados():
    saida = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if saida.returncode != 0:
        raise RuntimeError(
            "varredura da guarda não pôde ser feita: `git ls-files` falhou "
            f"(returncode {saida.returncode}): {saida.stderr.strip()}. "
            "Rode a suíte dentro de um clone git (com .git), não numa árvore copiada sem ele."
        )
    return [RAIZ / p for p in saida.stdout.split("\0") if p]


def test_nome_antigo_nao_aparece_em_arquivo_versionado():
    achados = []
    for caminho in _versionados():
        if caminho.resolve() == ESTE_ARQUIVO or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue           # binário ou ilegível: não é onde o nome mora
        for n, linha in enumerate(texto.splitlines(), start=1):
            if ANTIGO.search(linha):
                achados.append(f"{caminho.relative_to(RAIZ).as_posix()}:{n}: {linha.strip()[:80]}")
    assert achados == [], "nome antigo ainda presente:\n  " + "\n  ".join(achados)


def test_user_agent_carrega_o_nome_novo():
    """O User-Agent sai para fora da máquina, rumo ao Yahoo e à brapi: é o lugar onde um
    nome errado vira constrangimento. Confere o valor importado, não o texto do arquivo —
    um comentário ao lado do literal não é o que sai na rede."""
    assert "mesa-propria" in UA["User-Agent"]


def test_notice_continua_ascii_puro():
    """O NOTICE não tem acento em nenhuma palavra, e é por isso que o nome vai sem acento
    ali. Sem este check, a regra é folclore e o próximo editor 'corrige' a grafia."""
    (RAIZ / "NOTICE").read_bytes().decode("ascii")
