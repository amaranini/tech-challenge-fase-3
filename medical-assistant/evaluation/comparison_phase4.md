# Comparativo Fase 4 — roteamento, RAG e busca de prontuário

> 15 casos cobrindo: 5 só-RAG, 3 só-paciente, 3 ambos, 2 fora-de-escopo, 2 ID inexistente.
> **Roteamento correto: 15/15 (100.0%)**
> **Latência média: 3.47s** (RAG 0.04s | LLM 3.43s)

---

## 1. ✅ `rag_only` → detectado `rag_only` (7.17s)

**Pergunta:** Qual o protocolo institucional para manejo inicial de sepse?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.061s | paciente 0.000s | LLM 7.106s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.652**
  2. `protocol_013_geriatria.md` • _Conduta inicial_ • score: **0.562**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

O protocolo institucional para manejo inicial de sepse inclui uma avaliação clínica completa, com exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e uma avaliação pulmonar. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a ressecação cirúrgica como primeira opção para os pacientes em estágios iniciais. Para pacientes não candidatos à cirurgia, iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável. Iniciar acompanhamento psicológico e suporte nutricional.

---

## 2. ✅ `rag_only` → detectado `rag_only` (3.97s)

**Pergunta:** Como tratar infarto agudo do miocárdio com supra de ST nas primeiras horas?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.289s | paciente 0.000s | LLM 3.679s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Inicial_ • score: **0.616**
  2. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.603**
  3. `protocol_009_dermatologia.md` • _Conduta Inicial_ • score: **0.593**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial deve incluir a interrupção do anticoagulante que desencadeou o infarto, se aplicável. O tratamento de escolha é:
- **Dipyridamol** 100 mg via oral a cada 12 horas por 10 a 14 dias, ou
- **Aspirina** 325 mg via oral a cada 12 horas por 10 a 14 dias, em casos mais graves ou recidivantes.

---

## 3. ✅ `rag_only` → detectado `rag_only` (2.47s)

**Pergunta:** Quais os critérios diagnósticos atuais para diabetes mellitus tipo 2?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.000s | LLM 2.446s

**Fontes consultadas:**
  1. `protocol_015_cardiologia.md` • _Conduta subsequente_ • score: **0.574**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Os critérios diagnósticos atuais para diabetes mellitus tipo 2 incluem a história de glicose em jejum elevada, história familiar de diabetes, sintomas de glicose em jejum (ex.: sede constante, fome, perda de peso), e resultado de exame de glicemia em jejum.

---

## 4. ✅ `rag_only` → detectado `rag_only` (2.85s)

**Pergunta:** Como manejar exacerbação aguda de asma em crianças?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.020s | paciente 0.000s | LLM 2.827s

**Fontes consultadas:**
  1. `protocol_018_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.827**
  2. `protocol_033_pediatria.md` • _Perguntas relacionadas_ • score: **0.815**
  3. `protocol_018_pediatria.md` • _Indicação_ • score: **0.813**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para a exacerbação aguda de asma em crianças, é recomendado monitorar a frequência e a intensidade dos sintomas, incluindo a necessidade de uso de broncodilatadores de ação rápida. Se a condição persistir ou se houver sinais de deterioração, encaminhar para um especialista em pneumologia pediátrica.

---

## 5. ✅ `rag_only` → detectado `rag_only` (4.02s)

**Pergunta:** Qual a conduta inicial em paciente com suspeita de AVC isquêmico?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.025s | paciente 0.000s | LLM 3.996s

**Fontes consultadas:**
  1. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.614**
  2. `protocol_004_emergência.md` • _Indicação_ • score: **0.612**
  3. `protocol_004_emergência.md` • _Critérios de Alta/Encaminhamento_ • score: **0.608**

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A conduta inicial deve incluir exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e avaliação pulmonar. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a ressecação cirúrgica como primeira opção para os pacientes em estágios iniciais. Para pacientes não candidatos à cirurgia, iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável. Iniciar acompanhamento psicológico e suporte nutricional.

---

## 6. ✅ `patient_only` → detectado `patient_only` (1.11s)

**Pergunta:** Quais são as alergias do paciente P0001?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.002s | LLM 1.086s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

Alérgias do paciente P0001: Nenhuma.

---

## 7. ✅ `patient_only` → detectado `patient_only` (3.09s)

**Pergunta:** Qual o histórico clínico do paciente P0023?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.000s | RAG 0.029s | paciente 0.001s | LLM 3.060s

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

## 8. ✅ `patient_only` → detectado `patient_only` (1.27s)

**Pergunta:** Que medicações o paciente P0042 está em uso?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.023s | paciente 0.000s | LLM 1.248s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

Paciente P0042 está em uso de enalapril e atorvastatina.

---

## 9. ✅ `both` → detectado `both` (6.11s)

**Pergunta:** Para o paciente P0001 com suspeita de pneumonia comunitária, qual conduta segundo nossos protocolos?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0001']`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.000s | LLM 6.088s

**Fontes consultadas:**
  1. `protocol_017_infectologia.md` • _Introdução_ • score: **0.742**
  2. `protocol_017_infectologia.md` • _Perguntas relacionadas_ • score: **0.701**
  3. `protocol_002_infectologia.md` • _Introdução_ • score: **0.660**

**Pacientes consultados:**
  - **P0001** (Sr. Apollo Sousa, 5 anos, M): alergias: Nenhuma; medicações: soro fisiológico, paracetamol

**Resposta:**

### Orientação clínica

