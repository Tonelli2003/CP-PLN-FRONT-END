# Relatório de métricas — Prosa Bot (Duda · Clínica Veterinária Patas & Cia)

<<<<<<< HEAD
=======
## Resumo (1 página)
**Base:** 23 conversas (T1–T8 + 16 variadas), 88 turnos do usuário, LLM real `qwen2.5:3b` (Ollama), executado em 02/10/2026. Retorno completo de `GET /metrics` em `evidencias/metrics_snapshot.json`.

| Métrica | Valor |
|---|---:|
| Taxa de contenção | 69,6% |
| Taxa de fallback | 8,0% (7/88) |
| Taxa de handoff | 30,4% (7/23) |
| Mensagens por conversa | 3,83 |
| Taxa de resolução (contida e objetivo cumprido) | 43,5% |
| Latência média / p95 | 3.417 ms / 8.489 ms |

**Insight:** o guardrail de saída rejeitou 34,1% das respostas do LLM (15 de 44; 11 `fato_omitido`, 4 `fato_inventado`) e ainda deixou passar uma data errada (15/10 numa sexta 09/10), copiada do exemplo fixo da pergunta de data. Além disso, a contenção (69,6%) superestima a utilidade: a resolução real é 43,5%.

**Melhoria (já aplicada em parte):** (a) o exemplo da pergunta de data foi trocado por um sem dígitos (“ex.: sexta ou amanhã”) — **feito no código**; (b) validar datas `dd/mm` e frases repetidas no guardrail de saída, (c) exigir no prompt de FAQ que todos os fatos sejam repetidos, (d) logar o texto rejeitado. **Meta:** rejeições < 20%, 0 respostas aceitas com data errada ou frase duplicada. **Pendente do grupo:** reexecutar `run_scenarios.py` com o Ollama para medir o “depois” e atualizar as tabelas abaixo.

> Os números acima e o anexo foram medidos **antes** da correção (a); só a reexecução com o LLM real mostra o efeito.

---
# Anexo — análise detalhada

>>>>>>> 124e2bd (Atualizações no frontend e backend)
> **Origem dos números:** `python backend/scripts/run_scenarios.py --base-url http://localhost:8000 --api-key <chave>`, executado em 02/10/2026 com **LLM real (`qwen2.5:3b` via Ollama local)**. São 23 conversas (T1–T8 + 16 variadas) e 88 turnos do usuário. Retorno completo de `GET /metrics` em `docs/evidencias/metrics_snapshot.json`; conversas em `docs/evidencias/transcricoes.md`.
> ⚠️ As 8 notas de CSAT foram **simuladas pelo script** (para exercitar `POST /feedback`); não representam usuários reais.

## 1. Como as métricas são calculadas
Todas saem do **log por turno** (`data/runtime/turns.jsonl`), nunca de contadores em memória: sobrevivem a reinício e são auditáveis linha a linha. O log não guarda valores de slots e a mensagem vai mascarada (LGPD).

<!-- METRICS:START -->
<<<<<<< HEAD
**Retorno de `GET /metrics`** (período: 2026-10-02T21:48:15-03:00 → 2026-10-02T21:53:13-03:00)
=======
**Retorno de `GET /metrics`** (período: 2026-10-04T16:56:38-03:00 → 2026-10-04T17:01:37-03:00)
>>>>>>> 124e2bd (Atualizações no frontend e backend)

| Métrica | Valor | Definição |
|---|---:|---|
| Conversas | 23 | sessões com ao menos 1 mensagem do usuário |
| Turnos do usuário | 88 | |
| **Taxa de contenção** | **69,6%** | conversas sem handoff ÷ total de conversas |
<<<<<<< HEAD
| **Taxa de fallback** | **8,0%** (7/88) | turnos em fallback ÷ turnos do usuário |
| **Taxa de handoff** | **30,4%** (7/23) | conversas com handoff ÷ total de conversas |
| **Mensagens por conversa** | **3,83** | turnos do usuário ÷ conversas |
| Taxa de resolução | 43,5% | contida **e** com objetivo cumprido (agendou ou FAQ respondida) |
| Agendamentos concluídos | 4 | conclusão sobre fluxos iniciados: 40,0% |
| **Latência média / p95** | **3.417 ms / 8.489 ms** | por turno, LLM real (turnos de template ≈ 0 ms; 1ª chamada, com carga do modelo: 13,5 s) |
| CSAT médio (geral / contidas / transferidas) | 3,88 / 4,80 / 2,33 | 8 avaliações **simuladas** |
| Turnos com tom de acolhimento | 1 | sentimento negativo mudando o comportamento |

**Fonte da resposta:** `template` 44 · `llm` 29 · `template_guardrail` 15 (o LLM foi chamado em 44 turnos; em 15 a saída foi rejeitada e trocada pelo texto-base).

