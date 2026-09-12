"""O nome do produto é `jabuti`. Dois nomes mortos não podem voltar por descuido: PatrimônioOS
(do nascimento do repo até 11/09/2026) e Mesa Própria (11/09 a 12/09/2026). Um deles chegou a
aparecer no User-Agent que o motor manda para o Yahoo e a brapi, ou seja, fora da máquina do
usuário. Guarda mecânica, no mesmo espírito de test_fixtures_nao_carregam_dado_pessoal.

Convenção de grafia: `jabuti` é minúsculo, ASCII, uma palavra, em prosa e em identificador.
Não há exceção. A divisão prosa/identificador e a exceção do NOTICE existiam porque o nome
anterior tinha acento; com `jabuti` não há acento a tratar."""
import re
import subprocess
from pathlib import Path

from po.cotacoes.http import UA

RAIZ = Path(__file__).resolve().parent.parent
ESTE_ARQUIVO = Path(__file__).resolve()

# Um padrão por nome morto, porque a mensagem de falha precisa dizer QUAL voltou. As variantes
# com hífen e underscore são as que um rename descuidado realmente produz (patrimonio_os num
# nome de módulo, mesa-propria num slug).
#
# `patrim[oô]nio[-_]?os` deixa o ESPAÇO de fora de propósito: "patrimônio os" aparece em prosa
# portuguesa legítima ("retira do patrimônio os ativos"), e ali a guarda barraria commit de
# texto correto. Aquele nome nunca tomou a forma com espaço.
#
# `mesa[ _-]?pr[oó]pria` INCLUI o espaço obrigatoriamente, porque "Mesa Própria" com espaço era
# a forma canônica. E exige "própria" adjacente: guardar `mesa` sozinho barraria português comum,
# caso de "a mesa da corretora trabalha para a corretora" — frase que usa "mesa" sem nenhum nome
# de produto por perto.
#
# O hífen nunca fica NO MEIO da classe dos dois padrões — no meio ele vira operador de
# intervalo. Vem primeiro em `[-_]` (padrão 1) e por último em `[ _-]` (padrão 2); nas duas
# posições é lido como literal. `[ -_]`, com o hífen no meio, não é "espaço, hífen ou
# underscore": é a faixa 0x20-0x5F, que casa mesaXpropria e mesa9propria.
NOMES_ANTIGOS = [
    (re.compile(r"patrim[oô]nio[-_]?os", re.IGNORECASE), "PatrimônioOS"),
    (re.compile(r"mesa[ _-]?pr[oó]pria", re.IGNORECASE), "Mesa Própria"),
]


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


def test_nome_morto_nao_aparece_em_arquivo_versionado():
    achados = []
    for caminho in _versionados():
        if caminho.resolve() == ESTE_ARQUIVO or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue           # binário ou ilegível: não é onde o nome mora
        for n, linha in enumerate(texto.splitlines(), start=1):
            for padrao, morto in NOMES_ANTIGOS:
                if padrao.search(linha):
                    achados.append(f"{caminho.relative_to(RAIZ).as_posix()}:{n}: "
                                   f"{morto} — {linha.strip()[:70]}")
                    break
    assert achados == [], "nome morto ainda presente:\n  " + "\n  ".join(achados)


def test_a_classe_de_caracteres_nao_virou_faixa():
    """`[ -_]` é a faixa 0x20-0x5F, não "espaço, hífen ou underscore" — o hífen no meio de uma
    classe vira operador de intervalo. Escrito assim, o padrão sem espaço casaria prosa
    portuguesa legítima ("retira do patrimônio os ativos") e o padrão com espaço casaria
    separador arbitrário (mesaXpropria). Este teste fixa as duas pontas nos dois padrões: as
    formas que cada nome morto de fato teve passam, e separador arbitrário ou prosa legítima
    não."""
    padroes = dict((rotulo, p) for p, rotulo in NOMES_ANTIGOS)

    padrao_mesa = padroes["Mesa Própria"]
    for forma in ("mesa propria", "mesa-propria", "mesa_propria", "mesapropria", "Mesa Própria"):
        assert padrao_mesa.search(forma), f"{forma!r} é forma real do nome morto e escapou da guarda"
    for arbitrario in ("mesaXpropria", "mesa9propria", "mesa.propria"):
        assert not padrao_mesa.search(arbitrario), (
            f"{arbitrario!r} casou: a classe de caracteres virou faixa, e a guarda passou a "
            "barrar texto legítimo")

    padrao_patrimonio = padroes["PatrimônioOS"]
    for forma in ("patrimonio-os", "patrimonio_os", "patrimonioos", "PatrimônioOS"):
        assert padrao_patrimonio.search(forma), (
            f"{forma!r} é forma real do nome morto e escapou da guarda")
    for arbitrario in ("patrimonioXos", "patrimonio9os"):
        assert not padrao_patrimonio.search(arbitrario), (
            f"{arbitrario!r} casou: a classe de caracteres virou faixa, e a guarda passou a "
            "barrar texto legítimo")
    assert not padrao_patrimonio.search("retira do patrimônio os ativos"), (
        "casou prosa portuguesa legítima ('retira do patrimônio os ativos'): o espaço entrou "
        "na classe do padrão sem espaço, que existe justamente para não barrar esse texto")


def test_user_agent_carrega_o_nome_novo():
    """O User-Agent sai para fora da máquina, rumo ao Yahoo e à brapi: é o lugar onde um
    nome errado vira constrangimento. Confere o valor importado, não o texto do arquivo —
    um comentário ao lado do literal não é o que sai na rede."""
    assert "jabuti" in UA["User-Agent"]


def test_notice_continua_ascii_puro():
    """O NOTICE é ASCII puro e deve continuar. Este teste NÃO existe mais para justificar
    grafia do nome: `jabuti` não tem acento, então não há exceção a documentar. Ele existe
    porque NOTICE é arquivo de licença, lido por ferramenta e por humano em ambiente que não
    garante UTF-8, e pureza ASCII ali vale por si."""
    (RAIZ / "NOTICE").read_bytes().decode("ascii")
