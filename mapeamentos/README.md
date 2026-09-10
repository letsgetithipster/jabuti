# mapeamentos/ — como um documento de corretora vira dados/

A ingestão do PatrimônioOS não tem parser por corretora. Tem **um engine** e
**arquivos de mapeamento** (YAML). Corretora nova = mapeamento novo, sem código.
Esta pasta é superfície de contribuição, como `fiscal/`.

## Fluxo

1. Coloque o export em `inbox/` do seu workspace.
2. `python scripts/inspecionar_extrato.py inbox/arquivo.xlsx` mostra abas,
   cabeçalhos candidatos e amostra. É o que a LLM lê para escrever o mapeamento.
3. Se um mapeamento daqui casa com o cabeçalho, `importar_extrato.py` o detecta
   sozinho. Senão, a LLM escreve um em `mapeamentos/` **do workspace**, mostra a
   você, e só depois do seu "de acordo" o script roda.
4. `python scripts/importar_extrato.py <workspace> inbox/arquivo.xlsx --dry-run`
   executa e concilia sem gravar. Sem `--dry-run`, grava em `dados/` e deixa um
   log em `logs/importacoes/`.

Nada entra em `dados/` sem a **conciliação declarada** passar. Linha que não casa
regra nenhuma PARA a importação; não existe descarte silencioso.

## Prontos

| Mapeamento | Documento | Verificado contra export real | Conciliação |
|---|---|---|---|
| `clear-extrato` | Extrato da conta (xlsx), Clear | sim (fixture sintética com a estrutura real) | saldo-corrente |
| `schwab-transacoes` | Transactions (CSV), Schwab | sim | valor-da-linha |
| `b3-movimentacao` | Movimentação (xlsx), Área do Investidor B3 | **não** — formato documentado; contribua uma fixture | valor-da-linha |
| `exemplo-posicoes-csv` | posições tabulares com linha Total | modelo para adaptar | total-declarado |

A coluna "verificado contra export real" é o campo `verificado-contra-export-real`
de cada YAML, e `tests/test_mapeamentos_prontos.py` confere as duas pontas.

O mapeamento do workspace com o mesmo nome sobrepõe o do motor.

## Vocabulário do mapeamento

```yaml
nome: minha-corretora-extrato
versao: 1
descricao: o que é o documento
verificado-contra-export-real: false
detectar: {cabecalho-contem: [textos que identificam o cabeçalho]}   # auto-seleção
arquivo:
  formato: csv | xlsx
  aba: 0                       # xlsx: índice (0-based) ou nome
  encoding: utf-8-sig          # csv (latin-1 é comum em export brasileiro)
  delimitador: ","             # csv
  cabecalho-contem: [textos]   # linha em que TODOS aparecem é o cabeçalho (default: primeira não-vazia)
  fim-em-vazio: true           # a tabela termina na primeira linha vazia (rodapé fora)
datas:
  formatos: ["%d/%m/%Y"]       # strptime, na ordem de tentativa
  extrair: "^(\\S+)"           # opcional: regex com 1 grupo aplicado antes (ex.: "08/11/2026 as of ...")
conta: id-da-conta             # --conta sobrescreve
moeda: BRL
colunas:                       # apelido -> nome EXATO no cabeçalho
  data: Data
  descricao: Histórico
  valor: Valor
extrair:                       # opcional: regex por apelido, aplicada ao VALOR daquela coluna
  produto: "^(?P<ticker>[A-Z0-9]{4,6}) - "   # grupos viram apelidos; nome de grupo não pode
                                             # repetir apelido de colunas (sobrescreveria a coluna
                                             # na linha inteira). Vale igual nos grupos de `quando`.
linhas:                        # primeira regra que casa vence; nenhuma casa = ERRO
  - quando: {descricao: "^RENDIMENTO (?P<ticker>[A-Z0-9]{4,6})$"}   # todos os regex da regra precisam casar
    destino: proventos         # posicoes | fills | proventos | eventos | ignorar | ajuste
    campos: {tipo: rendimento, valor_bruto: "{valor}", valor_liquido: "{valor}"}
  - quando: {descricao: "^TED"}
    destino: ignorar
    motivo: caixa
  - quando: {descricao: "^SALDO DISPONIVEL$"}
    destino: ignorar         # rodapé de saldo DENTRO da tabela: não vira registro e, com
    motivo: rodapé de saldo  # fora-da-cadeia, também não entra na aritmética do saldo-corrente
    fora-da-cadeia: true     # só vale em `ignorar`
  - quando: {descricao: "^IMPOSTO (?P<ticker>[A-Z0-9]+)$"}
    destino: ajuste            # soma {valor} no campo da linha principal com a mesma chave
    aplica-em: proventos
    campo: valor_liquido
    chave: [data, ticker]
    valor: "{valor}"
conciliacao:                   # obrigatória; um dos três:
  tipo: saldo-corrente         # saldo[i] = saldo[i-1] + valor[i] em todas as linhas
  valor: valor
  saldo: saldo
  ordem: decrescente           # ordem do documento (Clear é decrescente)
  tolerancia: 0.011            # opcional, vale nos três tipos; justifique o número em observacoes
  # tipo: valor-da-linha       # fills: |valor| = qty×preço ± taxa; proventos: valor_bruto = |valor|
  # proventos: valor_bruto
  # tipo: total-declarado      # soma de campo (ou campo*campo) dos registros = total
  # soma: qty*pm
  # origem: {linha-contem: Total, coluna: investido}   # ou origem: flag (--total-declarado)
```

