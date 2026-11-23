"""Agente Auditor de ventas de obra social.

El auditor se conecta al servidor MCP por transporte ``stdio`` y reutiliza sus
tres herramientas para listar pendientes, obtener el detalle y actualizar el
estado. Las reglas de negocio R1–R8 son determinísticas y se aplican en el
cliente; el LLM opcional solo redacta un resumen de la corrida.

Variables de entorno para el LLM compatible con OpenAI:

- ``OPENAI_API_KEY``: clave de API. Si no está definida, no se usa el LLM.
- ``OPENAI_BASE_URL``: URL base, por ejemplo ``http://localhost:11434/v1``
  para Ollama. Por defecto ``https://api.openai.com/v1``.
- ``OPENAI_MODEL``: modelo; por defecto ``gpt-4o-mini``.
- ``OPENAI_TIMEOUT``: timeout en segundos; por defecto ``15``.
- ``LLM_EXTERNAL_ENABLED``: opt-in explícito para endpoints externos.

Los errores de red o de formato del LLM no interrumpen la auditoría: se emite
una advertencia y se usa el resumen local. El subproceso MCP recibe un entorno
mínimo, sin claves de LLM ni claves de cifrado de campos.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping
from contextlib import AsyncExitStack
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import TypeAdapter, ValidationError

from ventas_app.schemas import (
    Altura,
    Calle,
    Dni,
    Email,
    Localidad,
    Nombre,
    Provincia,
    Telefono,
)
from ventas_app.services.llm import (
    ConfiguracionLLM,
    ResultadoLLM,
    configuracion_llm_desde_entorno,
    generar_resumen_llm,
)
from ventas_app.services.pricing import (
    calcular_descuento_monto,
    obtener_descuento_porcentaje,
)

ESTADO_APROBADA = "APROBADA"
ESTADO_OBSERVADA = "OBSERVADA"

_PARENTESCOS_VALIDOS = frozenset(
    {
        "Cónyuge/Pareja",
        "Hijo/a",
        "Nieto/a",
        "Sobrino/a",
        "Familiar a cargo",
        "Amigo/Otro",
    }
)

_MARCAS_TARJETA = frozenset({"VISA", "MASTERCARD", "AMEX", "CABAL"})
_REGIMENES_AFILIACION = frozenset(
    {"PARTICULAR", "RELACION_DEPENDENCIA", "MONOTRIBUTO"}
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_ADAPTADOR_NOMBRE = TypeAdapter(Nombre)
_ADAPTADOR_DNI = TypeAdapter(Dni)
_ADAPTADOR_EMAIL = TypeAdapter(Email)
_ADAPTADOR_TELEFONO = TypeAdapter(Telefono)
_ADAPTADOR_CALLE = TypeAdapter(Calle)
_ADAPTADOR_ALTURA = TypeAdapter(Altura)
_ADAPTADOR_LOCALIDAD = TypeAdapter(Localidad)
_ADAPTADOR_PROVINCIA = TypeAdapter(Provincia)


class ErrorMCP(RuntimeError):
    """Error al comunicarse con el servidor MCP o al invocar una herramienta."""


class ClienteMCP(Protocol):
    """Interfaz mínima que necesita el auditor del servidor MCP."""

    @property
    def traza_mcp(self) -> list[dict[str, Any]]:
        """Invocaciones MCP registradas en orden."""

    async def listar_pendientes(self) -> list[dict[str, Any]]:
        """Devuelve las ventas pendientes de verificación."""

    async def obtener_detalle(self, venta_id: int) -> dict[str, Any]:
        """Devuelve el detalle de una venta."""

    async def actualizar_estado(
        self,
        venta_id: int,
        estado: str,
        observaciones: str | None = None,
    ) -> dict[str, Any]:
        """Actualiza el estado de una venta."""


_ENTORNO_MCP_PERMITIDO = frozenset(
    {
        "ALLOWED_HOSTS",
        "DATABASE_URL",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "TMPDIR",
        "TZ",
        "VIRTUAL_ENV",
    }
)


def _entorno_servidor() -> dict[str, str]:
    """Prepara un entorno mínimo para el subproceso MCP local.

    No copia ``OPENAI_API_KEY``, ``APP_ENCRYPTION_KEY`` ni otras credenciales.
    El flag ``VENTAS_SKIP_DOTENV`` impide que el hijo vuelva a cargar secretos
    desde ``.env``; el detalle de salud cifrado solo se expone como presencia.
    """
    entorno = {
        clave: valor
        for clave, valor in os.environ.items()
        if clave in _ENTORNO_MCP_PERMITIDO
    }
    ruta_src = str(_PROJECT_ROOT / "src")
    pythonpath = entorno.get("PYTHONPATH")
    entorno["PYTHONPATH"] = (
        f"{ruta_src}{os.pathsep}{pythonpath}" if pythonpath else ruta_src
    )
    entorno.setdefault("PYTHONUNBUFFERED", "1")
    entorno["VENTAS_SKIP_DOTENV"] = "1"
    return entorno


def _parametros_servidor() -> StdioServerParameters:
    """Define cómo lanzar el servidor MCP local por ``stdio``."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "ventas_app.mcp_server"],
        cwd=str(_PROJECT_ROOT),
        env=_entorno_servidor(),
    )


