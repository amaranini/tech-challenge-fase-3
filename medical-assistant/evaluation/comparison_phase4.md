# Comparativo Fase 4 — roteamento, RAG e busca de prontuário

> 15 casos cobrindo: 5 só-RAG, 3 só-paciente, 3 ambos, 2 fora-de-escopo, 2 ID inexistente.
> **Roteamento correto: 15/15 (100.0%)**
> **Latência média: 5.32s** (RAG 0.04s | LLM 5.28s)

---

## 1. ✅ `rag_only` → detectado `rag_only` (6.82s)

**Pergunta:** Qual o protocolo institucional para manejo inicial de sepse?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.050s | paciente 0.000s | LLM 6.766s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.652**
  2. `protocol_013_geriatria.md` • _Conduta inicial_ • score: **0.562**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial para a sepse deve incluir o diagnóstico da causa da infecção, com exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais (hemograma completo, PCR, IL-6, função imunológica), e avaliação dos sinais vitais. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a administração de antibióticos, e a necessidade de hospitalização ou internamento.

---

## 2. ✅ `rag_only` → detectado `rag_only` (14.08s)

**Pergunta:** Como tratar infarto agudo do miocárdio com supra de ST nas primeiras horas?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.230s | paciente 0.000s | LLM 13.852s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Inicial_ • score: **0.616**
  2. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.603**
  3. `protocol_009_dermatologia.md` • _Conduta Inicial_ • score: **0.593**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial para infarto agudo do miocárdio com supra de ST nas primeiras horas deve incluir:
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para prevenção de tromboembolismo.
- **Inserção de anticoagulantes** (por exemplo, Dipyridamol 200 mg via oral, duas vezes ao dia) para

---

## 3. ✅ `rag_only` → detectado `rag_only` (13.47s)

**Pergunta:** Quais os critérios diagnósticos atuais para diabetes mellitus tipo 2?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.022s | paciente 0.000s | LLM 13.452s

**Fontes consultadas:**
  1. `protocol_015_cardiologia.md` • _Conduta subsequente_ • score: **0.574**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Os critérios diagnósticos atuais para diabetes mellitus tipo 2 incluem: 1) glicose em jejum superior a 100 mg/dL (5,6 mmol/L) em duas ou mais ocasiões; 2) glicose em jejum superior a 160 mg/dL (8,6 mmol/L) em uma única ocasião, com sinais de hipoglicemia; 3) hipoglicemia em jejum e insulina sérica elevada; 4) história familiar de diabetes; 5) aumento do IMC e aumento da frequência cardíaca; 6) aumento da pressão arterial; 7) aumento da frequência cardíaca; 8) aumento da frequência cardíaca; 9) aumento da frequência cardíaca; 10) aumento da frequência cardíaca; 11) aumento da frequência cardíaca; 12) aumento da frequência cardíaca; 13) aumento da frequência cardíaca; 14) aumento da frequência cardíaca; 15) aumento da frequência cardíaca; 16) aumento da frequência cardíaca; 17) aumento da frequência cardíaca; 18) aumento da frequência cardíaca; 19) aumento da frequência cardíaca; 20) aumento da frequência cardíaca; 21) aumento da frequência cardíaca; 22) aumento da frequência cardíaca; 23) aumento da frequência cardíaca; 24) aumento da frequência cardíaca; 25) aumento da frequência cardíaca; 26) aumento da frequência cardíaca; 27) aumento da frequência cardíaca; 28) aumento da frequência cardíaca; 29) aumento da frequência cardíaca; 30) aumento da frequência cardíaca; 31) aumento da frequência cardíaca; 32) aumento da frequência cardíaca; 33) aumento da frequência cardíaca; 34) aumento da frequência cardíaca; 35) aumento da frequência cardíaca; 36) aumento da frequência cardíaca; 37) aumento da frequência

---

## 4. ✅ `rag_only` → detectado `rag_only` (3.15s)

**Pergunta:** Como manejar exacerbação aguda de asma em crianças?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.051s | paciente 0.000s | LLM 3.099s

