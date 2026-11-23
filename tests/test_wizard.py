"""Tests de renderizado y assets del wizard web (F04)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from ventas_app.database import SessionLocal
from ventas_app.models import Plan


def test_wizard_renderiza_etapas_campos_y_planes(client: TestClient) -> None:
    respuesta = client.get("/")

    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]

    html = respuesta.text

    assert "/static/vendor/tailwindcss-3.4.17.js" in html
    assert 'id="wizard"' in html
    assert 'id="template-integrante"' in html
    assert 'id="integrantes-container"' in html
    assert 'id="btn-agregar-integrante"' in html
    assert 'id="btn-confirmar"' in html
    assert 'id="comprobante"' in html
    assert 'id="comprobante-total"' in html
    assert "js/wizard.js" in html

    assert "1. Titular y grupo familiar" in html
    assert "2. Domicilio" in html
    assert "3. Plan y cotización" in html
    assert "Datos del titular" in html
    assert "Grupo familiar" in html
    assert "Domicilio" in html
    assert "Resumen de cotización" in html
    assert "Elegí el medio de pago" in html
    assert 'name="medio_pago"' in html
    assert 'value="TARJETA_CREDITO"' in html
    assert 'value="CBU"' in html
    assert 'value="PAGO_FACIL"' in html
    assert 'value="COBRADOR_DOMICILIO"' in html
    assert "30% de descuento" in html
    assert "20% de descuento" in html
    assert 'id="comprobante-medio-pago"' in html
    assert 'id="comprobante-instrumento"' in html
    assert 'id="comprobante-subtotal-base"' in html
    assert 'id="comprobante-fila-descuento"' in html
    assert 'id="comprobante-descuento"' in html
    assert 'id="pago-tarjeta"' in html
    assert 'id="pago-cbu"' in html
    assert 'id="tarjeta-numero"' in html
    assert 'id="tarjeta-cvv"' in html
    assert 'id="cbu-numero"' in html
    assert 'id="cbu-cuil"' in html
    assert 'name="ddjj-preexistencias"' in html
    assert 'name="ddjj-internaciones"' in html
    assert 'name="ddjj-embarazo"' in html
    assert 'name="ddjj-medicacion"' in html
    assert 'name="ddjj-discapacidad"' in html
    assert html.count('value="si"') == 5
    assert html.count('value="no"') == 5
    assert 'id="ddjj-detalle"' in html
    assert 'id="ddjj-detalle-required"' in html
    assert 'id="ddjj-detalle-hint"' in html
    assert 'id="ddjj-confirmada"' in html
    assert 'class="field-checkbox"' in html
    assert 'id="legajo-ddjj"' in html
    assert 'id="comprobante-ddjj"' in html
    assert 'id="wizard-sidebar"' in html
    assert html.count('role="button"') == 3
    assert 'id="regimen-afiliacion"' in html
    assert 'id="cuil-titular"' in html
    assert 'id="aporte-estimado"' in html
    assert 'id="fila-aporte"' in html
    assert 'id="legajo-regimen"' in html
    assert 'id="comprobante-regimen"' in html
    assert 'id="comprobante-cuil"' in html
    assert 'id="comprobante-aporte"' in html

    for campo in (
        "titular.nombre",
        "titular.apellido",
        "titular.dni",
        "titular.fecha_nacimiento",
        "titular.email",
        "titular.telefono",
        "domicilio.calle",
        "domicilio.altura",
        "domicilio.piso_depto",
        "domicilio.localidad",
        "domicilio.provincia",
        "domicilio.codigo_postal",
    ):
        assert f'data-state="{campo}"' in html

    for parentesco in (
        "Cónyuge/Pareja",
        "Hijo/a",
        "Nieto/a",
        "Sobrino/a",
        "Familiar a cargo",
        "Amigo/Otro",
    ):
        assert parentesco in html

    assert "Seleccioná un parentesco" in html
    assert "Tierra del Fuego, Antártida e Islas del Atlántico Sur" in html

    for plan, precio_titular, precio_adherente in (
        ("Plan Esencial", "45000", "30000"),
        ("Plan Integral", "78000", "52000"),
        ("Plan Superior", "125000", "85000"),
    ):
        assert plan in html
        assert f'data-precio-titular="{precio_titular}"' in html
        assert f'data-precio-adherente="{precio_adherente}"' in html

    assert html.index("Plan Esencial") < html.index("Plan Integral") < html.index("Plan Superior")
    assert "$45.000" in html
    assert "$78.000" in html
    assert "$125.000" in html


def test_wizard_excluye_planes_inactivos(client: TestClient) -> None:
    with SessionLocal() as db:
        db.add(
            Plan(
                nombre="Plan Oculto",
                precio_titular=10_000,
                precio_adherente=5_000,
                activo=False,
            )
        )
        db.commit()

    html = client.get("/").text

    assert "Plan Oculto" not in html
    assert "Plan Esencial" in html
    assert "Plan Integral" in html
    assert "Plan Superior" in html


def test_wizard_sin_planes_activos_muestra_un_aviso(client: TestClient) -> None:
    with SessionLocal() as db:
        db.execute(update(Plan).values(activo=False))
        db.commit()

    html = client.get("/").text

    assert "No hay planes activos disponibles" in html
    assert 'name="plan_id"' not in html


def test_assets_del_wizard_se_sirven(client: TestClient) -> None:
    respuesta = client.get("/static/js/wizard.js")

    assert respuesta.status_code == 200
    assert "javascript" in respuesta.headers["content-type"]

    js = respuesta.text

    for fragmento in (
        "sessionStorage",
        "fetch(url",
        "agregar-integrante",
        "template-integrante",
        "confirmarVenta",
        "mostrarComprobante",
        "precioTitular",
        "precioAdherente",
        "codigo_postal",
        "medio_pago",
        "inicializarMediosPago",
        "descuentoPct",
        "comprobante-descuento",
        "medio_pago: estado.medio_pago",
        "TARJETA_REGEX",
        "validarInstrumentoPago",
        "datosTarjeta",
        "datosCbu",
        "payload.tarjeta",
        "comprobante-instrumento",
        "wizard-edicion-data",
        "modoEdicion",
        "api/ventas/${edicion.id}",
        "PUT",
        "inicializarDDJJ",
        "ddjjConIndicadores",
        "ddjjCompleta",
        "ddjjValida",
        "actualizarDDJJDetalle",
        "radio.value === \"si\"",
        "detalle.required = hayIndicadores",
        "Respondé Sí o No",
        "declaracion_confirmada",
        "pasoCompleto",
        "actualizarIndicadoresPaso",
        "irAPaso",
        "inicializarValidacionPago",
        "campo.addEventListener(evento, actualizarIndicadoresPaso)",
        "comprobante-ddjj",
        "legajo-ddjj",
        "actualizarFormularioRegimen",
        "baseBonificadaActual",
        "regimen_afiliacion",
        "aporte_estimado",
        "comprobante-regimen",
        "comprobante-aporte",
    ):
        assert fragmento in js


def test_el_seed_del_wizard_no_duplica_planes(client: TestClient) -> None:
    client.get("/")

    with SessionLocal() as db:
        nombres = list(db.scalars(select(Plan.nombre)).all())

    assert sorted(nombres) == ["Plan Esencial", "Plan Integral", "Plan Superior"]
