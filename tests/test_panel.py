"""Tests del panel HTML de ventas (F05)."""

from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from ventas_app.database import SessionLocal
from ventas_app.models import Plan, Venta
from ventas_app.services.estados import cambiar_estado_venta


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
    cantidad_adherentes: int = 0,
    medio_pago: str = "PAGO_FACIL",
    ddjj: dict[str, Any] | None = None,
    regimen_afiliacion: str = "PARTICULAR",
    cuil_titular: str | None = None,
    aporte_estimado: int = 0,
    nombre_titular: str = "Ana",
    apellido_titular: str = "Pérez",
    dni_titular: str = "30111222",
    email: str = "ana.perez@example.com",
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
        "nombre_titular": nombre_titular,
        "apellido_titular": apellido_titular,
        "dni_titular": dni_titular,
        "fecha_nacimiento_titular": "1990-05-20",
        "email": email,
        "telefono": "+54 11 5555-5555",
        "calle": "Av. Corrientes",
        "altura": "1234",
        "piso_depto": "2 B",
        "localidad": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "codigo_postal": "1043",
        "plan_id": _obtener_plan_id(plan),
        "medio_pago": medio_pago,
        "ddjj": ddjj
        or {
            "preexistencias": False,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": None,
            "declaracion_confirmada": True,
        },
        "integrantes": integrantes,
        "regimen_afiliacion": regimen_afiliacion,
        "cuil_titular": cuil_titular,
        "aporte_estimado": aporte_estimado,
    }
    payload.update(_instrumento_para(medio_pago))

    respuesta = client.post("/api/ventas", json=payload)

    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _cambiar_estado(venta_id: int, estado: str) -> None:
    with SessionLocal() as db:
        venta = db.get(Venta, venta_id)
        assert venta is not None
        venta.estado = estado
        db.commit()


def test_panel_sin_ventas_muestra_estado_vacio(client: TestClient) -> None:
    respuesta = client.get("/ventas")

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]

    html = respuesta.text

    assert "Panel de ventas" in html
    assert "Todavía no hay ventas registradas" in html
    assert "Cargar primera venta" in html
    assert 'id="btn-auditar"' in html
    assert 'id="panel-auditoria"' in html
    assert 'id="traza-mcp-body"' in html
    assert "data-cantidad-integrantes" not in html


def test_panel_lista_venta_con_todos_los_datos(client: TestClient) -> None:
    venta = _crear_venta(client, plan="Plan Integral", cantidad_adherentes=2)

    html = client.get("/ventas").text

    assert 'class="min-w-full' in html
    assert f'id="venta-{venta["id"]}"' in html
    assert "Ana Pérez" in html
    assert "Plan Integral" in html
    assert 'data-cantidad-integrantes="2"' in html
    assert "$182.000" in html
    assert "Medio de pago" in html
    assert "Pago Fácil / Oficinas" in html
    assert "DDJJ" in html
    assert "Completa" in html
    assert 'data-estado="PENDIENTE_VERIFICACION"' in html
    assert 'class="stamp"' in html
    assert ">Pendiente<" in html
    assert "Observaciones" in html
    assert "data-observaciones" in html
    assert "Pendiente de auditoría" in html
    assert "1 resultado · página 1 de 1." in html


def test_panel_muestra_medio_de_pago_y_total_bonificado(
    client: TestClient,
) -> None:
    _crear_venta(
        client,
        plan="Plan Integral",
        cantidad_adherentes=1,
        medio_pago="TARJETA_CREDITO",
    )

    html = client.get("/ventas").text

    assert "Medio de pago" in html
    assert "Tarjeta de crédito" in html
    assert "30% desc." in html
    assert "VISA •••• 1111 · 12/99" in html
    assert "$91.000" in html


def test_panel_muestra_ddjj_completa_y_revision_medica(
    client: TestClient,
) -> None:
    _crear_venta(client)
    _crear_venta(
        client,
        ddjj={
            "preexistencias": True,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": "Hipertensión controlada.",
            "declaracion_confirmada": True,
        },
    )

    html = client.get("/ventas").text

    assert "Completa" in html
    assert "Revisión médica" in html
    assert "Hipertensión controlada." not in html


def test_panel_muestra_regimen_y_aporte(client: TestClient) -> None:
    _crear_venta(
        client,
        regimen_afiliacion="RELACION_DEPENDENCIA",
        cuil_titular="20123456789",
        aporte_estimado=20_000,
    )

    html = client.get("/ventas").text

    assert "Rel. dependencia" in html
    assert "Aporte $20.000" in html
    assert "$58.000" in html


