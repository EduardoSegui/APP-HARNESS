"""Tests de los modelos ORM."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ventas_app.database import _migrar_ventas_sqlite, engine, init_db
from ventas_app.models import EstadoVenta, Integrante, Parentesco, Plan, Venta


def crear_plan(
    db: Session,
    *,
    nombre: str = "Plan de Prueba",
    precio_titular: int = 50_000,
    precio_adherente: int = 25_000,
) -> Plan:
    plan = Plan(
        nombre=nombre,
        precio_titular=precio_titular,
        precio_adherente=precio_adherente,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def crear_venta(plan: Plan, **overrides: object) -> Venta:
    datos: dict[str, object] = {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": date(1990, 5, 20),
        "email": "ana.perez@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": None,
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan": plan,
        "precio_total": 50_000,
    }
    datos.update(overrides)
    return Venta(**datos)


def crear_integrante(dni: str = "40111222", **overrides: object) -> Integrante:
    datos: dict[str, object] = {
        "nombre": "Luis",
        "apellido": "Pérez",
        "dni": dni,
        "fecha_nacimiento": date(2010, 3, 15),
        "parentesco": Parentesco.HIJO_A.value,
    }
    datos.update(overrides)
    return Integrante(**datos)


def test_init_db_crea_las_tablas_esperadas() -> None:
    init_db()

    tablas = set(inspect(engine).get_table_names())

    assert {"planes", "ventas", "integrantes"}.issubset(tablas)


def test_plan_usa_activo_por_defecto(db: Session) -> None:
    plan = Plan(
        nombre="Plan Nuevo",
        precio_titular=10_000,
        precio_adherente=5_000,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    assert plan.id is not None
    assert plan.activo is True


def test_venta_e_integrantes_se_relacionan(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(plan)
    integrante = crear_integrante()
    venta.integrantes.append(integrante)

    db.add(venta)
    db.commit()
    db.refresh(venta)
    db.refresh(integrante)

    assert venta.id is not None
    assert venta.plan.id == plan.id
    assert venta.estado == EstadoVenta.PENDIENTE_VERIFICACION.value
    assert venta.observaciones is None
    assert venta.creado_en is not None
    assert venta.actualizado_en is not None
    assert integrante.venta_id == venta.id
    assert venta.integrantes == [integrante]
    assert integrante in plan.ventas[0].integrantes


def test_dni_duplicado_en_la_misma_venta_es_rechazado(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(plan)
    venta.integrantes.extend(
        [
            crear_integrante(dni="40111222"),
            crear_integrante(dni="40111222", nombre="Otro"),
        ]
    )
    db.add(venta)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_dni_repetido_en_ventas_distintas_esta_permitido(db: Session) -> None:
    plan = crear_plan(db)
    primera = crear_venta(plan)
    primera.integrantes.append(crear_integrante(dni="40111222"))
    segunda = crear_venta(plan, nombre_titular="Bruno", dni_titular="30111222")
    segunda.integrantes.append(crear_integrante(dni="40111222"))

    db.add_all([primera, segunda])
    db.commit()

    assert primera.id != segunda.id
    assert primera.integrantes[0].dni == segunda.integrantes[0].dni


def test_eliminar_venta_elimina_sus_integrantes(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(plan)
    venta.integrantes.append(crear_integrante())
    db.add(venta)
    db.commit()

    venta_id = venta.id
    integrante_id = venta.integrantes[0].id

    db.delete(venta)
    db.commit()
    db.expire_all()

    assert db.get(Venta, venta_id) is None
    assert db.get(Integrante, integrante_id) is None


def test_estado_invalido_es_rechazado_por_la_base(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(plan, estado="EN_REVISION")
    db.add(venta)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_parentesco_invalido_es_rechazado_por_la_base(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(plan)
    venta.integrantes.append(crear_integrante(parentesco="Primo/a"))
    db.add(venta)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_venta_persiste_metadatos_de_pago_enmascarados(db: Session) -> None:
    plan = crear_plan(db)
    venta = crear_venta(
        plan,
        medio_pago="TARJETA_CREDITO",
        subtotal_base=45_000,
        descuento_porcentaje=30,
        precio_total=31_500,
        pago_titular="Ana Pérez",
        pago_marca_entidad="VISA",
        pago_ultimos_4="1111",
        pago_vencimiento="12/30",
    )
    db.add(venta)
    db.commit()
    db.refresh(venta)

    assert venta.pago_titular == "Ana Pérez"
    assert venta.pago_marca_entidad == "VISA"
    assert venta.pago_ultimos_4 == "1111"
    assert venta.pago_vencimiento == "12/30"
    assert venta.pago_cuil is None


def test_migracion_f13_agrega_columnas_y_conserva_ventas(tmp_path) -> None:
    engine_viejo = create_engine(f"sqlite:///{tmp_path / 'ventas-viejas.db'}")
    with engine_viejo.begin() as conexion:
        conexion.exec_driver_sql(
            "CREATE TABLE ventas ("
            "id INTEGER PRIMARY KEY, "
            "precio_total INTEGER NOT NULL"
            ")"
        )
        conexion.exec_driver_sql(
            "INSERT INTO ventas (id, precio_total) VALUES (7, 45000)"
        )

    _migrar_ventas_sqlite(engine_viejo)
    _migrar_ventas_sqlite(engine_viejo)

    with engine_viejo.connect() as conexion:
        columnas = {
            fila[1]
            for fila in conexion.exec_driver_sql("PRAGMA table_info(ventas)")
        }
        fila = conexion.exec_driver_sql(
            "SELECT medio_pago, subtotal_base, descuento_porcentaje, "
            "pago_titular, pago_marca_entidad, pago_ultimos_4, "
            "pago_vencimiento, pago_cuil, ddjj_completada, "
            "ddjj_preexistencias, ddjj_internaciones, ddjj_embarazo, "
            "ddjj_medicacion_cronica, ddjj_discapacidad, ddjj_detalle "
            "FROM ventas WHERE id = 7"
        ).one()

    assert {
        "medio_pago",
        "subtotal_base",
        "descuento_porcentaje",
        "pago_titular",
        "pago_marca_entidad",
        "pago_ultimos_4",
        "pago_vencimiento",
        "pago_cuil",
        "ddjj_completada",
        "ddjj_preexistencias",
        "ddjj_internaciones",
        "ddjj_embarazo",
        "ddjj_medicacion_cronica",
        "ddjj_discapacidad",
        "ddjj_detalle",
    }.issubset(columnas)
    assert fila == (
        "PAGO_FACIL",
        45_000,
        0,
        None,
        None,
        None,
        None,
        None,
        0,
        0,
        0,
        0,
        0,
        0,
        None,
    )
    engine_viejo.dispose()
