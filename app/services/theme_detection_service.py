"""Service de detecção de tema (saúde) para decidir se o conteúdo deve
passar pelo fluxo de scoring.

Regras:
- Preferir sinais semânticos retornados pela IA (resumo + afirmações).
- Se a IA não fornecer sinais suficientes, fazer fallback baseado em texto
  (texto extraído de URL/OCR).

Quando o tema NÃO for suportado, o endpoint deve retornar uma resposta
amigável e NÃO deve executar o scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Tuple

from app.models.schemas import AIAnalysis


@dataclass(frozen=True)
class ThemeDetectionResult:
    tema_suportado: bool
    tema_detectado: str


# Palavras/expressões-alvo (PT-BR). Mantém-se relativamente conservador para
# reduzir falsos positivos.
_HEALTH_TOPICS: dict[str, Iterable[str]] = {
    "medicina": [
        "medicina",
        "m[eé]dico",
        "m[eé]dicos",
        "especialista",
        "cl[ií]nica",
        "tratamento",
        "terapia",
        "procedimento",
        "consulta",
    ],
    "saúde pública": [
        "sa[uú]de p[uú]blica",
        "vigil[aâ]ncia sanit[aá]ria",
        "epidemia",
        "pandemia",
        "surto",
        "sa[uú]de coletiva",
        "pol[ií]ticas de sa[uú]de",
        "programa de sa[uú]de",
    ],
    "doenças": [
        "doen[cç]a",
        "doen[cç]as",
        "sintoma",
        "sintomas",
        "diagn[oó]stico",
        "diagn[oó]sticos",
        "progn[oó]stico",
        "inflama[cç][aã]o",
        "infec[cç][aã]o",
    ],
    "vacinas": [
        "vacina",
        "vacinas",
        "imuniza[cç][aã]o",
        "imuniza[cç][aã]es",
        "campanha de vacina",
        "dose",
    ],
    "medicamentos": [
        "medicamento",
        "medicamentos",
        "rem[eé]dio",
        "rem[eé]dios",
        "antibi[oó]tico",
        "antibi[oó]ticos",
        "analg[eé]sico",
        "analg[eé]sicos",
    ],
    "tratamentos": [
        "tratamento",
        "tratamentos",
        "ter[mm]ap",
        "terapia",
        "cure",
    ],
    "hospitais": [
        "hospital",
        "hospitais",
        "pronto-socorro",
        "pronto socorro",
    ],
    "sistemas e órgãos": [
        "sus",
        "anvisa",
        "anvisa.gov.br",
        "agencia nacional de vigil[aâ]ncia sanit[aá]ria",
        "minist[eé]rio da sa[uú]de",
    ],
}


_HEALTH_KEYWORDS_FALLBACK = [
    # Geral (boa cobertura para OCR e texto curto)
    "saúde",
    "medicina",
    "doença",
    "doenças",
    "vacina",
    "vacinas",
    "medicamento",
    "medicamentos",
    "tratamento",
    "tratamentos",
    "hospital",
    "sus",
    "anvisa",
    "sintoma",
    "sintomas",
    "diagn[oó]stico",
    "diagn[oó]sticos",
]


# Limiares
_MIN_SEMANTIC_HINTS = 2  # quantidade mínima de tópicos detectados na parte semântica
_MIN_FALLBACK_HITS = 3  # quantidade mínima de hits no texto


def verificar_tema_saude(
    *,
    analise_ia: AIAnalysis,
    texto_base: str,
) -> ThemeDetectionResult:
    """Verifica se o conteúdo pertence ao domínio de saúde."""

    semantico = _normalize_for_match(" ".join([analise_ia.resumo or "", " ".join(analise_ia.afirmacoes or [])]))

    semantico_hits = _count_topic_hits(semantico)
    if semantico_hits["total"] >= _MIN_SEMANTIC_HINTS:
        return ThemeDetectionResult(
            tema_suportado=True,
            tema_detectado=_pick_primary_theme(semantico_hits),
        )

    # Fallback baseado em texto extraído/OCR
    fallback_text = _normalize_for_match(texto_base)
    fallback_count = _count_fallback_hits(fallback_text)

    if fallback_count >= _MIN_FALLBACK_HITS:
        # Atribui tema aproximado pelo que mais apareceu
        fallback_topics = _count_topic_hits(fallback_text)
        return ThemeDetectionResult(
            tema_suportado=True,
            tema_detectado=_pick_primary_theme(fallback_topics) if fallback_topics["total"] else "saúde",
        )

    # Não detectado
    tema_detectado = _infer_non_health_topic(texto_base, analise_ia)
    return ThemeDetectionResult(
        tema_suportado=False,
        tema_detectado=tema_detectado,
    )


def _infer_non_health_topic(texto_base: str, analise_ia: AIAnalysis) -> str:
    t = _normalize_for_match(" ".join([texto_base or "", analise_ia.resumo or ""]))

    # Heurística bem simples: tenta rotular alguns domínios comuns
    # (apenas para mensagem informativa).
    rotulos = {
        "esporte": ["futebol", "basquete", "olimp", "torcida", "campeonato"],
        "finanas": ["bolsa", "ações", "ações", "lucro", "receita", "juros", "dólar", "economia"],
        "política": ["eleição", "governo", "presidente", "senador", "partido"],
        "tecnologia": ["ia", "inteligência artificial", "software", "computador", "tecnologia"],
        "entretenimento": ["filme", "série", "celebridade", "hollywood", "show"],
    }

    for label, tokens in rotulos.items():
        if any(tok in t for tok in tokens):
            return label

    return "não identificado"


def _normalize_for_match(texto: str) -> str:
    if not texto:
        return ""
    t = texto.lower().strip()

    # Remover acentos de forma leve para melhorar matching (sem dependência extra)
    # A estratégia abaixo não é perfeita, mas ajuda bastante em OCR.
    t = t.replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a")
    t = t.replace("é", "e").replace("ê", "e")
    t = t.replace("í", "i").replace("ì", "i")
    t = t.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    t = t.replace("ú", "u").replace("ü", "u")
    t = t.replace("ç", "c")

    # Normaliza espaços
    t = " ".join(t.split())
    return t


def _count_topic_hits(texto: str) -> dict:
    """Conta hits por grupos/tópicos. Retorna dict com total e contagem por tema."""
    hits: dict[str, int] = {k: 0 for k in _HEALTH_TOPICS.keys()}

    for tema, patterns in _HEALTH_TOPICS.items():
        count = 0
        for p in patterns:
            if re.search(p, texto, flags=re.IGNORECASE):
                count += 1
        hits[tema] = count

    total = sum(1 for v in hits.values() if v > 0)
    return {"total": total, "by_theme": hits}


def _pick_primary_theme(counts: dict) -> str:
    by_theme: dict = counts.get("by_theme", {})
    if not by_theme:
        return "saúde"
    # Prioriza o tema com mais padrões presentes
    return max(by_theme.keys(), key=lambda k: by_theme.get(k, 0)) if counts.get("total") else "saúde"


def _count_fallback_hits(texto: str) -> int:
    if not texto:
        return 0
    # Tokens com normalização simples
    t = texto
    # Converte regex-like para substring direta em fallback para ser mais simples
    # (diagnóstico possui caracteres extras; já normalizamos acentos antes)
    tokens = [
        "saude",
        "medicina",
        "doenca",
        "doencas",
        "vacina",
        "vacinas",
        "medicamento",
        "medicamentos",
        "tratamento",
        "tratamentos",
        "hospital",
        "sus",
        "anvisa",
        "sintoma",
        "sintomas",
        "diagnostico",
        "diagnosticos",
    ]

    count = 0
    for tok in tokens:
        if tok in t:
            count += 1

    return count

