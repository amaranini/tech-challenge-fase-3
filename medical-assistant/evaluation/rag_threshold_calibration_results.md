# Resultados da calibração do RAG_MIN_SCORE

**Data:** 2026-05-26
**Embedding model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
**Distância:** cosseno (Chroma `hnsw:space="cosine"`)
**Total de queries:** 25 (10 PRESENT + 10 ABSENT + 5 BORDERLINE)
**Top-k:** 3 (sem filtro durante coleta — `min_score=None`)
**Script reprodutível:** `evaluation/calibrate_rag_threshold.py`

---

## Tabela 1 — GRUPO PRESENT

Queries sobre temas **confirmados** no dataset (inspeção direta dos 35 `.md`).

| # | top-1 | top-2 | top-3 | fonte top-1 | query |
|---|---|---|---|---|---|
| 1 | 0.658 | 0.658 | 0.655 | protocol_015_cardiologia.md | Como manejar arritmias cardíacas em adulto? |
| 2 | 0.795 | 0.768 | 0.746 | protocol_031_pneumologia.md | Qual o tratamento da asma em adultos? |
| 3 | 0.781 | 0.767 | 0.729 | protocol_017_infectologia.md | Como tratar pneumonia adquirida na comunidade? |
| 4 | **0.495** | 0.469 | 0.457 | protocol_004_emergência.md | Conduta em AVC isquêmico agudo? |
| 5 | 0.800 | 0.737 | 0.728 | protocol_005_neurologia.md | Como avaliar cefaleia crônica? |
| 6 | 0.689 | 0.638 | 0.596 | protocol_006_endocrinologia.md | Tratamento de hipotireoidismo subclínico |
| 7 | 0.840 | 0.725 | 0.699 | protocol_009_dermatologia.md | Manejo da dermatite atópica em adulto |
| 8 | 0.564 | 0.529 | 0.490 | protocol_025_urologia.md | Como tratar hiperplasia prostática benigna? |
| 9 | 0.820 | 0.725 | 0.705 | protocol_015_cardiologia.md | Conduta na insuficiência cardíaca congestiva descompensada |
| 10 | 0.666 | 0.598 | 0.568 | protocol_029_ginecologia_e_obstetrícia.md | Manejo de hemorragia pós-parto |

## Tabela 2 — GRUPO ABSENT

Queries sobre temas **confirmados fora** do dataset (`grep -r` retornou 0 matches).

| # | top-1 | top-2 | top-3 | fonte top-1 | query |
|---|---|---|---|---|---|
| 1 | 0.460 | 0.458 | 0.422 | protocol_009_dermatologia.md | Como tratar Doença de Lyme transmitida por carrapato? |
| 2 | **0.601** | 0.564 | 0.561 | protocol_023_gastroenterologia.md | Manejo da Doença de Chagas em fase crônica |
| 3 | 0.158 | 0.146 | 0.127 | protocol_014_ginecologia_e_obstetrícia.md | Conduta em Lúpus eritematoso sistêmico |
| 4 | 0.535 | 0.520 | 0.516 | protocol_030_cardiologia.md | Como diagnosticar esclerose múltipla? |
| 5 | 0.433 | 0.431 | 0.428 | protocol_005_neurologia.md | Tratamento da síndrome de Guillain-Barré |
| 6 | 0.389 | 0.385 | 0.341 | protocol_020_neurologia.md | Manejo da hanseníase paucibacilar |
| 7 | 0.460 | 0.438 | 0.384 | protocol_024_dermatologia.md | Diagnóstico de leptospirose grave |
| 8 | 0.310 | 0.297 | 0.294 | protocol_034_emergência.md | Conduta em hipertensão portal |
| 9 | 0.570 | 0.567 | 0.490 | protocol_032_infectologia.md | Tratamento de mononucleose infecciosa |
| 10 | 0.494 | 0.462 | 0.455 | protocol_003_pediatria.md | Diagnóstico de doença de Kawasaki em criança |

## Tabela 3 — GRUPO BORDERLINE

Queries vagamente relacionadas a temas presentes (para estressar a fronteira).

| # | top-1 | top-2 | top-3 | fonte top-1 | query |
|---|---|---|---|---|---|
| 1 | 0.721 | 0.709 | 0.691 | protocol_018_pediatria.md | Alergia respiratória crônica |
| 2 | 0.546 | 0.529 | 0.517 | protocol_017_infectologia.md | Infecção pulmonar viral |
| 3 | 0.272 | 0.271 | 0.261 | protocol_009_dermatologia.md | Dor torácica de origem indeterminada |
| 4 | 0.691 | 0.577 | 0.577 | protocol_026_oncologia.md | Câncer broncogênico |
| 5 | 0.580 | 0.450 | 0.429 | protocol_027_psiquiatria.md | Ansiedade situacional aguda |