Campos não declarados em `campos` são preenchidos assim: `data` pela coluna
`data` (ou `--data`), `conta` e `moeda` pelo mapeamento, e qualquer campo cujo
nome coincide com um apelido ou grupo de regex (`ticker`, `qty`, `preco`...).
`{apelido|padrão}` usa o padrão quando a célula está vazia. Número aceita
pt-BR e US (`1.234,56`, `$1,234.56`, `-R$ 5,00`); data segue `datas.formatos`.

Numa cadeia de `saldo-corrente`, linha com saldo e sem valor é **âncora**: só a
primeira da cadeia abre saldo; da segunda em diante ela tem que repetir o saldo
anterior, senão é salto sem lançamento que o explique. `ignorar` significa "não
vira registro", não "não conta na aritmética": um rodapé de saldo disponível ou
bloqueado dentro da tabela precisa de `fora-da-cadeia: true` na regra, senão ele
continua na cadeia e a quebra.

Em `valor-da-linha`, provento cujo campo conciliado é literalmente `"{valor}"`
não é conferência: os dois lados da comparação saem da mesma célula. Essas linhas
aparecem no resumo como **apenas transcritas** e não contam como conferidas. Se
forem tudo o que o documento tinha a oferecer à conciliação, a importação para —
declare `saldo-corrente` ou aponte `proventos:` para um campo que o documento
calcule (`valor_liquido`, quando há coluna de imposto).

Sem `tolerancia` declarada, cada tipo usa o seu default: um centavo em
`saldo-corrente` e `valor-da-linha`, e em `total-declarado` sobre `campo*campo`
o limite teórico do arredondamento (`0,005 × Σ` do primeiro fator), que é largo.
Declarar é o normal, não a exceção: o número medido no seu export, com o porquê
em `observacoes`.

Convenções: `hora` em `cotacoes.csv` é a hora da fonte; fonte diária sem hora
(PTAX, manual sem hora) grava `00:00`. JCP em extrato brasileiro costuma vir
líquido: grave `valor_bruto` igual ao líquido e registre isso em `observacoes`.

## Contribuindo um mapeamento

1. Fixture **sintética** em `tests/extratos_sinteticos.py` (xlsx) ou
   `tests/fixtures/extratos/` (csv): mesma estrutura do export real, nomes e
   valores fictícios, aritmética consistente com a conciliação. Nenhum dado real.
2. Teste em `tests/test_mapeamentos_prontos.py` com as contagens esperadas e um
   caso que quebra a conciliação.
3. `verificado-contra-export-real: true` só quando a fixture reproduz um export
   real que você conferiu.
