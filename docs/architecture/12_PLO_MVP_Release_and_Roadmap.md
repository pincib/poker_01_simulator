# Liberação do MVP PLO e expansão

**Status:** MVP liberado como modo de treino local.  
**Ativação:** iniciar o servidor local, escolher **Pot-Limit Omaha** em **Game** e distribuir uma mão. A seleção é enviada à API, validada no servidor e mantida para as mãos seguintes; não pode mudar durante uma mão.

## O que está liberado

O fluxo completo abrange distribuição PLO4, apostas pot-limit, bots, showdown Omaha, potes laterais, coach e revisão da sessão. O produto não envolve dinheiro real nem conexão com uma sala externa. O caminho de execução e jogo está no [guia do usuário](../USER_GUIDE.md); contratos HTTP estão na [referência da API](../API.md).

O MVP usa uma mesa de seis lugares, blinds $1/$2, stacks de $200 e sem ante, straddle, rake ou taxa. A mesa aceita ações legais calculadas pelo backend, usa exatamente duas cartas fechadas e três comunitárias no showdown e distribui payouts preservando fichas. A revisão é mantida em memória no processo local.

Na interface, o resumo abaixo do seletor de modalidade comunica regras fixas, bots heurísticos, natureza estimada do coach e retenção temporária da revisão. O coach exibe limitações junto à análise; não apresenta as estimativas como garantias.

## Limitações conhecidas no lançamento

- Perfis de bots são heurísticas de treino, não solver, GTO ou estratégia ótima.
- Equity e ranges usam amostragem; multiway, ranges de ação e decisões futuras dos adversários têm simplificações descritas no coach.
- Pot odds/SPR e avaliação de draws não modelam integralmente todos os stacks efetivos e redraws multiway.
- A classificação pré-flop de propósito da aposta PLO não é modelada.
- Histórico e revisão não sobrevivem à parada/reinício do processo.
- Interface do MVP oferece seis assentos fixos, blinds de $1/$2, stacks de $200 e recompra automática; não há opções de stake ou tamanho da mesa.
- Não há importador de histórico de salas, jogo em rede, persistência, torneios, dinheiro real, PLO5/PLO6 ou Hi-Lo.

## Acompanhamento e prioridade de estabilidade

O produto local não envia telemetria. Problemas relatados em sessões devem ser reproduzidos com a versão do código, variante, seed quando disponível, estado/ações da mão e o resultado esperado. Não compartilhar dados pessoais nem históricos de sala sem consentimento.

Prioridade para correções:

1. **Estabilidade e integridade:** ações ilegais, deadlocks, cartas duplicadas, payouts divergentes, estados irrecuperáveis ou falha ao reconstruir a revisão.
2. **Qualidade do coach:** estimativas, ranges, draws, blockers ou explicações incoerentes com regras PLO; rotular claramente incerteza e lacunas.
3. **Variedade de treino:** repetições de linhas, sizing e situações de stack/board, sem relaxar legalidade nem comunicar heurísticas como ótimas.

Rodar a suíte e `scripts/run_phase11_verification.py` antes de alterar regras, bots ou análise; registrar seed e métricas para reproduzir regressões. Para novos perfis ou cenários, adicionar uma validação própria sem tratar self-play como avaliação de força estratégica.

## Expansões posteriores

Cada iniciativa deve ter escopo, contrato, datasets/licenças quando necessários e critérios de validação definidos antes de implementação. Não são promessas de data nem parte deste MVP.

| Iniciativa | Escopo próprio necessário | Validação necessária |
| --- | --- | --- |
| Históricos importados | Formatos de origem, normalização de ações, privacidade, compatibilidade e mãos incompletas | Fixtures reais anonimizadas/licenciadas, reconstrução de contribuições e payouts, rejeição clara de payload inconsistente |
| PLO5/PLO6 | Novo ruleset e contagem de cartas, ranges, equity, avaliação e interface | Casos Omaha específicos, colisões de cartas, benchmarks, testes da mesa e revisão da variante |
| Torneios | Estrutura de blinds, níveis, antes, eliminações, premiação e gestão de stack | Simulação de transições de nível, conservação/premiação e cenários de all-in/eliminação |
| Treino multiway avançado | Ranges condicionais, side pots, stacks efetivos e equity por pote | Matchups de referência, ranges compatíveis sem colisões e benchmarks de latência/precisão |
| Estratégia com solver | Fonte/modelo, cobertura de árvore, sizing, abstrações e comunicação de limites | Referência independente, métricas de exploração/convergência, reprodutibilidade e revisão especializada |

O registro desta versão e da verificação está em [11_PLO_Integrated_Verification.md](11_PLO_Integrated_Verification.md). Regras fixas do jogo estão em [06_PLO_MVP_Product_Rules.md](06_PLO_MVP_Product_Rules.md).
