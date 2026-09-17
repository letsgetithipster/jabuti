"""Encanamento comum dos CLIs: mensagem de erro de arquivo e console que aguenta pt-BR.

Existia copiado em quatro scripts. Um fato mora em um lugar só: quando a frase melhorar
(ou quando aparecer mais uma causa comum de arquivo travado), ela melhora em todos.
"""
import sys
from pathlib import Path


def preparar_console() -> None:
    """Console cp1252 do Windows não escreve ≤ nem →, e o pre-commit roda estes CLIs:
    sem isto o script morre com UnicodeEncodeError em vez de imprimir a frase."""
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")


def caminho_do_erro(e: OSError, raiz: str | Path | None = None, padrao: str = "") -> str:
    """Qual arquivo o OSError acusa, relativo ao workspace quando `raiz` é dada.

    Fora do workspace (ou sem `raiz`), fica absoluto — melhor um caminho longo que um
    caminho errado. OSError nem sempre traz `filename`; daí o `padrao`."""
    caminho = e.filename or padrao or str(e)
    if raiz is not None:
        try:
            caminho = Path(caminho).resolve().relative_to(Path(raiz).resolve()).as_posix()
        except (ValueError, TypeError, OSError):
            pass
    return caminho


def mensagem_os(e: OSError, raiz: str | Path | None = None, padrao: str = "") -> str:
    """PermissionError/IsADirectoryError etc. viram frase acionável, com caminho relativo ao
    workspace quando `raiz` é dada — não um repr de exceção nem um traceback. FileNotFoundError
    é irmã de PermissionError (não mãe): quem chama tem que pegar OSError, não só a primeira."""
    caminho = caminho_do_erro(e, raiz, padrao)
    motivo = e.strerror or str(e)
    return (f"erro: não consegui ler/gravar {caminho} ({motivo}). "
            "O arquivo está aberto no Excel ou o OneDrive está sincronizando?")


def caminho_motor(raiz: str | Path, cfg: dict) -> Path:
    """Raiz do motor declarada em `caminhos.motor`, absolutizada contra o workspace.

    Vivia copiada dentro de importar_extrato.py, e todo CLI que imprime "agora rode ..."
    precisa dela: um fato mora em um lugar só."""
    m = Path(str(cfg["caminhos"]["motor"]))
    return m if m.is_absolute() else (Path(raiz) / m).resolve()