def _texto_resultado(resultado: Any) -> str:
    """Extrae el texto disponible de un resultado MCP."""
    partes: list[str] = []
    for bloque in getattr(resultado, "content", []) or []:
        texto = getattr(bloque, "text", None)
        if isinstance(texto, str) and texto:
            partes.append(texto)
    return "\n".join(partes)


def _extraer_resultado(resultado: Any) -> Any:
    """Convierte el contenido de una herramienta MCP en datos Python."""
    datos = getattr(resultado, "structured_content", None)
    if datos is None:
        texto = _texto_resultado(resultado)
        if not texto:
            raise ErrorMCP("La herramienta MCP no devolvió contenido.")
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErrorMCP(
                f"La herramienta MCP devolvió contenido no JSON: {texto}"
            ) from exc

    if isinstance(datos, dict) and set(datos) == {"result"}:
        return datos["result"]
    return datos


class ClienteMCPStdio:
    """Cliente MCP real que lanza el servidor local en un subproceso."""

    def __init__(
        self,
        parametros: StdioServerParameters | None = None,
    ) -> None:
        self._parametros = parametros or _parametros_servidor()
        self._stack: AsyncExitStack | None = None
        self._sesion: ClientSession | None = None
        self._traza_mcp: list[dict[str, Any]] = []

    @property
    def traza_mcp(self) -> list[dict[str, Any]]:
        """Copia ordenada de las invocaciones MCP realizadas."""
        return [dict(paso) for paso in self._traza_mcp]

    async def __aenter__(self) -> ClienteMCPStdio:
        self._stack = AsyncExitStack()
        try:
            lectura, escritura = await self._stack.enter_async_context(
                stdio_client(self._parametros)
            )
            self._sesion = await self._stack.enter_async_context(
                ClientSession(lectura, escritura)
            )
            await self._sesion.initialize()
        except Exception:
            await self._stack.aclose()
            self._stack = None
            self._sesion = None
            raise
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._sesion = None

    async def _llamar(
        self,
        nombre: str,
        argumentos: dict[str, Any],
    ) -> Any:
        if self._sesion is None:
            raise ErrorMCP("El cliente MCP no está inicializado.")

        traza = {
            "herramienta": nombre,
            "argumentos": dict(argumentos),
            "estado": "ok",
        }
        try:
            resultado = await self._sesion.call_tool(nombre, argumentos)
            if getattr(resultado, "is_error", False):
                detalle = _texto_resultado(resultado) or "error desconocido"
                raise ErrorMCP(
                    f"La herramienta MCP '{nombre}' falló: {detalle}"
                )
            return _extraer_resultado(resultado)
        except Exception as exc:
            traza["estado"] = "error"
            if isinstance(exc, ErrorMCP):
                raise
            raise ErrorMCP(
                f"No se pudo invocar la herramienta MCP '{nombre}': {exc}"
            ) from exc
        finally:
            self._traza_mcp.append(traza)

    async def listar_pendientes(self) -> list[dict[str, Any]]:
        datos = await self._llamar("listar_ventas_pendientes", {})
        if not isinstance(datos, list):
            raise ErrorMCP(
                "La herramienta listar_ventas_pendientes devolvió un formato "
                "inesperado."
            )
        if not all(isinstance(item, Mapping) for item in datos):
            raise ErrorMCP(
                "La herramienta listar_ventas_pendientes devolvió ventas "
                "con formato inesperado."
            )
        return [dict(item) for item in datos]

    async def obtener_detalle(self, venta_id: int) -> dict[str, Any]:
        datos = await self._llamar(
            "obtener_detalle_venta",
            {"venta_id": venta_id},
        )
        if not isinstance(datos, Mapping):
            raise ErrorMCP(
                "La herramienta obtener_detalle_venta devolvió un formato "
                "inesperado."
            )
        return dict(datos)

    async def actualizar_estado(
        self,
        venta_id: int,
        estado: str,
        observaciones: str | None = None,
    ) -> dict[str, Any]:
        datos = await self._llamar(
            "actualizar_estado_venta",
            {
                "venta_id": venta_id,
                "estado": estado,
                "observaciones": observaciones,
            },
        )
        if not isinstance(datos, Mapping):
            raise ErrorMCP(
                "La herramienta actualizar_estado_venta devolvió un formato "
                "inesperado."
            )
        return dict(datos)


