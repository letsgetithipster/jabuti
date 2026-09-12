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

# `po/` é o pacote do motor, resíduo deliberado do primeiro nome morto (PatrimônioOS).
# Renomeá-lo é task própria; a convenção de grafia deste arquivo não se aplica a ele.
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
# `mesa[\s_-]*pr[oó]pria(?!mente)` INCLUI espaço — e qualquer whitespace, quebra de linha
# inclusive, com `*` em vez de `?`: markdown fecha parágrafo com dois espaços antes do `\n`,
# então "mesa  \nprópria" tem três caracteres de separador, e só `*` cobre isso. Essa assimetria
# com o padrão 1 é essencial, não cosmética: "Mesa Própria" com espaço era a forma canônica, e a
# prosa deste repo é hard-wrapped, então reembrulhar parágrafo é o jeito mais provável de o nome
# voltar por descuido. O padrão 1 continua sem `\s` porque nele é o espaço que precisa ficar
# de fora.
#
# `(?!mente)` no fim exclui "propriamente": "a mesa propriamente dita" é prosa técnica comum,
# não resíduo de nome. `\b` foi cogitado e descartado — mataria `mesa_propria_config` e
# `patrimonio_os_extrato`, que são resíduo real e precisam continuar batendo.
#
# E exige "própria" adjacente: guardar `mesa` sozinho barraria português comum, caso de
# "a mesa da corretora trabalha para a corretora" — frase que usa "mesa" sem nenhum nome de
# produto por perto.
#
# O hífen nunca fica NO MEIO de uma classe de caracteres — no meio ele vira operador de
# intervalo. Vem primeiro em `[-_]` (padrão 1) e por último em `[\s_-]` (padrão 2); nas duas
# posições é lido como literal. `[ -_]`, com o hífen no meio, não é "espaço, hífen ou
# underscore": é a faixa 0x20-0x5F, que casaria mesaXpropria e mesa9propria.
NOMES_ANTIGOS = [
    (re.compile(r"patrim[oô]nio[-_]?os", re.IGNORECASE), "PatrimônioOS"),
    (re.compile(r"mesa[\s_-]*pr[oó]pria(?!mente)", re.IGNORECASE), "Mesa Própria"),
]


def _versionados():
    try:
        saida = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as erro:
        raise RuntimeError(
            "varredura da guarda não pôde ser feita: `git` não foi encontrado no PATH "
            f"({erro}). Instale o git e garanta que ele está acessível na sessão."
        ) from erro
    if saida.returncode != 0:
        raise RuntimeError(
            "varredura da guarda não pôde ser feita: `git ls-files` falhou "
            f"(returncode {saida.returncode}): {saida.stderr.strip()}. "
            "Rode a suíte dentro de um clone git (com .git), não numa árvore copiada sem ele."
        )
    return [RAIZ / p for p in saida.stdout.split("\0") if p]


def test_nome_morto_nao_aparece_em_arquivo_versionado():
    versionados = _versionados()
    assert ESTE_ARQUIVO in {p.resolve() for p in versionados}, (
        f"a varredura não enxergou o próprio arquivo da guarda: `git ls-files` respondeu, mas "
        f"listou {len(versionados)} arquivos. Índice vazio ou truncado — este verde não vale. "
        "Rode a suíte num clone com o índice populado.")

    achados = []
    for caminho in versionados:
        rel = caminho.relative_to(RAIZ).as_posix()
        for padrao, morto in NOMES_ANTIGOS:
            if padrao.search(rel):
                achados.append(f"{rel}: {morto} no NOME do arquivo")

        if caminho.resolve() == ESTE_ARQUIVO or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue           # binário ou ilegível: não é onde o nome mora
        for padrao, morto in NOMES_ANTIGOS:
            for m in padrao.finditer(texto):
                linha = texto.count("\n", 0, m.start()) + 1
                trecho = texto[max(0, m.start() - 20):m.end() + 30].replace("\n", "⏎").strip()
                achados.append(f"{rel}:{linha}: {morto} — {trecho}")
    assert achados == [], "nome morto ainda presente:\n  " + "\n  ".join(achados)


def test_o_nome_novo_e_sempre_minusculo():
    """A docstring do módulo declara a convenção de grafia. Sem este teste ela é só uma frase,
    e frase não impede `Jabuti` de entrar no próximo doc escrito em começo de período."""
    padrao = re.compile(r"jabut[ií]", re.IGNORECASE)
    achados = []
    for caminho in _versionados():
        if caminho.resolve() == ESTE_ARQUIVO or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue           # binário ou ilegível: não é onde o nome mora
        rel = caminho.relative_to(RAIZ).as_posix()
        for m in padrao.finditer(texto):
            if m.group() != "jabuti":
                linha = texto.count("\n", 0, m.start()) + 1
                achados.append(f"{rel}:{linha}: grafia {m.group()!r}, esperado 'jabuti'")
    assert achados == [], "grafia do nome fora da convenção:\n  " + "\n  ".join(achados)


def test_a_classe_de_caracteres_nao_virou_faixa():
    """Fixa os dois padrões: cada forma real do nome morto passa, e separador arbitrário ou
    prosa legítima (`propriamente`, `mesa` sem `própria` adjacente) não."""
    padroes = {rotulo: p for p, rotulo in NOMES_ANTIGOS}

    padrao_mesa = padroes["Mesa Própria"]
    for forma in ("mesa propria", "mesa-propria", "mesa_propria", "mesapropria", "Mesa Própria"):
        assert padrao_mesa.search(forma), f"{forma!r} é forma real do nome morto e escapou da guarda"
    for arbitrario in ("mesaXpropria", "mesa9propria", "mesa.propria"):
        assert not padrao_mesa.search(arbitrario), (
            f"{arbitrario!r} casou: a classe de caracteres virou faixa, e a guarda passou a "
            "barrar texto legítimo")
    assert not padrao_mesa.search("a mesa propriamente dita fica na corretora"), (
        "casou 'propriamente': falta o lookahead, e a guarda barra prosa técnica comum")
    assert not padrao_mesa.search("a mesa da corretora trabalha para a corretora"), (
        "casou 'mesa' sem 'própria' adjacente: a guarda passou a barrar português comum")

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
