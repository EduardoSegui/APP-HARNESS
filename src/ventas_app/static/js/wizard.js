"use strict";

(() => {
  const STORAGE_KEY = "ventas-obra-social.wizard.v1";
  const HOY_ISO = fechaLocalISO();
  const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)");
  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const TELEFONO_REGEX = /^[0-9+\s()\-]+$/;
  const ALTURA_REGEX = /^[0-9A-Za-z/ .-]+$/;
  const DNI_REGEX = /^\d{7,8}$/;
  const CP_REGEX = /^\d{4}$/;
  const formatoMoneda = new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  });

  function fechaLocalISO() {
    const ahora = new Date();
    const local = new Date(ahora.getTime() - ahora.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 10);
  }

  const formWizard = document.querySelector("#wizard");
  const progreso = document.querySelector("#progreso");
  const pasos = Array.from(document.querySelectorAll("[data-paso]"));
  const indicadores = Array.from(document.querySelectorAll("[data-indicador]"));
  const errorGeneral = document.querySelector("#error-general");
  const comprobante = document.querySelector("#comprobante");
  const contenedorIntegrantes = document.querySelector("#integrantes-container");
  const plantillaIntegrante = document.querySelector("#template-integrante");
  const sinIntegrantes = document.querySelector("#sin-integrantes");
  const btnAgregar = document.querySelector("#btn-agregar-integrante");
  const btnConfirmar = document.querySelector("#btn-confirmar");
  const pageHead = document.querySelector("#wizard-page-head");
  const resumenLegajo = document.querySelector("#resumen-legajo");
  const legajoTitular = document.querySelector("#legajo-titular");
  const legajoIntegrantes = document.querySelector("#legajo-integrantes");
  const legajoPlan = document.querySelector("#legajo-plan");
  const legajoMedioPago = document.querySelector("#legajo-medio-pago");
  const comprobanteEstado = document.querySelector("#comprobante-estado");

  const estadoInicial = {
    paso: 1,
    titular: {
      nombre: "",
      apellido: "",
      dni: "",
      fecha_nacimiento: "",
      email: "",
      telefono: "",
    },
    integrantes: [],
    domicilio: {
      calle: "",
      altura: "",
      piso_depto: "",
      localidad: "",
      provincia: "",
      codigo_postal: "",
    },
    plan_id: null,
    medio_pago: null,
  };

  const clonar = (valor) => JSON.parse(JSON.stringify(valor));
  const texto = (valor) => (typeof valor === "string" ? valor : "");
  let secuenciaIntegrante = Date.now();

  function nuevoIdIntegrante() {
    secuenciaIntegrante += 1;
    return `tmp-${secuenciaIntegrante}`;
  }

  let estado = cargarEstado();

  function normalizarIntegrante(dato) {
    return {
      _id: texto(dato?._id) || nuevoIdIntegrante(),
      nombre: texto(dato?.nombre),
      apellido: texto(dato?.apellido),
      dni: texto(dato?.dni),
      fecha_nacimiento: texto(dato?.fecha_nacimiento),
      parentesco: texto(dato?.parentesco),
    };
  }

  function cargarEstado() {
    const base = clonar(estadoInicial);

    try {
      const guardado = sessionStorage.getItem(STORAGE_KEY);
      if (!guardado) {
        return base;
      }

      const datos = JSON.parse(guardado);
      const paso = Number(datos?.paso);
      const planId = Number(datos?.plan_id);
      const titular = datos?.titular ?? {};
      const domicilio = datos?.domicilio ?? {};

      return {
        ...base,
        paso: [1, 2, 3].includes(paso) ? paso : 1,
        titular: Object.fromEntries(
          Object.keys(base.titular).map((clave) => [clave, texto(titular[clave])]),
        ),
        domicilio: Object.fromEntries(
          Object.keys(base.domicilio).map((clave) => [clave, texto(domicilio[clave])]),
        ),
        integrantes: Array.isArray(datos?.integrantes)
          ? datos.integrantes.map(normalizarIntegrante)
          : [],
        plan_id: Number.isInteger(planId) && planId > 0 ? planId : null,
        medio_pago: typeof datos?.medio_pago === "string" ? datos.medio_pago : null,
      };
    } catch (_error) {
      return base;
    }
  }

  function guardarEstado() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(estado));
    } catch (_error) {
      // Si el almacenamiento no está disponible, el wizard sigue funcionando en memoria.
    }
  }

  function valorEn(objeto, ruta) {
    return ruta.split(".").reduce((actual, clave) => actual?.[clave], objeto);
  }

  function escribirEn(objeto, ruta, valor) {
    const claves = ruta.split(".");
    const ultima = claves.pop();
    const destino = claves.reduce((actual, clave) => actual[clave], objeto);
    destino[ultima] = valor;
  }

  function inicializarCampos() {
    document.querySelectorAll("[data-state]").forEach((campo) => {
      campo.value = valorEn(estado, campo.dataset.state) ?? "";
      const evento = campo.tagName === "SELECT" ? "change" : "input";

      campo.addEventListener(evento, () => {
        escribirEn(estado, campo.dataset.state, campo.value);
        guardarEstado();
        actualizarCotizacion();
      });
    });
  }

  function actualizarContador() {
    const contador = document.querySelector("#contador-integrantes");
    if (contador) {
      contador.textContent = String(estado.integrantes.length);
    }
  }

  function crearIntegranteVacio() {
    return {
      _id: nuevoIdIntegrante(),
      nombre: "",
      apellido: "",
      dni: "",
      fecha_nacimiento: "",
      parentesco: "",
    };
  }

  function renderizarIntegrantes() {
    contenedorIntegrantes.replaceChildren();

    estado.integrantes.forEach((integrante, indice) => {
      const fragmento = plantillaIntegrante.content.cloneNode(true);
      const tarjeta = fragmento.querySelector("[data-integrante]");
      tarjeta.dataset.index = String(indice);
      fragmento.querySelector("[data-numero]").textContent = String(indice + 1);

      fragmento.querySelectorAll("[data-campo]").forEach((campo) => {
        const clave = campo.dataset.campo;
        campo.value = integrante[clave] ?? "";
        const evento = campo.tagName === "SELECT" ? "change" : "input";

        campo.addEventListener(evento, () => {
          integrante[clave] = campo.value;
          guardarEstado();
          actualizarCotizacion();
        });
      });

      fragmento.querySelector("[data-eliminar]").addEventListener("click", () => {
        estado.integrantes.splice(indice, 1);
        guardarEstado();
        renderizarIntegrantes();
        actualizarCotizacion();
      });

      contenedorIntegrantes.appendChild(fragmento);
    });

    sinIntegrantes.classList.toggle("hidden", estado.integrantes.length > 0);
    actualizarContador();
  }

  function inicializarPlanes() {
    const radios = Array.from(document.querySelectorAll('input[name="plan_id"]'));

    radios.forEach((radio) => {
      if (estado.plan_id !== null && String(estado.plan_id) === radio.value) {
        radio.checked = true;
      }

      const fila = radio.closest(".plan-row");
      if (fila) {
        fila.classList.toggle("is-selected", radio.checked);
      }

      radio.addEventListener("change", () => {
        if (!radio.checked) {
          return;
        }
        estado.plan_id = Number(radio.value);
        radios.forEach((otro) => {
          otro.closest(".plan-row")?.classList.toggle(
            "is-selected",
            otro === radio,
          );
        });
        guardarEstado();
        actualizarCotizacion();
      });
    });

    if (!radios.some((radio) => radio.checked)) {
      estado.plan_id = null;
      guardarEstado();
    }
  }

  function inicializarMediosPago() {
    const radios = Array.from(document.querySelectorAll('input[name="medio_pago"]'));

    radios.forEach((radio) => {
      if (estado.medio_pago !== null && String(estado.medio_pago) === radio.value) {
        radio.checked = true;
      }

      const fila = radio.closest(".plan-row");
      if (fila) {
        fila.classList.toggle("is-selected", radio.checked);
      }

      radio.addEventListener("change", () => {
        if (!radio.checked) {
          return;
        }
        estado.medio_pago = radio.value;
        radios.forEach((otro) => {
          otro.closest(".plan-row")?.classList.toggle(
            "is-selected",
            otro === radio,
          );
        });
        guardarEstado();
        actualizarCotizacion();
      });
    });

    if (!radios.some((radio) => radio.checked)) {
      estado.medio_pago = null;
      guardarEstado();
    }
  }

  function actualizarResumen() {
    const nombre = [
      texto(estado.titular.nombre).trim(),
      texto(estado.titular.apellido).trim(),
    ]
      .filter(Boolean)
      .join(" ");
    const cantidad = estado.integrantes.length;
    const planSeleccionado = document.querySelector('input[name="plan_id"]:checked');
    const medioSeleccionado = document.querySelector('input[name="medio_pago"]:checked');

    if (legajoTitular) {
      legajoTitular.textContent = nombre || "Titular sin cargar";
    }

    if (legajoIntegrantes) {
      legajoIntegrantes.textContent =
        `${cantidad} ${cantidad === 1 ? "adherente" : "adherentes"}`;
    }

    if (legajoPlan) {
      const nombrePlan = planSeleccionado
        ?.closest(".plan-row")
        ?.querySelector(".plan-row__name")
        ?.textContent?.trim();
      legajoPlan.textContent = nombrePlan || "Plan sin elegir";
    }

    if (legajoMedioPago) {
      const nombreMedio = medioSeleccionado
        ?.closest(".plan-row")
        ?.querySelector(".plan-row__name")
        ?.textContent?.trim();
      legajoMedioPago.textContent = nombreMedio || "Sin seleccionar";
    }
  }

  function actualizarCotizacion() {
    const cantidad = estado.integrantes.length;
    const cantidadEl = document.querySelector("#cotizacion-cantidad");
    const titularEl = document.querySelector("#cotizacion-titular");
    const subtotalEl = document.querySelector("#cotizacion-subtotal");
    const baseEl = document.querySelector("#cotizacion-base");
    const filaDescuentoEl = document.querySelector("#fila-descuento");
    const descuentoPctEl = document.querySelector("#cotizacion-descuento-pct");
    const descuentoEl = document.querySelector("#cotizacion-descuento");
    const totalEl = document.querySelector("#cotizacion-total");
    const planSeleccionado = document.querySelector('input[name="plan_id"]:checked');
    const medioSeleccionado = document.querySelector('input[name="medio_pago"]:checked');

    actualizarContador();
    actualizarResumen();

    if (cantidadEl) {
      cantidadEl.textContent = String(cantidad);
    }

    if (!planSeleccionado) {
      if (titularEl) titularEl.textContent = "—";
      if (subtotalEl) subtotalEl.textContent = "—";
      if (baseEl) baseEl.textContent = "—";
      if (filaDescuentoEl) filaDescuentoEl.classList.add("hidden");
      if (totalEl) totalEl.textContent = "—";
      btnConfirmar.disabled = true;
      return;
    }

    const precioTitular = Number(planSeleccionado.dataset.precioTitular);
    const precioAdherente = Number(planSeleccionado.dataset.precioAdherente);
    const subtotalAdherentes = cantidad * precioAdherente;
    const subtotalBase = precioTitular + subtotalAdherentes;

    if (titularEl) titularEl.textContent = formatoMoneda.format(precioTitular);
    if (subtotalEl) subtotalEl.textContent = `${formatoMoneda.format(subtotalAdherentes)} (${cantidad} × ${formatoMoneda.format(precioAdherente)})`;
    if (baseEl) baseEl.textContent = formatoMoneda.format(subtotalBase);

    const descuentoPct = medioSeleccionado ? Number(medioSeleccionado.dataset.descuento || 0) : 0;
    const descuentoMonto = Math.round(subtotalBase * (descuentoPct / 100));
    const total = subtotalBase - descuentoMonto;

    if (descuentoPct > 0 && filaDescuentoEl) {
      filaDescuentoEl.classList.remove("hidden");
      if (descuentoPctEl) descuentoPctEl.textContent = `${descuentoPct}% OFF`;
      if (descuentoEl) descuentoEl.textContent = `- ${formatoMoneda.format(descuentoMonto)}`;
    } else if (filaDescuentoEl) {
      filaDescuentoEl.classList.add("hidden");
    }

    if (totalEl) {
      totalEl.textContent = formatoMoneda.format(total);
    }

    btnConfirmar.disabled = !planSeleccionado || !medioSeleccionado;
  }

  function mostrarErrorGeneral(mensaje) {
    errorGeneral.textContent = mensaje;
    errorGeneral.classList.remove("hidden");
  }

  function ocultarErrorGeneral() {
    errorGeneral.textContent = "";
    errorGeneral.classList.add("hidden");
  }

  function limpiarErrores() {
    document.querySelectorAll(".error-campo").forEach((nodo) => nodo.remove());
    document.querySelectorAll(".campo-invalido").forEach((campo) => {
      campo.classList.remove("campo-invalido");
    });
    ocultarErrorGeneral();
  }

  function registrarError(campo, mensaje, errores) {
    if (campo) {
      campo.classList.add("campo-invalido");
      const error = document.createElement("p");
      error.className = "error-campo";
      error.textContent = mensaje;
      campo.insertAdjacentElement("afterend", error);
    }
    errores.push(mensaje);
  }

  function validarPaso(paso) {
    limpiarErrores();
    const errores = [];

    if (paso === 1) {
      const titular = estado.titular;
      const nombre = document.querySelector("#titular-nombre");
      const apellido = document.querySelector("#titular-apellido");
      const dni = document.querySelector("#titular-dni");
      const fecha = document.querySelector("#titular-fecha-nacimiento");
      const email = document.querySelector("#titular-email");
      const telefono = document.querySelector("#titular-telefono");

      if (texto(titular.nombre).trim().length < 2) {
        registrarError(nombre, "Ingresá el nombre del titular (mínimo 2 caracteres).", errores);
      }
      if (texto(titular.apellido).trim().length < 2) {
        registrarError(apellido, "Ingresá el apellido del titular (mínimo 2 caracteres).", errores);
      }
      if (!DNI_REGEX.test(texto(titular.dni).trim())) {
        registrarError(dni, "El DNI debe tener 7 u 8 dígitos, sin puntos ni espacios.", errores);
      }
      if (!texto(titular.fecha_nacimiento)) {
        registrarError(fecha, "Ingresá la fecha de nacimiento del titular.", errores);
      } else if (texto(titular.fecha_nacimiento) > HOY_ISO) {
        registrarError(fecha, "La fecha de nacimiento no puede ser futura.", errores);
      }
      if (!EMAIL_REGEX.test(texto(titular.email).trim())) {
        registrarError(email, "Ingresá un email válido.", errores);
      }
      if (
        !TELEFONO_REGEX.test(texto(titular.telefono).trim()) ||
        texto(titular.telefono).replace(/\D/g, "").length < 6
      ) {
        registrarError(telefono, "Ingresá un teléfono válido con al menos 6 dígitos.", errores);
      }

      estado.integrantes.forEach((integrante, indice) => {
        const tarjeta = contenedorIntegrantes.querySelector(
          `[data-integrante][data-index="${indice}"]`,
        );
        const campo = (nombreCampo) =>
          tarjeta?.querySelector(`[data-campo="${nombreCampo}"]`) ?? null;
        const numero = indice + 1;

        if (texto(integrante.nombre).trim().length < 2) {
          registrarError(campo("nombre"), `Ingresá el nombre del adherente ${numero}.`, errores);
        }
        if (texto(integrante.apellido).trim().length < 2) {
          registrarError(campo("apellido"), `Ingresá el apellido del adherente ${numero}.`, errores);
        }
        if (!DNI_REGEX.test(texto(integrante.dni).trim())) {
          registrarError(
            campo("dni"),
            `El DNI del adherente ${numero} debe tener 7 u 8 dígitos.`,
            errores,
          );
        }
        if (!texto(integrante.fecha_nacimiento)) {
          registrarError(
            campo("fecha_nacimiento"),
            `Ingresá la fecha de nacimiento del adherente ${numero}.`,
            errores,
          );
        } else if (texto(integrante.fecha_nacimiento) > HOY_ISO) {
          registrarError(
            campo("fecha_nacimiento"),
            `La fecha de nacimiento del adherente ${numero} no puede ser futura.`,
            errores,
          );
        }
        if (!texto(integrante.parentesco).trim()) {
          registrarError(campo("parentesco"), `Seleccioná el parentesco del adherente ${numero}.`, errores);
        }
      });

      const dnis = [
        texto(titular.dni).trim(),
        ...estado.integrantes.map((integrante) => texto(integrante.dni).trim()),
      ].filter(Boolean);
      if (new Set(dnis).size !== dnis.length) {
        registrarError(null, "Los DNIs del grupo familiar deben ser únicos.", errores);
      }
    }

    if (paso === 2) {
      const domicilio = estado.domicilio;
      const calle = document.querySelector("#domicilio-calle");
      const altura = document.querySelector("#domicilio-altura");
      const piso = document.querySelector("#domicilio-piso-depto");
      const localidad = document.querySelector("#domicilio-localidad");
      const provincia = document.querySelector("#domicilio-provincia");
      const codigoPostal = document.querySelector("#domicilio-codigo-postal");

      if (texto(domicilio.calle).trim().length < 2) {
        registrarError(calle, "Ingresá la calle (mínimo 2 caracteres).", errores);
      }
      if (
        texto(domicilio.altura).trim().length < 1 ||
        texto(domicilio.altura).trim().length > 10 ||
        !ALTURA_REGEX.test(texto(domicilio.altura).trim())
      ) {
        registrarError(altura, "Ingresá una altura válida (hasta 10 caracteres).", errores);
      }
      if (texto(domicilio.piso_depto).trim().length > 30) {
        registrarError(piso, "El piso/departamento admite hasta 30 caracteres.", errores);
      }
      if (texto(domicilio.localidad).trim().length < 2) {
        registrarError(localidad, "Ingresá la localidad (mínimo 2 caracteres).", errores);
      }
      if (texto(domicilio.provincia).trim().length < 2) {
        registrarError(provincia, "Seleccioná una provincia.", errores);
      }
      if (!CP_REGEX.test(texto(domicilio.codigo_postal).trim())) {
        registrarError(codigoPostal, "El código postal debe tener exactamente 4 dígitos.", errores);
      }
    }

    if (paso === 3) {
      if (!document.querySelector('input[name="plan_id"]:checked')) {
        registrarError(null, "Seleccioná un plan para confirmar la venta.", errores);
      }
      if (!document.querySelector('input[name="medio_pago"]:checked')) {
        registrarError(null, "Seleccioná un medio de pago para confirmar la venta.", errores);
      }
    }

    if (errores.length > 0) {
      mostrarErrorGeneral(errores.join(" "));
      document.querySelector(".campo-invalido")?.focus();
      return false;
    }

    ocultarErrorGeneral();
    return true;
  }

  function mostrarPaso() {
    pasos.forEach((seccion) => {
      seccion.classList.toggle("hidden", Number(seccion.dataset.paso) !== estado.paso);
    });

    const pasoActual = document.querySelector("#paso-actual");
    if (pasoActual) {
      pasoActual.textContent = String(estado.paso);
    }

    indicadores.forEach((indicador) => {
      const numero = Number(indicador.dataset.indicador);
      if (numero === estado.paso) {
        indicador.dataset.estado = "activo";
        indicador.setAttribute("aria-current", "step");
      } else {
        indicador.dataset.estado = numero < estado.paso ? "completado" : "pendiente";
        indicador.removeAttribute("aria-current");
      }
    });

    actualizarCotizacion();
    window.scrollTo({
      top: 0,
      behavior: movimientoReducido.matches ? "auto" : "smooth",
    });
  }

  function avanzar(paso) {
    if (!validarPaso(estado.paso)) {
      return;
    }
    estado.paso = paso;
    guardarEstado();
    mostrarPaso();
  }

  function retroceder(paso) {
    estado.paso = paso;
    guardarEstado();
    mostrarPaso();
  }

  function construirPayload() {
    const titular = estado.titular;
    const domicilio = estado.domicilio;

    return {
      nombre_titular: texto(titular.nombre).trim(),
      apellido_titular: texto(titular.apellido).trim(),
      dni_titular: texto(titular.dni).trim(),
      fecha_nacimiento_titular: texto(titular.fecha_nacimiento),
      email: texto(titular.email).trim(),
      telefono: texto(titular.telefono).trim(),
      calle: texto(domicilio.calle).trim(),
      altura: texto(domicilio.altura).trim(),
      piso_depto: texto(domicilio.piso_depto).trim() || null,
      localidad: texto(domicilio.localidad).trim(),
      provincia: texto(domicilio.provincia).trim(),
      codigo_postal: texto(domicilio.codigo_postal).trim(),
      plan_id: Number(estado.plan_id),
      medio_pago: estado.medio_pago,
      integrantes: estado.integrantes.map((integrante) => ({
        nombre: texto(integrante.nombre).trim(),
        apellido: texto(integrante.apellido).trim(),
        dni: texto(integrante.dni).trim(),
        fecha_nacimiento: texto(integrante.fecha_nacimiento),
        parentesco: texto(integrante.parentesco),
      })),
    };
  }

  function mensajeDeError(estadoHttp, datos) {
    const detalle = datos?.detail;

    if (typeof detalle === "string") {
      return detalle;
    }

    if (Array.isArray(detalle)) {
      const mensajes = detalle.map((item) => {
        const ubicacion = Array.isArray(item.loc)
          ? item.loc.filter((parte) => parte !== "body").join(".")
          : "";
        const mensaje = item.msg || "Dato inválido.";
        return ubicacion ? `${ubicacion}: ${mensaje}` : mensaje;
      });
      return mensajes.join(" · ");
    }

    return `No se pudo registrar la venta (HTTP ${estadoHttp}).`;
  }

  const etiquetasEstado = {
    PENDIENTE_VERIFICACION: "Pendiente",
    APROBADA: "Aprobada",
    OBSERVADA: "Observada",
  };

  function formatearFecha(valor) {
    const fecha = new Date(valor);
    if (Number.isNaN(fecha.getTime())) {
      return "—";
    }
    return fecha.toLocaleString("es-AR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  function mostrarComprobante(venta) {
    const plan = venta.plan ?? {};
    const cantidadAdherentes = Array.isArray(venta.integrantes) ? venta.integrantes.length : 0;

    const etiquetasMedio = {
      TARJETA_CREDITO: "Tarjeta de crédito (30% de descuento)",
      CBU: "CBU / Débito automático (20% de descuento)",
      PAGO_FACIL: "Pago Fácil / Rapipago / Oficinas",
      COBRADOR_DOMICILIO: "Cobrador a domicilio",
    };
    const medioPagoEl = document.querySelector("#comprobante-medio-pago");
    if (medioPagoEl) {
      medioPagoEl.textContent = etiquetasMedio[venta.medio_pago] || venta.medio_pago || "—";
    }

    const subtotalBaseEl = document.querySelector("#comprobante-subtotal-base");
    if (subtotalBaseEl) {
      subtotalBaseEl.textContent = formatoMoneda.format(venta.subtotal_base || venta.precio_total);
    }

    const filaDescuentoEl = document.querySelector("#comprobante-fila-descuento");
    const descuentoEl = document.querySelector("#comprobante-descuento");
    if (venta.descuento_porcentaje > 0 && filaDescuentoEl && descuentoEl) {
      const montoDescuento = (venta.subtotal_base || venta.precio_total) - venta.precio_total;
      descuentoEl.textContent = `- ${formatoMoneda.format(montoDescuento)} (${venta.descuento_porcentaje}% OFF)`;
      filaDescuentoEl.classList.remove("hidden");
    } else if (filaDescuentoEl) {
      filaDescuentoEl.classList.add("hidden");
    }

    document.querySelector("#comprobante-id").textContent = `#${venta.id}`;
    if (comprobanteEstado) {
      comprobanteEstado.textContent = etiquetasEstado[venta.estado] ?? venta.estado;
      comprobanteEstado.dataset.estado = venta.estado;
    }
    document.querySelector("#comprobante-titular").textContent =
      `${venta.nombre_titular} ${venta.apellido_titular}`;
    document.querySelector("#comprobante-plan").textContent = plan.nombre ?? "—";
    document.querySelector("#comprobante-fecha").textContent = formatearFecha(venta.creado_en);
    document.querySelector("#comprobante-adherentes").textContent = String(cantidadAdherentes);
    document.querySelector("#comprobante-desglose").textContent =
      `${formatoMoneda.format(plan.precio_titular ?? 0)} + ${cantidadAdherentes} × ${formatoMoneda.format(plan.precio_adherente ?? 0)}`;
    document.querySelector("#comprobante-total").textContent = formatoMoneda.format(venta.precio_total);

    pageHead?.classList.add("hidden");
    progreso.classList.add("hidden");
    resumenLegajo?.classList.add("hidden");
    formWizard.classList.add("hidden");
    ocultarErrorGeneral();
    comprobante.classList.remove("hidden");
    window.scrollTo({
      top: 0,
      behavior: movimientoReducido.matches ? "auto" : "smooth",
    });
  }

  async function confirmarVenta() {
    for (const paso of [1, 2, 3]) {
      if (!validarPaso(paso)) {
        estado.paso = paso;
        guardarEstado();
        mostrarPaso();
        document.querySelector(".campo-invalido")?.focus();
        return;
      }
    }

    const payload = construirPayload();
    const textoBoton = btnConfirmar.textContent;

    btnConfirmar.disabled = true;
    btnConfirmar.textContent = "Guardando...";

    try {
      const respuesta = await fetch("/api/ventas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const datos = await respuesta.json().catch(() => ({}));

      if (!respuesta.ok) {
        mostrarErrorGeneral(mensajeDeError(respuesta.status, datos));
        return;
      }

      sessionStorage.removeItem(STORAGE_KEY);
      mostrarComprobante(datos);
    } catch (_error) {
      mostrarErrorGeneral(
        "No se pudo conectar con el servidor. Revisá la conexión e intentá nuevamente.",
      );
    } finally {
      btnConfirmar.textContent = textoBoton;
      actualizarCotizacion();
    }
  }

  btnAgregar.addEventListener("click", () => {
    estado.integrantes.push(crearIntegranteVacio());
    guardarEstado();
    renderizarIntegrantes();
    actualizarCotizacion();

    const tarjetas = contenedorIntegrantes.querySelectorAll("[data-integrante]");
    tarjetas[tarjetas.length - 1]?.querySelector('[data-campo="nombre"]')?.focus();
  });

  document.querySelector("#btn-siguiente-1").addEventListener("click", () => avanzar(2));
  document.querySelector("#btn-siguiente-2").addEventListener("click", () => avanzar(3));
  document.querySelector("#btn-volver-2").addEventListener("click", () => retroceder(1));
  document.querySelector("#btn-volver-3").addEventListener("click", () => retroceder(2));
  btnConfirmar.addEventListener("click", confirmarVenta);
  document.querySelector("#btn-nueva-venta").addEventListener("click", () => {
    sessionStorage.removeItem(STORAGE_KEY);
    window.location.reload();
  });

  formWizard.addEventListener("submit", (evento) => {
    evento.preventDefault();
  });

  inicializarCampos();
  renderizarIntegrantes();
  inicializarPlanes();
  inicializarMediosPago();
  mostrarPaso();
})();
