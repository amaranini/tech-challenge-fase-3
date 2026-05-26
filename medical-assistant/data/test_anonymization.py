"""Testes da anonimização. Rode com:

    uv run pytest data/test_anonymization.py -v

Os testes carregam o modelo spaCy `pt_core_news_lg` na primeira chamada
(cerca de 1-2s) e cacheiam para os demais. Se o modelo não estiver baixado,
um RuntimeError com instrução clara aparece.
"""

from __future__ import annotations

import pytest

from anonymization import anonymize_text


def test_detecta_cpf_formatado():
    text = "O paciente tem CPF 123.456.789-00 e busca atendimento."
    result = anonymize_text(text)
    assert "123.456.789-00" not in result.anonymized_text
    assert "[CPF_1]" in result.anonymized_text
    assert "CPF" in result.entities_found


def test_detecta_cpf_nao_formatado():
    text = "Documento do paciente: 12345678900."
    result = anonymize_text(text)
    assert "12345678900" not in result.anonymized_text
    assert "[CPF_1]" in result.anonymized_text
    assert "CPF" in result.entities_found


def test_detecta_nome_em_frase():
    text = "Ana Maria Souza compareceu à consulta."
    result = anonymize_text(text)
    assert "Ana Maria Souza" not in result.anonymized_text
    assert "PESSOA" in result.entities_found


def test_detecta_multiplas_entidades_em_texto_longo():
    text = (
        "Paciente Pedro Augusto Almeida, CPF 987.654.321-00, "
        "telefone (11) 99876-5432, e-mail pedro@example.com, "
        "compareceu em 15/03/2024 ao Hospital São Lucas."
    )
    result = anonymize_text(text)
    found = set(result.entities_found)
    assert "CPF" in found
    assert "TELEFONE" in found
    assert "EMAIL" in found
    assert "DATA" in found
    assert "PESSOA" in found


def test_mantem_consistencia_mesmo_nome():
    text = (
        "João Silva veio à consulta. João Silva foi atendido pelo médico. "
        "Após a alta, João Silva agendou retorno."
    )
    result = anonymize_text(text)
    # O mesmo placeholder deve ocorrer 3 vezes e nenhum PESSOA_2.
    assert result.anonymized_text.count("[PESSOA_1]") == 3
    assert "[PESSOA_2]" not in result.anonymized_text


def test_nao_confunde_local_com_pessoa():
    text = "Pedro mudou-se de São Paulo para Belo Horizonte na semana passada."
    result = anonymize_text(text)
    # São Paulo e Belo Horizonte devem virar LOCAL, não PESSOA.
    assert "São Paulo" not in result.anonymized_text
    assert "Belo Horizonte" not in result.anonymized_text
    assert "[LOCAL_" in result.anonymized_text


def test_detecta_email():
    text = "Contato: medico.responsavel@hospital.com.br para urgências."
    result = anonymize_text(text)
    assert "medico.responsavel@hospital.com.br" not in result.anonymized_text
    assert "[EMAIL_1]" in result.anonymized_text


def test_detecta_telefone_com_ddd():
    text = "Telefone do contato: (11) 99876-5432, ligar após as 14h."
    result = anonymize_text(text)
    assert "(11) 99876-5432" not in result.anonymized_text
    assert "TELEFONE" in result.entities_found


def test_detecta_data_nascimento():
    text = "Data de nascimento: 12/05/1985, sexo feminino."
    result = anonymize_text(text)
    assert "12/05/1985" not in result.anonymized_text
    assert "DATA" in result.entities_found


def test_detecta_crm():
    text = "Atendido pelo médico responsável CRM/SP 123456."
    result = anonymize_text(text)
    assert "CRM/SP 123456" not in result.anonymized_text
    assert "CRM" in result.entities_found


def test_mapping_contem_originais():
    text = "Paciente Maria Souza, CPF 111.222.333-44."
    result = anonymize_text(text)
    # mapping deve registrar pelo menos os valores originais detectados
    originais = set(result.mapping.keys())
    assert "111.222.333-44" in originais


def test_texto_vazio_nao_quebra():
    result = anonymize_text("")
    assert result.anonymized_text == ""
    assert result.entities_found == []
    assert result.mapping == {}
