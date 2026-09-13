---
tipo: log-decisao
data: 2026-09-08
data-criacao: 2026-09-08
assunto: estrategia
---

# Política declarada — 2026-09-08

**Contexto.** Ana já investia em três blocos (ações BR, FIIs, renda fixa BR) quando rodou o `/jabuti-estrategia`, e entrou pela porta "já tenho estratégia". Perfil: 35 anos, horizonte de 30 anos, risco testado médio, reserva de 6 meses — faixa `longo-medio` da rubrica.

**Alternativas consideradas.** As três da faixa `longo-medio` (`metodo/bandas.yaml` do motor), mostradas ao lado da política que ela já tinha:

| | conservadora | equilibrada | agressiva | a dela |
|---|---|---|---|---|
| rf-br | 40 | 30 | 20 | 35 |
| acoes-br | 15 | 20 | 25 | 35 |
| fiis | 10 | 10 | 5 | 30 |
| rv-int | 15 | 25 | 35 | 0 |
| demais blocos | 20 | 15 | 15 | 0 |

**Decisão dela.** Manter a política pré-existente em três blocos, com as bandas de ±10 pontos em torno do alvo. Racional registrado por Ana: "quero dominar o que já tenho antes de abrir bloco internacional; revisito rv-int no fechamento de 2027".

**Divergência registrada pela casa.** Concentração em fiis (alvo 30%) acima do que a rubrica sugere para o perfil; fica como escolha consciente dela, não como recomendação da casa.

**Docs afetados.** `politica/01-alocacao-alvo.md` (tabela e histórico), `estado/SETUP.md`.