**Eventos de guardrail:** `output:fato_omitido` 11 · `output:fato_inventado` 4 · `input:prompt_injection` 2 · `input:orientacao_medica` 2 · `input:fora_de_escopo` 1 · `input:dado_sensivel` 1.

**Fallback por tipo:** `nao_entendi` 5 · `fora_da_base` 2. **Fallback por estado** (estado em que o bot ficou *após* o fallback): `menu` 4 · `aceite_humano` 2 · `idle` 1.

**Handoff por motivo:** `falha_repetida` 2 · `pedido_do_usuario` 1 · `tema_sensivel` 1 · `frustracao` 1 · `reclamacao` 1 · `emergencia` 1.

**Erros de validação de slots** (tratados sem perder dados): `horario_indisponivel` 2 · `data_inexistente` 1 · `email_invalido` 1 · `dia_lotado` 1 · `clinica_fechada` 1.

**Sentimento:** neutro 82 · negativo 3 · positivo 3. **FAQ mais consultadas:** endereço 3 · valores da consulta 2 · horário, vacinas, pagamento, primeira consulta e remarcar/cancelar 1 cada.

**Intenções (88 turnos):** agendar 45 · faq 10 · desconhecido 9 · confirmar 4 · orientacao_medica 3 · demais 17 (retomar, prompt_injection, reclamacao, agradecimento etc.; lista completa no snapshot).
=======
| **Taxa de fallback** | **8,0%** | turnos em fallback ÷ total de turnos do usuário |
| **Taxa de handoff** | **30,4%** | conversas com handoff ÷ total de conversas |
| **Mensagens por conversa** | **3,83** | turnos do usuário ÷ conversas |
| Taxa de resolução | 43,5% | contida **e** com objetivo cumprido (agendou ou teve FAQ respondida) |
| Agendamentos concluídos | 4 | conclusão sobre fluxos iniciados: 40,0% |
| Latência média / p95 | 3425 ms / 8089 ms | |
| CSAT médio (geral / contidas / transferidas) | 3,88 / 4,8 / 2,33 | 8 avaliações |
| Turnos com tom de acolhimento | 1 | sentimento negativo mudando o comportamento |

**Fallback por tipo**

| Tipo | Qtde |
|---|---:|
| nao_entendi | 5 |
| fora_da_base | 2 |

**Fallback por estado da conversa** (onde o bot estava quando falhou)

| Estado | Qtde |
|---|---:|
| menu | 4 |
| aceite_humano | 2 |
| idle | 1 |

**Handoff por motivo**

| Motivo | Qtde |
|---|---:|
| falha_repetida | 2 |
| reclamacao | 1 |
| pedido_do_usuario | 1 |
| frustracao | 1 |
| emergencia | 1 |
| tema_sensivel | 1 |

**Erros de validação de slots** (tratados sem perder dados)

| Erro | Qtde |
|---|---:|
| horario_indisponivel | 2 |
| data_inexistente | 1 |
| email_invalido | 1 |
| dia_lotado | 1 |
| clinica_fechada | 1 |

**Eventos de guardrail registrados**

| Guardrail | Qtde |
|---|---:|
| output:fato_omitido | 9 |
| output:fato_inventado | 4 |
| input:prompt_injection | 2 |
| input:orientacao_medica | 2 |
| input:fora_de_escopo | 1 |
| output:sem_pergunta | 1 |
| input:dado_sensivel | 1 |

**Distribuição de intenções**

| Intenção | Qtde |
|---|---:|
| agendar | 45 |
| faq | 10 |
| desconhecido | 9 |
| confirmar | 4 |
| orientacao_medica | 3 |
| retomar | 2 |
| prompt_injection | 2 |
| reclamacao | 2 |
| agradecimento | 2 |
| fora_de_escopo | 1 |
| despedida | 1 |
| menu_opcao | 1 |
| emergencia | 1 |
| tema_sensivel | 1 |
| humano | 1 |
| identidade | 1 |
| ajuda | 1 |
| saudacao | 1 |

**Fonte da resposta**

| Fonte | Qtde |
|---|---:|
| template | 44 |
| llm | 30 |
| template_guardrail | 14 |

>>>>>>> 124e2bd (Atualizações no frontend e backend)
<!-- METRICS:END -->

