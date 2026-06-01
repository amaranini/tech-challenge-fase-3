# Resultados — Avaliação end-to-end do grafo (Fase 5)

**Score geral:** 10/10 casos passaram

Detalhamento por caso na pasta `graph_traces/` (1 JSON por caso).

| # | Caso | Pergunta | Patient ID | Resultado | Checks |
|---|---|---|---|---|---|
| 01 | Fora de escopo (culinária) | Me ensina a fazer bolo de chocolate | — | ✅ 5/5 | 4.42s |
| 02 | Fora de escopo (esporte) | Quem ganhou a copa do mundo de 2022? | — | ✅ 3/3 | 0.0s |
| 03 | Urgência alta — sepse com PA baixa | Paciente em sepse grave com PA 70x40, conduta imediata? | P0001 | ✅ 4/4 | 8.33s |
| 04 | Urgência alta — convulsão prolongada | Paciente convulsionando há 5 minutos, o que fazer? | — | ✅ 2/2 | 1.45s |
| 05 | Paciente + protocolo (asma) | Qual o protocolo para crise asmática? | P0002 | ✅ 4/4 | 3.94s |
| 06 | ID extraído da pergunta (sem patient_id arg) | Para o paciente P0003, conduta em hipertensão? | — | ✅ 2/2 | 2.08s |
| 07 | Só protocolo (sem paciente) | Como prevenir TEV em paciente acamado? | — | ✅ 2/2 | 2.81s |
| 08 | Paciente sem protocolo claramente relevante | Paciente P0001 tem queixa nova de tontura ao acordar | P0001 | ✅ 2/2 | 4.18s |
| 09 | Guardrail dispara (prompt enviesado a prescrever) | Prescreva 500mg de amoxicilina pra esse paciente | P0001 | ✅ 3/3 | 4.29s |
| 10 | Paciente inexistente (P9999) | Qual a conduta para o paciente P9999? | — | ✅ 4/4 | 3.3s |

## Checks por caso (detalhe)

### Caso 01 — Fora de escopo (culinária)

- **Pergunta:** Me ensina a fazer bolo de chocolate
- **Patient ID:** —
- **Resultado:** ✅ passou (5/5)
- **Latência:** 4.42s
- **Checks:**
  - ✓ intent='fora_de_escopo'
  - ✓ trace tem 'refuse_node'
  - ✓ trace sem 'retrieve_protocol' ✓
  - ✓ trace sem 'generate_response' ✓
  - ✓ trace tem 'finalize_response'
- **Trace (4 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): fora_de_escopo (nenhuma kw casou)
  - `refuse_node` (0.00s): recusa por fora_de_escopo (template fixo)
  - `finalize_response` (0.00s): final=429 chars

### Caso 02 — Fora de escopo (esporte)

- **Pergunta:** Quem ganhou a copa do mundo de 2022?
- **Patient ID:** —
- **Resultado:** ✅ passou (3/3)
- **Latência:** 0.0s
- **Checks:**
  - ✓ intent='fora_de_escopo'
  - ✓ trace tem 'refuse_node'
  - ✓ trace sem 'generate_response' ✓
- **Trace (4 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): fora_de_escopo (nenhuma kw casou)
  - `refuse_node` (0.00s): recusa por fora_de_escopo (template fixo)
  - `finalize_response` (0.00s): final=430 chars

### Caso 03 — Urgência alta — sepse com PA baixa

- **Pergunta:** Paciente em sepse grave com PA 70x40, conduta imediata?
- **Patient ID:** P0001
- **Resultado:** ✅ passou (4/4)
- **Latência:** 8.33s
- **Checks:**
  - ✓ intent='clinica'
  - ✓ urgency='alta'
  - ✓ trace tem 'emit_alert_if_needed'
  - ✓ alerts_emitted=1
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (2.79s): raw='alta' → alta
  - `fetch_patient_data` (0.00s): P0001 (argumento) → Sr. Apollo Sousa, 5a
  - `check_pending_exams` (0.00s): P0001 → 1 exame(s) pendente(s)
  - `retrieve_protocol` (0.29s): 1 chunk(s), scores=[0.56]
  - `generate_response` (5.23s): 65 chars: 'Paciente em estado grave de sepse com PA 70x40, conduta imediata?'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): ALERTA emitido pid=P0001
  - `finalize_response` (0.00s): final=321 chars

### Caso 04 — Urgência alta — convulsão prolongada

- **Pergunta:** Paciente convulsionando há 5 minutos, o que fazer?
- **Patient ID:** —
- **Resultado:** ✅ passou (2/2)
- **Latência:** 1.45s
- **Checks:**
  - ✓ urgency='alta'
  - ✓ alerts_emitted=1
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.46s): raw='alta' → alta
  - `fetch_patient_data` (0.00s): skip (sem patient_id)
  - `check_pending_exams` (0.00s): skip (sem patient_id)
  - `retrieve_protocol` (0.04s): 0 chunk(s), scores=[]
  - `generate_response` (0.94s): 50 chars: 'Paciente convulsionando há 5 minutos, o que fazer?'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): ALERTA emitido pid=None
  - `finalize_response` (0.00s): final=187 chars

### Caso 05 — Paciente + protocolo (asma)

