"""Nomeação de artefato datado em `logs/importacoes/`.

Um fato, uma casa. A regra — *basename datado, e repetição no mesmo dia vira `-2`, `-3`* — vale
para o log de importação de documento (`escrita.py`) e para o payload cru de provider
(`provider.py`), que gravam na MESMA pasta. Enquanto era cópia, mudar o esquema de sufixo num
lado deixava o outro para trás em silêncio.
"""
from pathlib import Path


def caminho_datado_livre(pasta: str | Path, base: str, sufixo: str) -> Path:
    """Primeiro caminho livre em `pasta` para `<base><sufixo>`, `<base>-2<sufixo>`, etc.

    Cria a pasta se não existir. Duas rodadas no mesmo dia não se sobrescrevem: a segunda
    importação é outro evento e outra prova, e o registro da primeira não é rascunho.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho, k = pasta / f"{base}{sufixo}", 2
    while caminho.exists():
        caminho = pasta / f"{base}-{k}{sufixo}"
        k += 1
    return caminho