def _capitalizar(texto: str) -> str:
    """Pone en mayúscula la primera letra sin alterar el resto."""
    return texto[:1].upper() + texto[1:]


def _parsear_fecha(valor: Any) -> date | None:
    """Convierte una fecha ISO o un objeto de fecha en ``date``."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor)
        except ValueError:
            return None
    return None


def calcular_edad(fecha_nacimiento: date, hoy: date) -> int:
    """Calcula la edad cumplida a la fecha de referencia."""
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )


def _cumple_formato(adaptador: TypeAdapter[Any], valor: Any) -> bool:
    """Indica si un valor no vacío satisface el tipo Pydantic indicado."""
    if not isinstance(valor, str) or not valor.strip():
        return False
    try:
        adaptador.validate_python(valor)
    except ValidationError:
        return False
    return True


def _validar_campo_texto(
    detalle: Mapping[str, Any],
    campo: str,
    etiqueta: str,
    adaptador: TypeAdapter[Any],
    errores: list[str],
) -> None:
    """Valida un campo de texto obligatorio y agrega una observación si falla."""
    valor = detalle.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        errores.append(f"R3: Falta {etiqueta}.")
    elif not _cumple_formato(adaptador, valor):
        errores.append(f"R3: {_capitalizar(etiqueta)} no cumple el formato.")


def _validar_fecha(
    valor: Any,
    etiqueta: str,
    hoy: date,
    errores: list[str],
) -> None:
    """Valida que una fecha obligatoria sea ISO válida y no futura."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        errores.append(f"R3: Falta {etiqueta}.")
        return

    fecha = _parsear_fecha(valor)
    if fecha is None:
        errores.append(f"R3: {_capitalizar(etiqueta)} no es válida.")
    elif fecha > hoy:
        errores.append(f"R3: {_capitalizar(etiqueta)} no puede ser futura.")


def validar_r1_edad(
    detalle: Mapping[str, Any],
    hoy: date,
) -> list[str]:
    """R1: el titular debe tener 18 años o más a la fecha de auditoría."""
    fecha_nacimiento = _parsear_fecha(
        detalle.get("fecha_nacimiento_titular")
    )
    if fecha_nacimiento is None or fecha_nacimiento > hoy:
        # Una fecha inválida o futura se informa en R3.
        return []

    edad = calcular_edad(fecha_nacimiento, hoy)
    if edad < 18:
        return [f"R1: El titular tiene {edad} años; se requieren 18 o más."]
    return []


def validar_r2_dnis_unicos(detalle: Mapping[str, Any]) -> list[str]:
    """R2: los DNIs del grupo familiar deben ser únicos dentro de la venta."""
    dnis: list[str] = []

    dni_titular = detalle.get("dni_titular")
    if isinstance(dni_titular, str) and dni_titular.strip():
        dnis.append(dni_titular.strip())

    integrantes = detalle.get("integrantes")
    if isinstance(integrantes, list):
        for integrante in integrantes:
            if not isinstance(integrante, Mapping):
                continue
            dni = integrante.get("dni")
            if isinstance(dni, str) and dni.strip():
                dnis.append(dni.strip())

    duplicados = sorted({dni for dni in dnis if dnis.count(dni) > 1})
    return [
        f"R2: El DNI {dni} está repetido en el grupo familiar."
        for dni in duplicados
    ]


