---
name: importar-extrato
description: "Use quando o usuário pedir 'importar extrato', 'importa o CSV da corretora', 'sobe o export da Clear/Schwab/B3', 'popular o workspace com o extrato', '/importar-extrato' ou variação que indique levar um documento exportado da corretora (CSV ou xlsx em inbox/) para dados/. Divisão rígida: a LLM inspeciona o documento, escolhe ou ESCREVE o mapeamento (YAML em mapeamentos/) e o MOSTRA ao usuário; o script scripts/importar_extrato.py executa o parse e confere a aritmética declarada no próprio documento (saldo corrente, valor da linha ou total declarado). Não bateu, nada entra em dados/. A LLM nunca digita número de posição, provento ou fill."
---

# Importar extrato

## Quando usar

- Primeira carga do workspace a partir de um export de posições (qty e PM por ativo)
- Carga periódica de proventos, fills e eventos a partir do extrato/transactions da corretora
- Reconciliação: `--conferir` compara um export de posições com `dados/` sem gravar

Frases típicas: "importa o extrato da Clear", "sobe o CSV da Schwab", "/importar-extrato inbox/x.xlsx".

## Princípio operacional

- **Quem lê o documento é o script.** A LLM lê o *dump* de `inspecionar_extrato.py`, não o binário, e nunca copia número dele para `dados/`.
- **Mapeamento é dado, e o usuário vê antes.** Se nenhum mapeamento pronto casa, a LLM escreve um YAML novo em `mapeamentos/` do workspace (vocabulário em `mapeamentos/README.md` do motor), mostra o arquivo inteiro ao usuário e só roda depois do "de acordo".
- **Conciliação obrigatória.** Todo mapeamento declara como o documento prova a própria soma. Linha que não casa regra nenhuma PARA a importação; a LLM acrescenta a regra (ou um `ignorar` com motivo explícito) e mostra de novo.
- **Reimportar é seguro**: duplicata é pulada e contada. Posição que diverge da existente é conflito, nunca sobrescrita.
- **A mesma posição duas vezes no MESMO documento é conflito, não duas linhas.** `posicoes.csv` é uma linha por ticker/conta. Corretora que quebra a posição por lote ou por agente de custódia (B3 e Schwab fazem isso) exige consolidação **no mapeamento**, antes de importar — e quem escreve o mapeamento é a LLM. Somar as duas linhas à mão em `dados/` não é opção.

## Contexto canônico a ler antes

- `vault.config.yaml`: ids das contas e moeda de cada uma (o mapeamento aponta uma conta; `--conta` sobrescreve; moeda do mapeamento e da conta têm que bater).
- `mapeamentos/README.md` do motor: vocabulário do mapeamento e os prontos (`clear-extrato` e `schwab-transacoes`, verificados contra export real; `b3-movimentacao` e `exemplo-posicoes-csv`, ainda não).
- `mapeamentos/` do workspace: mapeamentos que o usuário já tem. Sem `--mapeamento`, o script tenta detectar pelo cabeçalho, primeiro no workspace, depois no motor.

## Fluxo

1. Confirmar o arquivo em `inbox/` e a conta de destino.
2. `python <motor>/scripts/inspecionar_extrato.py inbox/<arquivo>` e ler o dump (abas, cabeçalho, amostra, tipos das células).
3. Escolher o mapeamento:
   - Um pronto casa com o cabeçalho → seguir.
   - Nenhum casa → escrever `mapeamentos/<corretora>-<documento>.yaml` no workspace, com `verificado-contra-export-real: false`, regras explícitas para cada tipo de linha visto na amostra, e a conciliação que o documento permite (saldo corrente se há coluna de saldo; valor da linha se há qty × preço = valor; senão total declarado). **Mostrar o YAML ao usuário e esperar o de acordo.**
   - Rodapé de saldo **dentro** da tabela ("SALDO DISPONIVEL", "Saldo bloqueado") vira regra `ignorar` com `fora-da-cadeia: true`. `ignorar` sozinho só diz "não vira registro"; sem `fora-da-cadeia` a linha continua na aritmética do `saldo-corrente` e a quebra. Subir a `tolerancia` para esconder essa quebra é a saída errada: desliga a conferência do documento inteiro.
   - Documento sem coluna de data (posições): pedir ao usuário a data da posição para `--data`.
   - Conciliação `total-declarado` com `origem: flag`: pedir ao usuário o total que a corretora mostra e passar em `--total-declarado`. A LLM não calcula esse número.
