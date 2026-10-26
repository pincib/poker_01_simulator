# Verificação integrada da modalidade PLO

## Execução reproduzível

Na raiz do repositório, rode:

```powershell
python -B scripts/run_phase11_verification.py
```

O auditor fixa `seed=2001` para equity e `seed=3117` para showdown. Self-play usa
`seed=20261026`, seis assentos, stacks de 200, blinds 1/2 e sem rake; as
quantidades são prefixos determinísticos de 100, 500 e 2.000 mãos. Para uma
execução mais longa, `--max-hands 10000` eleva o último lote. `--iterations`
controla os rollouts do benchmark de equity (padrão: 10.000).

Critérios automatizados:

- matchup de referência PLO no flop dentro de 93,5% ±2 pontos para 10.000
  rollouts;
- equity com 1.000 rollouts abaixo de 2,0 s nos testes da suíte;
- showdown de seis jogadores abaixo de 0,25 s, com payouts iguais às
  contribuições e mãos vencedoras de cinco cartas;
- cada mão self-play termina, classifica-se como showdown ou vitória por fold,
  conserva fichas, cobra zero rake e não excede 200 ações;
- os contadores de empate, mãos all-in e folds crescem monotonicamente nos
  prefixos e aparecem no lote de 2.000 mãos.

O teste de integração HTTP começa uma mão PLO, envia uma ação legal, conclui a
mão e recupera o registro de revisão com variante, quatro cartas, board, ação e
contribuições. Os testes de motor também cobrem distribuição, validade de
ações, regras de Omaha, side pots, equity, ranges, coach e erros de API. A UI
mantém testes de contrato indiretos através do snapshot da mesa; não há um
runner de navegador automatizado neste repositório.

## Resultado registrado

Ambiente local: Windows 11, Python 3.14.7. Uma execução padrão em 2026-10-26:

| Verificação | Resultado | Tempo observado |
| --- | ---: | ---: |
| Equity PLO, flop, seed 2001 | 93,52% / 10.000 rollouts | 1,352 s |
| Showdown PLO, seis jogadores, seed 3117 | payouts conservados | 0,0019 s |
| Self-play, 100 mãos | 4 empates; 1 mão com all-in; 41 folds | 0,486 s |
| Self-play, 500 mãos | 25 empates; 4 mãos com all-in; 207 folds | 3,393 s |
| Self-play, 2.000 mãos | 117 empates; 17 mãos com all-in; 798 folds | 12,630 s |

Os três lotes tiveram zero rake, zero deadlocks e conservação de fichas. Os
tempos são observações do ambiente local, não garantias para outro hardware.
Os bots da mesa de treino não foram substituídos nem certificados por esse
auditor: o self-play usa uma política aleatória simples para exercitar regras,
não uma estratégia ótima.