def validar_r3_datos_obligatorios(
    detalle: Mapping[str, Any],
    hoy: date,
) -> list[str]:
    """R3: valida datos obligatorios y formatos de titular, adherentes y domicilio."""
    errores: list[str] = []

    campos_titular = (
        ("nombre_titular", "el nombre del titular", _ADAPTADOR_NOMBRE),
        ("apellido_titular", "el apellido del titular", _ADAPTADOR_NOMBRE),
        ("dni_titular", "el DNI del titular", _ADAPTADOR_DNI),
        ("email", "el email del titular", _ADAPTADOR_EMAIL),
        ("telefono", "el teléfono del titular", _ADAPTADOR_TELEFONO),
        ("calle", "la calle", _ADAPTADOR_CALLE),
        ("altura", "la altura", _ADAPTADOR_ALTURA),
        ("localidad", "la localidad", _ADAPTADOR_LOCALIDAD),
        ("provincia", "la provincia", _ADAPTADOR_PROVINCIA),
    )
    for campo, etiqueta, adaptador in campos_titular:
        _validar_campo_texto(detalle, campo, etiqueta, adaptador, errores)

    _validar_fecha(
        detalle.get("fecha_nacimiento_titular"),
        "la fecha de nacimiento del titular",
        hoy,
        errores,
    )

    telefono = detalle.get("telefono")
    if _cumple_formato(_ADAPTADOR_TELEFONO, telefono):
        assert isinstance(telefono, str)
        if sum(caracter.isdigit() for caracter in telefono) < 6:
            errores.append(
                "R3: El teléfono del titular debe contener al menos 6 dígitos."
            )

    integrantes = detalle.get("integrantes")
    if not isinstance(integrantes, list):
        errores.append("R3: La lista de integrantes no es válida.")
        return errores

    campos_integrante = (
        ("nombre", "el nombre", _ADAPTADOR_NOMBRE),
        ("apellido", "el apellido", _ADAPTADOR_NOMBRE),
        ("dni", "el DNI", _ADAPTADOR_DNI),
    )
    for indice, integrante in enumerate(integrantes, start=1):
        if not isinstance(integrante, Mapping):
            errores.append(
                f"R3: El integrante {indice} no tiene datos válidos."
            )
            continue

        for campo, etiqueta, adaptador in campos_integrante:
            valor = integrante.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                errores.append(
                    f"R3: Falta {etiqueta} del integrante {indice}."
                )
            elif not _cumple_formato(adaptador, valor):
                errores.append(
                    f"R3: {_capitalizar(etiqueta)} del integrante {indice} "
                    "no cumple el formato."
                )

        _validar_fecha(
            integrante.get("fecha_nacimiento"),
            f"la fecha de nacimiento del integrante {indice}",
            hoy,
            errores,
        )

        parentesco = integrante.get("parentesco")
        if not isinstance(parentesco, str) or not parentesco.strip():
            errores.append(
                f"R3: Falta el parentesco del integrante {indice}."
            )
        elif parentesco not in _PARENTESCOS_VALIDOS:
            errores.append(
                f"R3: El parentesco del integrante {indice} no es válido."
            )

    return errores


def validar_r4_codigo_postal(detalle: Mapping[str, Any]) -> list[str]:
    """R4: el código postal debe tener exactamente cuatro dígitos."""
    valor = detalle.get("codigo_postal")
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return ["R4: Falta el código postal."]

    if not isinstance(valor, str) or re.fullmatch(r"\d{4}", valor) is None:
        return [
            f"R4: El código postal '{valor}' no tiene el formato de 4 dígitos."
        ]
    return []


