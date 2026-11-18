"""Tests del harness de contexto: estado, rotación y presupuestos."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import contexto


def _sesion(
    numero: int,
    titulo: str = "Sesión de prueba",
    fecha: str = "2026-11-18",
    tests: str | None = "10 passed",
    harness: bool = True,
) -> str:
    lineas = [
        f"## Sesión {numero:02d} — {titulo}",
        "",
        f"**Fecha:** {fecha}",
        "",
        "### Verificación ejecutada",
        "",
        "| Comprobación | Comando | Resultado |",
        "|---|---|---|",
    ]
    if tests:
        lineas.append(f"| Suite de tests | `uv run pytest` | `{tests}` |")
    if harness:
        lineas.append("| Harness completo | `./init.sh` | OK |")
    return "\n".join(lineas) + "\n"


def _checkpoint(*sesiones: str, header: str = "# CHECKPOINT\n\n") -> str:
    return header + "\n".join(sesiones)


def _packet(tmp_path: Path, nombre: str = "features/F02.md") -> Path:
    path = tmp_path / nombre
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# F02 — Prueba",
                "",
                *[f"{heading}\n\nContenido.\n" for heading in contexto.PACKET_HEADINGS],
            ]
        ),
        encoding="utf-8",
    )
    return path


def _proyecto(
    tmp_path: Path,
    features: list[dict],
    checkpoint: str | None = None,
    *,
    estado: bool = True,
) -> Path:
    (tmp_path / "features.json").write_text(
        json.dumps({"features": features}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (tmp_path / ".agent" / "subagents").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agent" / "rules.md").write_text("# Reglas\n", encoding="utf-8")
    (tmp_path / ".agent" / "subagents" / "builder.md").write_text(
        "# Builder\n", encoding="utf-8"
    )
    (tmp_path / ".agent" / "subagents" / "verifier.md").write_text(
        "# Verifier\n", encoding="utf-8"
    )
    (tmp_path / "CHECKPOINT.md").write_text(
        checkpoint if checkpoint is not None else _checkpoint(_sesion(1)),
        encoding="utf-8",
    )
    if estado:
        (tmp_path / "STATE.md").write_text(contexto.build_state(tmp_path), encoding="utf-8")
    return tmp_path


def test_estado_sin_pendientes(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [
            {"id": "F01", "titulo": "Uno", "passes": True},
            {"id": "F02", "titulo": "Dos", "passes": True},
        ],
        _checkpoint(_sesion(2)),
    )

    estado = contexto.build_state(proyecto)

    assert "2/2 features verificadas" in estado
    assert "planificación (no hay features pendientes)" in estado
    assert "Sesión 02 — Sesión de prueba (2026-11-18)" in estado
    assert "10 passed" in estado
    assert "OK" in estado


def test_estado_con_pendiente_y_packet(tmp_path: Path) -> None:
    _packet(tmp_path)
    proyecto = _proyecto(
        tmp_path,
        [
            {"id": "F01", "titulo": "Uno", "passes": True},
            {
                "id": "F02",
                "titulo": "Dos",
                "passes": False,
                "packet": "features/F02.md",
            },
        ],
    )

    estado = contexto.build_state(proyecto)

    assert "1/2 features verificadas" in estado
    assert "F02 — Dos" in estado
    assert "features/F02.md" in estado


def test_estado_usa_la_suite_y_no_el_ultimo_passed(tmp_path: Path) -> None:
    bloque = """## Sesión 08 — F08

**Fecha:** 2026-11-17

### Verificación ejecutada

