# Comparativo Fase 4 — roteamento, RAG e busca de prontuário

> 15 casos cobrindo: 5 só-RAG, 3 só-paciente, 3 ambos, 2 fora-de-escopo, 2 ID inexistente.
> **Roteamento correto: 15/15 (100.0%)**
> **Latência média: 3.76s** (RAG 0.05s | LLM 3.70s)

---

## 1. ✅ `rag_only` → detectado `rag_only` (9.32s)

**Pergunta:** Qual o protocolo institucional para manejo inicial de sepse?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.242s | paciente 0.000s | LLM 9.080s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.652**
  2. `protocol_013_geriatria.md` • _Conduta inicial_ • score: **0.562**
  3. `protocol_026_oncologia.md` • _Conduta inicial_ • score: **0.519**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

O protocolo institucional para manejo inicial de sepse é descrito em [Trecho 1]. A conduta inicial inclui avaliação clínica detalhada, exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais, e reunião multidisciplinar para discussão do caso. Se o paciente for considerado ressecável, realizar a ressecação cirúrgica (lobectomia ou pneumonectomia). Para casos em que a cirurgia não é uma opção, iniciar quimioterapia neoadjuvante ou radioterapia conforme o estadiamento.

---

## 2. ✅ `rag_only` → detectado `rag_only` (13.69s)

**Pergunta:** Como tratar infarto agudo do miocárdio com supra de ST nas primeiras horas?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.271s | paciente 0.000s | LLM 13.416s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Inicial_ • score: **0.616**
  2. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.603**
  3. `protocol_009_dermatologia.md` • _Conduta Inicial_ • score: **0.593**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial para infarto agudo do miocárdio com supra de ST nas primeiras horas deve incluir:
- **Iniciar tratamento com anticoagulantes** (por exemplo, aspirina 300 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com corticosteroides** (por exemplo, prednisolona 5 mg via oral, uma vez ao dia) para reduzir o edema e o edema.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.
- **Iniciar tratamento com anticoagulantes** (por exemplo, warfarina 2 mg via oral, uma vez ao dia) para prevenir tromboembolismo.

---

## 3. ✅ `rag_only` → detectado `rag_only` (2.51s)

**Pergunta:** Quais os critérios diagnósticos atuais para diabetes mellitus tipo 2?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.024s | paciente 0.000s | LLM 2.480s

**Fontes consultadas:**
  1. `protocol_015_cardiologia.md` • _Conduta subsequente_ • score: **0.574**
  2. `protocol_030_cardiologia.md` • _Conduta inicial_ • score: **0.503**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Os critérios diagnósticos atuais para diabetes mellitus tipo 2 incluem a presença de glicose em jejum superior a 100 mg/dL (5.6 mmol/L) em duas ou mais ocasiões, além de sintomas de diabetes ou histórico familiar de diabetes.

---

## 4. ✅ `rag_only` → detectado `rag_only` (3.72s)

**Pergunta:** Como manejar exacerbação aguda de asma em crianças?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.029s | paciente 0.000s | LLM 3.691s

**Fontes consultadas:**
  1. `protocol_018_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.827**
  2. `protocol_033_pediatria.md` • _Perguntas relacionadas_ • score: **0.815**
  3. `protocol_018_pediatria.md` • _Indicação_ • score: **0.813**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para a manejo de exacerbação aguda de asma em crianças, é importante considerar a avaliação de fatores de risco, incluindo a presença de fatores de risco como alergias, história familiar de asma, e condições de saúde associadas. A terapia de ação rápida (como broncodilatadores) deve ser iniciada imediatamente, e a terapia de longo prazo pode incluir corticosteroides de uso contínuo, dependendo da gravidade do episódio.

---

## 5. ✅ `rag_only` → detectado `rag_only` (4.27s)

**Pergunta:** Qual a conduta inicial em paciente com suspeita de AVC isquêmico?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.027s | paciente 0.000s | LLM 4.239s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.614**
  2. `protocol_004_emergência.md` • _Indicação_ • score: **0.612**
  3. `protocol_004_emergência.md` • _Critérios de Alta/Encaminhamento_ • score: **0.608**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial para pacientes com suspeita de AVC isquêmico deve incluir avaliação de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e avaliação pulmonar. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a ressecação cirúrgica como primeira opção para os pacientes em estágios iniciais. Para pacientes não candidatos à cirurgia, iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável. Iniciar acompanhamento psicológico e suporte nutricional.

---

## 6. ✅ `patient_only` → detectado `patient_only` (1.3s)

**Pergunta:** Quais são as alergias do paciente P0001?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.022s | paciente 0.002s | LLM 1.273s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

Paciente P0001: Sr. Apollo Sousa (sintético)
Alergias: Nenhuma

---

## 7. ✅ `patient_only` → detectado `patient_only` (3.17s)

**Pergunta:** Qual o histórico clínico do paciente P0023?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.000s | RAG 0.022s | paciente 0.001s | LLM 3.148s

**Fontes consultadas:**
  1. `protocol_023_gastroenterologia.md` • _Critérios de alta/encaminhamento_ • score: **0.502**

**Pacientes consultados:**
  - **P0023** (Théo Abreu, 50 anos, M): alergias: nenhuma; medicações: atorvastatina, ácido acetilsalicílico

**Resposta:**

Paciente P0023: Théo Abreu (sintético)
Idade: 50 anos | Sexo: M
Alergias: nenhuma
Medicações em uso: atorvastatina, ácido acetilsalicílico
Histórico: Paciente tem histórico de hiperlipidemia e infarto do miocárdio há 5 anos, em tratamento regular com acompanhamento cardiológico.

---

## 8. ✅ `patient_only` → detectado `patient_only` (1.6s)

**Pergunta:** Que medicações o paciente P0042 está em uso?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.018s | paciente 0.000s | LLM 1.587s

**Fontes consultadas:**
  1. `protocol_015_cardiologia.md` • _Conduta subsequente_ • score: **0.541**
  2. `protocol_032_infectologia.md` • _Conduta Inicial_ • score: **0.531**
  3. `protocol_029_ginecologia_e_obstetrícia.md` • _Conduta Inicial_ • score: **0.525**

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

Paciente P0042 está em uso de enalapril e atorvastatina.

---

## 9. ✅ `both` → detectado `both` (4.76s)

**Pergunta:** Para o paciente P0001 com suspeita de pneumonia comunitária, qual conduta segundo nossos protocolos?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.025s | paciente 0.000s | LLM 4.733s

**Fontes consultadas:**
  1. `protocol_017_infectologia.md` • _Introdução_ • score: **0.742**
  2. `protocol_017_infectologia.md` • _Perguntas relacionadas_ • score: **0.701**
  3. `protocol_002_infectologia.md` • _Introdução_ • score: **0.660**

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

### Conduta Clínica

Seguindo os protocolos institucionais, a conduta inicial para o paciente P0001 com suspeita de pneumonia comunitária é:

- Realizar exames de sangue e exames de imagem para avaliação do quadro clínico.
- Considerar a internação hospitalar se o paciente apresentar sinais de deterioração do estado de saúde, como dificuldade respiratória, febre persistente, ou sinais de infecção bacteriana.
- Implementar tratamento com antibióticos, conforme a gravidade do quadro, e monitorar a resposta ao tratamento.
- Estabelecer um plano de acompanhamento para monitoramento da evolução do paciente e adequação do tratamento.

---

## 10. ✅ `both` → detectado `both` (2.95s)

**Pergunta:** Paciente P0023 chega com dor torácica em aperto — qual protocolo aplicar considerando o histórico dele?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.000s | LLM 2.931s

**Fontes consultadas:**
  1. `protocol_033_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.574**
  2. `protocol_017_infectologia.md` • _Critérios de Alta/Encaminhamento_ • score: **0.529**
  3. `protocol_002_infectologia.md` • _Critérios de Alta/Encaminhamento_ • score: **0.528**

**Pacientes consultados:**
  - **P0023** (Théo Abreu, 50 anos, M): alergias: nenhuma; medicações: atorvastatina, ácido acetilsalicílico

**Resposta:**

Paciente P0023 apresenta dor torácica em aperto, histórico de hiperlipidemia e infarto do miocárdio. O protocolo de alta indica que a paciente deve ser encaminhada para pneumologista pediátrico se houver complicações ou se não responder à terapia inicial após 72 horas.

---

## 11. ✅ `both` → detectado `both` (3.53s)

**Pergunta:** Para o paciente P0042 em pré-operatório, quais cuidados o protocolo de pré-anestesia prevê?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.024s | paciente 0.000s | LLM 3.510s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.581**
  2. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.579**
  3. `protocol_002_infectologia.md` • _Conduta Inicial_ • score: **0.564**

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

O protocolo de pré-anestesia prevê a realização de uma avaliação completa do paciente, incluindo exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e uma avaliação pulmonar. O protocolo também recomenda iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável, e iniciar acompanhamento psicológico e suporte nutricional.

---

## 12. ✅ `out_of_scope` → detectado `out_of_scope` (1.77s)

**Pergunta:** Como faço um bolo de chocolate?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.016s | paciente 0.000s | LLM 1.754s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para fazer um bolo de chocolate, você precisa de ovos, leite condensado, açúcar, fermento em pó, e uma mistura de chocolate. Leve ao forno por aproximadamente 20 minutos.

---

## 13. ✅ `out_of_scope` → detectado `out_of_scope` (1.29s)

**Pergunta:** Quem ganhou a Copa do Mundo de 2022?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.000s | LLM 1.262s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

O Brasil foi o campeão da Copa do Mundo de 2022, conquistando a medalha de ouro.

---

## 14. ✅ `invalid_id` → detectado `invalid_id` (1.53s)

**Pergunta:** Quais são as alergias do paciente P9999?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P9999']`

**Latências:** router 0.000s | RAG 0.020s | paciente 0.000s | LLM 1.505s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P9999**: ❌ não encontrado no banco

**Resposta:**

Alguns pacientes podem ter alergias a medicamentos, alimentos, e outros produtos. Por favor, informe quaisquer alergias do paciente P9999.

---

## 15. ✅ `invalid_id` → detectado `invalid_id` (0.97s)

**Pergunta:** Qual o histórico clínico do paciente P0099?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0099']`

**Latências:** router 0.000s | RAG 0.020s | paciente 0.000s | LLM 0.951s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0099**: ❌ não encontrado no banco

**Resposta:**

Paciente P0099 não encontrado no banco de dados.

---