**Fontes consultadas:**
  1. `protocol_018_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.827**
  2. `protocol_033_pediatria.md` • _Perguntas relacionadas_ • score: **0.815**
  3. `protocol_018_pediatria.md` • _Indicação_ • score: **0.813**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para a exacerbação aguda de asma em crianças, é importante manter a criança em um ambiente controlado, evitar irritantes como pó e fumaça, e monitorar a frequência e intensidade dos sintomas. Se a condição persistir ou se a criança apresentar sinais de insuficiência respiratória, encaminhar para um especialista em pneumologia pediátrica.

---

## 5. ✅ `rag_only` → detectado `rag_only` (4.41s)

**Pergunta:** Qual a conduta inicial em paciente com suspeita de AVC isquêmico?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.022s | paciente 0.000s | LLM 4.386s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.614**
  2. `protocol_004_emergência.md` • _Indicação_ • score: **0.612**
  3. `protocol_004_emergência.md` • _Critérios de Alta/Encaminhamento_ • score: **0.608**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial deve incluir uma avaliação completa do paciente, incluindo exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e uma avaliação pulmonar. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a ressecação cirúrgica como primeira opção para os pacientes em estágios iniciais. Para pacientes não candidatos à cirurgia, iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável. Iniciar acompanhamento psicológico e suporte nutricional.

---

## 6. ✅ `patient_only` → detectado `patient_only` (1.91s)

**Pergunta:** Quais são as alergias do paciente P0001?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.002s | LLM 1.891s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

Paciente P0001: Sr. Apollo Sousa (sintético)
Idade: 5 anos | Sexo: M
Alergias: Nenhuma

Esta é a informação disponível sobre o paciente.

---

## 7. ✅ `patient_only` → detectado `patient_only` (3.17s)

**Pergunta:** Qual o histórico clínico do paciente P0023?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.000s | RAG 0.019s | paciente 0.000s | LLM 3.153s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0023** (Théo Abreu, 50 anos, M): alergias: nenhuma; medicações: atorvastatina, ácido acetilsalicílico

**Resposta:**

Paciente P0023: Théo Abreu (sintético)
Idade: 50 anos | Sexo: M
Alergias: nenhuma
Medicações em uso: atorvastatina, ácido acetilsalicílico
Histórico: Paciente tem histórico de hiperlipidemia e infarto do miocárdio há 5 anos, em tratamento regular com acompanhamento cardiológico.

---

## 8. ✅ `patient_only` → detectado `patient_only` (1.34s)

**Pergunta:** Que medicações o paciente P0042 está em uso?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.000s | LLM 1.317s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

Paciente P0042 está em uso de enalapril e atorvastatina.

---

## 9. ✅ `both` → detectado `both` (13.91s)

**Pergunta:** Para o paciente P0001 com suspeita de pneumonia comunitária, qual conduta segundo nossos protocolos?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.042s | paciente 0.001s | LLM 13.868s

**Fontes consultadas:**
  1. `protocol_017_infectologia.md` • _Introdução_ • score: **0.742**
  2. `protocol_017_infectologia.md` • _Perguntas relacionadas_ • score: **0.701**
  3. `protocol_002_infectologia.md` • _Introdução_ • score: **0.660**

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

### Orientação Clínica

# Protocolo Clínico para o Tratamento da Pneumonia Adquirida na Comunidade (PAC)

# Protocolo Clínico para o Tratamento da Pneumonia Adquirida na Comunidade (PAC)

## Conduta inicial

### Considerações gerais
- O paciente P0001 é um adulto com suspeita de pneumonia comunitária. O tratamento deve ser iniciado com antibióticos, considerando a resistência bacteriana local e a gravidade da pneumonia.

### Dados do paciente
- Idade: 5 anos
- Sexo: M
- Alergias: Nenhuma
- Medicações em uso: soro fisiológico, paracetamol
- Histórico: Paciente masculino de 5 anos com histórico de asma leve, episódios esporádicos de bronquite. Recebe acompanhamento pediátrico regular.

### Considerações gerais
- O paciente P0001 é um adulto com suspeita de pneumonia comunitária. O tratamento deve ser iniciado com antibióticos, considerando a resistência bacteriana local e a gravidade da pneumonia.

### Conduta inicial
- **Diagnóstico confirmado**: Realizar exames de laboratório para confirmação da pneumonia, incluindo cultura de secreções respiratórias e teste de resistência bacteriana. Avaliar a gravidade da pneumonia com base em sinais vitais, sinais de respiração, e histórico clínico.
- **Tratamento inicial**: Iniciar antibióticos com base no tipo de bactéria suspeita, considerando resistência local. Adicionar corticosteroides para pacientes com sintomas de inflamação pulmonar.
- **Monitoramento**: Realizar exames de laboratório e exames de imagem para monitorar o curso da pneumonia e avaliar a resposta ao tratamento. Realizar reavaliação em 48 horas.
- **Intensificação do tratamento**: Considerar a necessidade de intensificação do tratamento se houver evolução da pneumonia ou se houver sinais de complicações, como infecção pulmonar complicada ou pneumotórax.

### Considerações adicionais
- **Paciente com histórico de pneumonia**: Se o paciente já t

---

## 10. ✅ `both` → detectado `both` (8.93s)

**Pergunta:** Paciente P0023 chega com dor torácica em aperto — qual protocolo aplicar considerando o histórico dele?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.001s | RAG 0.050s | paciente 0.002s | LLM 8.876s

**Fontes consultadas:**
  1. `protocol_033_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.574**

