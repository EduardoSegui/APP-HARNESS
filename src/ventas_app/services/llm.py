"""Proveedores LLM con redacción y aislamiento de datos sensibles."""

from __future__ import annotations

import ipaddress
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_OPENAI_BASE_URL_DEFAULT = "https://api.openai.com/v1"
_OPENAI_MODEL_DEFAULT = "gpt-4o-mini"
_OPENAI_TIMEOUT_DEFAULT = 15.0
_CODIGOS_REGLA = re.compile(r"\bR[1-8]\b")


@dataclass(frozen=True, slots=True)
class ResultadoLLM:
    """Resultado de una llamada opcional a un proveedor LLM."""

    resumen: str | None = None
    ok: bool = False
    advertencia: str | None = None


@dataclass(frozen=True, slots=True)
class ConfiguracionLLM:
    """Configuración de un proveedor compatible con OpenAI."""

    api_key: str
    base_url: str = _OPENAI_BASE_URL_DEFAULT
    modelo: str = _OPENAI_MODEL_DEFAULT
    timeout: float = _OPENAI_TIMEOUT_DEFAULT
    externo: bool | None = None

    def __post_init__(self) -> None:
        if self.externo is None:
            object.__setattr__(
                self,
                "externo",
                not es_endpoint_local(self.base_url),
            )


class LLMProvider(Protocol):
    """Contrato mínimo de un proveedor de resumen narrativo."""

    @property
    def externo(self) -> bool:
        """Indica si el proveedor envía datos fuera de la LAN."""

    def generar_resumen(
        self,
        aprobadas: int,
        observadas: int,
        errores: Sequence[str],
    ) -> ResultadoLLM:
        """Genera un resumen sin decidir estados de ventas."""


def es_endpoint_local(base_url: str) -> bool:
    """Considera locales loopback, IP privadas y nombres de LAN."""
    hostname = urlparse(base_url).hostname
    if not hostname:
        return False
    hostname = hostname.lower().rstrip(".")
    if hostname in {"localhost", "127.0.0.1", "::1", "ollama"}:
        return True
    if hostname.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def configuracion_llm_desde_entorno(
    entorno: Mapping[str, str] | None = None,
) -> ConfiguracionLLM | None:
    """Lee la configuración LLM; devuelve ``None`` si no hay API key."""
    fuente = os.environ if entorno is None else entorno
    api_key = fuente.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    base_url = (
        fuente.get("OPENAI_BASE_URL", "").strip()
        or _OPENAI_BASE_URL_DEFAULT
    )
    modelo = (
        fuente.get("OPENAI_MODEL", "").strip() or _OPENAI_MODEL_DEFAULT
    )
    timeout_crudo = fuente.get("OPENAI_TIMEOUT", "").strip()
    try:
        timeout = (
            float(timeout_crudo)
            if timeout_crudo
            else _OPENAI_TIMEOUT_DEFAULT
        )
    except ValueError:
        timeout = _OPENAI_TIMEOUT_DEFAULT
    if timeout <= 0:
        timeout = _OPENAI_TIMEOUT_DEFAULT

    return ConfiguracionLLM(
        api_key=api_key,
        base_url=base_url,
        modelo=modelo,
        timeout=timeout,
    )


def _redactar_texto(texto: str) -> str:
    """Oculta secuencias numéricas sensibles en textos internos."""
    return re.sub(r"\d{4,}", "***", texto)


def _conteo_codigos(errores: Sequence[str]) -> str:
    """Devuelve solo códigos R1–R8 y cantidades, nunca el texto original."""
    conteo: Counter[str] = Counter()
    for error in errores:
        for codigo in _CODIGOS_REGLA.findall(error):
            conteo[codigo] += 1
    if not conteo:
        return "Sin observaciones por regla."
    return "\n".join(
        f"{codigo}: {conteo[codigo]}"
        for codigo in sorted(conteo, key=lambda valor: int(valor[1:]))
    )


