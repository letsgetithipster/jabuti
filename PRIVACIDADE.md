# PRIVACIDADE — o que fica na sua máquina, e o que sai

Este documento existe para que a frase da camada 2 do [GUARDRAILS.md](GUARDRAILS.md) —
"seus dados ficam no workspace" — seja **conferível**, e não uma promessa. Ele descreve o
produto como ele é hoje. Quando o comportamento mudar, este arquivo muda no mesmo commit.

Você é o controlador dos seus próprios dados. A LGPD (Lei 13.709/2018, art. 4º, I) não
alcança tratamento feito por pessoa natural para fins exclusivamente particulares e não
econômicos, que é exatamente o uso deste repositório. Os autores do projeto **não recebem,
não hospedam e não têm como ver** nada do seu workspace: não existe servidor, conta,
telemetria nem "crash report".

## O que o workspace guarda

| Onde | O quê | Vai para o git? |
|---|---|---|
| `dados/*.csv` | o seu livro: o que você comprou, a que preço, quando, em qual conta; os proventos; as cotações com fonte, data e hora | **sim** — é o histórico que sustenta o IR, e versionar é o que o torna auditável |
| `politica/` | idade, horizonte, custo de vida, capacidade de aporte, perfil de risco, bandas | **sim** |
| `logs/` | aportes, decisões, importações (cada uma aponta o documento de origem) | **sim** |
| `estado/` | o `ESTADO.md` gerado e o `SETUP.md` do onboarding | **sim** |
| `inbox/` | o export **bruto** da corretora: pode trazer CPF, número da conta, nome completo, endereço | **não** — `.gitignore` cobre `inbox/*` |
| `planilhas/*.xlsx` | o cockpit, regenerável a qualquer momento | **não** |
| `.env`, `.env.*` | segredo de provider, se você usar algum | **não**, e o `check_segredos` nunca varre esses arquivos |

A lista das tabelas de `dados/` não é copiada aqui de propósito: ela muda, e a casa dela é
`scripts/po/csvs.py` (`SCHEMAS`). Um fato mora num lugar só.

## O que sai da sua máquina

São três saídas. Não há uma quarta.

<!-- saida: cotacoes -->
**1. O ticker, para o provider de cotação.** `atualizar_cotacoes.py` faz uma requisição HTTP
por ativo ao provider configurado em `vault.config.yaml` (Yahoo, brapi ou BCB/SGS). O que
sai é o **símbolo** do ativo e nada mais: nem quantidade, nem preço médio, nem conta, nem
quem você é. O provider aprende que alguém consultou `PETR4`; não aprende que você tem
`PETR4`. Se nem isso você quiser, use `provider: manual` (e `cambio: manual`, se tiver
posição fora do BRL) e cole os preços à mão — o motor funciona inteiro assim, e é a única
configuração em que **nada** sai pela rede.

<!-- saida: llm -->
**2. O conteúdo que você mostra à LLM.** Esta é a maior saída, e a que menos gente enxerga.
O jabuti é operado por uma LLM que lê os seus arquivos: o `ESTADO.md`, a sua política, as
suas teses, e o que mais a conversa pedir. Esse conteúdo vai para o provedor da LLM que
você escolheu, sob os termos **dele**, não os deste projeto. O jabuti não muda isso e não
tem como mudar. O que ele faz é deixar o recorte explícito: `dados/` é CSV lido por script,
e a LLM só precisa ver o que você abrir na conversa. Se o seu provedor treina modelo com o
que você manda, isso vale aqui como vale em qualquer outro arquivo que você cole nele.

<!-- saida: git -->
**3. O que você mesmo empurrar para um remoto git.** O workspace nasce sem remoto. Se você
criar um, **crie privado**, e declare-o em `vault.config.yaml`:

```yaml
privacidade:
  remoto-declarado: 'git@github.com:voce/meu-vault.git'
```

O validador falha enquanto a URL declarada não for a URL configurada. Ele não impede o
push — git não é do motor — mas garante que publicar seja um gesto consciente, e não um
remoto herdado de um clone esquecido. É o erro mais caro que este produto permite: o
histórico do git não se apaga, e reescrever história já publicada não desfaz quem clonou.

## O que o `.gitignore` protege, e o que ele não protege

Protege: `inbox/` (extrato bruto), `planilhas/*.xlsx`, `.env*`, `__pycache__/`,
`.claude/skills/` (cópia do motor, não conteúdo seu).

**Não protege, por desenho:** `dados/`, `politica/`, `logs/` e `estado/`. Eles são o
produto. Versioná-los é o que dá histórico ao seu patrimônio e procedência a cada número.
Se isso não é o que você quer, não crie remoto — versionar localmente entrega todo o
benefício e zero exposição.

## Retenção do `inbox/`

O extrato bruto serve para uma coisa: ser lido uma vez pela importação, que confere a
aritmética do próprio documento e grava o resultado em `dados/`, deixando em
`logs/importacoes/` um registro que aponta o arquivo de origem. Depois disso ele não tem
mais função no motor. **Apague-o quando terminar.** O motor não apaga por você: apagar
arquivo do usuário sem ordem do usuário é exatamente o tipo de iniciativa que este produto
não toma.

## Se você for contribuir

Mapeamento de corretora entra **só com fixture sintética**. Nunca anexe um extrato real,
nem "anonimizado à mão" — a superfície de contribuição mais convidativa deste repo é
justamente a que tenta o contribuidor a colar o próprio extrato. Há guarda mecânica:
`tests/test_mapeamentos_prontos.py` varre as fixtures atrás de dado pessoal. Veja
[CONTRIBUTING.md](CONTRIBUTING.md).