| Comprobación | Comando | Resultado |
|---|---|---|
| Suite de tests | `uv run pytest -v` | `177 passed` |
| Tests del panel | `uv run pytest tests/test_panel.py -q` | `9 passed` |
"""
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F08", "titulo": "Ocho", "passes": True}],
        "# CHECKPOINT\n\n" + bloque,
    )

    estado = contexto.build_state(proyecto)

    assert "177 passed" in estado
    assert "9 passed" not in estado


def test_estado_sin_sesiones(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        "# CHECKPOINT\n\n",
    )

    estado = contexto.build_state(proyecto)

    assert "sin sesiones registradas" in estado


def test_load_features_rechaza_duplicados(tmp_path: Path) -> None:
    _proyecto(
        tmp_path,
        [
            {"id": "F01", "titulo": "Uno", "passes": True},
            {"id": "F01", "titulo": "Otra", "passes": False},
        ],
        estado=False,
    )

    with pytest.raises(contexto.ContextoError, match="duplicada"):
        contexto.load_features(tmp_path)


def test_load_features_rechaza_passes_no_booleano(tmp_path: Path) -> None:
    _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": "true"}],
        estado=False,
    )

    with pytest.raises(contexto.ContextoError, match="booleano"):
        contexto.load_features(tmp_path)


def test_check_ok(tmp_path: Path) -> None:
    _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])

    assert contexto.check(tmp_path) == []


def test_check_detecta_state_viejo(tmp_path: Path) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])
    (proyecto / "STATE.md").write_text("viejo\n", encoding="utf-8")

    errores = contexto.check(proyecto)

    assert any("STATE.md no coincide" in error for error in errores)


def test_check_detecta_cap_de_agents(tmp_path: Path) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])
    (proyecto / "AGENTS.md").write_text("x" * (6 * 1024 + 1), encoding="utf-8")

    errores = contexto.check(proyecto)

    assert any("AGENTS.md excede el cap" in error for error in errores)


def test_check_detecta_packet_inexistente(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [
            {
                "id": "F02",
                "titulo": "Dos",
                "passes": False,
                "packet": "features/F02.md",
            }
        ],
    )

    errores = contexto.check(proyecto)

    assert any("no existe el packet" in error for error in errores)


def test_check_detecta_packet_sin_secciones(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [
            {
                "id": "F02",
                "titulo": "Dos",
                "passes": False,
                "packet": "features/F02.md",
            }
        ],
    )
    path = proyecto / "features" / "F02.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# F02\n\nSolo un título.\n", encoding="utf-8")

    errores = contexto.check(proyecto)

    assert any("falta la sección" in error for error in errores)


def test_check_detecta_checkpoint_largo(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        _checkpoint(_sesion(1), _sesion(2), _sesion(3)),
    )

    errores = contexto.check(proyecto)

    assert any("3 sesiones" in error for error in errores)


def test_check_detecta_archivo_faltante(tmp_path: Path) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])
    (proyecto / ".agent" / "rules.md").unlink()

    errores = contexto.check(proyecto)

    assert any("falta el archivo obligatorio" in error for error in errores)


def test_rotate_mueve_sesiones_y_no_duplica(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        _checkpoint(_sesion(1), _sesion(2), _sesion(3)),
    )

    movidas, journals = contexto.rotate(proyecto)

    assert movidas == 1
    assert journals == [proyecto / "docs" / "journal" / "2026.md"]
    checkpoint = (proyecto / "CHECKPOINT.md").read_text(encoding="utf-8")
    assert "## Sesión 01" not in checkpoint
    assert "## Sesión 02" in checkpoint
    assert "## Sesión 03" in checkpoint
    journal = (proyecto / "docs" / "journal" / "2026.md").read_text(encoding="utf-8")
    assert "## Sesión 01" in journal
    assert "## Sesión 02" not in journal

    movidas_otra_vez, _ = contexto.rotate(proyecto)
    assert movidas_otra_vez == 0
    journal = (proyecto / "docs" / "journal" / "2026.md").read_text(encoding="utf-8")
    assert journal.count("## Sesión 01") == 1


def test_rotate_keep_tres(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        _checkpoint(_sesion(1), _sesion(2), _sesion(3), _sesion(4)),
    )

    movidas, _ = contexto.rotate(proyecto, keep=3)

    assert movidas == 1
    checkpoint = (proyecto / "CHECKPOINT.md").read_text(encoding="utf-8")
    assert "## Sesión 01" not in checkpoint
    assert "## Sesión 02" in checkpoint
    assert "## Sesión 04" in checkpoint


def test_rotate_preserva_estado_historico(tmp_path: Path) -> None:
    header = "# CHECKPOINT — Bitácora\n\n## Estado actual\n\n- Última sesión: F08.\n\n"
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        _checkpoint(_sesion(1), _sesion(2), _sesion(3), header=header),
    )

    contexto.rotate(proyecto)

    journal = (proyecto / "docs" / "journal" / "2026.md").read_text(encoding="utf-8")
    assert "## Estado histórico (antes de la rotación)" in journal
    assert "Última sesión: F08." in journal


def test_rotate_sin_sesiones_suficientes(tmp_path: Path) -> None:
    proyecto = _proyecto(
        tmp_path,
        [{"id": "F01", "titulo": "Uno", "passes": False}],
        _checkpoint(_sesion(1), _sesion(2)),
    )

    movidas, journals = contexto.rotate(proyecto)

    assert movidas == 0
    assert journals == []


def test_cli_check_ok(tmp_path: Path) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])

    assert contexto.main(["--root", str(proyecto), "--check"]) == 0


def test_cli_check_falla(tmp_path: Path) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])
    (proyecto / "STATE.md").write_text("viejo\n", encoding="utf-8")

    assert contexto.main(["--root", str(proyecto), "--check"]) == 1


def test_cli_estado_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proyecto = _proyecto(tmp_path, [{"id": "F01", "titulo": "Uno", "passes": False}])

    assert contexto.main(["--root", str(proyecto), "estado", "--stdout"]) == 0
    assert "Estado del proyecto" in capsys.readouterr().out


def test_comando_sesion_usa_el_estado_generado() -> None:
    path = contexto.ROOT / ".opencode" / "commands" / "sesion.md"

    contenido = path.read_text(encoding="utf-8")

    assert "contexto.py estado --stdout" in contenido
    assert "git status --short" in contenido


def test_repo_real_pasa_el_presupuesto() -> None:
    assert contexto.check(contexto.ROOT) == []