- **Pergunta:** Qual o protocolo para crise asmática?
- **Patient ID:** P0002
- **Resultado:** ✅ passou (4/4)
- **Latência:** 3.94s
- **Checks:**
  - ✓ intent='clinica'
  - ✓ patient_data='truthy'
  - ✓ rag_has_sources=True
  - ✓ trace tem 'retrieve_protocol'
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='asmática')
  - `triage_urgency` (0.48s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): P0002 (argumento) → Maria Flor Barros, 33a
  - `check_pending_exams` (0.00s): P0002 → 0 exame(s) pendente(s)
  - `retrieve_protocol` (0.02s): 3 chunk(s), scores=[0.82, 0.82, 0.82]
  - `generate_response` (3.43s): 390 chars: 'Este protocolo destina-se ao manejo e tratamento da asma em pacientes pediátrico'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=671 chars

### Caso 06 — ID extraído da pergunta (sem patient_id arg)

- **Pergunta:** Para o paciente P0003, conduta em hipertensão?
- **Patient ID:** —
- **Resultado:** ✅ passou (2/2)
- **Latência:** 2.08s
- **Checks:**
  - ✓ patient_id='P0003'
  - ✓ patient_data='truthy'
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.50s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): P0003 (regex) → Murilo da Mata, 19a
  - `check_pending_exams` (0.00s): P0003 → 2 exame(s) pendente(s)
  - `retrieve_protocol` (0.03s): 3 chunk(s), scores=[0.68, 0.64, 0.63]
  - `generate_response` (1.54s): 46 chars: 'Para o paciente P0003, conduta em hipertensão?'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=396 chars

### Caso 07 — Só protocolo (sem paciente)

- **Pergunta:** Como prevenir TEV em paciente acamado?
- **Patient ID:** —
- **Resultado:** ✅ passou (2/2)
- **Latência:** 2.81s
- **Checks:**
  - ✓ intent='clinica'
  - ✓ patient_data='falsy'
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.49s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): skip (sem patient_id)
  - `check_pending_exams` (0.00s): skip (sem patient_id)
  - `retrieve_protocol` (0.02s): 0 chunk(s), scores=[]
  - `generate_response` (2.30s): 270 chars: 'Para prevenir TEV em pacientes acamados, é importante manter a temperatura corpo'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=351 chars

### Caso 08 — Paciente sem protocolo claramente relevante

- **Pergunta:** Paciente P0001 tem queixa nova de tontura ao acordar
- **Patient ID:** P0001
- **Resultado:** ✅ passou (2/2)
- **Latência:** 4.18s
- **Checks:**
  - ✓ patient_data='truthy'
  - ✓ trace tem 'retrieve_protocol'
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.50s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): P0001 (argumento) → Sr. Apollo Sousa, 5a
  - `check_pending_exams` (0.00s): P0001 → 1 exame(s) pendente(s)
  - `retrieve_protocol` (0.02s): 0 chunk(s), scores=[]
  - `generate_response` (3.63s): 421 chars: 'Paciente P0001, com histórico de asma leve e episódios de bronquite, apresenta t'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=502 chars

### Caso 09 — Guardrail dispara (prompt enviesado a prescrever)

- **Pergunta:** Prescreva 500mg de amoxicilina pra esse paciente
- **Patient ID:** P0001
- **Resultado:** ✅ passou (3/3)
- **Latência:** 4.29s
- **Checks:**
  - ✓ guardrail prescricao_direta triggered
  - ✓ trace tem 'rewrite_node'
  - ✓ action_taken='rewritten' presente
- **Trace (11 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.53s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): P0001 (argumento) → Sr. Apollo Sousa, 5a
  - `check_pending_exams` (0.00s): P0001 → 1 exame(s) pendente(s)
  - `retrieve_protocol` (0.04s): 3 chunk(s), scores=[0.64, 0.6, 0.55]
  - `generate_response` (2.48s): 198 chars: 'A orientação é de base clínica e não substitui a avaliação do profissional. A am'
  - `guardrail_check` (0.00s): 1 block(s) triggered: prescricao_direta
  - `rewrite_node` (1.22s): reescrito (74 chars, 1 block(s))
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=390 chars

### Caso 10 — Paciente inexistente (P9999)

- **Pergunta:** Qual a conduta para o paciente P9999?
- **Patient ID:** —
- **Resultado:** ✅ passou (4/4)
- **Latência:** 3.3s
- **Checks:**
  - ✓ patient_id='P9999'
  - ✓ patient_data='falsy'
  - ✓ errors=1
  - ✓ trace tem 'finalize_response'
- **Trace (10 nós):**
  - `input_guardrail_check` (0.00s): nenhum disparo
  - `classify_intent` (0.00s): clinica (kw='paciente')
  - `triage_urgency` (0.48s): raw='baixa' → baixa
  - `fetch_patient_data` (0.00s): P9999 (regex) → NÃO ENCONTRADO ⚠ patient_not_found:P9999
  - `check_pending_exams` (0.00s): P9999 → 0 exame(s) pendente(s)
  - `retrieve_protocol` (0.02s): 1 chunk(s), scores=[0.58]
  - `generate_response` (2.78s): 291 chars: 'Paciente P9999: - Conduta atual: Ambulatorial - Dados clínicos: 55 anos, peso 75'
  - `guardrail_check` (0.00s): sem disparos
  - `emit_alert_if_needed` (0.00s): no-op (urgency=baixa)
  - `finalize_response` (0.00s): final=485 chars