def _validar_datos_pago(
    medio_pago: str,
    detalle: Mapping[str, Any],
    errores: list[str],
) -> None:
    """Valida los metadatos enmascarados de tarjeta o CBU."""
    if medio_pago == "TARJETA_CREDITO":
        titular = detalle.get("pago_titular")
        marca = detalle.get("pago_marca_entidad")
        ultimos_4 = detalle.get("pago_ultimos_4")
        vencimiento = detalle.get("pago_vencimiento")
        if not all(
            isinstance(valor, str) and valor.strip()
            for valor in (titular, marca, ultimos_4, vencimiento)
        ):
            errores.append(
                "R5: Faltan los datos enmascarados de la tarjeta de crédito."
            )
            return
        if marca not in _MARCAS_TARJETA:
            errores.append(f"R5: La marca de tarjeta '{marca}' no es válida.")
        if re.fullmatch(r"\d{4}", ultimos_4) is None:
            errores.append(
                "R5: Los últimos 4 dígitos de la tarjeta no son válidos."
            )
        if re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", vencimiento) is None:
            errores.append(
                "R5: El vencimiento de la tarjeta no tiene formato MM/AA."
            )
        return

    if medio_pago == "CBU":
        titular = detalle.get("pago_titular")
        entidad = detalle.get("pago_marca_entidad")
        ultimos_4 = detalle.get("pago_ultimos_4")
        cuil = detalle.get("pago_cuil")
        if not all(
            isinstance(valor, str) and valor.strip()
            for valor in (titular, entidad, ultimos_4, cuil)
        ):
            errores.append("R5: Faltan los datos enmascarados del CBU.")
            return
        if re.fullmatch(r"\d{4}", ultimos_4) is None:
            errores.append("R5: Los últimos 4 dígitos del CBU no son válidos.")
        if re.fullmatch(r"\d{11}", cuil) is None:
            errores.append("R5: El CUIL del CBU debe tener 11 dígitos.")


def validar_r5_plan_y_precio(detalle: Mapping[str, Any]) -> list[str]:
    """R5: el plan debe existir, estar activo y tener el precio total vigente."""
    errores: list[str] = []

    plan = detalle.get("plan")
    if not isinstance(plan, Mapping):
        return ["R5: El plan seleccionado no existe."]

    if not plan.get("activo"):
        errores.append("R5: El plan seleccionado no existe o está inactivo.")

    precio_titular = plan.get("precio_titular")
    precio_adherente = plan.get("precio_adherente")
    if (
        not isinstance(precio_titular, int)
        or isinstance(precio_titular, bool)
        or not isinstance(precio_adherente, int)
        or isinstance(precio_adherente, bool)
        or precio_titular <= 0
        or precio_adherente < 0
    ):
        errores.append("R5: Los precios del plan no son válidos.")
        return errores

    integrantes = detalle.get("integrantes")
    if not isinstance(integrantes, list):
        return errores

    precio_total = detalle.get("precio_total")
    if not isinstance(precio_total, int) or isinstance(precio_total, bool):
        errores.append("R5: El precio total persistido no es válido.")
        return errores

    subtotal_esperado = precio_titular + len(integrantes) * precio_adherente
    medio_pago = detalle.get("medio_pago")
    if not isinstance(medio_pago, str) or not medio_pago.strip():
        errores.append("R5: Falta el medio de pago.")
        return errores

    try:
        descuento_pct = obtener_descuento_porcentaje(medio_pago)
    except ValueError:
        errores.append(f"R5: El medio de pago '{medio_pago}' no es válido.")
        return errores

    subtotal_persistido = detalle.get("subtotal_base")
    if not isinstance(subtotal_persistido, int) or isinstance(
        subtotal_persistido, bool
    ):
        errores.append("R5: El subtotal base persistido no es válido.")
        return errores

    if subtotal_persistido != subtotal_esperado:
        errores.append(
            "R5: El subtotal base persistido "
            f"({subtotal_persistido}) no coincide con el cálculo vigente "
            f"({subtotal_esperado})."
        )

    descuento_persistido = detalle.get("descuento_porcentaje")
    if not isinstance(descuento_persistido, int) or isinstance(
        descuento_persistido, bool
    ):
        errores.append("R5: El descuento persistido no es válido.")
        return errores

    if descuento_persistido != descuento_pct:
        errores.append(
            "R5: El descuento persistido "
            f"({descuento_persistido}%) no coincide con el medio de pago "
            f"'{medio_pago}' ({descuento_pct}%)."
        )

    _validar_datos_pago(medio_pago, detalle, errores)

    aporte_estimado = detalle.get("aporte_estimado", 0)
    if (
        not isinstance(aporte_estimado, int)
        or isinstance(aporte_estimado, bool)
        or aporte_estimado < 0
    ):
        errores.append("R5: El aporte estimado persistido no es válido.")
        aporte_estimado = 0

    descuento_monto = calcular_descuento_monto(
        subtotal_esperado,
        descuento_pct,
    )
    esperado = max(0, subtotal_esperado - descuento_monto - aporte_estimado)

    if precio_total != esperado:
        errores.append(
            "R5: El precio total persistido "
            f"({precio_total}) no coincide con el cálculo vigente "
            f"({esperado})."
        )

    return errores


