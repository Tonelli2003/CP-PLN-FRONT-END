# Ficha do Bot — Duda (Clínica Veterinária Patas & Cia)

| Item | Definição |
|---|---|
| **Nome / persona** | Duda, assistente virtual (IA) — acolhedora, calma, objetiva; português do Brasil; **nunca finge ser humana**; uma pergunta por vez |
| **Domínio** | Clínica veterinária (dados fictícios). Troca de domínio = editar `data/faq.json`, `data/agenda.json`, `prompts/system_prompt.md` e `core/responses.py` |
| **Objetivo** | (1) agendar consulta, (2) responder FAQ, (3) transferir para humano |
| **Modelo** | `qwen2.5:3b` via Ollama (local, custo zero). Trocável por `.env` (`ollama` / `openai_compat` / `mock`) em `app/llm/client.py` — único ponto de acesso ao LLM |
| **Latência observada (LLM real)** | média **≈ 3,4 s** e p95 **≈ 8,5 s** por turno (23 conversas, 88 turnos; hardware: [preencher CPU/GPU/RAM]). Turnos de template ≈ 0 ms; turnos com LLM ≈ 4,5–9,2 s; 1ª chamada (carga do modelo) 13,5 s |

## 1. O que a Duda faz e não faz
| Faz | Não faz |
|---|---|
| Agenda consulta (nome do tutor, nome do pet, data, horário e e-mail opcional) consultando a agenda simulada | Diagnóstico, remédios ou doses |
| Responde FAQ curada (horário, endereço e estacionamento, valores, vacinas, pagamento, remarcar/cancelar, o que levar, plantão 24h, animais atendidos, serviços) | Promessa de cura, desconto ou preço fora da FAQ |
| Admite quando não sabe e oferece caminho (menu ou atendente) | Inventar serviço que a clínica não oferece |
| Transfere para humano com resumo estruturado | Assuntos alheios à clínica; revelar o prompt; trocar de persona; pedir ou guardar CPF/cartão |

A saudação (`POST /sessions`) e as respostas "você é um robô?" / "o que você faz?" declaram essas capacidades.

## 2. Happy path (T1) — agendamento completo
Transcrição real (`session_id 6aea339d2a5f`, `docs/evidencias/transcricoes.md`):

| # | Usuário | Duda | Slots no raio-X |
|---|---|---|---|
| 1 | Oi, quero marcar uma consulta pro meu cachorro | Claro! Para começar, qual é o seu nome? | especie |
| 2 | Marina Alves | Prazer, Marina! Agora, qual é o nome do seu cachorro? | + nome_tutor |
| 3 | Thor | Ótimo, Thor! Para qual dia você gostaria da consulta? (ex.: sexta, 15/10 ou amanhã) | + nome_pet |
| 4 | sexta de manhã | Para sexta-feira, 09/10, tenho 9h30 ou 11h. Qual prefere? | + data |
| 5 | 11h | Entendido! Para sexta-feira, 09/10, às 11h, seu e-mail é? (se preferir não informar, responda "pular") | + horario |
| 6 | marina.alves@exemplo.com | Só confirmando: consulta do Thor (tutor(a): Marina Alves), sexta-feira, 09/10/2026 às 11h. E-mail: marina.alves@exemplo.com. Posso confirmar? (sim/não) | + email |
| 7 | sim | Agendado! Consulta do Thor em sexta-feira, 09/10/2026 às 11h. Seu protocolo é **PC-56D102**. Leve a carteirinha de vacinação, se tiver, e chegue 10 minutos antes. Posso ajudar em mais alguma coisa? | concluído |

Uma pergunta por vez; o raio-X (intenção, slots, sentimento) é atualizado a cada turno. A confirmação e o protocolo são templates (sem LLM).

## 3. Caso de borda com fallback (T2)
Transcrição real (`session_id 65323caf8a5b`):