- **Diagnóstico inicial**: Pneumonia comunitária é considerada em pacientes com sintomas de tosse, febre e falta de ar. Avalie a gravidade com base em sinais vitais, como frequência respiratória e oxigênio saturado.
- **Tratamento**: Inicialmente, recomendamos uso de antibióticos como amoxicilina ou doxiciclina. Se houver resistência, considerar a utilização de metronidazol. Monitorar a resposta ao tratamento e avaliar a necessidade de hospitalização.
- **Prevenção**: Reduzir o uso de antibióticos em pacientes com histórico de resistência, e orientar sobre uso de antifúngicos em pacientes com histórico de fungite.
- **Intervenção**: Encaminhar o paciente para avaliação clínica e laboratorial, incluindo exames de sangue, exames de imagem e exames de laboratório.

---

## 10. ✅ `both` → detectado `both` (2.3s)

**Pergunta:** Paciente P0023 chega com dor torácica em aperto — qual protocolo aplicar considerando o histórico dele?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0023']`

**Latências:** router 0.001s | RAG 0.022s | paciente 0.000s | LLM 2.276s

**Fontes consultadas:**
  1. `protocol_033_pediatria.md` • _Critérios de Alta/Encaminhamento_ • score: **0.574**

**Pacientes consultados:**
  - **P0023** (Théo Abreu, 50 anos, M): alergias: nenhuma; medicações: atorvastatina, ácido acetilsalicílico

**Resposta:**

Paciente P0023 apresenta dor torácica em aperto, histórico de hiperlipidemia e infarto do miocárdio. Considerar protocolo de monitoramento intensivo e avaliação de comorbidades, incluindo a possibilidade de terapia cardiovascular.

---

## 11. ✅ `both` → detectado `both` (4.62s)

**Pergunta:** Para o paciente P0042 em pré-operatório, quais cuidados o protocolo de pré-anestesia prevê?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0042']`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.000s | LLM 4.595s

**Fontes consultadas:**
  1. `protocol_032_infectologia.md` • _Conduta Subsequente_ • score: **0.581**
  2. `protocol_011_oncologia.md` • _Conduta Inicial_ • score: **0.579**
  3. `protocol_002_infectologia.md` • _Conduta Inicial_ • score: **0.564**

**Pacientes consultados:**
  - **P0042** (Vitor Gabriel Almeida, 89 anos, M): alergias: sulfonamidas; medicações: enalapril, atorvastatina

**Resposta:**

O protocolo de pré-anestesia prevê a realização de uma avaliação completa do paciente, incluindo exames de imagem (tomografia computadorizada do tórax e abdômen), exames laboratoriais e uma avaliação pulmonar. A equipe multidisciplinar deve discutir o plano de tratamento, considerando a ressecação cirúrgica como primeira opção para os pacientes em estágios iniciais. Para pacientes não candidatos à cirurgia, iniciar a quimioterapia neoadjuvante ou terapia-alvo, se aplicável. Iniciar acompanhamento psicológico e suporte nutricional.

---

## 12. ✅ `out_of_scope` → detectado `out_of_scope` (8.16s)

**Pergunta:** Como faço um bolo de chocolate?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.017s | paciente 0.000s | LLM 8.139s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

Para fazer um bolo de chocolate, você precisa de:

- 1 kg de chocolate em pó
- 2 ovos
- 1 lata de leite condensado
- 1/2 xícara de açúcar
- 1/2 xícara de leite
- 1/2 xícara de manteiga
- 1/2 xícara de farinha de trigo
- 1/2 xícara de fermento em pó

Faça o bolo de acordo com o seguinte passo a passo:

1. Misture o chocolate em pó, o açúcar, o leite condensado e a manteiga em uma tigela grande. Coloque em um recipiente antiaderente e leve ao fogo para ferver.
2. Despeje o leite quente e misture bem. Deixe esfriar.
3. Em uma tigela separada, bata os ovos com a farinha de trigo e o fermento em pó. Adicione o bolo fervido e misture bem.
4. Despeje o bolo em um molde untado com manteiga e forre com papel de alumínio. Leve ao forno a 180°C por 30 minutos ou até que a camada superior esteja dourada.
5. Desenforme e deixe esfriar antes de servir.

---

## 13. ✅ `out_of_scope` → detectado `out_of_scope` (1.55s)

**Pergunta:** Quem ganhou a Copa do Mundo de 2022?

**Roteamento:** `needs_rag=True`, `needs_patient=False`, `patient_ids=[]`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.000s | LLM 1.524s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
_(nenhum)_

**Resposta:**

A Alemanha foi campeã da Copa do Mundo de 2022, com o time alemão, que venceu o Brasil por 3 a 1.

---

## 14. ✅ `invalid_id` → detectado `invalid_id` (2.3s)

**Pergunta:** Quais são as alergias do paciente P9999?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P9999']`

**Latências:** router 0.000s | RAG 0.022s | paciente 0.001s | LLM 2.280s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P9999**: ❌ não encontrado no banco

**Resposta:**

Alguns pacientes podem ter alergias a medicamentos, alimentos ou substâncias. Por favor, informe se o paciente P9999 tem alergias conhecidas, como alérgicos a penicilina, alérgicos a ovos, ou alérgicos a produtos químicos.

---

## 15. ✅ `invalid_id` → detectado `invalid_id` (1.13s)

**Pergunta:** Qual o histórico clínico do paciente P0099?

**Roteamento:** `needs_rag=True`, `needs_patient=True`, `patient_ids=['P0099']`

**Latências:** router 0.000s | RAG 0.021s | paciente 0.000s | LLM 1.111s

**Fontes consultadas:**
_(nenhuma)_

**Pacientes consultados:**
  - **P0099**: ❌ não encontrado no banco

**Resposta:**

Histórico clínico do paciente P0099 não encontrado no banco de dados.

---
