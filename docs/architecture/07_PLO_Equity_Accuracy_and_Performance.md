# Precisão e desempenho de equity PLO

## Contrato de cálculo

- Hold'em recebe duas cartas fechadas; PLO4 recebe quatro. Ranges são listas de combinações concretas com o mesmo número de cartas da mão analisada.
- Board parcial de zero, três, quatro ou cinco cartas é aceito. Cada rollout completa o board até cinco cartas e elimina do baralho cartas da mão, board e todas as mãos amostradas.
- Um range sem combinações após remoção de blockers e um conjunto multiway sem combinações mutuamente compatíveis são erros explícitos; o cálculo não reutiliza cartas para forçar uma amostra.
- `seed` reproduz exatamente o resultado no mesmo código/runtime. Vitórias, empates e derrotas medem a frequência do resultado; equity credita a fração do pote correspondente ao número de vencedores empatados.
- Pot odds, EV de call antes de rake e SPR reutilizam os calculadores existentes. A estimativa multiway não presume que todos os stacks efetivos sejam iguais; o SPR fornecido ao coach continua sendo a relação heads-up para o stack individual informado.

## Critérios de aceitação estatística

- River conhecido é determinístico e deve retornar resultado exato (zero incerteza de runout).
- Para matchup parcial amostrado, o teste de referência usa 10.000 rollouts, seed `2001`, `As Ah Kd Qc` contra `Ks Kh Jd Tc` no flop `2c 3d 4h`. A equity de referência é 93,5%, com tolerância de ±2 pontos percentuais.
- Como a share por rollout fica entre zero e um, o pior erro-padrão de Monte Carlo é 50/√N pontos percentuais. Em 1.000 rollouts, a faixa aproximada de 95% é ±3,2 pontos; 10.000 rollouts reduzem para ±1 ponto. A tolerância do teste também acomoda a variância da amostragem.

## Desempenho de referência

Ambiente medido: Windows local, Python 3.14, backend sem dependências obrigatórias, CPU de desenvolvimento sem isolamento de benchmark. Matchup acima:

| Rollouts PLO no flop | Tempo observado | Meta de atualização interativa |
| ---: | ---: | ---: |
| 1.000 | 0,111 s | até 2,0 s |
| 10.000 | 1,302 s | análise detalhada/revisão |

O teste automatizado mede 1.000 rollouts e exige menos de 2,0 s para deixar margem entre máquinas. Não usar esse valor como garantia de latência em hardware mais lento; o número de rollouts permanece exposto em `EquityResult`/coach para que estimativas sejam interpretáveis.
