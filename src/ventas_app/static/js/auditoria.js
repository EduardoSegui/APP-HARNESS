"use strict";

(() => {
  const boton = document.querySelector("#btn-auditar");
  if (!boton) {
    return;
  }

  const CSRF_TOKEN =
    document.querySelector('meta[name="csrf-token"]')?.content || "";

  const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)");

  const textoBoton = document.querySelector("#btn-auditar-texto");
  const spinner = document.querySelector("#spinner-auditoria");
  const estado = document.querySelector("#auditoria-estado");
  const panel = document.querySelector("#panel-auditoria");
  const procesadas = document.querySelector("#auditoria-procesadas");
  const aprobadas = document.querySelector("#auditoria-aprobadas");
  const observadas = document.querySelector("#auditoria-observadas");
  const narrativa = document.querySelector("#auditoria-narrativa");
  const advertencia = document.querySelector("#auditoria-advertencia");
  const llmEstado = document.querySelector("#auditoria-llm-estado");
  const trazaBody = document.querySelector("#traza-mcp-body");

  const etiquetasEstado = {
    PENDIENTE_VERIFICACION: "Pendiente",
    APROBADA: "Aprobada",
    OBSERVADA: "Observada",
  };

  function mostrarCargando() {
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
    textoBoton.textContent = "Auditando pendientes...";
    spinner.classList.remove("hidden");
    estado.textContent =
      "Consultando ventas pendientes y ejecutando reglas R1–R6 vía MCP...";
    estado.className = "audit-status";
  }

  function restaurarBoton() {
    boton.disabled = false;
    boton.removeAttribute("aria-busy");
    textoBoton.textContent = "Auditar Pendientes con IA";
    spinner.classList.add("hidden");
  }

  function crearCelda(texto, clase) {
    const celda = document.createElement("td");
    celda.className = clase;
    celda.textContent = texto;
    return celda;
  }

  function renderizarTraza(traza) {
    trazaBody.replaceChildren();

    if (!Array.isArray(traza) || traza.length === 0) {
      const fila = document.createElement("tr");
      const celda = crearCelda(
        "Sin invocaciones MCP registradas.",
        "trace-table__empty",
      );
      celda.colSpan = 4;
      fila.appendChild(celda);
      trazaBody.appendChild(fila);
      return;
    }

    traza.forEach((paso, indice) => {
      const fila = document.createElement("tr");

      fila.appendChild(
        crearCelda(String(indice + 1), "trace-table__index"),
      );
      fila.appendChild(
        crearCelda(
          String(paso.herramienta || "desconocida"),
          "trace-table__tool",
        ),
      );

      let argumentos = "{}";
      try {
        argumentos = JSON.stringify(paso.argumentos ?? {});
      } catch (_error) {
        argumentos = "{}";
      }
      const celdaArgumentos = crearCelda(
        argumentos,
        "trace-table__args",
      );
      celdaArgumentos.title = argumentos;
      fila.appendChild(celdaArgumentos);

      const estadoPaso = String(paso.estado || "desconocido");
      const celdaEstado = crearCelda(
        estadoPaso,
        estadoPaso === "ok"
          ? "trace-table__status trace-table__status--ok"
          : "trace-table__status trace-table__status--error",
      );
      fila.appendChild(celdaEstado);
      trazaBody.appendChild(fila);
    });
  }

  function actualizarObservaciones(celda, estadoVenta, observaciones) {
    celda.replaceChildren();

    if (observaciones) {
      const detalle = document.createElement("span");
      detalle.className = "whitespace-pre-line";
      detalle.textContent = observaciones;
      celda.appendChild(detalle);
      return;
    }

    const detalle = document.createElement("span");
    if (estadoVenta === "APROBADA") {
      detalle.className = "observation--ok";
      detalle.textContent = "Sin observaciones";
    } else if (estadoVenta === "PENDIENTE_VERIFICACION") {
      detalle.className = "observation--pending";
      detalle.textContent = "Pendiente de auditoría";
    } else {
      detalle.className = "observation--muted";
      detalle.textContent = "—";
    }
    celda.appendChild(detalle);
  }

  function actualizarTabla(traza) {
    if (!Array.isArray(traza)) {
      return;
    }

    traza.forEach((paso) => {
      if (
        paso.herramienta !== "actualizar_estado_venta" ||
        paso.estado !== "ok"
      ) {
        return;
      }

      const argumentos = paso.argumentos || {};
      const fila = document.getElementById(`venta-${argumentos.venta_id}`);
      if (!fila) {
        return;
      }

      const badge = fila.querySelector("[data-estado]");
      if (badge) {
        const estadoVenta = String(argumentos.estado || "");
        badge.dataset.estado = estadoVenta;
        badge.textContent = etiquetasEstado[estadoVenta] ?? estadoVenta;
        badge.className = "stamp";
      }

      const celdaObservaciones = fila.querySelector("[data-observaciones]");
      if (celdaObservaciones) {
        actualizarObservaciones(
          celdaObservaciones,
          String(argumentos.estado || ""),
          argumentos.observaciones,
        );
      }
    });
  }

  function renderizarResultado(datos) {
    procesadas.textContent = String(datos.procesadas ?? 0);
    aprobadas.textContent = String(datos.aprobadas ?? 0);
    observadas.textContent = String(datos.observadas ?? 0);

    narrativa.textContent =
      datos.resumen_llm ||
      "El LLM no generó un resumen narrativo; revisá la advertencia.";

    llmEstado.textContent = datos.llm_ok
      ? "LLM OK"
      : "LLM no disponible";
    llmEstado.className = datos.llm_ok
      ? "llm-badge llm-badge--ok"
      : "llm-badge llm-badge--warn";

    advertencia.textContent = datos.advertencia || "";
    advertencia.classList.toggle("hidden", !datos.advertencia);

    renderizarTraza(datos.traza_mcp);
    actualizarTabla(datos.traza_mcp);

    panel.classList.remove("hidden");
    panel.open = true;
    panel.scrollIntoView({
      behavior: movimientoReducido.matches ? "auto" : "smooth",
      block: "nearest",
    });

    estado.textContent =
      `Auditoría finalizada: ${datos.procesadas ?? 0} procesadas, ` +
      `${datos.aprobadas ?? 0} aprobadas y ${datos.observadas ?? 0} observadas.`;
    estado.className = "audit-status audit-status--ok";
  }

  async function auditarPendientes() {
    mostrarCargando();

    try {
      const respuesta = await fetch("/api/auditar", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-CSRF-Token": CSRF_TOKEN,
        },
      });
      let datos = {};
      try {
        datos = await respuesta.json();
      } catch (_error) {
        datos = {};
      }

      if (!respuesta.ok) {
        throw new Error(
          datos.detail || `No se pudo auditar (HTTP ${respuesta.status}).`,
        );
      }

      renderizarResultado(datos);
    } catch (error) {
      panel.classList.remove("hidden");
      panel.open = true;
      advertencia.textContent =
        error instanceof Error
          ? error.message
          : "No se pudo completar la auditoría.";
      advertencia.classList.remove("hidden");
      estado.textContent = "La auditoría no pudo completarse.";
      estado.className = "audit-status audit-status--error";
    } finally {
      restaurarBoton();
    }
  }

  boton.addEventListener("click", auditarPendientes);
})();
