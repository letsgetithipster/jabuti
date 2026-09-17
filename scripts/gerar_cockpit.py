"""Gera o cockpit xlsx (LEIAME, Posições, Blocos) a partir de dados/ e da política.

Uso: python scripts/gerar_cockpit.py <raiz>

Regenerável e não versionado; caminho em vault.config.yaml (caminhos.planilhas). Exige openpyxl
(pip install -r requirements-xlsx.txt).

Códigos de saída:
  0  cockpit gerado
  1  openpyxl ausente, dados/ ou política inconsistente, ou arquivo ilegível/travado
  2  uso inválido (argumento faltando ou desconhecido)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*: se um deles
                     # quebrar, o traceback ainda sai legível no cp1252

from po.cockpit import gerar_cockpit  # noqa: E402
from po.ingestao.leitores import DependenciaAusente  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    if not raiz.is_dir():   # mesma frase do validador e do gerar_estado
        print(f"erro: workspace {args.raiz} não existe")
        sys.exit(1)
    try:
        caminho = gerar_cockpit(raiz)
    except DependenciaAusente as e:
        print(f"erro: {e}")
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        # OSError e não PermissionError: no Windows o arquivo aberto no Excel dá PermissionError,
        # mas em Linux e macOS um diretório no lugar do arquivo dá IsADirectoryError, e disco cheio
        # dá OSError puro. Pegar só a primeira deixava as outras virarem traceback.
        print(mensagem_os(e, raiz))
        sys.exit(1)
    print(f"Cockpit gerado: {caminho}")
    print("Nada nele é editável: tudo regenera a cada execução. A fila do aporte: "
          "python scripts/consultar_aporte.py <raiz> VALOR")


if __name__ == "__main__":
    main()