4. `python <motor>/scripts/importar_extrato.py <raiz> inbox/<arquivo> --mapeamento <nome> [--conta] [--data] [--total-declarado] --dry-run`. Ler: contagens por tabela, ignoradas por motivo, regras que nunca casaram (aviso só no `--dry-run`), resultado da conciliação.
   - ERRO de linha não classificada → voltar ao passo 3 e acrescentar a regra.
   - ERRO de conciliação → não "ajustar" nada para bater: mostrar a linha apontada ao usuário; documento e mapeamento é que se corrigem.
   - ERRO "nenhuma linha de dados abaixo do cabeçalho" → aba errada, cabeçalho que o mapeamento não achou, ou export em branco: voltar ao `inspecionar_extrato.py`.
5. Rodar sem `--dry-run`. Relatar o que entrou (`posicoes +N`, `fills +N`...), duplicadas puladas e o caminho do log em `logs/importacoes/`.
6. Ticker que entra **sem nenhum fill** ganha um fill `saldo-inicial` (qty e preço = PM, na data do documento ou de `--data`): dizer isso ao usuário; é o que fecha o ledger. A condição é "sem fill", não "posição nova" — ticker que já tem fill de verdade nunca ganha abertura sintética, e uma rodada de recuperação completa a abertura que faltou sem duplicar nada.
7. Rodar `validar_workspace.py`. Posição importada sem cotação é ERRO esperado: seguir com `/atualizar-cotacoes` e depois `python <motor>/scripts/gerar_estado.py <raiz>` (e `gerar_cockpit.py`, se o usuário usa o cockpit).

## Códigos de saída (é por eles que a LLM ramifica, não pelo texto)

| Código | Significa | O que fazer |
|---|---|---|
| 0 | importou, ou `--dry-run`/`--conferir` sem divergência | seguir o fluxo |
| 1 | erro que impediu a rodada: config, mapeamento, leitura, conciliação ou gravação | corrigir a causa apontada e rodar de novo |
| 2 | uso inválido da linha de comando (argparse) | conferir os argumentos |
| 3 | `--conferir` achou divergência entre o documento e `dados/` | nada gravado; resolver a divergência antes de importar |

`--conferir` é a rodada de diagnóstico: **3 = divergiu, 0 = não divergiu**. Não é erro de execução, é resultado — ramificar pelo código, não pelo texto do relatório.

## Casos especiais

- **Gravação que morre no meio** (arquivo aberto no Excel, disco cheio): sai **1**, mas parte entrou. É a **única** saída de erro em que `dados/` mudou. O script nomeia tabela por tabela o que chegou a entrar e aponta o log em `logs/importacoes/`. A recuperação é resolver a causa e **rodar de novo**: a importação é idempotente, o que já entrou não duplica. Nunca editar `dados/` à mão para "completar" o que faltou.
- **"N provento(s) apenas transcrito(s) do documento"** na descrição da conciliação **não é aviso de falha**: é a conciliação sendo honesta sobre linhas cujo valor gravado É a própria célula lida, ou seja, que não provam nada (os dois lados da comparação saem da mesma coluna). A importação segue normalmente. Traduzir assim ao usuário. Só quando **todos** os proventos são assim e nenhuma linha foi de fato conferida vira ERRO, com o remédio na própria mensagem: declarar `conciliacao.tipo: saldo-corrente`, ou apontar `proventos:` para um campo que o documento calcule (`valor_liquido`, quando há coluna de imposto).
- Extrato da Clear traz operações em bolsa agregadas por nota: fills por ticker NÃO saem dele (vêm da nota de corretagem ou do export de movimentação da B3). O mapeamento pronto ignora essas linhas com motivo.
- JCP em extrato brasileiro vem líquido: `valor_bruto` é gravado igual ao líquido e o mapeamento declara isso em `observacoes`.
- Schwab: `NRA Tax Adj` é ajuste do líquido do dividendo do mesmo dia/ticker; `Stock Split` e `Stock Merger` viram propostas em `eventos.csv` (confirmado `nao`) para o usuário completar a razão.
- `.xlsx` sem openpyxl instalado: o script diz `pip install -r requirements-xlsx.txt`; alternativa é o usuário exportar como CSV.
- Posição já existente com qty/PM diferente: conflito declarado, nada gravado. Oferecer `--conferir` e deixar o usuário decidir o que corrigir em `dados/`.

## O que esta skill NÃO faz

- **Não digita número**: nem posição, nem provento, nem fill, nem total declarado
- **Não escreve parser Python por corretora** — só mapeamento YAML
- **Não grava com conciliação falhando** e não "corrige" o documento para bater
- **Não aplica evento corporativo em qty/PM** (só registra a proposta; Fase 4)
- **Não busca cotação** (→ `/atualizar-cotacoes`) nem regenera ESTADO/cockpit sozinha (→ `gerar_estado.py`, `gerar_cockpit.py`)
- **Não commita**
