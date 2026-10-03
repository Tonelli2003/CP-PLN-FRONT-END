"""Atualiza as TABELAS de docs/metricas.md (entre os marcadores) a partir de docs/evidencias/metrics_snapshot.json.
Uso: python scripts/gerar_relatorio_metricas.py
O texto de leitura crítica e a proposta de melhoria continuam sendo escritos pelo grupo."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START, END = "<!-- METRICS:START -->", "<!-- METRICS:END -->"


def pct(x):
    return f"{x * 100:.1f}%".replace(".", ",")


def table(d, h1, h2="Qtde"):
    if not d:
        return "_(sem ocorrências)_\n"
    return f"| {h1} | {h2} |\n|---|---:|\n" + "\n".join(f"| {k} | {v} |" for k, v in d.items()) + "\n"


def build(m):
    csat = lambda v: "—" if v is None else str(v).replace(".", ",")  # noqa: E731
    return f"""
**Retorno de `GET /metrics`** (período: {m['periodo']['inicio']} → {m['periodo']['fim']})

| Métrica | Valor | Definição |
|---|---:|---|
| Conversas | {m['total_conversas']} | sessões com ao menos 1 mensagem do usuário |
| Turnos do usuário | {m['total_turnos_usuario']} | |
| **Taxa de contenção** | **{pct(m['taxa_contencao'])}** | conversas sem handoff ÷ total de conversas |
| **Taxa de fallback** | **{pct(m['taxa_fallback'])}** | turnos em fallback ÷ total de turnos do usuário |
| **Taxa de handoff** | **{pct(m['taxa_handoff'])}** | conversas com handoff ÷ total de conversas |
| **Mensagens por conversa** | **{str(m['mensagens_por_conversa']).replace('.', ',')}** | turnos do usuário ÷ conversas |
| Taxa de resolução | {pct(m['taxa_resolucao'])} | contida **e** com objetivo cumprido (agendou ou teve FAQ respondida) |
| Agendamentos concluídos | {m['agendamentos_concluidos']} | conclusão sobre fluxos iniciados: {pct(m['taxa_conclusao_agendamento'])} |
| Latência média / p95 | {m['latencia_media_ms']} ms / {m['latencia_p95_ms']} ms | |
| CSAT médio (geral / contidas / transferidas) | {csat(m['csat_medio'])} / {csat(m['csat_medio_conversas_contidas'])} / {csat(m['csat_medio_conversas_transferidas'])} | {m['total_feedbacks']} avaliações |
| Turnos com tom de acolhimento | {m['turnos_com_tom_de_acolhimento']} | sentimento negativo mudando o comportamento |

**Fallback por tipo**

{table(m['fallback_por_tipo'], 'Tipo')}
**Fallback por estado da conversa** (onde o bot estava quando falhou)

{table(m['fallback_por_estado'], 'Estado')}
**Handoff por motivo**

{table(m['handoff_por_motivo'], 'Motivo')}
**Erros de validação de slots** (tratados sem perder dados)

{table(m['erros_validacao'], 'Erro')}
**Eventos de guardrail registrados**

{table(m['eventos_guardrail'], 'Guardrail')}
**Distribuição de intenções**

{table(m['distribuicao_intencoes'], 'Intenção')}
**Fonte da resposta**

{table(m['fonte_da_resposta'], 'Fonte')}
"""


def main_update(m):
    p = ROOT / "docs" / "metricas.md"
    txt = p.read_text(encoding="utf-8")
    new = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: START + build(m) + END, txt, flags=re.S)
    p.write_text(new, encoding="utf-8")
    print("docs/metricas.md atualizado")


if __name__ == "__main__":
    main_update(json.loads((ROOT / "docs" / "evidencias" / "metrics_snapshot.json").read_text(encoding="utf-8")))