def validar_r6_integridad(detalle: Mapping[str, Any]) -> list[str]:
    """R6: la venta debe tener titular y adherentes asociados a esa misma venta."""
    errores: list[str] = []

    venta_id = detalle.get("id")
    if (
        not isinstance(venta_id, int)
        or isinstance(venta_id, bool)
        or venta_id <= 0
    ):
        errores.append("R6: La venta no tiene un identificador válido.")
        venta_id = None

    datos_titular = (
        detalle.get("nombre_titular"),
        detalle.get("apellido_titular"),
        detalle.get("dni_titular"),
    )
    if not any(
        isinstance(valor, str) and valor.strip() for valor in datos_titular
    ):
        errores.append("R6: La venta no posee un titular.")

    integrantes = detalle.get("integrantes")
    if not isinstance(integrantes, list):
        errores.append("R6: La lista de integrantes de la venta no es válida.")
        return errores

    for indice, integrante in enumerate(integrantes, start=1):
        if not isinstance(integrante, Mapping):
            errores.append(
                f"R6: El integrante {indice} no está asociado a la venta."
            )
            continue

        venta_id_integrante = integrante.get("venta_id")
        if venta_id_integrante is None:
            errores.append(
                f"R6: El integrante {indice} no está asociado a la venta."
            )
            continue

        if venta_id is not None and venta_id_integrante != venta_id:
            dni = integrante.get("dni")
            referencia_dni = (
                f" (DNI {dni})"
                if isinstance(dni, str) and dni.strip()
                else ""
            )
            errores.append(
                f"R6: El integrante {indice}{referencia_dni} no pertenece "
                f"a la venta {venta_id}."
            )

    return errores


def validar_r7_ddjj_salud(detalle: Mapping[str, Any]) -> list[str]:
    """R7: la DDJJ debe estar completa y derivar los casos de riesgo médico."""
    if detalle.get("ddjj_completada") is not True:
        return ["R7: Falta completar la declaración jurada de salud."]

    preexistencias = detalle.get("ddjj_preexistencias") is True
    internaciones = detalle.get("ddjj_internaciones") is True
    embarazo = detalle.get("ddjj_embarazo") is True
    medicacion = detalle.get("ddjj_medicacion_cronica") is True
    discapacidad = detalle.get("ddjj_discapacidad") is True
    detalle_salud = detalle.get("ddjj_detalle")

    if (
        preexistencias
        or internaciones
        or embarazo
        or medicacion
        or discapacidad
    ) and not (
        isinstance(detalle_salud, str) and detalle_salud.strip()
    ):
        return [
            "R7: La DDJJ de salud requiere detalle para los indicadores "
            "declarados."
        ]

    if preexistencias or internaciones or discapacidad:
        return [
            "R7: La DDJJ declara preexistencias, internaciones o discapacidad; "
            "requiere revisión médica."
        ]

    return []


def validar_r8_regimen_aportes(detalle: Mapping[str, Any]) -> list[str]:
    """R8: valida régimen, CUIL y aporte estimado."""
    regimen = detalle.get("regimen_afiliacion")
    if regimen not in _REGIMENES_AFILIACION:
        return ["R8: El régimen de afiliación no es válido."]

    aporte = detalle.get("aporte_estimado")
    if not isinstance(aporte, int) or isinstance(aporte, bool) or aporte < 0:
        return ["R8: El aporte estimado no es válido."]

    cuil = detalle.get("cuil_titular")
    if regimen == "PARTICULAR":
        if aporte != 0:
            return ["R8: El régimen PARTICULAR no admite aporte estimado."]
    elif not isinstance(cuil, str) or re.fullmatch(r"\d{11}", cuil) is None:
        return [
            f"R8: El régimen {regimen} exige un CUIL de 11 dígitos "
            "para el titular."
        ]

    if cuil is not None and (
        not isinstance(cuil, str) or re.fullmatch(r"\d{11}", cuil) is None
    ):
        return ["R8: El CUIL del titular debe tener 11 dígitos."]

    subtotal = detalle.get("subtotal_base")
    descuento_pct = detalle.get("descuento_porcentaje")
    if (
        isinstance(subtotal, int)
        and not isinstance(subtotal, bool)
        and subtotal >= 0
        and isinstance(descuento_pct, int)
        and not isinstance(descuento_pct, bool)
        and 0 <= descuento_pct <= 100
    ):
        base_bonificada = subtotal - calcular_descuento_monto(
            subtotal,
            descuento_pct,
        )
        if aporte > base_bonificada:
            return [
                "R8: El aporte estimado no puede superar la base bonificada."
            ]

    return []


