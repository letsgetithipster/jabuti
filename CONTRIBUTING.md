# Contribuindo com o jabuti

Obrigado. Antes de qualquer coisa, duas frases que economizam o seu tempo.

**O método canônico não entra por PR.** Rubricas, frameworks, princípios e os números de
`metodo/` mudam por issue de método, com racional escrito, discussão e decisão registrada.
Um PR que muda uma banda ou uma nota será fechado com um convite para abrir a issue — não
por burocracia, mas porque método é o produto, e produto não se altera em revisão de código.

**As bordas estão abertas, e são onde o repo cresce.** Estas quatro, em ordem de valor:

| Borda | O que é | Onde |
|---|---|---|
| mapeamento de corretora | um YAML que ensina o engine a ler um documento novo, sem código | `mapeamentos/` |
| provider de cotação | um adaptador que devolve preço com fonte, data e hora | `scripts/po/cotacoes/providers/` |
| pacote fiscal anual | as regras de um ano-fiscal, com validade estampada | `fiscal/` |
| teste | sonda que prova um comportamento que hoje só está prometido | `tests/` |

## A regra dura: fixture sintética, nunca extrato real

Mapeamento novo vem com fixture. A fixture é **sintética**: inventada, com ticker, valor,
nome e documento que não são de ninguém. Nunca anexe o seu extrato, nem um extrato
"anonimizado à mão" — anonimização à mão erra, e o git não esquece.

Isto é regra de privacidade, não de estilo: a superfície de contribuição mais convidativa
deste repo é justamente a que tenta o contribuidor a colar o próprio extrato, porque ele é
o arquivo que está ali na tela na hora de escrever o mapeamento. Há guarda mecânica —
`tests/test_mapeamentos_prontos.py` varre as fixtures atrás de dado pessoal — e ela não
substitui a sua atenção. Leia [PRIVACIDADE.md](PRIVACIDADE.md).

## Montando o ambiente

```bash
git clone git@github.com:letsgetithipster/jabuti.git
cd jabuti
python -m pip install -r requirements.txt          # pyyaml + pytest
python -m pip install -r requirements-xlsx.txt     # openpyxl: NÃO é opcional para contribuir
git config core.hooksPath .githooks                # o hook valida e roda a suíte em todo commit
python -m pytest -q
python scripts/validar_workspace.py exemplos/workspace-exemplo
```

O `requirements-xlsx.txt` é opcional para **usar** e obrigatório para **contribuir**: sem
openpyxl, 15 testes aparecem como `skipped` e você não exercita o caminho de xlsx.

Contribua de um clone só para isso. Não rode o `/jabuti-init` nele: a instalação põe os seus
dados na raiz, e com `vault.config.yaml` ali os hooks bloqueiam commit e push, de propósito.
Quem usa e contribui tem dois clones, o de uso e o de contribuição.

Dois verdes fecham qualquer mudança: `python -m pytest -q` e o validador do exemplo em
`0 erro(s), 0 aviso(s)`. O pre-commit roda os dois. **Nunca `--no-verify`:** se o hook
reclama, ele está certo ou o hook é o bug — nas duas hipóteses, passar por cima esconde a
resposta.

## O que este repo pede de um teste

**Todo teste novo precisa de "reverta e conte":** mude o alvo que ele diz proteger e
confirme que ele fica vermelho. Teste que passa nos dois estados é decoração, e decoração
num repo de guardrails é pior que ausência, porque compra confiança sem entregar nada.
Diga no PR qual mutação você aplicou e o que ela derrubou.

Se um teste **não** cai onde você esperava e isso é deliberado, escreva por quê. O repo tem
vários controles assim, e todos declaram o ponto cego na própria docstring.

## Como o repo escreve

- **Output em pt-BR**, com separador decimal brasileiro. O produto é para o investidor
  brasileiro; a interface é português.
- **Erro é frase acionável**, nunca traceback, nunca silêncio. Toda mensagem de erro diz o
  que aconteceu e qual é o próximo comando. Se você não consegue escrever o próximo
  comando, provavelmente o erro está no lugar errado.
- **Nenhuma afirmação em README, SKILL ou docstring no presente sem código que a cumpra.**
  Se a coisa ainda não existe, escreva que ainda não existe. Há guardas que cobram isso em
  `tests/test_docs_nao_prometem.py`.
- **Um fato mora num lugar só.** Espelho mantido à mão é dívida.
- O console do Windows é cp1252: use `PYTHONIOENCODING=utf-8` na sua sessão e
  `encoding="utf-8"` em toda leitura e escrita. Texto gerado grava com `newline="\n"`.

## Mensagem de commit

Uma linha de assunto em minúsculas, com prefixo do tipo (`feat:`, `fix:`, `docs:`,
`refactor:`, `test:`), e um corpo que explica **por quê**, não o quê — o diff já mostra o
quê. Sem acento no assunto, para acompanhar o histórico existente.

## Relatando um problema

Diga o comando que você rodou, a saída inteira, o seu sistema operacional e a versão do
Python. Se for sobre número, diga qual arquivo de `dados/` sustenta o número — e **não cole
dado seu**: reproduza contra `exemplos/workspace-exemplo`, que existe exatamente para isso.
