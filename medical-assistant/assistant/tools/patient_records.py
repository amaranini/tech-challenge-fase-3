"""Consulta de prontuário em SQLite.

Função principal: `get_patient_by_id(patient_id) -> PatientRecord | None`.
Retorna `None` se o ID não existir (graceful failure).

Smoke test (linha de comando):
    uv run python -m assistant.tools.patient_records P0001
    uv run python -m assistant.tools.patient_records P9999
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
DB_PATH = PROJECT_ROOT / "assistant" / "data" / "patients.db"


@dataclass
class PatientRecord:
    id: str
    nome: str
    idade: int
    sexo: str
    alergias: str
    medicacoes_atuais: str
    historico_resumido: str
    exames_pendentes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "idade": self.idade,
            "sexo": self.sexo,
            "alergias": self.alergias,
            "medicacoes_atuais": self.medicacoes_atuais,
            "historico_resumido": self.historico_resumido,
            "exames_pendentes": self.exames_pendentes,
        }


def get_patient_by_id(patient_id: str, db_path: Path | str = DB_PATH) -> PatientRecord | None:
    """Busca um paciente pelo ID. Retorna None se não existir.

    Levanta `FileNotFoundError` se o banco ainda não foi construído.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Banco de pacientes não encontrado em '{db_path}'.\n"
            f"Construa antes: uv run python assistant/tools/build_patient_db.py"
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, nome, idade, sexo, alergias, medicacoes_atuais, "
            "       historico_resumido, exames_pendentes "
            "FROM pacientes WHERE id = ?",
            (patient_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        logger.info("get_patient_by_id(%r) → não encontrado", patient_id)
        return None

    try:
        exames = json.loads(row["exames_pendentes"] or "[]")
    except json.JSONDecodeError:
        exames = []

    rec = PatientRecord(
        id=row["id"],
        nome=row["nome"],
        idade=row["idade"],
        sexo=row["sexo"],
        alergias=row["alergias"] or "",
        medicacoes_atuais=row["medicacoes_atuais"] or "",
        historico_resumido=row["historico_resumido"] or "",
        exames_pendentes=exames,
    )
    logger.info("get_patient_by_id(%r) → %s, %d anos", patient_id, rec.nome, rec.idade)
    return rec


def list_patients(
    db_path: Path | str = DB_PATH,
    limit: int = 100,
) -> list[dict]:
    """Lista resumida de pacientes (id, nome, idade, sexo).

    Usada pelo endpoint `/patients` da API (Fase 7) pra popular o dropdown
    da UI. Não traz dados sensíveis — só o suficiente pra identificação.

    Retorna [] se o banco não existir (ao invés de levantar) — útil pra
    health checks da API.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        logger.warning("list_patients: banco não encontrado em %s", db_path)
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, nome, idade, sexo FROM pacientes "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_pending_exams(patient_id: str, db_path: Path | str = DB_PATH) -> list[dict]:
    """Lista exames pendentes do paciente na tabela `exames_pendentes` (Fase 5).

    Retorna [] em qualquer cenário de "sem exames":
    - paciente não tem nenhum exame pendente
    - paciente não existe (sem levantar exceção — comportamento gracioso)

    Levanta `FileNotFoundError` apenas se o banco não foi construído ainda.

    Estrutura de cada item:
        {"tipo_exame": str, "data_solicitacao": str (ISO), "prioridade": str}

    Ordenação: prioridade DESC (imediato > urgente > rotina), depois
    data_solicitacao DESC (mais recente primeiro).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"Banco de pacientes não encontrado em '{db_path}'.\n"
            f"Construa antes: uv run python assistant/tools/build_patient_db.py"
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT tipo_exame, data_solicitacao, prioridade "
            "FROM exames_pendentes "
            "WHERE patient_id = ? "
            "ORDER BY CASE prioridade "
            "  WHEN 'imediato' THEN 0 "
            "  WHEN 'urgente'  THEN 1 "
            "  WHEN 'rotina'   THEN 2 "
            "END ASC, data_solicitacao DESC",
            (patient_id,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        # Tabela ausente: DB construído em versão pré-Fase 5.
        conn.close()
        logger.warning("get_pending_exams: tabela exames_pendentes ausente (%s)", e)
        return []
    finally:
        conn.close()

    exams = [dict(r) for r in rows]
    logger.info("get_pending_exams(%r) → %d exame(s)", patient_id, len(exams))
    return exams


def _cli(patient_id: str) -> int:
    """Smoke test: imprime o prontuário ou mensagem de não-encontrado."""
    try:
        rec = get_patient_by_id(patient_id)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1
    if rec is None:
        print(f"⚠ Paciente {patient_id!r} não encontrado no banco.")
        return 0
    print(f"Paciente {rec.id}: {rec.nome}")
    print(f"  Idade: {rec.idade} | Sexo: {rec.sexo}")
    print(f"  Alergias: {rec.alergias}")
    print(f"  Medicações em uso: {rec.medicacoes_atuais}")
    print(f"  Histórico:")
    print(f"    {rec.historico_resumido}")
    print(f"  Exames pendentes (legado JSON): {rec.exames_pendentes}")
    print()
    print(f"  Exames pendentes (tabela exames_pendentes, Fase 5):")
    exams = get_pending_exams(patient_id)
    if not exams:
        print("    (nenhum)")
    for e in exams:
        print(f"    - [{e['prioridade']:<8s}] {e['tipo_exame']} "
              f"(solicitado em {e['data_solicitacao']})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: uv run python -m assistant.tools.patient_records P0001")
        sys.exit(2)
    sys.exit(_cli(sys.argv[1]))
