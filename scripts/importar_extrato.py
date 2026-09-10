"""Importa um documento de corretora para dados/ via mapeamento, com conciliação declarada.

Uso: python scripts/importar_extrato.py <raiz> <arquivo> [--mapeamento NOME|CAMINHO.yaml]
        [--conta ID] [--data AAAA-MM-DD] [--total-declarado VALOR] [--dry-run] [--conferir]

Divisão rígida (GUARDRAILS, camada 1): a LLM escreve o mapeamento e o mostra a você;
este script executa o parse e confere a aritmética do próprio documento. Não bateu,
nada entra em dados/. Sem --mapeamento, tenta detectar pelo cabeçalho entre os
mapeamentos do workspace (mapeamentos/) e do motor.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):   # console cp1252 do Windows não escreve ≤ nem →
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from po.config import carregar_config, moedas_por_conta  # noqa: E402
from po.ingestao.conciliacao import conciliar  # noqa: E402
from po.ingestao.engine import executar  # noqa: E402
from po.ingestao.escrita import conferir, gravar  # noqa: E402
from po.ingestao.leitores import DependenciaAusente, ler_tabela  # noqa: E402
from po.ingestao.mapeamento import carregar_mapeamento, detectar_mapeamento, resolver_mapeamento  # noqa: E402
from po.numeros import parse_valor  # noqa: E402


def _mensagem_os(e: OSError, raiz: str | Path) -> str:
    """PermissionError/IsADirectoryError etc. viram frase acionável, com caminho relativo ao
    workspace quando possível — não um repr de exceção nem um traceback. FileNotFoundError é
    irmã de PermissionError (não mãe): quem chama tem que pegar OSError, não só a primeira."""
    caminho = e.filename or str(e)
    try:
        caminho = Path(caminho).resolve().relative_to(Path(raiz).resolve()).as_posix()
    except (ValueError, TypeError, OSError):
        pass
    motivo = e.strerror or str(e)
    return (f"erro: não consegui ler/gravar {caminho} ({motivo}). "
           "O arquivo está aberto no Excel ou o OneDrive está sincronizando?")


def _motor(raiz: Path, cfg: dict) -> Path:
    m = Path(str(cfg["caminhos"]["motor"]))
    return m if m.is_absolute() else (raiz / m).resolve()


def _descrever(mapa: dict, caminho: Path) -> list[str]:
    verificado = "sim" if mapa.get("verificado-contra-export-real") else "NÃO (contribua uma fixture)"
    out = [f"Mapeamento: {mapa['nome']} ({caminho}) · verificado contra export real: {verificado}",
           "  Colunas: " + ", ".join(f"{ap} ← {col!r}" for ap, col in mapa["colunas"].items())]
    for regra in mapa["linhas"]:
        cond = " e ".join(f"{ap} ~ /{rx}/" for ap, rx in regra["quando"].items())
        alvo = regra["destino"]
        if alvo == "ignorar":
            alvo += f" ({regra.get('motivo')})"
        elif alvo == "ajuste":
            alvo += f" em {regra.get('aplica-em')}.{regra.get('campo', 'valor_liquido')}"
        out.append(f"  {cond} → {alvo}")
    out.append(f"  Conciliação: {mapa['conciliacao']['tipo']}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="raiz do workspace")
    ap.add_argument("arquivo", help="documento exportado da corretora (csv ou xlsx), normalmente em inbox/")
    ap.add_argument("--mapeamento", help="nome em mapeamentos/ ou caminho .yaml (default: detectar pelo cabeçalho)")
    ap.add_argument("--conta", help="id da conta na config (default: o do mapeamento)")
    ap.add_argument("--data", help="AAAA-MM-DD para documentos sem coluna de data (ex.: posições)")
    ap.add_argument("--total-declarado", help="total lido por VOCÊ no documento/corretora, quando o mapeamento pede")
    ap.add_argument("--dry-run", action="store_true", help="executa e concilia, não grava")
    ap.add_argument("--conferir", action="store_true", help="compara o documento com dados/, não grava")
    args = ap.parse_args()
    raiz = Path(args.raiz).resolve()
    arquivo = Path(args.arquivo)
    try:
        cfg = carregar_config(raiz)
        motor = _motor(raiz, cfg)
        if args.mapeamento:
            caminho_mapa = resolver_mapeamento(args.mapeamento, raiz, motor)
        else:
            caminho_mapa = detectar_mapeamento(arquivo, raiz, motor)
            if caminho_mapa is None:
                raise ValueError("nenhum mapeamento conhecido casa com este documento — rode "
                                 "scripts/inspecionar_extrato.py, escreva um mapeamento em mapeamentos/ "
                                 "e passe --mapeamento")
        mapa = carregar_mapeamento(caminho_mapa)
        conta = args.conta or mapa["conta"]
        moedas = moedas_por_conta(cfg)
        if conta not in moedas:
            raise ValueError(f"conta {conta!r} não declarada na config (contas: {sorted(moedas)}) — passe --conta")
        if moedas[conta] != mapa["moeda"]:
            raise ValueError(f"mapeamento declara moeda {mapa['moeda']} mas a conta {conta} é {moedas[conta]}")
        total = None
        if args.total_declarado is not None:
            total = parse_valor(args.total_declarado)
            if total is None:
                raise ValueError(f"--total-declarado inválido: {args.total_declarado!r}")
        tabela = ler_tabela(arquivo, mapa["arquivo"])
    except (DependenciaAusente, FileNotFoundError, ValueError) as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        print(_mensagem_os(e, raiz))
        sys.exit(1)

    for linha in _descrever(mapa, caminho_mapa):
        print(linha)
    res = executar(mapa, tabela, conta=conta, data_padrao=args.data)
    erros, descricao = list(res.erros), ""
    if not erros:
        errs, descricao = conciliar(mapa, tabela, res, total)
        erros.extend(errs)
    print(f"\nLinhas: {res.linhas_lidas} lidas · {res.classificadas} classificadas · {len(res.ignoradas)} ignoradas")
    for nome, regs in res.registros.items():
        if regs:
            print(f"  {nome}: {len(regs)}")
    if args.dry_run:
        sem_uso = [i for i, c in res.acertos.items() if c == 0]
        if sem_uso:
            print(f"  aviso: regra(s) {sem_uso} de 'linhas' nunca casaram com nenhuma linha do documento")
    if erros:
        print("\nERROS — nada gravado:")
        for e in erros:
            print(f"  ERRO {e}")
        sys.exit(1)
    print(f"Conciliação OK — {descricao}")
    if args.conferir:
        print("\nConferência contra dados/ (nada gravado):")
        try:
            for linha in conferir(raiz, res):
                print(linha)
        except ValueError as e:
            print(f"erro: {e}")
            sys.exit(1)
        except OSError as e:
            print(_mensagem_os(e, raiz))
            sys.exit(1)
        return
    if args.dry_run:
        print("\n--dry-run: nada gravado.")
        return
    try:
        r = gravar(raiz, res, mapeamento=mapa["nome"], arquivo=arquivo.name, conciliacao=descricao, conta=conta)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        print(_mensagem_os(e, raiz))
        sys.exit(1)
    novas = ", ".join(f"{t} +{n}" for t, n in r["gravadas"].items() if n)
    dup = ", ".join(f"{t} {n}" for t, n in r["duplicadas"].items() if n)
    print("\n" + (f"Gravado em dados/: {novas}" if novas else "Nada novo para gravar (tudo já estava em dados/)")
          + (f" · duplicadas puladas: {dup}" if dup else ""))
    print(f"Log: {r['log'].relative_to(raiz).as_posix()}")
    print(f"Agora rode: python {motor / 'scripts' / 'validar_workspace.py'} {raiz}")


if __name__ == "__main__":
    main()
