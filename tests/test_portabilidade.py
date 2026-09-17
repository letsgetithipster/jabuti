"""A fronteira entre o motor e a máquina — a única que a suíte nunca exercitou, porque até aqui
ela rodou só na máquina do autor, em win32, pelo pre-commit.

Dois invariantes, os dois medidos como defeito ANTES de virarem teste:

1. **Texto gerado nasce com LF.** Os seis `write_text` de `scripts/` gravavam sem declarar
   `newline`, então o Python traduzia `\n` para `\r\n` no Windows e não traduzia no Linux: o
   mesmo comando, bytes diferentes por plataforma. E o `.gitattributes` do workspace declara
   `*.md text eol=lf`, então no Windows rodar o primeiro comando do README deixava `git status`
   sujo num clone recém-feito, com `git diff` VAZIO — a pior forma de sujeira, porque não há o
   que ler no diff para entender o que aconteceu.

2. **O exemplo é reproduzível byte a byte.** O exemplo versionado é hoje a melhor documentação
   do repo (lê-se no GitHub sem clonar) e é o que a demo da primeira tela do README executa. Se
   o gerador deixar de produzi-lo exatamente, ou o exemplo apodreceu ou o gerador mudou, e nos
   dois casos alguém precisa decidir — não descobrir depois do anúncio.

A data de referência da comparação vem do PRÓPRIO arquivo, nunca de `today()`: ancorar no
calendário deixaria este teste vermelho todo dia seguinte ao da geração, com erro que não
corresponde a defeito de dado nenhum.
"""
import ast
import datetime
from pathlib import Path

from po.estado import gerar_estado
from po.frontmatter import extrair_frontmatter

RAIZ = Path(__file__).resolve().parent.parent
EXEMPLO = RAIZ / "exemplos" / "workspace-exemplo"
ESTADO_DO_EXEMPLO = EXEMPLO / "estado" / "ESTADO.md"


def _write_text_sem_newline() -> list[str]:
    """Chamadas `.write_text(...)` em `scripts/` que não declaram `newline`.

    AST e não regex: metade das chamadas é multilinha (o log de importação monta o texto em doze
    linhas de concatenação e fecha o `encoding=` lá embaixo), e regex sobre linha não enxerga um
    kwarg que está dezoito linhas abaixo do nome da função.
    """
    achados = []
    for caminho in sorted((RAIZ / "scripts").rglob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                    and no.func.attr == "write_text"
                    and not any(k.arg == "newline" for k in no.keywords)):
                achados.append(f"{caminho.relative_to(RAIZ).as_posix()}:{no.lineno}")
    return achados


def test_todo_escritor_de_texto_do_motor_declara_newline():
    achados = _write_text_sem_newline()
    assert achados == [], (
        "estas chamadas gravam texto sem declarar newline, e portanto gravam CRLF no Windows e "
        "LF no Linux — o mesmo comando, bytes diferentes:\n  " + "\n  ".join(achados) +
        '\nUse write_text(..., encoding="utf-8", newline="\\n"). CSV não entra nesta conta: '
        "`po.csvs` já abre com newline='' como o módulo csv exige.")


def test_o_estado_do_exemplo_e_reproduzivel_byte_a_byte(tmp_path):
    """Regenera o ESTADO do exemplo numa cópia e compara os BYTES com o arquivo versionado.

    Bytes, não texto: `read_text` normaliza fim de linha e esconderia exatamente o defeito que
    este teste existe para pegar.
    """
    from test_validar_dados import copia_exemplo

    meta, _ = extrair_frontmatter(ESTADO_DO_EXEMPLO.read_text(encoding="utf-8-sig"))
    data = meta.get("data-referencia")
    assert isinstance(data, datetime.date), (
        f"data-referencia do ESTADO do exemplo é {data!r}; este teste ancora nela, e sem ela não "
        "há como reproduzir o arquivo sem depender do calendário")

    ws = copia_exemplo(tmp_path)
    (ws / "estado" / "ESTADO.md").unlink()
    gerar_estado(ws, hoje=data)
    produzido = (ws / "estado" / "ESTADO.md").read_bytes()
    versionado = ESTADO_DO_EXEMPLO.read_bytes()
    crlf_produzido = produzido.count(b"\r\n")
    crlf_versionado = versionado.count(b"\r\n")
    assert produzido == versionado, (
        "o ESTADO.md versionado do exemplo não é o que o gerador produz hoje.\n"
        f"CRLF no produzido: {crlf_produzido}; no versionado: {crlf_versionado}.\n"
        "Se só o fim de linha difere, o defeito é o escritor (veja o teste acima). Se o conteúdo "
        "difere, regenere o exemplo com `python scripts/gerar_estado.py exemplos/workspace-exemplo "
        f"--data {data.isoformat()}` e commite o resultado.")
