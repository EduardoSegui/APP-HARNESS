"""Tests de los esquemas Pydantic v2."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ventas_app.models import EstadoVenta, Integrante, MedioPago, Parentesco, Plan, Venta
from ventas_app.schemas import IntegranteIn, PlanOut, VentaIn, VentaOut


def payload_valido(**overrides: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.perez@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": "2 B",
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": 1,
        "medio_pago": "PAGO_FACIL",
        "integrantes": [
            {
                "nombre": "Luis",
                "apellido": "Pérez",
                "dni": "40111222",
                "fecha_nacimiento": "2010-03-15",
                "parentesco": "Hijo/a",
            }
        ],
    }
    datos.update(overrides)
    return datos


def test_venta_in_valida_y_normaliza_datos() -> None:
    datos = payload_valido(
        nombre_titular="  Ana  ",
        dni_titular=" 30111222 ",
        piso_depto="  2 B  ",
    )

    venta = VentaIn.model_validate(datos)

    assert venta.nombre_titular == "Ana"
    assert venta.dni_titular == "30111222"
    assert venta.piso_depto == "2 B"
    assert venta.integrantes[0].parentesco is Parentesco.HIJO_A
    assert venta.integrantes[0].fecha_nacimiento == date(2010, 3, 15)


def test_piso_depto_es_opcional_y_vacio_se_normaliza_a_none() -> None:
    sin_piso = payload_valido()
    sin_piso.pop("piso_depto")
    assert VentaIn.model_validate(sin_piso).piso_depto is None

    for valor in ("", "   "):
        venta = VentaIn.model_validate(payload_valido(piso_depto=valor))
        assert venta.piso_depto is None


@pytest.mark.parametrize("parentesco", list(Parentesco))
def test_todos_los_parentescos_permitidos(parentesco: Parentesco) -> None:
    integrante = IntegranteIn.model_validate(
        {
            "nombre": "Luis",
            "apellido": "Pérez",
            "dni": "40111222",
            "fecha_nacimiento": "2010-03-15",
            "parentesco": parentesco,
        }
    )

    assert integrante.parentesco is parentesco


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("dni_titular", "30.111.222"),
        ("dni_titular", "123456"),
        ("dni_titular", "123456789"),
        ("email", "ana@"),
        ("email", "ana.perez.example.com"),
        ("telefono", "12345"),
        ("telefono", "abc-def"),
        ("codigo_postal", "C1043"),
        ("codigo_postal", "104"),
        ("calle", " "),
        ("altura", ""),
        ("plan_id", 0),
    ],
)
def test_venta_in_rechaza_datos_invalidos(campo: str, valor: object) -> None:
    with pytest.raises(ValidationError):
        VentaIn.model_validate(payload_valido(**{campo: valor}))


def test_venta_in_rechaza_fecha_futura_del_titular() -> None:
    fecha_futura = (date.today() + timedelta(days=1)).isoformat()

    with pytest.raises(ValidationError):
        VentaIn.model_validate(
            payload_valido(fecha_nacimiento_titular=fecha_futura)
        )


def test_integrante_in_rechaza_fecha_futura() -> None:
    with pytest.raises(ValidationError):
        IntegranteIn.model_validate(
            {
                "nombre": "Luis",
                "apellido": "Pérez",
                "dni": "40111222",
                "fecha_nacimiento": (
                    date.today() + timedelta(days=1)
                ).isoformat(),
                "parentesco": "Hijo/a",
            }
        )


def test_venta_in_rechaza_parentesco_invalido() -> None:
    datos = payload_valido()
    datos["integrantes"][0]["parentesco"] = "Primo/a"

    with pytest.raises(ValidationError):
        VentaIn.model_validate(datos)


def test_venta_in_rechaza_campos_extra() -> None:
    with pytest.raises(ValidationError):
        VentaIn.model_validate(payload_valido(precio_total=1))

    datos = payload_valido()
    datos["integrantes"][0]["email"] = "luis@example.com"

    with pytest.raises(ValidationError):
        VentaIn.model_validate(datos)


def test_venta_in_rechaza_dni_duplicado_con_el_titular() -> None:
    datos = payload_valido()
    datos["integrantes"][0]["dni"] = datos["dni_titular"]

    with pytest.raises(ValidationError, match="DNIs del grupo familiar"):
        VentaIn.model_validate(datos)


def test_venta_in_rechaza_dni_duplicado_entre_integrantes() -> None:
    datos = payload_valido()
    datos["integrantes"].append(
        {
            "nombre": "Otro",
            "apellido": "Pérez",
            "dni": "40111222",
            "fecha_nacimiento": "2012-01-01",
            "parentesco": "Nieto/a",
        }
    )

    with pytest.raises(ValidationError, match="DNIs del grupo familiar"):
        VentaIn.model_validate(datos)


def test_plan_out_desde_orm(db: Session) -> None:
    plan = Plan(
        nombre="Plan Integral Test",
        precio_titular=78_000,
        precio_adherente=52_000,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    salida = PlanOut.model_validate(plan)

    assert salida.id == plan.id
    assert salida.nombre == "Plan Integral Test"
    assert salida.precio_titular == 78_000
    assert salida.precio_adherente == 52_000
    assert salida.activo is True


def test_venta_out_desde_orm_con_plan_e_integrantes(db: Session) -> None:
    plan = Plan(
        nombre="Plan Superior Test",
        precio_titular=125_000,
        precio_adherente=85_000,
    )
    venta = Venta(
        nombre_titular="Ana",
        apellido_titular="Pérez",
        dni_titular="30111222",
        fecha_nacimiento_titular=date(1990, 5, 20),
        email="ana.perez@example.com",
        telefono="+54 11 5555-5555",
        calle="Av. Corrientes",
        altura="1234",
        piso_depto=None,
        localidad="Ciudad Autónoma de Buenos Aires",
        provincia="Ciudad Autónoma de Buenos Aires",
        codigo_postal="1043",
        plan=plan,
        precio_total=125_000,
    )
    venta.integrantes.append(
        Integrante(
            nombre="Luis",
            apellido="Pérez",
            dni="40111222",
            fecha_nacimiento=date(2010, 3, 15),
            parentesco=Parentesco.HIJO_A.value,
        )
    )
    db.add(venta)
    db.commit()
    db.refresh(venta)

    salida = VentaOut.model_validate(venta)
    serializado = salida.model_dump(mode="json")

    assert salida.estado is EstadoVenta.PENDIENTE_VERIFICACION
    assert salida.medio_pago is MedioPago.PAGO_FACIL
    assert salida.subtotal_base == 0
    assert salida.descuento_porcentaje == 0
    assert salida.plan.nombre == "Plan Superior Test"
    assert salida.integrantes[0].parentesco is Parentesco.HIJO_A
    assert salida.observaciones is None
    assert serializado["estado"] == "PENDIENTE_VERIFICACION"
    assert serializado["medio_pago"] == "PAGO_FACIL"
    assert serializado["integrantes"][0]["parentesco"] == "Hijo/a"
    assert serializado["plan"]["precio_titular"] == 125_000


def test_venta_in_medio_pago_valido_e_invalido() -> None:
    for medio in ["TARJETA_CREDITO", "CBU", "PAGO_FACIL", "COBRADOR_DOMICILIO"]:
        venta = VentaIn.model_validate(payload_valido(medio_pago=medio))
        assert venta.medio_pago == MedioPago(medio)

    with pytest.raises(ValidationError):
        VentaIn.model_validate(payload_valido(medio_pago="CRIPTOMONEDA"))


def test_venta_in_exige_medio_pago() -> None:
    datos = payload_valido()
    datos.pop("medio_pago")

    with pytest.raises(ValidationError) as excinfo:
        VentaIn.model_validate(datos)

    assert any(
        error["loc"] == ("medio_pago",) and error["type"] == "missing"
        for error in excinfo.value.errors()
    )
