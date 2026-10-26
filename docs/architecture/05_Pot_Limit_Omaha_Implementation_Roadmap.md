# Roadmap de implementação: Pot-Limit Omaha (PLO)

**Status:** etapas 1–11 concluídas; MVP PLO4 liberado como modo de treino local.  
**Objetivo:** registrar escopo, critérios e evolução do suporte Pot-Limit Omaha (quatro cartas).

## Ponto de partida

O MVP já oferece mãos completas de Hold’em e PLO4 localmente, incluindo apostas pot-limit, bots heurísticos, avaliação Omaha, potes laterais, coach e revisão de mãos. PLO não usa solver e tem as limitações documentadas em [12_PLO_MVP_Release_and_Roadmap.md](12_PLO_MVP_Release_and_Roadmap.md). As regras fixas estão em [06_PLO_MVP_Product_Rules.md](06_PLO_MVP_Product_Rules.md); o caminho de ativação para usuários está em [guia do usuário](../USER_GUIDE.md).

Este plano preserva o backend Python sem dependências obrigatórias e a interface web atual. Cada fase deve terminar com os critérios de aceite descritos nela.

## Etapas

### 1. Fechar escopo e regras do produto

- Fixar a primeira versão como PLO high, quatro cartas fechadas, 2–6 jogadores e apostas pot-limit.
- Adotar as decisões registradas em [Regras de produto do MVP PLO](06_PLO_MVP_Product_Rules.md): mesa local de seis lugares, blinds $1/$2, stacks de $200, sem rake, ante ou straddle.
- Manter modalidade, tamanho da mesa na UI, blinds, stack inicial e política sem rake fixos no MVP; o motor aceita de 2 a 6 jogadores. Recompra automática de $200 quando um assento zera.
- Aplicar as regras descritas no documento de produto para all-in curto, devolução de aposta não igualada, construção de potes laterais, runout automático e desempate por fichas indivisíveis.
- Usar os materiais de estudo existentes para priorizar vocabulário e conceitos do coach: nut hands, redraws, wraps, blockers, equity e SPR.

**Aceite:** regras da versão inicial documentadas em `06_PLO_MVP_Product_Rules.md`, sem ambiguidades sobre distribuição, apostas, showdown e divisão de potes.

### 2. Tornar o motor de regras independente da modalidade

- Generalizar o estado da mão para receber `GameRules`, sem restringir a transição à aposta no-limit de Hold’em.
- Distribuir duas cartas por jogador em Hold’em e quatro em PLO, preservando baralho, posições, blinds e cartas queimadas.
- Parametrizar limites de assentos e validações de cartas pelo ruleset.
- Manter compatibilidade com o modo atual de Hold’em e explicitar a variante no estado e nos registros de mão.

**Aceite:** ambos os modos iniciam mãos válidas; nenhum fluxo de Hold’em depende de suposições silenciosas sobre quantidade de cartas ou estrutura de aposta.

### 3. Implementar apostas pot-limit completas

- Integrar o limite de raise pot-limit ao validador central de ações em todas as streets.
- Calcular min-raise, máximo raise-to, call, bet, raise e all-in curto a partir do pote e das contribuições atuais.
- Tratar corretamente blinds, múltiplos raises, jogadores all-in e jogadores sem direito de reabrir a ação.
- Devolver ações legais e limites de aposta calculados pelo backend; o cliente não deve ser a autoridade das regras.

**Aceite:** nenhuma ação aceita aposta acima do pote ou fora do stack; sequências de raise, short all-in e reabertura obedecem às regras definidas.

### 4. Completar showdown e potes para PLO

- Selecionar a avaliação por modalidade: Hold’em usa a melhor combinação permitida; PLO usa exatamente duas cartas fechadas e três comunitárias.
- Ligar a avaliação Omaha já existente ao término de mão e ao desempate.
- Construir e distribuir potes principais e laterais com múltiplos jogadores all-in e empates.
- Garantir conservação de fichas e registrar cartas vencedoras usadas no showdown.