**Pacientes consultados:**
  - **P0023** (Théo Abreu, 50 anos, M): alergias: nenhuma; medicações: atorvastatina, ácido acetilsalicílico

**Resposta:**

### CRITÉRIOS DE ALTA/ENCAMINHAMENTO

- **Paciente P0023**: Théo Abreu, 50 anos, homem, com histórico de hiperlipidemia e infarto do miocárdio há 5 anos, em tratamento regular com acompanhamento cardiológico. O paciente apresenta controle adequado dos sintomas e boa adesão ao tratamento. Considerar encaminhamento para pneumologista pediátrico em casos de asma persistente e difícil controle, avaliação de comorbidades ou necessidade de terapia avançada. Reavaliação em 3 a 6 meses após estabilização, com possibilidade de redução da medicação se o controle for mantido.

### DADOS DO(S) PACIENTE(S)

- **Paciente P0023**: Théo Abreu (sintético)
- **Idade**: 50 anos
- **Sexo**: M
- **Alergias**: Nenhuma
- **Medicações em uso**: atorvastatina, ácido acetilsalicílico
- **Histórico**: Paciente tem histórico de hiperlipidemia e infarto do miocárdio há 5 anos, em tratamento regular com acompanhamento cardiológico.

### PERGUNTA

Paciente P0023 chega com dor torácica em aperto — qual protocolo aplicar considerando o histórico dele?

---

## 11. ✅ `both` → detectado `both` (2.16s)

**Pergunta:** Para o paciente P0042 em pré-operatório, quais cuidados o protocolo de pré-anestesia prevê?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.001s | LLM 2.134s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.581**
  2. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.579**
  3. `protocol_002_infectologia.md` • _Conduta Inicial_ • score: **0.564**

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

O protocolo de pré-anestesia prevê o uso de sedação e analgesia adequados, avaliação de risco e benefício do anestesia, e monitoramento intensivo.

---

## 12. ✅ `out_of_scope` → detectado `out_of_scope` (2.46s)

**Pergunta:** Como faço um bolo de chocolate?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.028s | paciente 0.000s | LLM 2.429s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para fazer um bolo de chocolate, você precisará de ingredientes básicos como ovos, leite condensado, açúcar, fermento em pó, e chocolate em pó ou em pedaços. Faça o bolo conforme o protocolo, e por último, cubra o bolo com o chocolate em pó ou em pedaços.

---

## 13. ✅ `out_of_scope` → detectado `out_of_scope` (1.91s)

**Pergunta:** Quem ganhou a Copa do Mundo de 2022?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.024s | paciente 0.000s | LLM 1.883s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A Copa do Mundo de 2022 foi ganhada pela seleção da Arábia Saudita, que venceu o grupo B com 10 pontos. A Argentina foi a vice-campeã, com 7 pontos.

---

## 14. ✅ `invalid_id` → detectado `invalid_id` (1.03s)

**Pergunta:** Quais são as alergias do paciente P9999?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P9999']`

**Latências:** router 0.000s | RAG 0.018s | paciente 0.000s | LLM 1.015s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P9999**: ❌ não encontrado no banco

**Resposta:**

Paciente P9999 não foi encontrado no banco de dados.

---

## 15. ✅ `invalid_id` → detectado `invalid_id` (1.03s)

**Pergunta:** Qual o histórico clínico do paciente P0099?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0099']`

**Latências:** router 0.000s | RAG 0.015s | paciente 0.000s | LLM 1.013s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0099**: ❌ não encontrado no banco

**Resposta:**

O paciente P0099 não foi encontrado no banco de dados.

---
