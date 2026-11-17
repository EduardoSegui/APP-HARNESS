"use strict";

(() => {
  const boton = document.querySelector("#btn-auditar");
  if (!boton) {
    return;
  }

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

  const clasesEstado = {
    PENDIENTE_VERIFICACION:
      "inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-200",
    APROBADA:
      "inline-flex rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800 ring-1 ring-inset ring-green-200",
    OBSERVADA:
      "inline-flex rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-800 ring-1 ring-inset ring-red-200",
  };

  function mostrarCargando() {
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
    textoBoton.textContent = "Auditando pendientes...";
    spinner.classList.remove("hidden");
    estado.textContent =
      "Consultando ventas pendientes y ejecutando reglas R1–R6 vía MCP...";
    estado.className = "mt-3 min-h-5 text-sm text-slate-500";
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
        "px-3 py-3 text-slate-500",
      );
      celda.colSpan = 4;
      fila.appendChild(celda);
      trazaBody.appendChild(fila);
      return;
    }

    traza.forEach((paso, indice) => {
      const fila = document.createElement("tr");

      fila.appendChild(
        crearCelda(String(indice + 1), "px-3 py-2 text-slate-500"),
      );
      fila.appendChild(
        crearCelda(
          String(paso.herramienta || "desconocida"),
          "whitespace-nowrap px-3 py-2 font-mono text-slate-800",
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
        "max-w-md break-all px-3 py-2 font-mono text-slate-600",
      );
      celdaArgumentos.title = argumentos;
      fila.appendChild(celdaArgumentos);

      const estadoPaso = String(paso.estado || "desconocido");
      const celdaEstado = crearCelda(
        estadoPaso,
        estadoPaso === "ok"
          ? "whitespace-nowrap px-3 py-2 font-semibold text-green-700"
          : "whitespace-nowrap px-3 py-2 font-semibold text-red-700",
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
      detalle.className = "text-green-700";
      detalle.textContent = "Sin observaciones";
    } else if (estadoVenta === "PENDIENTE_VERIFICACION") {
      detalle.className = "text-amber-700";
      detalle.textContent = "Pendiente de auditoría";
    } else {
      detalle.className = "text-slate-400";
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
        badge.textContent = estadoVenta;
        badge.className =
          clasesEstado[estadoVenta] ||
          "inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-inset ring-slate-200";
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
      ? "rounded-full bg-green-100 px-2.5 py-1 text-xs font-semibold text-green-800"
      : "rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800";

    advertencia.textContent = datos.advertencia || "";
    advertencia.classList.toggle("hidden", !datos.advertencia);

    renderizarTraza(datos.traza_mcp);
    actualizarTabla(datos.traza_mcp);

    panel.classList.remove("hidden");
    panel.open = true;
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });

    estado.textContent =
      `Auditoría finalizada: ${datos.procesadas ?? 0} procesadas, ` +
      `${datos.aprobadas ?? 0} aprobadas y ${datos.observadas ?? 0} observadas.`;
    estado.className = "mt-3 min-h-5 text-sm text-green-700";
  }

  async function auditarPendientes() {
    mostrarCargando();

    try {
      const respuesta = await fetch("/api/auditar", {
        method: "POST",
        headers: { Accept: "application/json" },
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
      estado.className = "mt-3 min-h-5 text-sm text-red-700";
    } finally {
      restaurarBoton();
    }
  }

  boton.addEventListener("click", auditarPendientes);
})();
