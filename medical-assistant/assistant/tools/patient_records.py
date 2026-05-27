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
    print(f"  Exames pendentes: {rec.exames_pendentes}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: uv run python -m assistant.tools.patient_records P0001")
        sys.exit(2)
    sys.exit(_cli(sys.argv[1]))