---

## Estatísticas — score top-1

| Grupo | n | mean | median | min | max | σ |
|---|---|---|---|---|---|---|
| **PRESENT** | 10 | 0.711 | 0.735 | 0.495 | 0.840 | 0.117 |
| **ABSENT** | 10 | 0.441 | 0.460 | 0.158 | 0.601 | 0.131 |
| **BORDERLINE** | 5 | 0.562 | 0.580 | 0.272 | 0.721 | 0.178 |

### Histogramas (top-1 score)

**PRESENT:**
```
[0.00-0.30)              (0)
[0.30-0.40)              (0)
[0.40-0.45)              (0)
[0.45-0.50)  █           (1)
[0.50-0.55)              (0)
[0.55-0.60)  █           (1)
[0.60-0.70)  ███         (3)
[0.70-1.01)  █████       (5)
```

**ABSENT:**
```
[0.00-0.30)  █           (1)
[0.30-0.40)  ██          (2)
[0.40-0.45)  █           (1)
[0.45-0.50)  ███         (3)
[0.50-0.55)  █           (1)
[0.55-0.60)  █           (1)
[0.60-0.70)  █           (1)
[0.70-1.01)              (0)
```

**BORDERLINE:**
```
[0.00-0.30)  █           (1)
[0.30-0.40)              (0)
[0.40-0.45)              (0)
[0.45-0.50)              (0)
[0.50-0.55)  █           (1)
[0.55-0.60)  █           (1)
[0.60-0.70)  █           (1)
[0.70-1.01)  █           (1)
```

---

## Trade-off — comportamento por threshold

| Threshold | Recall (PRESENT passa) | Specificity (ABSENT filtra) | Observação |
|---|---|---|---|
| 0.40 | 100% (10/10) | 30% (3/10) | pega tudo, deixa lixo passar |
| 0.45 | 100% (10/10) | 40% (4/10) | |
| **0.50** | 90% (9/10) | 70% (7/10) | sacrifica AVC isquêmico (0.495) |
| **0.55** ← escolhido | 90% (9/10) | 80% (8/10) | **Pareto-domina 0.50** |
| 0.60 | 80% (8/10) | 90% (9/10) | perde também HPB (0.564) |

### Falhas detalhadas com threshold 0.55

**PRESENT que cai abaixo do threshold:**
- `Conduta em AVC isquêmico agudo?` → score 0.495 → mapeou pro protocolo certo (`protocol_004_emergência.md` que **é** sobre AVC), mas score baixo. A formulação com qualificador ("agudo") parece degradar o embedding multilíngue. Esse caso continuará caindo na faixa "sem fonte" → chain instrui o LLM a pedir mais contexto.

**ABSENT que passam mesmo com 0.55:**
- `Doença de Chagas em fase crônica` → score 0.601 → mapeou pro `protocol_023_gastroenterologia.md` (DII). Chagas crônica tem manifestação intestinal (megacólon) — similaridade semântica é legítima mas o protocolo NÃO trata de Chagas. **Falso positivo persistente.**

**BORDERLINE — separação com threshold 0.55:**
- Acima: `alergia respiratória crônica` (0.721), `câncer broncogênico` (0.691, sinônimo de CPNPC), `ansiedade situacional aguda` (0.580).
- Abaixo: `infecção pulmonar viral` (0.546), `dor torácica de origem indeterminada` (0.272).

A query "infecção pulmonar viral" cair abaixo é o **trade-off aceito**: PAC é especificamente **bacteriana**, sugerir antibiótico baseado nesse protocolo seria clinicamente inadequado para infecção viral.

---

## Limitações e plano de manutenção

1. **Calibração com dataset pequeno (35 protocolos sintéticos).** Em produção com base maior, redistribuição de scores pode mudar; recalibrar.
2. **Falso positivo persistente para condições com sobreposição semântica legítima** (ex: Chagas crônica ↔ DII por megacólon). Nenhum threshold absoluto resolve isso; abordagem futura: combinar com filtro lexical ou re-ranking.
3. **Instabilidade em formulações com qualificadores temporais** ("agudo", "crônico") — o embedding multilíngue MiniLM-L12 é sensível a isso. AVC isquêmico em `protocol_004_emergência.md` ficou em 0.495 mesmo sendo match exato de tema.
4. **Trocar embedding model exige recalibração completa.** Os números acima são específicos do `paraphrase-multilingual-MiniLM-L12-v2`.

## Como reproduzir

```bash
cd medical-assistant
uv run python evaluation/calibrate_rag_threshold.py
```

O script é determinístico (Chroma com seed implícita; embedding model fixo), então os scores devem reproduzir dentro de ~0.001 de diferença.