class _ProveedorOpenAICompatible:
    """Implementación común del protocolo HTTP compatible con OpenAI."""

    def __init__(
        self,
        config: ConfiguracionLLM,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport

    @property
    def externo(self) -> bool:
        return bool(self.config.externo)

    def _carga(
        self,
        aprobadas: int,
        observadas: int,
        errores: Sequence[str],
    ) -> dict[str, object]:
        raise NotImplementedError

    def generar_resumen(
        self,
        aprobadas: int,
        observadas: int,
        errores: Sequence[str],
    ) -> ResultadoLLM:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        try:
            with httpx.Client(
                timeout=self.config.timeout,
                transport=self.transport,
            ) as cliente:
                respuesta = cliente.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._carga(aprobadas, observadas, errores),
                )
                respuesta.raise_for_status()
                datos = respuesta.json()
                contenido = datos["choices"][0]["message"]["content"]
                if not isinstance(contenido, str) or not contenido.strip():
                    raise ValueError("respuesta vacía del LLM")
                return ResultadoLLM(
                    resumen=contenido.strip(),
                    ok=True,
                    advertencia=None,
                )
        except (
            httpx.HTTPError,
            httpx.InvalidURL,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            return ResultadoLLM(
                ok=False,
                advertencia=(
                    "No se pudo obtener el resumen del LLM "
                    f"({type(exc).__name__}); se usó el resumen local."
                ),
            )


class LocalLLMProvider(_ProveedorOpenAICompatible):
    """Proveedor en LAN/local (Ollama u otro compatible con OpenAI)."""

    @property
    def externo(self) -> bool:
        return False

    def _carga(
        self,
        aprobadas: int,
        observadas: int,
        errores: Sequence[str],
    ) -> dict[str, object]:
        detalle_errores = (
            "\n".join(_redactar_texto(error) for error in errores)
            if errores
            else "Sin observaciones."
        )
        return {
            "model": self.config.modelo,
            "temperature": 0,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Sos el Agente Auditor de una obra social. Redactá en "
                        "español un resumen operativo breve de la auditoría. "
                        "No inventes datos, no cambies estados y no agregues "
                        "reglas nuevas."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Resultado determinístico: {aprobadas} aprobadas y "
                        f"{observadas} observadas.\n"
                        f"Observaciones registradas:\n{detalle_errores}"
                    ),
                },
            ],
        }


class ExternalLLMProvider(_ProveedorOpenAICompatible):
    """Proveedor externo opt-in; solo recibe conteos y códigos R1–R8."""

    @property
    def externo(self) -> bool:
        return True

    def _carga(
        self,
        aprobadas: int,
        observadas: int,
        errores: Sequence[str],
    ) -> dict[str, object]:
        return {
            "model": self.config.modelo,
            "temperature": 0,
            "max_tokens": 300,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Sos el Agente Auditor de una obra social. Redactá en "
                        "español un resumen operativo breve usando únicamente "
                        "los conteos agregados. No inventes datos, no cambies "
                        "estados y no agregues reglas nuevas."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Resultado determinístico: {aprobadas} aprobadas y "
                        f"{observadas} observadas.\n"
                        "Conteo de observaciones por regla:\n"
                        f"{_conteo_codigos(errores)}"
                    ),
                },
            ],
        }


def _externo_habilitado() -> bool:
    return os.getenv("LLM_EXTERNAL_ENABLED", "false").lower() == "true"


def crear_proveedor(
    config: ConfiguracionLLM,
    transport: httpx.BaseTransport | None = None,
) -> LLMProvider:
    """Selecciona local o externo según la URL configurada."""
    # La URL manda: un endpoint público nunca se trata como local aunque el
    # objeto de configuración haya sido construido manualmente.
    if config.externo or not es_endpoint_local(config.base_url):
        return ExternalLLMProvider(config, transport)
    return LocalLLMProvider(config, transport)


def generar_resumen_llm(
    aprobadas: int,
    observadas: int,
    errores: Sequence[str],
    config: ConfiguracionLLM | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ResultadoLLM:
    """Genera un resumen sin delegar decisiones de estado al modelo.

    Los proveedores externos están deshabilitados por defecto y, cuando se
    habilitan explícitamente, reciben solo conteos y códigos de regla.
    """
    if config is None:
        config = configuracion_llm_desde_entorno()
    if config is None:
        return ResultadoLLM(
            ok=False,
            advertencia="LLM no configurado; se usó el resumen local.",
        )

    es_externo = bool(config.externo) or not es_endpoint_local(config.base_url)
    if es_externo and not _externo_habilitado():
        return ResultadoLLM(
            ok=False,
            advertencia=(
                "No se usó el resumen del LLM: proveedor externo "
                "deshabilitado; se usó el resumen local."
            ),
        )
    if es_externo and urlparse(config.base_url).scheme != "https":
        return ResultadoLLM(
            ok=False,
            advertencia=(
                "No se usó el resumen del LLM: el proveedor externo requiere "
                "HTTPS; se usó el resumen local."
            ),
        )

    proveedor = crear_proveedor(config, transport)
    resultado = proveedor.generar_resumen(aprobadas, observadas, errores)
    if es_externo:
        _registrar_uso_externo(resultado)
    return resultado


def _registrar_uso_externo(resultado: ResultadoLLM) -> None:
    """Audita el uso externo sin guardar prompt, URL ni API key."""
    try:
        from ventas_app.database import SessionLocal
        from ventas_app.security import registrar_evento_seguridad

        with SessionLocal() as db:
            registrar_evento_seguridad(
                db,
                tipo="LLM_EXTERNO",
                resultado="OK" if resultado.ok else "FALLO",
                detalle="Intento de resumen con proveedor externo.",
            )
            db.commit()
    except Exception:  # pragma: no cover - la auditoría no debe romper el flujo
        logger.exception("No se pudo registrar el uso del LLM externo")


__all__ = [
    "ConfiguracionLLM",
    "ExternalLLMProvider",
    "LLMProvider",
    "LocalLLMProvider",
    "ResultadoLLM",
    "configuracion_llm_desde_entorno",
    "crear_proveedor",
    "es_endpoint_local",
    "generar_resumen_llm",
]
