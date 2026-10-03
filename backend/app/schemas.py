"""Modelos Pydantic de entrada e saída — o CONTRATO da API (qualquer "lente" depende só disto)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Só restringe os CARACTERES (o id vira nome de arquivo: bloqueia path traversal). Qualquer id bem formado, mesmo curto
# como "abc", que não exista devolve 404 (e não 422), como pede o contrato.
SESSION_ID_PATTERN = r"^[A-Za-z0-9_\-]{1,64}$"


class ErrorDetail(BaseModel):
    code: str = Field(..., examples=["sessao_nao_encontrada"])
    message: str = Field(..., description="Mensagem pronta para exibir ao usuário.")


class ErrorResponse(BaseModel):
    detail: ErrorDetail


# ---------------------------------------------------------------- health
class LLMHealth(BaseModel):
    provider: str
    model: str
    available: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = Field(..., description="'degraded' = API no ar, mas LLM indisponível.")
    app: str
    llm: LLMHealth
    sessions_in_memory: int


# ---------------------------------------------------------------- sessões
class SessionCreateResponse(BaseModel):
    session_id: str = Field(..., examples=["8f1c2a9b03de"])
    greeting: str = Field(..., description="Saudação do bot, que declara suas capacidades.")
    capabilities: list[str]
    created_at: str


class Slots(BaseModel):
    nome_tutor: Optional[str] = None
    nome_pet: Optional[str] = None
    especie: Optional[str] = None
    data: Optional[str] = Field(None, description="ISO (YYYY-MM-DD), validada contra a agenda.")
    horario: Optional[str] = Field(None, description="HH:MM, validado contra a agenda.")
    email: Optional[str] = Field(None, description="'nao_informado' se o usuário preferiu pular.")


class Sentiment(BaseModel):
    label: Literal["positivo", "neutro", "negativo"]
    score: float = Field(..., ge=0, le=1, description="Confiança na etiqueta.")
    polarity: float = Field(..., ge=-1, le=1)


class HandoffSummary(BaseModel):
    protocolo: str
    motivo: str
    motivo_codigo: str
    prioridade: Literal["alta", "normal"]
    intencao: str
    dados_coletados: dict[str, Any]
    pendencias_do_agendamento: list[str]
    relato: str
    acoes_realizadas: list[str]
    sentimento: dict[str, Any]
    turnos_do_usuario: int
    criado_em: str


class Handoff(BaseModel):
    active: bool = False
    reason: Optional[str] = None
    priority: Optional[Literal["alta", "normal"]] = None
    protocol: Optional[str] = None
    summary: Optional[HandoffSummary] = None


class FlowInfo(BaseModel):
    state: str = Field(..., description="idle | agendar")
    awaiting: Optional[str] = Field(None, description="Dado/etapa que o bot espera na próxima mensagem.")


class GuardrailEvent(BaseModel):
    stage: str
    name: str
    action: str
    detail: Optional[str] = None


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    ts: str


class SessionDetail(BaseModel):
    session_id: str
    created_at: str
    status: Literal["ativa", "transferida", "encerrada"]
    turn: int
    slots: Slots
    flow: FlowInfo
    handoff: Handoff
    booking: Optional[dict[str, Any]] = None
    history: list[HistoryItem]


class SessionDeleteResponse(BaseModel):
    session_id: str
    deleted: bool = True


# ---------------------------------------------------------------- chat
class ChatRequest(BaseModel):
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN, examples=["8f1c2a9b03de"])
    message: str = Field(..., min_length=1, max_length=1000, examples=["Quero marcar para sexta de manhã"])

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("a mensagem não pode ser vazia")
        return v


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    intent_confidence: float
    slots: Slots
    sentiment: Sentiment
    fallback: bool
    fallback_type: Optional[str] = Field(None, description="nao_entendi | fora_da_base | slot_<nome>")
    handoff: Handoff
    turn: int = Field(..., description="Número do turno do usuário nesta sessão.")
    latency_ms: int
    source: str = Field(..., description="template | llm | template_guardrail | template_degraded")
    llm_used: bool
    guardrail_events: list[GuardrailEvent]
    flow: FlowInfo


# ---------------------------------------------------------------- feedback / handoffs
class FeedbackRequest(BaseModel):
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN)
    rating: int = Field(..., ge=1, le=5, description="CSAT de 1 a 5.")
    comment: Optional[str] = Field(None, max_length=500)


class FeedbackResponse(BaseModel):
    session_id: str
    rating: int
    registered: bool = True


class HandoffQueueItem(BaseModel):
    session_id: str
    protocol: str
    reason: str
    priority: Literal["alta", "normal"]
    created_at: str
    summary: HandoffSummary
    notes: list[str] = Field(default_factory=list, description="Mensagens enviadas pelo cliente após a transferência.")


# ---------------------------------------------------------------- métricas
class MetricsResponse(BaseModel):
    periodo: dict[str, Optional[str]]
    total_conversas: int
    total_turnos_usuario: int
    taxa_contencao: float = Field(..., description="conversas sem handoff ÷ total de conversas (0..1)")
    taxa_fallback: float = Field(..., description="turnos em fallback ÷ total de turnos do usuário (0..1)")
    taxa_handoff: float = Field(..., description="conversas com handoff ÷ total de conversas (0..1)")
    mensagens_por_conversa: float
    taxa_resolucao: float
    agendamentos_concluidos: int
    taxa_conclusao_agendamento: float
    latencia_media_ms: int
    latencia_p95_ms: int
    distribuicao_intencoes: dict[str, int]
    distribuicao_sentimento: dict[str, int]
    fallback_por_tipo: dict[str, int]
    fallback_por_estado: dict[str, int]
    handoff_por_motivo: dict[str, int]
    erros_validacao: dict[str, int]
    eventos_guardrail: dict[str, int] = Field(..., description="Disparos de guardrails (entrada/saída/LLM), por 'etapa:nome'.")
    turnos_com_tom_de_acolhimento: int = Field(..., description="Turnos em que o sentimento negativo mudou o tom do bot.")
    fonte_da_resposta: dict[str, int]
    faq_mais_consultadas: dict[str, int]
    total_feedbacks: int
    csat_medio: Optional[float] = None
    csat_medio_conversas_contidas: Optional[float] = None
    csat_medio_conversas_transferidas: Optional[float] = None