**Aceite:** exemplos de mão cobrem board-only trap (não permitido em Omaha), uso de exatamente duas cartas da mão, empate e potes laterais; a soma de payouts corresponde às contribuições.

### 5. Generalizar equity, ranges e pot odds para Omaha

- Adaptar Monte Carlo para mãos de quatro cartas, board parcial, múltiplos oponentes e ranges de combinações de quatro cartas.
- Remover colisões de cartas ao amostrar ranges e runouts; distribuir empates pela quantidade de vencedores.
- Reutilizar avaliação rápida e cálculo de pot odds, EV e SPR, validando entradas e casos sem combinações possíveis.
- Definir precisão e latência aceitáveis para atualização durante uma decisão; permitir seed para resultados reproduzíveis.
- Aplicar o contrato, as tolerâncias e o benchmark em [Precisão e desempenho de equity PLO](07_PLO_Equity_Accuracy_and_Performance.md).

**Aceite:** matchups conhecidos e cenários de flop/turn têm resultados dentro das tolerâncias documentadas em `07_PLO_Equity_Accuracy_and_Performance.md`; benchmarks medem tempo e quantidade de rollouts no ambiente de referência.

### 6. Evoluir análise de draws e qualidade de mão PLO

- Completar outs limpos/sujos e blockers para draws de sequência, flush e redraws usando as restrições Omaha.
- Identificar draws de nut e distinguir outs que melhoram a mão sem garantir a melhor mão possível.
- Incorporar textura de board, duplicação de cartas, flushes possíveis e redraws do adversário.
- Retornar evidências legíveis para o coach, sem apresentar estimativas como certezas.
- Definir as semânticas de nut outs, redraw, blocker e outs sem adversário conhecido conforme [Análise de draws PLO](08_PLO_Draw_Analysis.md).

**Aceite:** cenários de wraps, flush draws, blockers e redraws conhecidos são classificados corretamente e explicados com os outs considerados/removidos; sem mão adversária exposta, os outs permanecem explicitamente não verificados.

### 7. Criar estratégia e perfis de bots para PLO

- Adaptar os bots para avaliar quatro cartas, ranges e sizing pot-limit, sem reutilizar força de mão de Hold’em como proxy.
- Definir perfis iniciais simples e configuráveis (por exemplo, tight, agressivo e calling station), documentando que não são solver/GTO.
- Incluir seleção de mãos pré-flop e respostas pós-flop adequadas a nut potential, posição, stack e SPR.
- Instrumentar decisões para que cada ação possa ser explicada e reproduzida.

**Aceite:** bot completa mãos sem ação ilegal ou deadlock; decisões respeitam limites pot-limit; o produto não rotula heurísticas como estratégia ótima.

### 8. Adaptar coach, histórico e revisão de mãos

- Tornar o coach consciente da variante e usar métricas Omaha nas decisões e explicações.
- Revisar conselhos atuais que pressupõem duas cartas, categorias de range de Hold’em ou equidade heads-up fixa.
- Persistir variante, quatro cartas do jogador, board, ações, contribuições, ranges/estimativas e resultado na revisão.
- Adicionar revisão de leak PLO de forma incremental, separando indicadores PLO dos de Hold’em.

**Aceite:** uma mão PLO pode ser reconstruída do histórico; conselho e revisão mostram dados da variante correta e indicam limitações das estimativas.

### 9. Expor seleção de modalidade e ações pela API

- Permitir selecionar Hold’em ou PLO ao iniciar uma sessão/mão, com validação no servidor.
- Incluir variante, hole cards, limites de aposta, ações legais e dados de showdown nos contratos de API.
- Atualizar parsing de ranges e payloads para suportar combinações de quatro cartas.
- Retornar erros claros para variante ou ações inválidas; manter respostas compatíveis ou versionar o contrato quando necessário.

**Aceite:** API inicia e avança mãos nos dois modos, recusa entradas inválidas e não depende de estado de variante mantido apenas no navegador.

