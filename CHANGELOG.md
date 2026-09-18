# Changelog

O que mudou, do ponto de vista de quem **usa** o jabuti. Mudança que o usuário não sente
(refactor interno, teste novo, texto de comentário) não entra aqui — entra no git.

Regra de entrada: uma linha por mudança, no imperativo do efeito, e **toda mudança de
formato de `dados/` ou de `vault.config.yaml` nomeia na própria linha o que rodar**, ou diz
que não há nada a rodar. Quem clonou há três meses precisa saber o que fazer, não o que
aconteceu.

## Não lançado

### Mudou para quem já usa

- **O mês não avança para o aporte com posição sem valor novo.** `atualizar_cotacoes.py`
  termina nomeando o que não conseguiu atualizar sozinho (fundo, previdência, renda fixa,
  ticker que o provider não achou), com o último valor conhecido e o `--manual` pronto; a
  `/jabuti-mes` e a `/jabuti-importar` deixam de "seguir" no código 3 e perguntam esses
  valores antes do ESTADO e da fila. Em `consultar_aporte.py`, o aviso de valor velho passa
  a sair antes da fila, não depois. Códigos de saída não mudam.
- **Saem três tabelas de `dados/`**: `posicoes.csv`, `indices.csv` e `movimentacoes.csv`.
  A posição passa a ser derivada do livro (`fills.csv` + `eventos.csv` + a classe declarada
  em `ativos.csv`), e o workspace nasce com cinco CSVs em vez de sete. **Não há migrador,
  por construção:** um workspace antigo com `posicoes.csv` no disco continua lendo (a
  classe de um ticker que ninguém declarou em `ativos.csv` ainda vem de lá), e uma posição
  da tabela antiga sem nenhum fill vira erro do validador com a linha de `saldo-inicial`
  pronta para colar em `fills.csv`. Nada a rodar.
- **`dados/ativos.csv` é novo**: a declaração de classe por ticker, e o único arquivo de
  `dados/` que se edita à mão. Fill de ticker sem classe é erro com o comando pronto:
  `python <motor>/scripts/registrar.py . ativo TICKER=classe`.
- **Mapeamento de corretora declara o formato numérico**: chave `numeros: pt-BR` ou
  `numeros: en-US`, obrigatória. Se você escreveu um mapeamento próprio, acrescente a
  chave; o validador de mapeamento diz qual. Antes o motor adivinhava, e `0,030` virava `30`.
- **`vault.config.yaml` nasce com `cotacoes.provider: yahoo`** em vez de `manual`. Workspace
  antigo continua válido com `manual`; troque à mão se quiser cotação automática.
- **`vault.config.yaml` ganha o bloco opcional `privacidade.remoto-declarado`**. Workspace
  antigo sem o bloco continua válido; o validador só o exige quando o workspace tem remoto
  git, e a frase de erro traz a linha a colar.
- **A aba Aporte sai do cockpit xlsx.** A fila do aporte mora em
  `python <motor>/scripts/consultar_aporte.py . VALOR`, que é o que a rotina do mês roda.
- **O onboarding termina em `/jabuti-mes`**, a rotina do mês numa skill só. Cotar é passo
  das skills que precisam dele, não uma skill própria.

### Novo

- `scripts/registrar.py`: dizer "eu comprei" passa a ter caminho. Subcomandos `compra`,
  `venda`, `provento`, `estorno` (remove da linha do tempo o fill que casa exatamente),
  `evento` (split, grupamento, bonificação; o livro só aplica com `--confirmar`) e `ativo`.
  Todos com eco de confirmação, `--dry-run` e log datado. Quantidades e preços em pt-BR.
- `scripts/consultar_aporte.py`: a fila do aporte sai da fórmula de Excel e vira código que
  um teste confronta. O mês sem aporte é a mesma consulta com valor zero.
- `/jabuti-mes`: a rotina do mês — decidir onde aportar, ou registrar o que aconteceu.
- `/jabuti-divida` e `/jabuti-capacidade`: leem o MCP da Finnest, só leitura, sem escrever
  em `dados/`; o teto de escopo é `read:financial`. Detalhe em `docs/finnest-skills.md`.
- `importar_extrato.py --conferir`: a foto da corretora confere o livro sem escrever nele, e
  a divergência sai com a aritmética e o comando de correção prontos.
  `--aceitar-como compra` fecha o livro pela foto, com o caveat impresso e logado.
- O livro aplica evento societário confirmado (split, grupamento, bonificação), aceita
  estorno e corta por data.
- `criar_workspace.py` checa o ambiente antes de copiar: Python 3.11+, pyyaml e git, cada
  falta com o comando de correção; openpyxl ausente é só aviso.
- `PRIVACIDADE.md` na raiz: o que o workspace guarda, as três saídas de dado e a retenção
  do `inbox/`.
- Oitavo check do validador, `check_publicacao`: workspace com remoto git exige
  `privacidade.remoto-declarado` igual à URL configurada.
- `CONTRIBUTING.md` na raiz, com a regra dura de fixture sintética, e este `CHANGELOG.md`.

### Corrigido

- O `ESTADO.md` publica o total derivado do livro; antes podia publicar o total de antes do
  fill, e o validador era quem acusava.
- Quem ainda não tem posição recebe um ESTADO de uma linha, com o que fazer quando comprar,
  em vez de `Total investido: R$ 0,00` com pendências corretas e inúteis.
- `atualizar_cotacoes.py --manual A=1 --manual B=2` cotava só B, em silêncio.
- Recotar depois de confirmar um split não propõe um segundo split: o evento confirmado
  ajusta a base da comparação.
- O cotador deriva o universo do livro: ticker que entrou só por fill é cotável pelo comando
  que o próprio `gerar_estado.py` manda rodar.
- Texto gerado pelo motor nasce com LF em qualquer sistema operacional. Antes, no Windows,
  rodar o primeiro comando do README deixava o clone sujo com `git diff` vazio.
- O exemplo e a demo do README valoram numa data fixa, nunca no relógio: a demo não ganha
  uma pendência de cotação velha no dia em que a cotação completa sete dias.
- Posição declarada na tabela antiga sem nenhum fill é erro, não zero silencioso.
- Quantidade e preço saem em pt-BR no validador, na prévia da importação e no `registrar.py`.
- O onboarding parou de mandar colar uma skill que não existe, e o texto embarcado no
  workspace parou de prometer o que o motor não constrói. Há guarda para os dois.

### Dívida declarada

- **Ingestão por provider (adaptador da Finnest) e `movimentacoes.csv`**: fora do v1. A
  tabela deixou de nascer em `dados/` e nenhum script a escreve; o schema fica no motor sem
  escritor até o adaptador entrar (v1.1).
- **Backlog com dono**: `TOLERANCIA_QTY` em `scripts/po/ledger.py` (oito usos em `scripts/po/`,
  sem teste que prenda o limiar) e o `:g` residual, que formata com ponto onde o produto
  promete pt-BR, em `scripts/po/csvs.py` (4), `scripts/po/ingestao/conciliacao.py` (9),
  `scripts/po/estado.py` (3, os limites de banda) e `scripts/po/validar/check_politica.py` (3).
