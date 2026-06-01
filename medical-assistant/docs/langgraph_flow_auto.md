# Diagrama do grafo — gerado automaticamente

Este arquivo é gerado por `assistant/graph.py:export_diagram()`.
Para a versão escrita à mão (mais legível pro relatório), veja [`langgraph_flow.md`](langgraph_flow.md).

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	input_guardrail_check(input_guardrail_check)
	classify_intent(classify_intent)
	triage_urgency(triage_urgency)
	fetch_patient_data(fetch_patient_data)
	check_pending_exams(check_pending_exams)
	retrieve_protocol(retrieve_protocol)
	generate_response(generate_response)
	guardrail_check(guardrail_check)
	emit_alert_if_needed(emit_alert_if_needed)
	finalize_response(finalize_response)
	refuse_node(refuse_node)
	rewrite_node(rewrite_node)
	__end__([<p>__end__</p>]):::last
	__start__ --> input_guardrail_check;
	check_pending_exams --> retrieve_protocol;
	emit_alert_if_needed --> finalize_response;
	fetch_patient_data --> check_pending_exams;
	finalize_response --> __end__;
	generate_response --> guardrail_check;
	refuse_node --> finalize_response;
	retrieve_protocol --> generate_response;
	rewrite_node --> emit_alert_if_needed;
	triage_urgency --> fetch_patient_data;
	input_guardrail_check -.-> refuse_node;
	input_guardrail_check -.-> classify_intent;
	classify_intent -.-> refuse_node;
	classify_intent -.-> triage_urgency;
	guardrail_check -.-> rewrite_node;
	guardrail_check -.-> emit_alert_if_needed;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```