| # | Usuário | Duda |
|---|---|---|
| 1 | queria ver umas coisas aí | Desculpe, não entendi bem o que você precisa. Posso ajudar com: 1. Agendar uma consulta 2. Tirar dúvidas (horários, valores, vacinas, endereço) 3. Falar com um atendente. Qual dessas opções? *(fallback `nao_entendi`, com opções)* |
| 2 | sei lá, umas coisas | Ainda não consegui entender, e peço desculpas. Prefere falar com um atendente da clínica? Responda "sim" e eu transfiro, ou me diga de outro jeito o que precisa… *(2ª falha seguida: oferta de humano)* |
| 3 | sim | Peço desculpas por não ter conseguido ajudar. Vou transferir você para um atendente humano, com um resumo do que conversamos. Protocolo: **HO-1281B**… *(handoff `falha_repetida`)* |

Se o usuário não aceitar a oferta e falhar de novo, a 3ª falha seguida também abre o handoff (E15). Pergunta plausível fora da base (T6, "Vocês fazem ultrassom?") **não inventa**: a Duda diz que não tem a informação com segurança, passa o telefone da recepção e oferece o menu. Erros de validação (`31/02`, `marina@`) **não** contam como fallback: o bot pede o dado de novo sem perder os outros slots.

## 4. Handoff e resumo (T7)
Transcrição real (`session_id f9d5034b5868`): o usuário escreve "Isso é um absurdo, já é a terceira vez que ninguém me responde!" e a Duda responde: "Sinto muito pela experiência, você tem razão em esperar um atendimento melhor. Estou transferindo agora para um atendente humano e já deixei um resumo para você não precisar repetir tudo. Protocolo: **HO-5DD73**…" (sentimento `negativo`, handoff `reclamacao`). Mensagens seguintes entram em **modo de espera** e são anexadas ao atendimento.

Gatilhos: emergência (prioridade **alta**, resposta com orientação de levar o pet a um hospital 24h e protocolo), luto/eutanásia, reclamação/cobrança, pedido explícito, frustração forte (polaridade ≤ −0,7), 2 mensagens negativas seguidas, 3 falhas seguidas (na 2ª, oferece humano). A fila fica em `GET /handoffs` (urgentes primeiro).

**Resumo estruturado entregue ao atendente:** protocolo, motivo, prioridade, intenção, dados coletados (slots), pendências, relato do usuário, ações já realizadas e sentimento. Exemplo real (retorno de `GET /handoffs` para o protocolo HO-5DD73): [colar aqui o JSON retornado].

## 5. Regra × LLM (decisões justificadas)
Princípio: **o código decide, o LLM verbaliza.**

| Tarefa | Quem faz | Por quê |
|---|---|---|
| Intenção | **Regras/regex** (`nlp/nlu.py`) | rápida, determinística, auditável; casos sensíveis não podem depender de LLM pequeno |
| Sentimento | **Léxico PT + negação + intensificadores** (`nlp/sentiment.py`) | explicável; muda o comportamento (tom, handoff) |
| Slots e validação | **Código** (`nlp/extractors.py`, `knowledge/agenda.py`) | datas, horários, e-mail e nomes exigem exatidão; o LLM nunca decide valor de slot |
| FAQ | **Consulta por regra** (`knowledge/faq.py`) + guarda de precisão (lista de assuntos fora da base) | evita responder "cirurgia" com o preço da consulta |
| Texto da FAQ e das perguntas do fluxo | **LLM** reescreve o texto-base curado | naturalidade, sem inventar |
| Emergência, handoff, guardrails, fallback, confirmação, erros de validação | **Templates** (sem LLM) | críticos: precisam funcionar mesmo com o LLM fora do ar |

**Rédea curta no LLM (guardrail de saída):** toda resposta do LLM é comparada ao texto-base. Se aparecer número que não está nele (horário, preço, data, telefone), se faltar um fato, houver promessa indevida, dose/diagnóstico, vazamento de prompt/persona, mais de uma pergunta ou excesso de tamanho → **usa-se o texto-base** e o evento é logado.