def test_panel_busca_por_dni_y_apellido(client: TestClient) -> None:
    _crear_venta(client, nombre_titular="Ana", apellido_titular="Pérez")
    _crear_venta(
        client,
        nombre_titular="Beto",
        apellido_titular="Gómez",
        dni_titular="30111223",
        email="beto@example.com",
    )

    por_dni = client.get("/ventas?q=30111223").text
    assert "Beto Gómez" in por_dni
    assert "Ana Pérez" not in por_dni
    assert "1 resultado" in por_dni

    por_apellido = client.get("/ventas?q=Gómez").text
    assert "Beto Gómez" in por_apellido
    assert "Ana Pérez" not in por_apellido


def test_panel_filtra_combinando_estado_plan_medio_y_regimen(
    client: TestClient,
) -> None:
    _crear_venta(client, nombre_titular="Ana", apellido_titular="Pérez")
    beto = _crear_venta(
        client,
        nombre_titular="Beto",
        apellido_titular="Gómez",
        dni_titular="30111223",
        email="beto@example.com",
        plan="Plan Esencial",
        medio_pago="CBU",
        regimen_afiliacion="RELACION_DEPENDENCIA",
        cuil_titular="20123456789",
        aporte_estimado=5_000,
    )
    _cambiar_estado(beto["id"], "APROBADA")
    plan_id = _obtener_plan_id("Plan Esencial")

    html = client.get(
        "/ventas",
        params={
            "estado": "APROBADA",
            "plan_id": plan_id,
            "medio_pago": "CBU",
            "regimen_afiliacion": "RELACION_DEPENDENCIA",
        },
    ).text

    assert "Beto Gómez" in html
    assert "Ana Pérez" not in html
    assert "1 resultado" in html


def test_panel_acepta_filtros_vacios(client: TestClient) -> None:
    _crear_venta(client)

    respuesta = client.get(
        "/ventas",
        params={
            "q": "",
            "estado": "",
            "plan_id": "",
            "medio_pago": "",
            "regimen_afiliacion": "",
        },
    )

    assert respuesta.status_code == 200
    assert "Ana Pérez" in respuesta.text


def test_panel_sin_resultados_permite_limpiar_filtros(
    client: TestClient,
) -> None:
    _crear_venta(client)

    html = client.get("/ventas?q=NO-EXISTE").text

    assert "No hay ventas que coincidan con los filtros" in html
    assert "Limpiar filtros" in html
    assert "Todavía no hay ventas registradas" not in html


def test_panel_pagina_resultados(client: TestClient) -> None:
    for indice in range(21):
        _crear_venta(
            client,
            nombre_titular=f"Persona {indice}",
            apellido_titular="Prueba",
            dni_titular=f"30{100000 + indice:06d}",
            email=f"persona{indice}@example.com",
        )

    primera = client.get("/ventas").text
    segunda = client.get("/ventas?pagina=2").text

    assert "21 resultados · página 1 de 2." in primera
    assert "Siguiente" in primera
    assert "21 resultados · página 2 de 2." in segunda
    assert "Anterior" in segunda


def test_api_ventas_filtra_y_pagina(client: TestClient) -> None:
    _crear_venta(client, nombre_titular="Ana", apellido_titular="Pérez")
    _crear_venta(
        client,
        nombre_titular="Beto",
        apellido_titular="Gómez",
        dni_titular="30111223",
        email="beto@example.com",
    )

    respuesta = client.get("/api/ventas", params={"q": "Gómez"})

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["total"] == 1
    assert datos["pagina"] == 1
    assert datos["items"][0]["nombre_titular"] == "Beto"

    invalido = client.get("/api/ventas", params={"estado": "INEXISTENTE"})
    assert invalido.status_code == 422


def test_panel_muestra_acciones_de_edicion_y_lectura(
    client: TestClient,
) -> None:
    venta = _crear_venta(client)
    html_pendiente = client.get("/ventas").text

    assert "Acciones" in html_pendiente
    assert "Editar legajo" in html_pendiente
    assert f"/ventas/{venta['id']}/editar" in html_pendiente

    _cambiar_estado(venta["id"], "APROBADA")
    html_aprobada = client.get("/ventas").text

    assert "Ver legajo" in html_aprobada
    assert f"/ventas/{venta['id']}" in html_aprobada
    assert "Credencial" in html_aprobada
    assert f"/ventas/{venta['id']}/credencial" in html_aprobada
    assert "Editar legajo" not in html_aprobada