### 10. Adaptar mesa e controles da interface

- Habilitar o seletor de modalidade quando os fluxos PLO estiverem disponíveis.
- Renderizar quatro cartas privadas com leitura clara em desktop e telas estreitas.
- Ajustar rótulos e presets para mostrar aposta total (`raise to`) e o máximo permitido no pot-limit.
- Exibir variante, blinds, pote, ações legais e feedback de erro/ação em andamento com consistência.
- Preservar privacidade das cartas dos bots até o showdown e a identidade visual atual.

**Aceite:** uma mão é acompanhável e jogável nos tamanhos de tela suportados, sem cartas ou controles cortados; a UI reflete os limites recebidos do backend.

### 11. Verificação integrada e robustez

- Cobrir regras, distribuição, legalidade de ações, avaliação, potes, equity, bots, API, histórico e estados da interface.
- Adicionar cenários determinísticos com decks/seeds fixos e invariantes de conservação de fichas.
- Rodar self-play PLO em quantidade crescente de mãos e auditar mãos concluídas, empates, all-ins, folds e deadlocks.
- Registrar benchmarks de equity e showdown; corrigir regressões antes de liberar a modalidade.

**Aceite:** critérios funcionais e de desempenho definidos passam de forma reproduzível; uma sessão completa de início a revisão funciona sem intervenção manual.

### 12. Liberar o MVP PLO e planejar expansão

- Liberar inicialmente como modo de treino local contra bots, com limites e limitações comunicados na interface.
- Atualizar documentação de execução, arquitetura, API e guia de usuário.
- Acompanhar problemas encontrados em sessões e priorizar estabilidade, qualidade do coach e variedade de situações.
- Considerar como fases posteriores: hand histories importadas, formatos PLO adicionais, torneios, treino multiway mais avançado e estratégia baseada em solver, cada um com escopo e validação próprios.

**Aceite:** caminho de ativação documentado; um usuário consegue selecionar PLO, completar mãos e consultar revisão; limitações conhecidas são registradas.

## Ordem e dependências

```text
1. Escopo e regras
   ↓
2. Motor por variante → 3. Apostas pot-limit → 4. Showdown e potes
   ↓                                      ↓
5. Equity/ranges → 6. Draws/análise → 7. Bots → 8. Coach e revisão
                                                   ↓
                                  9. API → 10. Interface → 11. Verificação
                                                   ↓
                                              12. MVP
```

As etapas 5–8 puderam avançar em paralelo depois que os contratos de variante, estado e avaliação foram estabilizados. A integração e liberação foram validadas na etapa 11; registro e métricas estão em [11_PLO_Integrated_Verification.md](11_PLO_Integrated_Verification.md).

## Fora do MVP inicial

- Promessa de jogo ótimo, solver completo ou aconselhamento financeiro.
- Multiplayer online, contas, nuvem ou dependência de serviços externos.
- Importação universal de históricos antes de definir formatos e regras suportados.
- Outras variantes (PLO5/PLO6, Hi-Lo, Courchevel) sem especificação e testes próprios.

## Referências do projeto

- [README do simulador](../../README.md)
- [Roadmap geral de implementação](03_Simulator_Implementation_Roadmap.md)
- [Arquitetura do cérebro do simulador](02_Poker_Simulator_Brain_Architecture.md)
- [Guia Pot-Limit Omaha: Zero to PLO50](../study_guides/Zero%20to%20PLO50%20-%20v7.md)
- [Companion de estudos](../study_guides/Zero%20to%20PLO50%20-%20Study%20Companion%20v1.0%20(EN).md)
- [Perfis heurísticos dos bots PLO](09_PLO_Bot_Profiles_and_Reproducibility.md)
- [Coach e revisão de mãos PLO](10_PLO_Coach_and_Hand_Review.md)
- [Liberação do MVP e roadmap de expansão](12_PLO_MVP_Release_and_Roadmap.md)