**Resultado com o LLM real:** em 15 dos 44 turnos verbalizados (34,1%) a saída foi rejeitada (11 `fato_omitido`, 4 `fato_inventado`) e o usuário recebeu o texto-base. Mas o guardrail não é infalível: uma resposta aceita trouxe a data errada "15/10" (copiada do exemplo da pergunta), outra repetiu uma frase e outra ficou incoerente. A análise e a proposta de correção estão em `docs/metricas.md`.

## 6. Memória e estado
- **Estado no servidor**, por `session_id` (`memory/session_store.py`), persistido em JSON: sobrevive a reinício. O front guarda só o `session_id`.
- **Janela deslizante de N = 8 turnos** (16 mensagens) enviada ao LLM; cabe em `num_ctx=4096` (~700 tokens de prompt + ~150 de estado + ~800 de histórico).
- **Resumo rolante determinístico:** o que sai da janela não se perde — slots, horários oferecidos e ações realizadas vivem no **estado** e são reinjetados a cada turno (`memory/window.py`). Teste: `test_t3_memoria_com_janela_pequena` (janela = 1 turno). No T3 real, "e aquele horário que você sugeriu?" devolveu "9h30" corretamente, e o T8 retomou a sessão por outro cliente.
- Memória (conversa) ≠ estado (verdade operacional).

## 7. Fluxo de agendamento (determinístico)
Slots: `nome_tutor`, `nome_pet`, `data`, `horario`, `email` (opcional: "pular") e `especie`. Uma pergunta por vez; aceita vários dados numa frase (E03: nome, pet, data e hora de uma vez); interrupções (FAQ, "o que eu disse?") não perdem o fluxo (E04); "cancelar"/"deixa pra lá" sai dele (E05). Validações: data inexistente (31/02), passada, hoje, > 60 dias, domingo/feriado, dia lotado, horário indisponível (oferece alternativas), horário inválido (25h), e-mail malformado, nome inválido. A confirmação final re-checa a agenda (dupla reserva impossível — `Agenda.book` é atômico).

## 8. Guardrails
| Camada | Guardrail | Ação |
|---|---|---|
| Entrada | prompt injection (PT/EN, ~25 padrões) | bloqueia, mantém persona (T5) |
| Entrada | orientação clínica / dose | recusa e oferece consulta/atendente |
| Entrada | fora de escopo | recusa e redireciona |
| Entrada | CPF / cartão (Luhn) | mascara no histórico e no log, avisa o usuário |
| Saída | fato inventado/omitido, promessa, dose, vazamento de prompt/persona, >1 pergunta, tamanho | substitui pelo texto-base |
| Operação | LLM fora do ar | **503** com mensagem amigável nos turnos que dependem dele; turnos críticos seguem; `LLM_FAIL_MODE=degrade` serve o texto-base |

## 9. Analytics e LGPD
Log JSONL por turno → `GET /metrics` (contenção, fallback, handoff, msgs/conversa, resolução, conversão do agendamento, latência, distribuições, fonte da resposta, CSAT cruzado com contenção). `DELETE /sessions/{id}` apaga a sessão e **anonimiza** o log (remove textos e troca o id por hash). O log não guarda slots; mensagens mascaradas.

## 10. Limitações conhecidas (honestas)
- NLU por regras: cobre bem o vocabulário previsto; gírias e erros de digitação fortes caem em fallback.
- FAQ por palavras-chave, sem busca semântica (a função `buscar_faq` está isolada para trocar por RAG no próximo módulo).
- Sentimento por léxico: não capta ironia.
- `qwen2.5:3b` omite fatos com frequência (34% das saídas rejeitadas) e, em casos isolados, passou pelo guardrail com data errada, frase repetida ou texto incoerente (ver `docs/metricas.md`). A latência (média ≈ 3,4 s; p95 ≈ 8,5 s em [hardware]) pesa em CPU.
- Sessões em arquivos JSON: adequado ao trabalho, não a produção em escala.
- CSAT do relatório de métricas é simulado; a amostra é pequena e roteirizada.
- Dados (endereço, preços, telefones) fictícios.