def test_editar_venta_precarga_el_wizard(client: TestClient) -> None:
    venta = _crear_venta(client, plan="Plan Integral", cantidad_adherentes=1)

    respuesta = client.get(f"/ventas/{venta['id']}/editar")

    assert respuesta.status_code == 200
    html = respuesta.text
    assert 'id="wizard-edicion-data"' in html
    assert "Editar legajo #" in html
    assert "Guardar cambios" in html
    assert "Ana" in html
    assert "PAGO_FACIL" in html
    assert "regimen_afiliacion" in html


def test_editar_venta_aprobada_redirige_al_legajo(client: TestClient) -> None:
    venta = _crear_venta(client)
    _cambiar_estado(venta["id"], "APROBADA")

    respuesta = client.get(
        f"/ventas/{venta['id']}/editar",
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == f"/ventas/{venta['id']}"


def test_detalle_venta_muestra_lectura_y_enmascaramiento(
    client: TestClient,
) -> None:
    venta = _crear_venta(
        client,
        plan="Plan Integral",
        cantidad_adherentes=1,
        medio_pago="TARJETA_CREDITO",
    )
    url = f"/ventas/{venta['id']}"

    respuesta = client.get(url)
    assert respuesta.status_code == 200
    assert "Legajo #" in respuesta.text
    assert "VISA •••• 1111" in respuesta.text
    assert "Declaración jurada de salud" in respuesta.text
    assert "Preexistencias" in respuesta.text
    assert "Editar legajo" in respuesta.text

    _cambiar_estado(venta["id"], "APROBADA")
    aprobada = client.get(url)
    assert aprobada.status_code == 200
    assert "Aprobada" in aprobada.text
    assert "Editar legajo" not in aprobada.text


def test_detalle_venta_muestra_regimen_y_aporte(client: TestClient) -> None:
    venta = _crear_venta(
        client,
        plan="Plan Integral",
        regimen_afiliacion="RELACION_DEPENDENCIA",
        cuil_titular="20123456789",
        aporte_estimado=20_000,
    )

    html = client.get(f"/ventas/{venta['id']}").text

    assert "Relación de dependencia" in html
    assert "20••••••89" in html
    assert "Aporte estimado" in html
    assert "$58.000" in html


def test_legajo_muestra_timeline_y_credencial_aprobada(
    client: TestClient,
) -> None:
    venta = _crear_venta(
        client,
        plan="Plan Integral",
        medio_pago="TARJETA_CREDITO",
        ddjj={
            "preexistencias": True,
            "internaciones_ultimos_12m": False,
            "embarazo_actual": False,
            "medicacion_cronica": False,
            "discapacidad_declarada": False,
            "detalle": "Hipertensión controlada.",
            "declaracion_confirmada": True,
        },
    )
    with SessionLocal() as db:
        cambiar_estado_venta(db, venta["id"], "APROBADA")

    legajo = client.get(f"/ventas/{venta['id']}")
    assert legajo.status_code == 200
    assert "Línea de tiempo del legajo" in legajo.text
    assert "Legajo creado" in legajo.text
    assert "Auditoría: aprobada" in legajo.text
    assert "Imprimir credencial" in legajo.text

    credencial = client.get(f"/ventas/{venta['id']}/credencial")
    assert credencial.status_code == 200
    assert "Credencial provisoria" in credencial.text
    assert f"OS-{venta['id']:06d}" in credencial.text
    assert "Ana Pérez" in credencial.text
    assert "Plan Integral" in credencial.text
    assert "Hipertensión" not in credencial.text
    assert "VISA" not in credencial.text


def test_credencial_solo_para_ventas_aprobadas(client: TestClient) -> None:
    venta = _crear_venta(client)

    respuesta = client.get(f"/ventas/{venta['id']}/credencial")

    assert respuesta.status_code == 404


def test_rutas_de_venta_inexistente_devuelven_404(client: TestClient) -> None:
    assert client.get("/ventas/999999").status_code == 404
    assert client.get("/ventas/999999/editar").status_code == 404


def test_panel_ordena_ventas_de_mas_reciente_a_mas_antigua(client: TestClient) -> None:
    antigua = _crear_venta(client, plan="Plan Esencial")
    reciente = _crear_venta(client, plan="Plan Integral")

    with SessionLocal() as db:
        venta_antigua = db.get(Venta, antigua["id"])
        venta_reciente = db.get(Venta, reciente["id"])
        assert venta_antigua is not None
        assert venta_reciente is not None
        venta_antigua.creado_en = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        venta_reciente.creado_en = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
        db.commit()

    html = client.get("/ventas").text

    indice_reciente = html.index(f'id="venta-{reciente["id"]}"')
    indice_antigua = html.index(f'id="venta-{antigua["id"]}"')

    assert indice_reciente < indice_antigua


def test_panel_muestra_los_badges_de_los_tres_estados(client: TestClient) -> None:
    pendiente = _crear_venta(client)
    aprobada = _crear_venta(client)
    observada = _crear_venta(client)

    with SessionLocal() as db:
        venta_pendiente = db.get(Venta, pendiente["id"])
        venta_aprobada = db.get(Venta, aprobada["id"])
        venta_observada = db.get(Venta, observada["id"])
        assert venta_pendiente is not None
        assert venta_aprobada is not None
        assert venta_observada is not None
        venta_aprobada.estado = "APROBADA"
        venta_aprobada.observaciones = None
        venta_observada.estado = "OBSERVADA"
        venta_observada.observaciones = "R1: El titular no cumple la edad mínima."
        db.commit()

    html = client.get("/ventas").text

    assert 'data-estado="PENDIENTE_VERIFICACION"' in html
    assert 'data-estado="APROBADA"' in html
    assert 'data-estado="OBSERVADA"' in html
    assert 'class="stamp"' in html
    assert ">Pendiente<" in html
    assert ">Aprobada<" in html
    assert ">Observada<" in html
    assert "3 resultados · página 1 de 1." in html


def test_panel_muestra_ventas_con_plan_inactivo(client: TestClient) -> None:
    venta = _crear_venta(client, plan="Plan Superior")

    with SessionLocal() as db:
        plan = db.get(Plan, venta["plan_id"])
        assert plan is not None
        plan.activo = False
        db.commit()

    html = client.get("/ventas").text

    assert f'id="venta-{venta["id"]}"' in html
    assert "Plan Superior" in html


def test_panel_incluye_controles_de_auditoria_en_vivo(
    client: TestClient,
) -> None:
    html = client.get("/ventas").text

    assert "Auditar Pendientes con IA" in html
    assert 'id="btn-auditar"' in html
    assert 'id="spinner-auditoria"' in html
    assert 'id="auditoria-estado"' in html
    assert 'id="panel-auditoria"' in html
    assert 'id="auditoria-procesadas"' in html
    assert 'id="auditoria-aprobadas"' in html
    assert 'id="auditoria-observadas"' in html
    assert 'id="auditoria-narrativa"' in html
    assert 'id="auditoria-advertencia"' in html
    assert 'id="traza-mcp-body"' in html
    assert "Traza de herramientas MCP" in html
    assert "/static/js/auditoria.js" in html


def test_panel_muestra_observaciones_exactas_por_estado(
    client: TestClient,
) -> None:
    pendiente = _crear_venta(client)
    aprobada = _crear_venta(client)
    observada = _crear_venta(client)

    with SessionLocal() as db:
        venta_aprobada = db.get(Venta, aprobada["id"])
        venta_observada = db.get(Venta, observada["id"])
        assert venta_aprobada is not None
        assert venta_observada is not None
        venta_aprobada.estado = "APROBADA"
        venta_aprobada.observaciones = None
        venta_observada.estado = "OBSERVADA"
        venta_observada.observaciones = (
            "R1: El titular tiene 17 años; se requieren 18 o más.\n"
            "R4: El código postal 'C1425' no tiene el formato de 4 dígitos."
        )
        db.commit()

    html = client.get("/ventas").text
    html_visible = unescape(html)

    assert f'id="venta-{pendiente["id"]}"' in html
    assert "Pendiente de auditoría" in html
    assert "Sin observaciones" in html
    assert "R1: El titular tiene 17 años; se requieren 18 o más." in html_visible
    assert (
        "R4: El código postal 'C1425' no tiene el formato de 4 dígitos."
        in html_visible
    )
    assert "whitespace-pre-line" in html


def test_panel_sirve_el_javascript_de_auditoria(client: TestClient) -> None:
    respuesta = client.get("/static/js/auditoria.js")

    assert respuesta.status_code == 200
    assert "javascript" in respuesta.headers["content-type"]
    assert 'fetch("/api/auditar"' in respuesta.text
    assert "traza-mcp-body" in respuesta.text
    assert "actualizar_estado_venta" in respuesta.text
    assert "data-observaciones" in respuesta.text


def test_comprobante_enlaza_al_panel_de_ventas(client: TestClient) -> None:
    html = client.get("/").text

    assert 'id="enlace-panel-ventas"' in html
    assert 'href="/ventas"' in html
    assert "Ir al panel de ventas" in html