## 2. Leitura crítica (o que os números dizem — e o que escondem)
1. **Insight principal: o guardrail de saída rejeitou 34% das respostas do LLM, mas deixou passar defeitos.** Dos 44 turnos em que o `qwen2.5:3b` foi chamado, 15 (34,1%) viraram `template_guardrail`: 11 por `fato_omitido` e 4 por `fato_inventado`. Cruzando o log com as transcrições:
   - **Omissões:** 7 das 11 são respostas de FAQ com vários fatos (valores, endereço, vacinas, cancelamento): o modelo pequeno resume e perde um deles. As outras 4 estão no fluxo de agendamento.
   - **Invenções:** os 4 ocorrem no agendamento, e 3 delas são respostas à **pergunta de data**, cujo texto traz o exemplo fixo "(ex.: sexta, 15/10 ou amanhã)". Há indício forte da causa: na conversa E10 o modelo escreveu "sexta-feira, **15/10**" quando o slot era 09/10 (15/10 nem é sexta), e essa resposta **chegou ao usuário**. O modelo parece copiar a data do exemplo.
   - **O que o guardrail não pega:** além dessa data errada (E10), passaram uma frase duplicada ("Posso ajudar em mais alguma coisa?" duas vezes, E02) e uma resposta incoerente após o aviso de CPF (E16). O guardrail valida números/horários e fatos da base, mas não consistência de datas `dd/mm`, repetição ou coerência.
   - **Custo oculto:** os 15 turnos rejeitados gastaram de 4,7 a 9,2 s de LLM para entregar o texto-base. Estimando os turnos de template em ≈ 0 ms, cada turno com LLM leva cerca de 6,8 s (3.417 ms × 88 ÷ 44).
2. **A contenção sozinha engana.** 69,6% de contenção parece bom, mas a **resolução é 43,5%**: 26 pontos de conversas "contidas" não terminaram em agendamento nem em FAQ respondida (desistências, saudações, testes). Contenção mede "não chamou humano", não "ajudou".
3. **Nem todo handoff é falha.** Dos 7 handoffs, 5 são *por desenho* (emergência, luto, reclamação, pedido do usuário, frustração). Só **2 (`falha_repetida`) são culpa do bot**, e ambos vêm de testes com entrada deliberadamente vaga (T2 e E15).
4. **Os 7 fallbacks vêm todos de entradas planejadas como difíceis:** 5 `nao_entendi` (T2 e E15, mensagens como "hmm", "talvez", "sei lá") e 2 `fora_da_base` (ultrassom e hotel para pets, em que o bot admite que não sabe, como esperado em T6). O campo `fallback_por_estado` registra o estado em que o bot ficou *depois* do fallback (menu na 1ª falha, oferta de humano na 2ª, handoff na 3ª; 4+2+1 = 7), então **não indica** que o menu cause falhas. A escalada funcionou como projetado. Já os erros de validação (data inexistente, e-mail inválido, horário ocupado, dia lotado, feriado) são tratados sem perder slots e sem contar como fallback. Conclusão honesta: com uma amostra roteirizada, a taxa de 8% **não mede** a fraqueza real do NLU.
5. **CSAT × contenção:** o cruzamento está implementado (contidas × transferidas), mas com notas simuladas só prova que o mecanismo funciona. Com notas reais, mostraria se a contenção "compra" satisfação ou esconde frustração.

## 3. Proposta de melhoria (baseada nos dados)
**Hipótese:** o modelo de 3B (i) copia a data do exemplo fixo da pergunta e (ii) resume respostas de FAQ com vários fatos; e o guardrail atual não cobre datas `dd/mm` nem repetição.
**Mudanças:**
- (a) Trocar o exemplo da pergunta de data por um sem dígitos ("ex.: sexta ou amanhã") ou gerado dinamicamente a partir da data de hoje.
- (b) No guardrail de saída: validar datas `dd/mm` contra o slot/oferta do turno e rejeitar frases repetidas.
- (c) No prompt de verbalização da FAQ, exigir "repita todos os horários, valores e endereços" e incluir um exemplo (few-shot) com vários fatos.
- (d) Registrar no log o texto rejeitado (mascarado), para auditar cada rejeição.

**Como medir:** repetir o mesmo roteiro (T1–T8 + 16 conversas) e comparar (1) `template_guardrail ÷ (llm + template_guardrail)`, hoje **34,1%**, com meta < 20%; (2) auditoria manual das transcrições, contando respostas aceitas com data errada (hoje **1**) e frases duplicadas (hoje **1**), com meta **0**; (3) latência média (hoje **3.417 ms**).

**Para o fallback:** coletar conversas reais de colegas (com frases não roteirizadas) antes de mexer no NLU, e só então priorizar sinônimos novos e a busca parcial na FAQ (`buscar_faq`) antes do menu.

## 4. Limitações da medição
- Amostra pequena e **roteirizada** (23 conversas): as taxas não generalizam; fallback e handoff por falha refletem testes feitos para falhar.
- CSAT **simulado**; abandono sem handoff conta como "contida" (por isso existe `taxa_resolucao`).
<<<<<<< HEAD
- Latência depende do hardware ([preencher: CPU/GPU/RAM]) e a primeira chamada inclui o carregamento do modelo (13,5 s).
=======
- Latência depende do hardware (**PENDENTE — grupo informar CPU/GPU/RAM**) e a primeira chamada inclui o carregamento do modelo (13,5 s).
>>>>>>> 124e2bd (Atualizações no frontend e backend)
- O log não guarda o texto rejeitado pelo guardrail; a análise das causas usou as transcrições e é indício, não prova (proposta d).
