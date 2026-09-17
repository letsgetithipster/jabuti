"""Importa um documento de corretora para dados/ via mapeamento, com conciliação declarada.

Uso: python scripts/importar_extrato.py <raiz> <arquivo> [--mapeamento NOME|CAMINHO.yaml]
        [--conta ID] [--data AAAA-MM-DD] [--total-declarado VALOR] [--dry-run] [--conferir]

Divisão rígida (GUARDRAILS, camada 1): a LLM escreve o mapeamento e o mostra a você;
este script executa o parse e confere a aritmética do próprio documento. Não bateu,
nada entra em dados/. Sem --mapeamento, tenta detectar pelo cabeçalho entre os
mapeamentos do workspace (mapeamentos/) e do motor.

Códigos de saída: 0 importou (ou --dry-run/--conferir sem divergência)
· 1 erro que impediu a rodada: config, mapeamento, leitura, conciliação ou gravação. Nada entra em
  dados/ sem a conciliação passar; a única exceção é a gravação que morre no meio (arquivo travado,
  disco cheio), e aí o texto e o log de importação nomeiam tabela por tabela o que chegou a entrar
· 2 uso inválido da linha de comando (argparse)
· 3 --conferir achou divergência entre o documento e dados/ (nada gravado; não é erro de execução)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from po.cli import caminho_motor, mensagem_os, preparar_console  # noqa: E402

preparar_console()   # antes dos demais imports de po.*: se um deles
                     # quebrar, o traceback ainda sai legível no cp1252

from po.ativos import ler_ativos  # noqa: E402
from po.config import carregar_config, moedas_por_conta  # noqa: E402
from po.csvs import ler_csv, ultimas_cotacoes  # noqa: E402
from po.ingestao.conciliacao import conciliar  # noqa: E402
from po.ingestao.engine import executar  # noqa: E402
from po.ingestao.escrita import GravacaoParcial, conferir, gravar  # noqa: E402
from po.ingestao.leitores import DependenciaAusente, ler_tabela  # noqa: E402
from po.ingestao.mapeamento import carregar_mapeamento, detectar_mapeamento, resolver_mapeamento  # noqa: E402
from po.ledger import posicoes_de_fills  # noqa: E402
from po.numeros import parse_valor  # noqa: E402


def _sem_cotacao(raiz: Path) -> list[str]:
    """Tickers da carteira DERIVADA (fills + eventos + ativos) sem nenhuma cotação em dados/.
    É exatamente o que o validador vai acusar; ler dados/ depois da gravação, em vez de olhar o
    que esta rodada gravou, cobre a rodada de recuperação (o fill entrou na tentativa anterior)
    e não lembra de cotar ticker cuja venda zerou a posição. Qualquer leitura suja devolve
    vazio: quem acusa dado sujo é o validador, não este lembrete."""
    lidas = {}
    for nome in ("fills", "eventos", "cotacoes"):
        linhas, erros = ler_csv(nome, raiz / "dados" / f"{nome}.csv")
        if erros:
            return []
        lidas[nome] = linhas
    classes, erros, _ = ler_ativos(raiz)
    if erros:
        return []
    derivadas, _ = posicoes_de_fills(lidas["fills"], lidas["eventos"], classes)
    cotadas = ultimas_cotacoes(lidas["cotacoes"])
    return sorted({p["ticker"] for p in derivadas if p["ticker"] not in cotadas})


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
        motor = caminho_motor(raiz, cfg)
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
        print(mensagem_os(e, raiz))
        sys.exit(1)

    for linha in _descrever(mapa, caminho_mapa):
        print(linha)
    res = executar(mapa, tabela, conta=conta, data_padrao=args.data)
    # `res.erros` primeiro: documento vazio E coluna renomeada mostraria a frase genérica de vazio
    # no lugar do erro preciso, que é o que resolve o problema do usuário.
    if res.linhas_lidas == 0 and not res.erros:
        # sem isto o usuário via "0 lidas · 0 classificadas", a conciliação passava vazia e a
        # rodada terminava dizendo que nada havia a gravar — como se o documento estivesse em dia
        print(f"\nerro: nenhuma linha de dados abaixo do cabeçalho em {arquivo.name} — nada a importar. "
              "Costuma ser aba errada, cabeçalho que o mapeamento não encontrou, ou export salvo "
              f"em branco. Rode: python scripts/inspecionar_extrato.py {arquivo} para ver as abas, "
              "o cabeçalho e as primeiras linhas do arquivo.")
        sys.exit(1)
    erros, descricao = list(res.erros), ""
    if not erros:
        errs, descricao = conciliar(mapa, tabela, res, total)
        erros.extend(errs)
    print(f"\nLinhas: {res.linhas_lidas} lidas · {res.classificadas} classificadas · {len(res.ignoradas)} ignoradas")
    for nome, regs in res.registros.items():
        if regs:
            print(f"  {nome}: {len(regs)}")
    if args.dry_run:
        # Só aqui: --dry-run é o momento de calibrar um mapeamento novo. Um mapa real tem uma
        # regra por tipo de evento e um mês aciona duas ou três, então o aviso em toda rodada
        # dispararia sempre e treinaria o usuário a ignorá-lo. Na gravação real a informação
        # não some: o log de importação registra a contagem por regra. E o sintoma forte,
        # coluna renomeada, já para a importação — linha sem regra é ERRO, não aviso.
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
            linhas, divergiu, n_novos = conferir(raiz, res)
        except ValueError as e:
            print(f"erro: {e}")
            sys.exit(1)
        except OSError as e:
            print(mensagem_os(e, raiz))
            sys.exit(1)
        for linha in linhas:
            print(linha)
        if divergiu:
            # divergência não é erro de execução: a rodada fez o que foi pedida. O código
            # separado existe para quem chama ramificar sem parsear texto.
            print("\nDivergência entre o documento e dados/ — nada gravado. Resolva antes de importar.")
            sys.exit(3)
        print("\nSem divergência: nada em dados/ conflita com o documento"
              + (f", e há {n_novos} registro(s) novo(s) a gravar." if n_novos
                 else ". Não há registro novo: rodar sem --conferir não muda dados/."))
        return
    if args.dry_run:
        print("\n--dry-run: nada gravado.")
        return
    try:
        r = gravar(raiz, res, mapeamento=mapa["nome"], arquivo=arquivo.name, conciliacao=descricao, conta=conta)
    except GravacaoParcial as e:
        entrou = ", ".join(f"{t} +{n}" for t, n in e.gravadas.items() if n) or "nada"
        # a causa vira a MESMA frase acionável do resto do CLI (caminho relativo ao
        # workspace, "aberto no Excel?"), não o repr cru do OSError
        causa = mensagem_os(e.causa, raiz) if isinstance(e.causa, OSError) else f"erro: {e}"
        print(f"\nA gravação falhou no meio. {causa}")
        print(f"O que chegou a entrar em dados/: {entrou}. O resto não entrou.")
        if e.log is not None:
            print(f"Log: {e.log.relative_to(raiz).as_posix()}")
        print("Resolva a causa (feche o arquivo no Excel, libere espaço) e rode de novo: "
              "a importação é idempotente, o que já entrou não duplica.")
        sys.exit(1)
    except ValueError as e:
        print(f"erro: {e}")
        sys.exit(1)
    except OSError as e:
        print(mensagem_os(e, raiz))
        sys.exit(1)
    partes = []
    for t, n in r["gravadas"].items():
        if not n:
            continue
        if t == "fills" and r["aberturas"]:
            a = r["aberturas"]
            partes.append(f"fills +{n} ({a} abertura{'s' if a != 1 else ''}, tipo=saldo-inicial)")
        else:
            partes.append(f"{t} +{n}")
    novas = " · ".join(partes)
    dup = ", ".join(f"{t} {n}" for t, n in r["duplicadas"].items() if n)
    print("\n" + (f"Gravado em dados/: {novas}" if novas else "Nada novo para gravar (tudo já estava em dados/)")
          + (f" · duplicadas puladas: {dup}" if dup else ""))
    print(f"Log: {r['log'].relative_to(raiz).as_posix()}")
    if r["aberturas"]:
        # Abertura de livro é fiscalmente honesta sobre o custo e muda sobre a data de aquisição.
        # Dizer isso na hora em que ela nasce é o que impede a invalidez fiscal de ser invisível.
        print(f"{r['aberturas']} abertura(s) de livro (saldo-inicial): registram o custo declarado na "
              "data do documento, não a data real de aquisição de cada lote.")
    sem_cotacao = _sem_cotacao(raiz)
    if sem_cotacao:
        # posição sem cotação deixa o validador vermelho, e inventar preço a partir do PM seria
        # fabricar número de mercado. Então o CLI manda cotar antes de validar.
        print(f"Sem cotação em dados/: {', '.join(sem_cotacao)}. Cote antes de validar: "
              f"python {motor / 'scripts' / 'atualizar_cotacoes.py'} {raiz}")
    print(f"Agora rode: python {motor / 'scripts' / 'validar_workspace.py'} {raiz}")


if __name__ == "__main__":
    main()
