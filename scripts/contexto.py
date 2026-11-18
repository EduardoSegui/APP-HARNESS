#!/usr/bin/env python3
"""Genera STATE.md y valida el presupuesto de contexto del harness.

Uso:
    uv run python scripts/contexto.py estado
    uv run python scripts/contexto.py estado --stdout
    uv run python scripts/contexto.py rotate
    uv run python scripts/contexto.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEEP_SESSIONS = 2
PACKET_CAP = 8 * 1024
CAPS = {
    "AGENTS.md": 6 * 1024,
    ".agent/rules.md": 4 * 1024,
    "STATE.md": 3 * 1024,
    "CHECKPOINT.md": 12 * 1024,
    ".agent/subagents/builder.md": 3 * 1024,
    ".agent/subagents/verifier.md": 3 * 1024,
}
REQUIRED_FILES = (
    "AGENTS.md",
    "features.json",
    "STATE.md",
    "CHECKPOINT.md",
    ".agent/rules.md",
    ".agent/subagents/builder.md",
    ".agent/subagents/verifier.md",
)
PACKET_HEADINGS = (
    "## Objetivo",
    "## Alcance",
    "## Fuera de alcance",
    "## Criterios de aceptación",
    "## Archivos previstos",
    "## Tests y casos borde",
    "## Referencias",
)

CHECKPOINT_HEADER = """# CHECKPOINT — Ventana de sesiones recientes

> Estado actual: [`STATE.md`](STATE.md). Historia completa: [`docs/journal/`](docs/journal/).
> Se conservan las últimas 2 sesiones; `uv run python scripts/contexto.py rotate` mueve las anteriores.

"""

JOURNAL_HEADER = """# Bitácora {year} — Archivo histórico

> Estado actual: [`STATE.md`](../../STATE.md). Ventana reciente: [`CHECKPOINT.md`](../../CHECKPOINT.md).
> Entradas anteriores al cierre vigente. No editar; solo agregar.