def aplicar_reglas(
    detalle: Mapping[str, Any],
    hoy: date | None = None,
) -> list[str]:
    """Aplica R1–R8 y devuelve una lista legible de incumplimientos."""
    if not isinstance(detalle, Mapping):
        return ["R6: El detalle de la venta no es válido."]

    fecha_referencia = hoy or date.today()
    errores: list[str] = []

    errores.extend(validar_r1_edad(detalle, fecha_referencia))
    errores.extend(validar_r2_dnis_unicos(detalle))
    errores.extend(
        validar_r3_datos_obligatorios(detalle, fecha_referencia)
    )
    errores.extend(validar_r4_codigo_postal(detalle))
    errores.extend(validar_r5_plan_y_precio(detalle))
    errores.extend(validar_r6_integridad(detalle))
    errores.extend(validar_r7_ddjj_salud(detalle))
    errores.extend(validar_r8_regimen_aportes(detalle))

    return errores


async def auditar_ventas(
    cliente: ClienteMCP,
    hoy: date | None = None,
) -> dict[str, Any]:
    """Audita las ventas pendientes usando un cliente MCP ya conectado."""
    aprobadas = 0
    observadas = 0
    errores_observados: list[str] = []

    for venta in await cliente.listar_pendientes():
        venta_id = venta.get("id")
        if not isinstance(venta_id, int) or isinstance(venta_id, bool):
            raise ErrorMCP(
                "El listado de ventas pendientes contiene una venta sin ID "
                "válido."
            )

        detalle = await cliente.obtener_detalle(venta_id)
        errores = aplicar_reglas(detalle, hoy)

        if errores:
            await cliente.actualizar_estado(
                venta_id,
                ESTADO_OBSERVADA,
                "\n".join(errores),
            )
            observadas += 1
            errores_observados.extend(
                f"Venta #{venta_id}: {error}" for error in errores
            )
        else:
            await cliente.actualizar_estado(
                venta_id,
                ESTADO_APROBADA,
                None,
            )
            aprobadas += 1

    procesadas = aprobadas + observadas
    if procesadas:
        resultado_llm = generar_resumen_llm(
            aprobadas,
            observadas,
            errores_observados,
        )
    else:
        resultado_llm = ResultadoLLM(
            ok=False,
            advertencia="No hay ventas pendientes para auditar.",
        )

    return {
        "procesadas": procesadas,
        "aprobadas": aprobadas,
        "observadas": observadas,
        "resumen_llm": resultado_llm.resumen,
        "llm_ok": resultado_llm.ok,
        "advertencia": resultado_llm.advertencia,
        "traza_mcp": cliente.traza_mcp,
    }


async def _auditar_con_servidor_mcp(
    hoy: date | None = None,
) -> dict[str, Any]:
    async with ClienteMCPStdio() as cliente:
        return await auditar_ventas(cliente, hoy)


def ejecutar_auditoria(hoy: date | None = None) -> dict[str, Any]:
    """Ejecuta una auditoría completa como cliente MCP por ``stdio``."""
    return asyncio.run(_auditar_con_servidor_mcp(hoy))


def main() -> int:
    """Ejecuta la auditoría y registra el resumen en la salida estándar."""
    try:
        resultado = ejecutar_auditoria()
    except Exception as exc:
        print(
            f"Error al ejecutar la auditoría MCP: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        "Resumen de auditoría: "
        f"{resultado['procesadas']} procesadas, "
        f"{resultado['aprobadas']} aprobadas, "
        f"{resultado['observadas']} observadas."
    )
    if resultado["resumen_llm"]:
        print(resultado["resumen_llm"])
    if resultado["advertencia"]:
        print(
            f"Advertencia: {resultado['advertencia']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
