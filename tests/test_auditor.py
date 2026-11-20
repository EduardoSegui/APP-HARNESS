"""Tests del Agente Auditor (F07)."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app import auditor as modulo_auditor
from ventas_app.auditor import (
    ClienteMCPStdio,
    ConfiguracionLLM,
    ErrorMCP,
    ResultadoLLM,
    aplicar_reglas,
    auditar_ventas,
    calcular_edad,
    configuracion_llm_desde_entorno,
    ejecutar_auditoria,
    generar_resumen_llm,
    main,
)
from ventas_app.database import SessionLocal
from ventas_app.mcp_server import (
    actualizar_estado_venta,
    obtener_detalle_venta,
)
from ventas_app.models import Plan, Venta

HOY = date(2026, 11, 16)


def _conteos(resultado: dict[str, Any]) -> tuple[int, int, int]:
    """Extrae procesadas, aprobadas y observadas del resultado público."""
    return (
        resultado["procesadas"],
        resultado["aprobadas"],
        resultado["observadas"],
    )


def _detalle_valido() -> dict[str, Any]:
    """Detalle completo que cumple las seis reglas de auditoría."""
    return {
        "id": 7,
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": "1990-05-20",
        "email": "ana.perez@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": None,
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": 2,
        "plan": {
            "id": 2,
            "nombre": "Plan Integral",
            "precio_titular": 78_000,
            "precio_adherente": 52_000,
            "activo": True,
        },
        "medio_pago": "PAGO_FACIL",
        "subtotal_base": 130_000,
        "descuento_porcentaje": 0,
        "ddjj_completada": True,
        "ddjj_preexistencias": False,
        "ddjj_internaciones": False,
        "ddjj_embarazo": False,
        "ddjj_medicacion_cronica": False,
        "ddjj_discapacidad": False,
        "ddjj_detalle": None,
        "regimen_afiliacion": "PARTICULAR",
        "cuil_titular": None,
        "aporte_estimado": 0,
        "precio_total": 130_000,
        "estado": "PENDIENTE_VERIFICACION",
        "observaciones": None,
        "integrantes": [
            {
                "id": 10,
                "venta_id": 7,
                "nombre": "Luis",
                "apellido": "Pérez",
                "dni": "40111001",
                "fecha_nacimiento": "2010-03-15",
                "parentesco": "Hijo/a",
            }
        ],
        "creado_en": "2026-11-16T10:00:00",
        "actualizado_en": "2026-11-16T10:00:00",
    }


def _obtener_plan_id(nombre: str) -> int:
    with SessionLocal() as db:
        plan_id = db.scalar(select(Plan.id).where(Plan.nombre == nombre))
    assert plan_id is not None, f"No existe el plan {nombre}"
    return plan_id


TARJETA_VALIDA = {
    "marca": "VISA",
    "numero": "4111111111111111",
    "titular": "Ana Pérez",
    "vencimiento": "12/99",
    "cvv": "123",
}
CBU_VALIDO = {
    "numero": "0170099220000067890123",
    "entidad": "Banco Ejemplo",
    "titular": "Ana Pérez",
    "cuil": "20123456789",
}


def _instrumento_para(medio_pago: str) -> dict[str, Any]:
    if medio_pago == "TARJETA_CREDITO":
        return {"tarjeta": dict(TARJETA_VALIDA)}
    if medio_pago == "CBU":
        return {"cbu": dict(CBU_VALIDO)}
    return {}


def _crear_venta(
    client: TestClient,
    *,
    plan: str = "Plan Integral",
    fecha_titular: str = "1990-05-20",
    cantidad_adherentes: int = 0,
    medio_pago: str = "PAGO_FACIL",
) -> dict[str, Any]:
    integrantes = [
        {
            "nombre": f"Adherente {indice}",
            "apellido": "Pérez",
            "dni": str(40_111_000 + indice),
            "fecha_nacimiento": "2010-03-15",
            "parentesco": "Hijo/a",
        }
        for indice in range(1, cantidad_adherentes + 1)
    ]
    payload = {
        "nombre_titular": "Ana",
        "apellido_titular": "Pérez",
        "dni_titular": "30111222",
        "fecha_nacimiento_titular": fecha_titular,
        "email": "ana.perez@example.com",
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": "2 B",
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": _obtener_plan_id(plan),
        "medio_pago": medio_pago,
        "ddjj": {
            "preexistencias": False,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": None,
            "declaracion_confirmada": True,
        },
        "integrantes": integrantes,
    }
    payload.update(_instrumento_para(medio_pago))
    respuesta = client.post("/api/ventas", json=payload)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


@pytest.mark.parametrize(
    ("nacimiento", "hoy", "esperada"),
    [
        (date(2008, 11, 17), date(2026, 11, 16), 17),
        (date(2008, 11, 16), date(2026, 11, 16), 18),
        (date(2008, 11, 15), date(2026, 11, 16), 18),
        (date(2000, 2, 29), date(2018, 2, 28), 17),
        (date(2000, 2, 29), date(2018, 3, 1), 18),
    ],
)
def test_calcular_edad(
    nacimiento: date,
    hoy: date,
    esperada: int,
) -> None:
    assert calcular_edad(nacimiento, hoy) == esperada


def test_detalle_valido_no_genera_observaciones() -> None:
    assert aplicar_reglas(_detalle_valido(), HOY) == []


def test_r1_titular_menor_de_18_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["fecha_nacimiento_titular"] = "2009-11-16"

    assert aplicar_reglas(detalle, HOY) == [
        "R1: El titular tiene 17 años; se requieren 18 o más."
    ]


def test_r1_titular_que_cumple_18_hoy_es_aprobado() -> None:
    detalle = _detalle_valido()
    detalle["fecha_nacimiento_titular"] = "2008-11-16"

    assert aplicar_reglas(detalle, HOY) == []


def test_r1_no_duplica_el_error_de_una_fecha_futura() -> None:
    detalle = _detalle_valido()
    detalle["fecha_nacimiento_titular"] = "2026-11-17"

    errores = aplicar_reglas(detalle, HOY)

    assert errores == [
        "R3: La fecha de nacimiento del titular no puede ser futura."
    ]


def test_r2_detecta_dni_del_titular_repetido_en_un_integrante() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"][0]["dni"] = detalle["dni_titular"]

    assert aplicar_reglas(detalle, HOY) == [
        "R2: El DNI 30111222 está repetido en el grupo familiar."
    ]


def test_r2_detecta_dni_repetido_entre_integrantes() -> None:
    detalle = _detalle_valido()
    segundo = dict(detalle["integrantes"][0])
    segundo["id"] = 11
    segundo["nombre"] = "María"
    detalle["integrantes"].append(segundo)
    detalle["subtotal_base"] = 182_000
    detalle["precio_total"] = 182_000

    assert aplicar_reglas(detalle, HOY) == [
        "R2: El DNI 40111001 está repetido en el grupo familiar."
    ]


@pytest.mark.parametrize(
    ("campo", "valor", "fragmento"),
    [
        ("nombre_titular", "", "Falta el nombre del titular"),
        ("nombre_titular", "A", "El nombre del titular no cumple"),
        ("apellido_titular", None, "Falta el apellido del titular"),
        ("dni_titular", "123", "El DNI del titular no cumple"),
        ("email", "no-es-email", "El email del titular no cumple"),
        ("telefono", "------", "al menos 6 dígitos"),
        ("calle", "", "Falta la calle"),
        ("altura", "?", "La altura no cumple"),
        ("localidad", None, "Falta la localidad"),
        ("provincia", "A", "La provincia no cumple"),
    ],
)
def test_r3_valida_campos_obligatorios_del_titular(
    campo: str,
    valor: Any,
    fragmento: str,
) -> None:
    detalle = _detalle_valido()
    detalle[campo] = valor

    errores = aplicar_reglas(detalle, HOY)

    assert any(fragmento in error for error in errores)


@pytest.mark.parametrize(
    ("valor", "fragmento"),
    [
        ("", "Falta la fecha de nacimiento del titular"),
        ("20/05/1990", "La fecha de nacimiento del titular no es válida"),
        (
            "2026-11-17",
            "La fecha de nacimiento del titular no puede ser futura",
        ),
    ],
)
def test_r3_valida_fecha_del_titular(
    valor: str,
    fragmento: str,
) -> None:
    detalle = _detalle_valido()
    detalle["fecha_nacimiento_titular"] = valor

    errores = aplicar_reglas(detalle, HOY)

    assert any(fragmento in error for error in errores)


@pytest.mark.parametrize(
    ("campo", "valor", "fragmento"),
    [
        ("nombre", "", "Falta el nombre del integrante 1"),
        (
            "apellido",
            "A",
            "El apellido del integrante 1 no cumple el formato",
        ),
        ("dni", "123", "El DNI del integrante 1 no cumple el formato"),
        (
            "fecha_nacimiento",
            "2010-99-99",
            "La fecha de nacimiento del integrante 1 no es válida",
        ),
        (
            "parentesco",
            "Primo",
            "El parentesco del integrante 1 no es válido",
        ),
    ],
)
def test_r3_valida_datos_del_integrante(
    campo: str,
    valor: str,
    fragmento: str,
) -> None:
    detalle = _detalle_valido()
    detalle["integrantes"][0][campo] = valor

    errores = aplicar_reglas(detalle, HOY)

    assert any(fragmento in error for error in errores)


def test_r3_integrante_con_fecha_futura() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"][0]["fecha_nacimiento"] = "2026-11-17"

    errores = aplicar_reglas(detalle, HOY)

    assert errores == [
        "R3: La fecha de nacimiento del integrante 1 no puede ser futura."
    ]


def test_r3_y_r6_informan_lista_de_integrantes_invalida() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"] = None

    errores = aplicar_reglas(detalle, HOY)

    assert "R3: La lista de integrantes no es válida." in errores
    assert "R6: La lista de integrantes de la venta no es válida." in errores


def test_r3_integrante_que_no_es_objeto() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"] = ["Luis"]

    errores = aplicar_reglas(detalle, HOY)

    assert "R3: El integrante 1 no tiene datos válidos." in errores
    assert "R6: El integrante 1 no está asociado a la venta." in errores


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("C1425", "R4: El código postal 'C1425' no tiene el formato de 4 dígitos."),
        ("104", "R4: El código postal '104' no tiene el formato de 4 dígitos."),
        (
            "10433",
            "R4: El código postal '10433' no tiene el formato de 4 dígitos.",
        ),
        ("", "R4: Falta el código postal."),
        (None, "R4: Falta el código postal."),
    ],
)
def test_r4_codigo_postal_invalido(
    valor: Any,
    esperado: str,
) -> None:
    detalle = _detalle_valido()
    detalle["codigo_postal"] = valor

    assert aplicar_reglas(detalle, HOY) == [esperado]


def test_r5_plan_inactivo() -> None:
    detalle = _detalle_valido()
    detalle["plan"]["activo"] = False

    assert aplicar_reglas(detalle, HOY) == [
        "R5: El plan seleccionado no existe o está inactivo."
    ]


def test_r5_plan_inexistente() -> None:
    detalle = _detalle_valido()
    detalle["plan"] = None

    assert aplicar_reglas(detalle, HOY) == [
        "R5: El plan seleccionado no existe."
    ]


def test_r5_precio_total_no_coincide() -> None:
    detalle = _detalle_valido()
    detalle["precio_total"] = 1

    errores = aplicar_reglas(detalle, HOY)

    assert len(errores) == 1
    assert errores[0].startswith("R5: El precio total persistido (1)")
    assert "no coincide con el cálculo vigente (130000)" in errores[0]


def test_r5_precios_del_plan_invalidos() -> None:
    detalle = _detalle_valido()
    detalle["plan"]["precio_adherente"] = -1

    assert aplicar_reglas(detalle, HOY) == [
        "R5: Los precios del plan no son válidos."
    ]


def test_r5_sin_integrantes_usa_solo_el_precio_del_titular() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"] = []
    detalle["subtotal_base"] = 78_000
    detalle["precio_total"] = 78_000

    assert aplicar_reglas(detalle, HOY) == []


def test_r5_con_descuento_tarjeta_credito_valido() -> None:
    detalle = _detalle_valido()
    # 78_000 + 52_000 = 130_000 -> 30% desc = 39_000 -> 91_000
    detalle["medio_pago"] = "TARJETA_CREDITO"
    detalle["descuento_porcentaje"] = 30
    detalle["pago_titular"] = "Ana Pérez"
    detalle["pago_marca_entidad"] = "VISA"
    detalle["pago_ultimos_4"] = "1111"
    detalle["pago_vencimiento"] = "12/99"
    detalle["precio_total"] = 91_000

    assert aplicar_reglas(detalle, HOY) == []


def test_r5_con_descuento_tarjeta_credito_invalido() -> None:
    detalle = _detalle_valido()
    detalle["medio_pago"] = "TARJETA_CREDITO"
    detalle["descuento_porcentaje"] = 30
    detalle["pago_titular"] = "Ana Pérez"
    detalle["pago_marca_entidad"] = "VISA"
    detalle["pago_ultimos_4"] = "1111"
    detalle["pago_vencimiento"] = "12/99"
    detalle["precio_total"] = 130_000  # No aplicó el descuento

    errores = aplicar_reglas(detalle, HOY)
    assert any(
        "R5: El precio total persistido (130000) no coincide con el "
        "cálculo vigente (91000)" in e
        for e in errores
    )


def test_r5_con_descuento_cbu_valido() -> None:
    detalle = _detalle_valido()
    # 78_000 + 52_000 = 130_000 -> 20% desc = 26_000 -> 104_000
    detalle["medio_pago"] = "CBU"
    detalle["descuento_porcentaje"] = 20
    detalle["pago_titular"] = "Ana Pérez"
    detalle["pago_marca_entidad"] = "Banco Ejemplo"
    detalle["pago_ultimos_4"] = "0123"
    detalle["pago_cuil"] = "20123456789"
    detalle["precio_total"] = 104_000

    assert aplicar_reglas(detalle, HOY) == []


def test_r5_medio_pago_no_reconocido() -> None:
    detalle = _detalle_valido()
    detalle["medio_pago"] = "CHEQUE"

    assert aplicar_reglas(detalle, HOY) == [
        "R5: El medio de pago 'CHEQUE' no es válido."
    ]


def test_r5_sin_medio_pago_es_observado() -> None:
    detalle = _detalle_valido()
    del detalle["medio_pago"]

    assert aplicar_reglas(detalle, HOY) == ["R5: Falta el medio de pago."]


def test_r5_tarjeta_sin_datos_enmascarados_es_observada() -> None:
    detalle = _detalle_valido()
    detalle["medio_pago"] = "TARJETA_CREDITO"
    detalle["descuento_porcentaje"] = 30
    detalle["precio_total"] = 91_000

    assert aplicar_reglas(detalle, HOY) == [
        "R5: Faltan los datos enmascarados de la tarjeta de crédito."
    ]


def test_r5_cbu_con_cuil_invalido_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["medio_pago"] = "CBU"
    detalle["descuento_porcentaje"] = 20
    detalle["pago_titular"] = "Ana Pérez"
    detalle["pago_marca_entidad"] = "Banco Ejemplo"
    detalle["pago_ultimos_4"] = "0123"
    detalle["pago_cuil"] = "123"
    detalle["precio_total"] = 104_000

    assert aplicar_reglas(detalle, HOY) == [
        "R5: El CUIL del CBU debe tener 11 dígitos."
    ]


def test_r5_subtotal_base_adulterado_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["subtotal_base"] = 100_000

    errores = aplicar_reglas(detalle, HOY)

    assert any(
        "R5: El subtotal base persistido (100000) no coincide con el "
        "cálculo vigente (130000)" in error
        for error in errores
    )


def test_r5_descuento_persistido_adulterado_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["medio_pago"] = "TARJETA_CREDITO"
    detalle["descuento_porcentaje"] = 0
    detalle["precio_total"] = 91_000

    errores = aplicar_reglas(detalle, HOY)

    assert any(
        "R5: El descuento persistido (0%) no coincide con el medio de "
        "pago 'TARJETA_CREDITO' (30%)" in error
        for error in errores
    )


def test_r7_ddjj_completa_sin_riesgo_no_observa() -> None:
    assert aplicar_reglas(_detalle_valido(), HOY) == []


def test_r7_preexistencia_requiere_revision_medica() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_preexistencias"] = True
    detalle["ddjj_detalle"] = "Hipertensión controlada."

    assert aplicar_reglas(detalle, HOY) == [
        "R7: La DDJJ declara preexistencias, internaciones o discapacidad; "
        "requiere revisión médica."
    ]


def test_r7_internacion_requiere_revision_medica() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_internaciones"] = True
    detalle["ddjj_detalle"] = "Internación por cirugía en 2025."

    assert aplicar_reglas(detalle, HOY) == [
        "R7: La DDJJ declara preexistencias, internaciones o discapacidad; "
        "requiere revisión médica."
    ]


def test_r7_discapacidad_requiere_revision_medica() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_discapacidad"] = True
    detalle["ddjj_detalle"] = "Certificado vigente."

    assert aplicar_reglas(detalle, HOY) == [
        "R7: La DDJJ declara preexistencias, internaciones o discapacidad; "
        "requiere revisión médica."
    ]


def test_r7_indicador_sin_detalle_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_embarazo"] = True
    detalle["ddjj_detalle"] = None

    assert aplicar_reglas(detalle, HOY) == [
        "R7: La DDJJ de salud requiere detalle para los indicadores declarados."
    ]


def test_r7_embarazo_con_detalle_no_requiere_revision() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_embarazo"] = True
    detalle["ddjj_detalle"] = "Embarazo de 12 semanas."

    assert aplicar_reglas(detalle, HOY) == []


def test_r7_venta_historica_sin_ddjj_es_observada() -> None:
    detalle = _detalle_valido()
    detalle["ddjj_completada"] = False

    assert aplicar_reglas(detalle, HOY) == [
        "R7: Falta completar la declaración jurada de salud."
    ]


def test_r8_particular_con_aporte_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["aporte_estimado"] = 10_000
    detalle["precio_total"] = 120_000

    assert aplicar_reglas(detalle, HOY) == [
        "R8: El régimen PARTICULAR no admite aporte estimado."
    ]


def test_r8_desregulado_sin_cuil_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "RELACION_DEPENDENCIA"

    assert aplicar_reglas(detalle, HOY) == [
        "R8: El régimen RELACION_DEPENDENCIA exige un CUIL de 11 dígitos "
        "para el titular."
    ]


def test_r8_cuil_invalido_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "MONOTRIBUTO"
    detalle["cuil_titular"] = "123"

    assert aplicar_reglas(detalle, HOY) == [
        "R8: El régimen MONOTRIBUTO exige un CUIL de 11 dígitos para el "
        "titular."
    ]


def test_r8_aporte_mayor_a_la_base_es_observado() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "RELACION_DEPENDENCIA"
    detalle["cuil_titular"] = "20123456789"
    detalle["aporte_estimado"] = 130_001
    detalle["precio_total"] = 0

    assert aplicar_reglas(detalle, HOY) == [
        "R8: El aporte estimado no puede superar la base bonificada."
    ]


def test_r8_aporte_igual_a_la_base_permite_total_cero() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "MONOTRIBUTO"
    detalle["cuil_titular"] = "20123456789"
    detalle["aporte_estimado"] = 130_000
    detalle["precio_total"] = 0

    assert aplicar_reglas(detalle, HOY) == []


def test_r8_desregulado_valido() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "RELACION_DEPENDENCIA"
    detalle["cuil_titular"] = "20123456789"
    detalle["aporte_estimado"] = 20_000
    detalle["precio_total"] = 110_000

    assert aplicar_reglas(detalle, HOY) == []


def test_r8_regimen_invalido() -> None:
    detalle = _detalle_valido()
    detalle["regimen_afiliacion"] = "INEXISTENTE"

    assert aplicar_reglas(detalle, HOY) == [
        "R8: El régimen de afiliación no es válido."
    ]


def test_r6_integrante_de_otra_venta() -> None:
    detalle = _detalle_valido()
    detalle["integrantes"][0]["venta_id"] = 99

    assert aplicar_reglas(detalle, HOY) == [
        "R6: El integrante 1 (DNI 40111001) no pertenece a la venta 7."
    ]


def test_r6_integrante_sin_venta_asociada() -> None:
    detalle = _detalle_valido()
    del detalle["integrantes"][0]["venta_id"]

    assert aplicar_reglas(detalle, HOY) == [
        "R6: El integrante 1 no está asociado a la venta."
    ]


def test_r6_venta_sin_titular() -> None:
    detalle = _detalle_valido()
    detalle["nombre_titular"] = ""
    detalle["apellido_titular"] = ""
    detalle["dni_titular"] = ""

    errores = aplicar_reglas(detalle, HOY)

    assert "R6: La venta no posee un titular." in errores
    assert any(
        error.startswith("R3: Falta") for error in errores
    )


def test_r6_venta_sin_identificador() -> None:
    detalle = _detalle_valido()
    detalle["id"] = 0

    assert aplicar_reglas(detalle, HOY) == [
        "R6: La venta no tiene un identificador válido."
    ]


def test_auditoria_aprueba_venta_valida(client: TestClient) -> None:
    creada = _crear_venta(client)

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 1, 0)
    assert set(resultado) == {
        "procesadas",
        "aprobadas",
        "observadas",
        "resumen_llm",
        "llm_ok",
        "advertencia",
        "traza_mcp",
    }
    assert [paso["herramienta"] for paso in resultado["traza_mcp"]] == [
        "listar_ventas_pendientes",
        "obtener_detalle_venta",
        "actualizar_estado_venta",
    ]
    assert resultado["traza_mcp"][1]["argumentos"] == {
        "venta_id": creada["id"]
    }
    assert resultado["traza_mcp"][2]["argumentos"] == {
        "venta_id": creada["id"],
        "estado": "APROBADA",
        "observaciones": None,
    }
    assert resultado["llm_ok"] is False
    assert "no configurado" in (resultado["advertencia"] or "")

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.observaciones is None


def test_auditoria_observa_titular_menor(client: TestClient) -> None:
    creada = _crear_venta(client, fecha_titular="2009-11-16")

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 0, 1)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert venta.observaciones is not None
        assert "R1: El titular tiene 17 años; se requieren 18 o más." in (
            venta.observaciones
        )


def test_auditoria_es_idempotente(client: TestClient) -> None:
    creada = _crear_venta(client)

    primera = ejecutar_auditoria(hoy=HOY)
    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        actualizado_en = venta.actualizado_en
        assert venta.estado == "APROBADA"

    segunda = ejecutar_auditoria(hoy=HOY)

    assert _conteos(primera) == (1, 1, 0)
    assert _conteos(segunda) == (0, 0, 0)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.actualizado_en == actualizado_en


def test_auditoria_no_modifica_ventas_ya_procesadas(
    client: TestClient,
) -> None:
    procesada = _crear_venta(client)
    pendiente = _crear_venta(client)
    actualizar_estado_venta(
        procesada["id"],
        "OBSERVADA",
        "R2: Observación previa.",
    )

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 1, 0)

    with SessionLocal() as db:
        primera = db.get(Venta, procesada["id"])
        segunda = db.get(Venta, pendiente["id"])
        assert primera is not None
        assert segunda is not None
        assert primera.estado == "OBSERVADA"
        assert primera.observaciones == "R2: Observación previa."
        assert segunda.estado == "APROBADA"


def test_auditoria_informa_plan_inactivo(client: TestClient) -> None:
    creada = _crear_venta(client, plan="Plan Superior")

    with SessionLocal() as db:
        plan = db.scalar(select(Plan).where(Plan.nombre == "Plan Superior"))
        assert plan is not None
        plan.activo = False
        db.commit()

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 0, 1)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert "R5: El plan seleccionado no existe o está inactivo." in (
            venta.observaciones or ""
        )


def test_auditoria_informa_codigo_postal_invalido(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        venta.codigo_postal = "C1425"
        db.commit()

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 0, 1)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert (
            "R4: El código postal 'C1425' no tiene el formato de 4 dígitos."
            in (venta.observaciones or "")
        )


def test_auditoria_informa_precio_incorrecto(client: TestClient) -> None:
    creada = _crear_venta(client)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        venta.precio_total = 1
        db.commit()

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 0, 1)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert "R5: El precio total persistido (1) no coincide" in (
            venta.observaciones or ""
        )


def test_auditoria_informa_datos_invalidos(client: TestClient) -> None:
    creada = _crear_venta(client)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        venta.email = ""
        db.commit()

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 0, 1)

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "OBSERVADA"
        assert "R3: Falta el email del titular." in (
            venta.observaciones or ""
        )


def test_auditoria_sin_ventas_pendientes() -> None:
    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (0, 0, 0)
    assert resultado["resumen_llm"] is None
    assert resultado["llm_ok"] is False
    assert resultado["advertencia"] == "No hay ventas pendientes para auditar."
    assert [paso["herramienta"] for paso in resultado["traza_mcp"]] == [
        "listar_ventas_pendientes"
    ]


def test_detalle_mcp_incluye_venta_id_de_integrantes(
    client: TestClient,
) -> None:
    creada = _crear_venta(client, cantidad_adherentes=1)

    detalle = obtener_detalle_venta(creada["id"])

    assert detalle["integrantes"][0]["venta_id"] == creada["id"]


def test_main_imprime_resumen(
    client: TestClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    creada = _crear_venta(client)

    main()

    salida = capsys.readouterr().out
    assert (
        "Resumen de auditoría: 1 procesadas, 1 aprobadas, 0 observadas."
        in salida
    )

    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"


def test_auditor_no_accede_directo_a_la_base() -> None:
    fuente = Path(modulo_auditor.__file__).read_text(encoding="utf-8")

    assert "SessionLocal" not in fuente
    assert "sqlalchemy" not in fuente.lower()
    assert "from ventas_app.models" not in fuente
    assert "from mcp.client.stdio import stdio_client" in fuente
    assert "OPENAI_API_KEY" in fuente
    assert "OPENAI_BASE_URL" in fuente


def test_cliente_mcp_real_invoca_las_tres_herramientas(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)

    async def flujo() -> tuple[
        list[dict[str, Any]],
        dict[str, Any],
        dict[str, Any],
        list[dict[str, Any]],
    ]:
        async with ClienteMCPStdio() as cliente_mcp:
            pendientes = await cliente_mcp.listar_pendientes()
            detalle = await cliente_mcp.obtener_detalle(creada["id"])
            actualizada = await cliente_mcp.actualizar_estado(
                creada["id"],
                "APROBADA",
            )
            pendientes_finales = await cliente_mcp.listar_pendientes()
        return pendientes, detalle, actualizada, pendientes_finales

    pendientes, detalle, actualizada, pendientes_finales = asyncio.run(
        flujo()
    )

    assert [venta["id"] for venta in pendientes] == [creada["id"]]
    assert detalle["medio_pago"] == "PAGO_FACIL"
    assert detalle["subtotal_base"] == 78_000
    assert detalle["descuento_porcentaje"] == 0
    assert detalle["estado"] == "PENDIENTE_VERIFICACION"
    assert actualizada["estado"] == "APROBADA"
    assert actualizada["observaciones"] is None
    assert pendientes_finales == []


def test_cliente_mcp_real_audita_venta_con_descuento(
    client: TestClient,
) -> None:
    creada = _crear_venta(
        client,
        plan="Plan Integral",
        cantidad_adherentes=1,
        medio_pago="TARJETA_CREDITO",
    )

    resultado = ejecutar_auditoria(hoy=HOY)

    assert _conteos(resultado) == (1, 1, 0)
    with SessionLocal() as db:
        venta = db.get(Venta, creada["id"])
        assert venta is not None
        assert venta.estado == "APROBADA"
        assert venta.observaciones is None


def test_cliente_mcp_real_registra_traza_ordenada(
    client: TestClient,
) -> None:
    creada = _crear_venta(client)

    async def flujo() -> list[dict[str, Any]]:
        async with ClienteMCPStdio() as cliente_mcp:
            await cliente_mcp.listar_pendientes()
            await cliente_mcp.obtener_detalle(creada["id"])
            await cliente_mcp.actualizar_estado(
                creada["id"],
                "OBSERVADA",
                "R2: Observación de prueba.",
            )
            return cliente_mcp.traza_mcp

    traza = asyncio.run(flujo())

    assert [paso["herramienta"] for paso in traza] == [
        "listar_ventas_pendientes",
        "obtener_detalle_venta",
        "actualizar_estado_venta",
    ]
    assert traza[2]["argumentos"] == {
        "venta_id": creada["id"],
        "estado": "OBSERVADA",
        "observaciones": "R2: Observación de prueba.",
    }
    assert all(paso["estado"] == "ok" for paso in traza)


def test_cliente_mcp_real_registra_error_en_traza() -> None:
    async def flujo() -> list[dict[str, Any]]:
        async with ClienteMCPStdio() as cliente_mcp:
            with pytest.raises(ErrorMCP, match="no existe"):
                await cliente_mcp.obtener_detalle(999999)
            return cliente_mcp.traza_mcp

    traza = asyncio.run(flujo())

    assert traza == [
        {
            "herramienta": "obtener_detalle_venta",
            "argumentos": {"venta_id": 999999},
            "estado": "error",
        }
    ]


def test_cliente_mcp_real_propaga_error_limpio() -> None:
    async def flujo() -> None:
        async with ClienteMCPStdio() as cliente_mcp:
            await cliente_mcp.obtener_detalle(999999)

    with pytest.raises(ErrorMCP, match="no existe"):
        asyncio.run(flujo())


class _ClienteMCPFalso:
    def __init__(self, detalle: dict[str, Any]) -> None:
        self.detalle = detalle
        self.actualizaciones: list[tuple[int, str, str | None]] = []
        self.traza_mcp: list[dict[str, Any]] = []

    async def listar_pendientes(self) -> list[dict[str, Any]]:
        self.traza_mcp.append(
            {
                "herramienta": "listar_ventas_pendientes",
                "argumentos": {},
                "estado": "ok",
            }
        )
        return [{"id": self.detalle["id"]}]

    async def obtener_detalle(self, venta_id: int) -> dict[str, Any]:
        assert venta_id == self.detalle["id"]
        self.traza_mcp.append(
            {
                "herramienta": "obtener_detalle_venta",
                "argumentos": {"venta_id": venta_id},
                "estado": "ok",
            }
        )
        return dict(self.detalle)

    async def actualizar_estado(
        self,
        venta_id: int,
        estado: str,
        observaciones: str | None = None,
    ) -> dict[str, Any]:
        self.actualizaciones.append((venta_id, estado, observaciones))
        self.traza_mcp.append(
            {
                "herramienta": "actualizar_estado_venta",
                "argumentos": {
                    "venta_id": venta_id,
                    "estado": estado,
                    "observaciones": observaciones,
                },
                "estado": "ok",
            }
        )
        return {"id": venta_id, "estado": estado}


def test_auditar_ventas_usa_interfaz_mcp_y_resumen_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente = _ClienteMCPFalso(_detalle_valido())
    monkeypatch.setattr(
        modulo_auditor,
        "generar_resumen_llm",
        lambda aprobadas, observadas, errores: ResultadoLLM(
            resumen="Resumen narrativo.",
            ok=True,
        ),
    )

    resultado = asyncio.run(auditar_ventas(cliente, HOY))

    assert _conteos(resultado) == (1, 1, 0)
    assert resultado["resumen_llm"] == "Resumen narrativo."
    assert resultado["llm_ok"] is True
    assert resultado["advertencia"] is None
    assert [paso["herramienta"] for paso in resultado["traza_mcp"]] == [
        "listar_ventas_pendientes",
        "obtener_detalle_venta",
        "actualizar_estado_venta",
    ]
    assert cliente.actualizaciones == [(7, "APROBADA", None)]


def test_configuracion_llm_sin_api_key() -> None:
    assert configuracion_llm_desde_entorno({}) is None
    assert configuracion_llm_desde_entorno({"OPENAI_API_KEY": "   "}) is None


def test_configuracion_llm_para_ollama_y_qwen() -> None:
    config = configuracion_llm_desde_entorno(
        {
            "OPENAI_API_KEY": "clave-local",
            "OPENAI_BASE_URL": "http://localhost:11434/v1/",
            "OPENAI_MODEL": "qwen2.5",
            "OPENAI_TIMEOUT": "2.5",
        }
    )

    assert config == ConfiguracionLLM(
        api_key="clave-local",
        base_url="http://localhost:11434/v1/",
        modelo="qwen2.5",
        timeout=2.5,
    )


@pytest.mark.parametrize("timeout", ["", "no-es-numero", "0", "-3"])
def test_configuracion_llm_timeout_invalido_usa_default(
    timeout: str,
) -> None:
    config = configuracion_llm_desde_entorno(
        {
            "OPENAI_API_KEY": "clave",
            "OPENAI_TIMEOUT": timeout,
        }
    )

    assert config is not None
    assert config.timeout == 15.0


def test_generar_resumen_llm_usa_base_url_modelo_y_credenciales() -> None:
    pedidos: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Resumen del modelo."}}]},
        )

    config = ConfiguracionLLM(
        api_key="sk-prueba",
        base_url="http://localhost:11434/v1/",
        modelo="qwen2.5",
        timeout=1.5,
    )

    resumen = generar_resumen_llm(
        2,
        1,
        [
            "Venta #2: R1: El titular tiene 17 años.",
            "Venta #2: R2: El DNI 30111222 está repetido.",
        ],
        config=config,
        transport=httpx.MockTransport(responder),
    )

    assert resumen.resumen == "Resumen del modelo."
    assert resumen.ok is True
    assert resumen.advertencia is None
    assert len(pedidos) == 1
    assert str(pedidos[0].url) == (
        "http://localhost:11434/v1/chat/completions"
    )
    assert pedidos[0].headers["Authorization"] == "Bearer sk-prueba"
    carga = json.loads(pedidos[0].content)
    assert carga["model"] == "qwen2.5"
    assert "2 aprobadas" in carga["messages"][1]["content"]
    assert "1 observadas" in carga["messages"][1]["content"]
    carga_como_texto = json.dumps(carga, ensure_ascii=False)
    assert "30111222" not in carga_como_texto
    assert "***" in carga_como_texto


def test_generar_resumen_llm_timeout_devuelve_advertencia() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    resultado = generar_resumen_llm(
        1,
        0,
        [],
        config=ConfiguracionLLM(api_key="sk", timeout=0.1),
        transport=httpx.MockTransport(responder),
    )

    assert resultado.resumen is None
    assert resultado.ok is False
    assert "resumen del LLM" in (resultado.advertencia or "")


def test_generar_resumen_llm_error_http_devuelve_advertencia() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "servicio no disponible"})

    resultado = generar_resumen_llm(
        0,
        1,
        ["Venta #1: R4: Falta el código postal."],
        config=ConfiguracionLLM(api_key="sk", timeout=1.0),
        transport=httpx.MockTransport(responder),
    )

    assert resultado.resumen is None
    assert resultado.ok is False
    assert "resumen del LLM" in (resultado.advertencia or "")


def test_generar_resumen_llm_respuesta_invalida_devuelve_advertencia() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    resultado = generar_resumen_llm(
        1,
        0,
        [],
        config=ConfiguracionLLM(api_key="sk", timeout=1.0),
        transport=httpx.MockTransport(responder),
    )

    assert resultado.resumen is None
    assert resultado.ok is False
    assert "resumen del LLM" in (resultado.advertencia or "")


def test_generar_resumen_llm_sin_configuracion_no_llama_a_la_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resultado = generar_resumen_llm(1, 0, [])

    assert resultado.resumen is None
    assert resultado.ok is False
    assert "no configurado" in (resultado.advertencia or "")


def test_main_imprime_resumen_llm(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        modulo_auditor,
        "ejecutar_auditoria",
        lambda: {
            "procesadas": 3,
            "aprobadas": 2,
            "observadas": 1,
            "resumen_llm": "Resumen narrativo del LLM.",
            "llm_ok": True,
            "advertencia": None,
            "traza_mcp": [],
        },
    )

    codigo = main()

    salida = capsys.readouterr().out
    assert codigo == 0
    assert (
        "Resumen de auditoría: 3 procesadas, 2 aprobadas, 1 observadas."
        in salida
    )
    assert "Resumen narrativo del LLM." in salida


def test_main_maneja_error_mcp_sin_traza(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fallar() -> dict[str, Any]:
        raise ErrorMCP("servidor no disponible")

    monkeypatch.setattr(modulo_auditor, "ejecutar_auditoria", fallar)

    codigo = main()

    capturado = capsys.readouterr()
    assert codigo == 1
    assert capturado.out == ""
    assert "Error al ejecutar la auditoría MCP" in capturado.err
    assert "servidor no disponible" in capturado.err
    assert "Traceback" not in capturado.err