"""

SESSION_RE = re.compile(r"(?m)^## Sesión (\d+) — (.+)$")
FEATURE_ID_RE = re.compile(r"^F\d{2,}$")


class ContextoError(Exception):
    """Error de estructura del harness."""


@dataclass(frozen=True)
class Feature:
    id: str
    titulo: str
    passes: bool
    packet: str | None = None
    descripcion: str | None = None


@dataclass(frozen=True)
class Session:
    numero: int
    titulo: str
    fecha: str | None
    fuente: str
    bloque: str
    tests: str | None
    harness: str | None

    @property
    def ancla(self) -> str:
        return f"sesión-{self.numero:02d}"


def _leer(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tamano_kb(path: Path) -> str:
    return f"{path.stat().st_size / 1024:.1f} KB"


def load_features(root: Path = ROOT) -> list[Feature]:
    path = root / "features.json"
    if not path.exists():
        raise ContextoError("falta features.json")
    try:
        data = json.loads(_leer(path))
    except json.JSONDecodeError as exc:
        raise ContextoError(f"features.json no es JSON válido: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise ContextoError("features.json debe tener una lista 'features'")

    features: list[Feature] = []
    vistos: set[str] = set()
    for posicion, item in enumerate(data["features"], start=1):
        if not isinstance(item, dict):
            raise ContextoError(f"feature #{posicion} no es un objeto")
        feature_id = item.get("id")
        if not isinstance(feature_id, str) or not FEATURE_ID_RE.fullmatch(feature_id):
            raise ContextoError(f"feature #{posicion}: id inválido ({feature_id!r})")
        if feature_id in vistos:
            raise ContextoError(f"feature duplicada: {feature_id}")
        vistos.add(feature_id)
        titulo = item.get("titulo")
        if not isinstance(titulo, str) or not titulo.strip():
            raise ContextoError(f"{feature_id}: falta 'titulo'")
        passes = item.get("passes")
        if not isinstance(passes, bool):
            raise ContextoError(f"{feature_id}: 'passes' debe ser booleano")
        packet = item.get("packet")
        if packet is not None and (not isinstance(packet, str) or not packet.strip()):
            raise ContextoError(f"{feature_id}: 'packet' debe ser una ruta no vacía")
        descripcion = item.get("descripcion")
        if descripcion is not None and not isinstance(descripcion, str):
            raise ContextoError(f"{feature_id}: 'descripcion' debe ser texto")
        features.append(
            Feature(
                id=feature_id,
                titulo=titulo.strip(),
                passes=passes,
                packet=packet.strip() if packet else None,
                descripcion=descripcion.strip() if descripcion else None,
            )
        )
    return features


def parse_sessions(text: str, fuente: str) -> list[Session]:
    matches = list(SESSION_RE.finditer(text))
    sesiones: list[Session] = []
    for indice, match in enumerate(matches):
        inicio = match.start()
        fin = matches[indice + 1].start() if indice + 1 < len(matches) else len(text)
        bloque = text[inicio:fin].rstrip() + "\n"
        fecha_match = re.search(r"\*\*Fecha:\*\*\s*(\d{4}-\d{2}-\d{2})", bloque)
        tests_match = re.search(
            r"(?:Suite de tests|uv run pytest)[^\n]*?(\d+)\s+passed", bloque
        )
        if tests_match:
            tests = f"{tests_match.group(1)} passed"
        else:
            tests_genericos = re.findall(r"(\d+)\s+passed", bloque)
            tests = f"{tests_genericos[-1]} passed" if tests_genericos else None
        harness = None
        if re.search(r"Harness completo.*?\|\s*OK\s*\|", bloque) or re.search(
            r"`\./init\.sh`.*?OK", bloque
        ):
            harness = "OK"
        sesiones.append(
            Session(
                numero=int(match.group(1)),
                titulo=match.group(2).strip(),
                fecha=fecha_match.group(1) if fecha_match else None,
                fuente=fuente,
                bloque=bloque,
                tests=tests,
                harness=harness,
            )
        )
    return sesiones


def all_sessions(root: Path = ROOT) -> list[Session]:
    sesiones: list[Session] = []
    checkpoint = root / "CHECKPOINT.md"
    if checkpoint.exists():
        sesiones.extend(parse_sessions(_leer(checkpoint), "CHECKPOINT.md"))
    journal_dir = root / "docs" / "journal"
    if journal_dir.is_dir():
        for path in sorted(journal_dir.glob("*.md")):
            relativa = path.relative_to(root).as_posix()
            sesiones.extend(parse_sessions(_leer(path), relativa))

    por_numero: dict[int, Session] = {}
    for sesion in sesiones:
        actual = por_numero.get(sesion.numero)
        if actual is None or sesion.fuente == "CHECKPOINT.md":
            por_numero[sesion.numero] = sesion
    return [por_numero[numero] for numero in sorted(por_numero)]


def latest_session(root: Path = ROOT) -> Session | None:
    sesiones = all_sessions(root)
    return sesiones[-1] if sesiones else None


def build_state(root: Path = ROOT) -> str:
    features = load_features(root)
    total = len(features)
    verificadas = [feature for feature in features if feature.passes]
    pendientes = [feature for feature in features if not feature.passes]

    lineas = [
        "# Estado del proyecto",
        "",
        "> Generado por `uv run python scripts/contexto.py estado`. No editar a mano.",
        "",
        f"- **Plan:** {len(verificadas)}/{total} features verificadas (`features.json`).",
    ]

    if pendientes:
        siguiente = pendientes[0]
        detalle = f" — packet: `{siguiente.packet}`" if siguiente.packet else ""
        lineas.append(f"- **Próximo paso:** {siguiente.id} — {siguiente.titulo}{detalle}.")
    else:
        lineas.append("- **Próximo paso:** planificación (no hay features pendientes).")

    ultima = latest_session(root)
    if ultima:
        fecha = f" ({ultima.fecha})" if ultima.fecha else ""
        lineas.append(
            f"- **Última sesión:** Sesión {ultima.numero:02d} — {ultima.titulo}{fecha}."
        )
        lineas.append(f"- **Última entrada:** `{ultima.fuente}#{ultima.ancla}`.")
        if ultima.tests:
            lineas.append(f"- **Tests:** {ultima.tests}.")
        if ultima.harness:
            lineas.append(f"- **Harness:** {ultima.harness}.")
    else:
        lineas.append("- **Última sesión:** sin sesiones registradas.")

    return "\n".join(lineas) + "\n"


def write_state(root: Path = ROOT) -> Path:
    path = root / "STATE.md"
    path.write_text(build_state(root), encoding="utf-8")
    return path


def _year_of(session: Session) -> str:
    if session.fecha:
        return session.fecha[:4]
    return "2026"


def _journal_path(root: Path, year: str) -> Path:
    return root / "docs" / "journal" / f"{year}.md"


def _ensure_journal(path: Path, year: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(JOURNAL_HEADER.format(year=year), encoding="utf-8")


def _append_if_missing(path: Path, session: Session) -> bool:
    existente = _leer(path) if path.exists() else ""
    patron = re.compile(rf"(?m)^## Sesión 0*{session.numero} — ")
    if patron.search(existente):
        return False
    _ensure_journal(path, _year_of(session))
    with path.open("a", encoding="utf-8") as archivo:
        if not existente.endswith("\n\n"):
            archivo.write("\n")
        archivo.write(session.bloque)
        archivo.write("\n")
    return True


def rotate(root: Path = ROOT, keep: int = KEEP_SESSIONS) -> tuple[int, list[Path]]:
    if keep < 0:
        raise ContextoError("'keep' no puede ser negativo")
    checkpoint = root / "CHECKPOINT.md"
    if not checkpoint.exists():
        raise ContextoError("falta CHECKPOINT.md")
    texto = _leer(checkpoint)
    matches = list(SESSION_RE.finditer(texto))
    if len(matches) <= keep:
        return 0, []

    header = texto[: matches[0].start()]
    sesiones = parse_sessions(texto, "CHECKPOINT.md")
    archivadas = sesiones[:-keep] if keep else sesiones
    conservadas = sesiones[-keep:] if keep else []

    journals: list[Path] = []
    for sesion in archivadas:
        path = _journal_path(root, _year_of(sesion))
        _ensure_journal(path, _year_of(sesion))
        if _append_if_missing(path, sesion):
            journals.append(path)

    # Preserva el encabezado viejo (por ejemplo, "Estado actual") en el archivo.
    if "## Estado actual" in header and archivadas:
        year = _year_of(archivadas[-1])
        path = _journal_path(root, year)
        _ensure_journal(path, year)
        actual = _leer(path)
        marcador = "## Estado histórico (antes de la rotación)"
        if marcador not in actual:
            with path.open("a", encoding="utf-8") as archivo:
                archivo.write(f"\n{marcador}\n\n{header.strip()}\n")
            journals.append(path)

    nuevo = CHECKPOINT_HEADER + "\n".join(s.bloque for s in conservadas).rstrip() + "\n"
    checkpoint.write_text(nuevo, encoding="utf-8")
    return len(archivadas), sorted(set(journals))


def _validar_packet(root: Path, feature: Feature) -> list[str]:
    errores: list[str] = []
    if not feature.packet:
        return errores
    path = root / feature.packet
    if not path.exists():
        errores.append(f"{feature.id}: no existe el packet '{feature.packet}'")
        return errores
    tamano = path.stat().st_size
    if tamano > PACKET_CAP:
        errores.append(
            f"{feature.packet} excede el cap de packet ({tamano} > {PACKET_CAP} bytes)"
        )
    contenido = _leer(path)
    for heading in PACKET_HEADINGS:
        if heading not in contenido:
            errores.append(f"{feature.packet}: falta la sección '{heading}'")
    return errores


def check(root: Path = ROOT) -> list[str]:
    errores: list[str] = []

    for nombre in REQUIRED_FILES:
        if not (root / nombre).exists():
            errores.append(f"falta el archivo obligatorio '{nombre}'")

    for nombre, cap in CAPS.items():
        path = root / nombre
        if path.exists() and path.stat().st_size > cap:
            errores.append(
                f"{nombre} excede el cap ({path.stat().st_size} > {cap} bytes)"
            )

    try:
        features = load_features(root)
    except ContextoError as exc:
        errores.append(str(exc))
        features = []

    for feature in features:
        errores.extend(_validar_packet(root, feature))

    state = root / "STATE.md"
    if state.exists():
        esperado = build_state(root)
        if state.read_text(encoding="utf-8").rstrip("\n") != esperado.rstrip("\n"):
            errores.append(
                "STATE.md no coincide con el estado generado; "
                "ejecutá 'uv run python scripts/contexto.py estado'"
            )

    checkpoint = root / "CHECKPOINT.md"
    if checkpoint.exists():
        sesiones = parse_sessions(_leer(checkpoint), "CHECKPOINT.md")
        if len(sesiones) > KEEP_SESSIONS:
            errores.append(
                f"CHECKPOINT.md tiene {len(sesiones)} sesiones; "
                f"ejecutá 'uv run python scripts/contexto.py rotate'"
            )

    return errores


def _reporte(root: Path) -> str:
    partes = []
    for nombre in ("AGENTS.md", ".agent/rules.md", "STATE.md", "CHECKPOINT.md"):
        path = root / nombre
        if path.exists():
            partes.append(f"{nombre} {_tamano_kb(path)}")
    return "Contexto: " + " · ".join(partes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contexto")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--check", action="store_true", help="validar el harness")
    subparsers = parser.add_subparsers(dest="comando")

    estado = subparsers.add_parser("estado", help="generar STATE.md")
    estado.add_argument("--stdout", action="store_true", help="imprimir sin escribir")

    rotar = subparsers.add_parser("rotate", help="archivar sesiones viejas")
    rotar.add_argument("--keep", type=int, default=KEEP_SESSIONS, help=argparse.SUPPRESS)
    rotar.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    root: Path = args.root

    if args.check:
        errores = check(root)
        if errores:
            for error in errores:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(_reporte(root))
        print("Contexto OK.")
        return 0

    if args.comando == "estado":
        contenido = build_state(root)
        if args.stdout:
            print(contenido, end="")
        else:
            (root / "STATE.md").write_text(contenido, encoding="utf-8")
            print("STATE.md actualizado.")
        return 0

    if args.comando == "rotate":
        if args.dry_run:
            sesiones = parse_sessions(_leer(root / "CHECKPOINT.md"), "CHECKPOINT.md")
            print(f"Sesiones en CHECKPOINT.md: {len(sesiones)}; se conservarían {args.keep}.")
            return 0
        movidas, journals = rotate(root, keep=args.keep)
        if movidas == 0:
            print("Nada para rotar.")
        else:
            print(f"Sesiones archivadas: {movidas}.")
            for journal in journals:
                print(f"  → {journal.relative_to(root)}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
