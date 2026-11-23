"use strict";

(() => {
  const STORAGE_KEY = "ventas-obra-social.wizard.v1";
  const CSRF_TOKEN =
    document.querySelector('meta[name="csrf-token"]')?.content || "";
  const HOY_ISO = fechaLocalISO();
  const movimientoReducido = window.matchMedia("(prefers-reduced-motion: reduce)");
  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const TELEFONO_REGEX = /^[0-9+\s()\-]+$/;
  const ALTURA_REGEX = /^[0-9A-Za-z/ .-]+$/;
  const DNI_REGEX = /^\d{7,8}$/;
  const CP_REGEX = /^\d{4}$/;
  const TARJETA_REGEX = /^\d{16}$/;
  const VENCIMIENTO_REGEX = /^(0[1-9]|1[0-2])\/\d{2}$/;
  const CVV_REGEX = /^\d{3,4}$/;
  const CBU_REGEX = /^\d{22}$/;
  const CUIL_REGEX = /^\d{11}$/;
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
  const legajoDDJJ = document.querySelector("#legajo-ddjj");
  const legajoRegimen = document.querySelector("#legajo-regimen");
  const comprobanteEstado = document.querySelector("#comprobante-estado");
  const edicion = cargarEdicion();
  const modoEdicion = Boolean(edicion);

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
    regimen_afiliacion: "PARTICULAR",
    cuil_titular: "",
    aporte_estimado: "",
    ddjj: {
      preexistencias: null,
      internaciones_ultimos_12m: null,
      embarazo_actual: null,
      medicacion_cronica: null,
      discapacidad_declarada: null,
      detalle: "",
      declaracion_confirmada: false,
    },
  };

  const clonar = (valor) => JSON.parse(JSON.stringify(valor));
  const texto = (valor) => (typeof valor === "string" ? valor : "");
  let secuenciaIntegrante = Date.now();

  function nuevoIdIntegrante() {
    secuenciaIntegrante += 1;
    return `tmp-${secuenciaIntegrante}`;
  }

  let estado = modoEdicion ? estadoDesdeVenta(edicion) : cargarEstado();

  function cargarEdicion() {
    const nodo = document.querySelector("#wizard-edicion-data");
    if (!nodo) {
      return null;
    }
    try {
      const datos = JSON.parse(nodo.textContent);
      return Number.isInteger(datos?.id) ? datos : null;
    } catch (_error) {
      return null;
    }
  }

  function estadoDesdeVenta(venta) {
    const base = clonar(estadoInicial);
    return {
      ...base,
      paso: 1,
      titular: {
        nombre: texto(venta.nombre_titular),
        apellido: texto(venta.apellido_titular),
        dni: texto(venta.dni_titular),
        fecha_nacimiento: texto(venta.fecha_nacimiento_titular),
        email: texto(venta.email),
        telefono: texto(venta.telefono),
      },
      domicilio: {
        calle: texto(venta.calle),
        altura: texto(venta.altura),
        piso_depto: texto(venta.piso_depto),
        localidad: texto(venta.localidad),
        provincia: texto(venta.provincia),
        codigo_postal: texto(venta.codigo_postal),
      },
      plan_id: Number.isInteger(Number(venta.plan_id)) ? Number(venta.plan_id) : null,
      medio_pago: texto(venta.medio_pago) || null,
      regimen_afiliacion: texto(venta.regimen_afiliacion) || "PARTICULAR",
      cuil_titular: texto(venta.cuil_titular),
      aporte_estimado:
        venta.aporte_estimado === null || venta.aporte_estimado === undefined
          ? ""
          : String(venta.aporte_estimado),
      integrantes: Array.isArray(venta.integrantes)
        ? venta.integrantes.map(normalizarIntegrante)
        : [],
      ddjj: {
        preexistencias: venta.ddjj_completada
          ? Boolean(venta.ddjj_preexistencias)
          : null,
        internaciones_ultimos_12m: venta.ddjj_completada
          ? Boolean(venta.ddjj_internaciones)
          : null,
        embarazo_actual: venta.ddjj_completada
          ? Boolean(venta.ddjj_embarazo)
          : null,
        medicacion_cronica: venta.ddjj_completada
          ? Boolean(venta.ddjj_medicacion_cronica)
          : null,
        discapacidad_declarada: venta.ddjj_completada
          ? Boolean(venta.ddjj_discapacidad)
          : null,
        detalle: texto(venta.ddjj_detalle),
        declaracion_confirmada: Boolean(venta.ddjj_completada),
      },
    };
  }

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

      // Compatibilidad segura: solo se restauran paso y plan. Los datos
      // personales, de salud y de pago nunca se persisten en el navegador.
      const datos = JSON.parse(guardado);
      const paso = Number(datos?.paso);
      const planId = Number(datos?.plan_id);
      const estadoSeguro = {
        ...base,
        paso: [1, 2, 3].includes(paso) ? paso : 1,
        plan_id: Number.isInteger(planId) && planId > 0 ? planId : null,
      };
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          paso: estadoSeguro.paso,
          plan_id: estadoSeguro.plan_id,
        }),
      );
      return estadoSeguro;
    } catch (_error) {
      return base;
    }
  }

  function guardarEstado() {
    if (modoEdicion) {
      return;
    }
    try {
      // Nunca se guardan PII, salud ni instrumentos de pago.
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          paso: estado.paso,
          plan_id: estado.plan_id,
        }),
      );
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
        actualizarFormularioPago();
        guardarEstado();
        actualizarCotizacion();
      });
    });

    if (!radios.some((radio) => radio.checked)) {
      estado.medio_pago = null;
      guardarEstado();
    }

    actualizarFormularioPago();
  }

  function limpiarFormularioPago(contenedor) {
    contenedor?.querySelectorAll("input, select").forEach((campo) => {
      campo.value = "";
    });
  }

  function actualizarFormularioPago() {
    const formularioTarjeta = document.querySelector("#pago-tarjeta");
    const formularioCbu = document.querySelector("#pago-cbu");
    const esTarjeta = estado.medio_pago === "TARJETA_CREDITO";
    const esCbu = estado.medio_pago === "CBU";

    formularioTarjeta?.classList.toggle("hidden", !esTarjeta);
    formularioCbu?.classList.toggle("hidden", !esCbu);

    if (!esTarjeta) {
      limpiarFormularioPago(formularioTarjeta);
    }
    if (!esCbu) {
      limpiarFormularioPago(formularioCbu);
    }

    actualizarInstrumentoActual();
  }

  function hayInstrumentoActual(medio) {
    return Boolean(
      modoEdicion
        && edicion?.medio_pago === medio
        && edicion?.pago_ultimos_4,
    );
  }

  function actualizarInstrumentoActual() {
    const tarjetaActual = document.querySelector("#pago-tarjeta-actual");
    const cbuActual = document.querySelector("#pago-cbu-actual");

    if (tarjetaActual) {
      if (hayInstrumentoActual("TARJETA_CREDITO")) {
        const vencimiento = edicion.pago_vencimiento
          ? ` · Vto ${edicion.pago_vencimiento}`
          : "";
        tarjetaActual.textContent =
          `Instrumento actual: ${edicion.pago_marca_entidad} •••• ${edicion.pago_ultimos_4}${vencimiento}. Dejá los campos vacíos para conservarlo.`;
        tarjetaActual.classList.remove("hidden");
      } else {
        tarjetaActual.classList.add("hidden");
      }
    }

    if (cbuActual) {
      if (hayInstrumentoActual("CBU")) {
        cbuActual.textContent =
          `Instrumento actual: ${edicion.pago_marca_entidad} · CBU •••• ${edicion.pago_ultimos_4} · CUIL ${edicion.pago_cuil}. Dejá los campos vacíos para conservarlo.`;
        cbuActual.classList.remove("hidden");
      } else {
        cbuActual.classList.add("hidden");
      }
    }
  }

  function datosTarjeta() {
    return {
      marca: document.querySelector("#tarjeta-marca")?.value ?? "",
      numero: texto(document.querySelector("#tarjeta-numero")?.value).trim(),
      titular: texto(document.querySelector("#tarjeta-titular")?.value).trim(),
      vencimiento: texto(document.querySelector("#tarjeta-vencimiento")?.value).trim(),
      cvv: texto(document.querySelector("#tarjeta-cvv")?.value).trim(),
    };
  }

  function datosCbu() {
    return {
      numero: texto(document.querySelector("#cbu-numero")?.value).trim(),
      entidad: texto(document.querySelector("#cbu-entidad")?.value).trim(),
      titular: texto(document.querySelector("#cbu-titular")?.value).trim(),
      cuil: texto(document.querySelector("#cbu-cuil")?.value).trim(),
    };
  }

  function formularioPagoVacio(tipo) {
    const datos = tipo === "TARJETA_CREDITO" ? datosTarjeta() : datosCbu();
    return Object.values(datos).every((valor) => !texto(valor).trim());
  }

  function vencimientoVencido(valor) {
    const coincidencia = VENCIMIENTO_REGEX.exec(valor);
    if (!coincidencia) {
      return false;
    }
    const hoy = new Date();
    const anio = 2000 + Number(coincidencia[2]);
    const mes = Number(coincidencia[1]);
    return anio < hoy.getFullYear() || (anio === hoy.getFullYear() && mes < hoy.getMonth() + 1);
  }

  function validarInstrumentoPago(errores) {
    if (estado.medio_pago === "TARJETA_CREDITO") {
      if (
        hayInstrumentoActual("TARJETA_CREDITO")
        && formularioPagoVacio("TARJETA_CREDITO")
      ) {
        return;
      }
      const marca = document.querySelector("#tarjeta-marca");
      const numero = document.querySelector("#tarjeta-numero");
      const titular = document.querySelector("#tarjeta-titular");
      const vencimiento = document.querySelector("#tarjeta-vencimiento");
      const cvv = document.querySelector("#tarjeta-cvv");

      if (!marca?.value) {
        registrarError(marca, "Seleccioná la marca de la tarjeta.", errores);
      }
      if (!TARJETA_REGEX.test(texto(numero?.value).trim())) {
        registrarError(numero, "El número de tarjeta debe tener 16 dígitos.", errores);
      }
      if (texto(titular?.value).trim().length < 2) {
        registrarError(titular, "Ingresá el titular de la tarjeta.", errores);
      }
      if (!VENCIMIENTO_REGEX.test(texto(vencimiento?.value).trim())) {
        registrarError(vencimiento, "El vencimiento debe tener formato MM/AA.", errores);
      } else if (vencimientoVencido(texto(vencimiento?.value).trim())) {
        registrarError(vencimiento, "La tarjeta está vencida.", errores);
      }
      if (!CVV_REGEX.test(texto(cvv?.value).trim())) {
        registrarError(cvv, "El CVV debe tener 3 o 4 dígitos.", errores);
      }
    }

    if (estado.medio_pago === "CBU") {
      if (
        hayInstrumentoActual("CBU")
        && formularioPagoVacio("CBU")
      ) {
        return;
      }
      const numero = document.querySelector("#cbu-numero");
      const entidad = document.querySelector("#cbu-entidad");
      const titular = document.querySelector("#cbu-titular");
      const cuil = document.querySelector("#cbu-cuil");

      if (!CBU_REGEX.test(texto(numero?.value).trim())) {
        registrarError(numero, "El CBU debe tener 22 dígitos.", errores);
      }
      if (texto(entidad?.value).trim().length < 2) {
        registrarError(entidad, "Ingresá el banco o entidad.", errores);
      }
      if (texto(titular?.value).trim().length < 2) {
        registrarError(titular, "Ingresá el titular de la cuenta.", errores);
      }
      if (!CUIL_REGEX.test(texto(cuil?.value).trim())) {
        registrarError(cuil, "El CUIL/CUIT debe tener 11 dígitos.", errores);
      }
    }
  }

  function inicializarValidacionPago() {
    const campos = document.querySelectorAll(
      "#pago-tarjeta input, #pago-tarjeta select, #pago-cbu input",
    );
    campos.forEach((campo) => {
      const evento = campo.tagName === "SELECT" ? "change" : "input";
      campo.addEventListener(evento, actualizarIndicadoresPaso);
    });
  }

  function ddjjConIndicadores() {
    return Boolean(
      estado.ddjj.preexistencias
        || estado.ddjj.internaciones_ultimos_12m
        || estado.ddjj.embarazo_actual
        || estado.ddjj.medicacion_cronica
        || estado.ddjj.discapacidad_declarada,
    );
  }

  function ddjjRequiereRevision() {
    return Boolean(
      estado.ddjj.preexistencias
        || estado.ddjj.internaciones_ultimos_12m
        || estado.ddjj.discapacidad_declarada,
    );
  }

  function ddjjCompleta() {
    return [
      estado.ddjj.preexistencias,
      estado.ddjj.internaciones_ultimos_12m,
      estado.ddjj.embarazo_actual,
      estado.ddjj.medicacion_cronica,
      estado.ddjj.discapacidad_declarada,
    ].every((valor) => typeof valor === "boolean");
  }

  function ddjjValida() {
    return Boolean(
      ddjjCompleta()
      && estado.ddjj.declaracion_confirmada
      && (
        !ddjjConIndicadores()
        || texto(estado.ddjj.detalle).trim().length >= 5
      ),
    );
  }

  function instrumentoPagoCompleto() {
    if (estado.medio_pago === "TARJETA_CREDITO") {
      if (
        hayInstrumentoActual("TARJETA_CREDITO")
        && formularioPagoVacio("TARJETA_CREDITO")
      ) {
        return true;
      }
      const datos = datosTarjeta();
      return Boolean(
        datos.marca
        && TARJETA_REGEX.test(datos.numero)
        && datos.titular.length >= 2
        && VENCIMIENTO_REGEX.test(datos.vencimiento)
        && !vencimientoVencido(datos.vencimiento)
        && CVV_REGEX.test(datos.cvv),
      );
    }
    if (estado.medio_pago === "CBU") {
      if (hayInstrumentoActual("CBU") && formularioPagoVacio("CBU")) {
        return true;
      }
      const datos = datosCbu();
      return Boolean(
        CBU_REGEX.test(datos.numero)
        && datos.entidad.length >= 2
        && datos.titular.length >= 2
        && CUIL_REGEX.test(datos.cuil),
      );
    }
    return Boolean(estado.medio_pago);
  }

  function pasoCompleto(paso) {
    if (paso === 1) {
      const titular = estado.titular;
      const telefono = texto(titular.telefono).trim();
      if (
        texto(titular.nombre).trim().length < 2
        || texto(titular.apellido).trim().length < 2
        || !DNI_REGEX.test(texto(titular.dni).trim())
        || !texto(titular.fecha_nacimiento)
        || texto(titular.fecha_nacimiento) > HOY_ISO
        || !EMAIL_REGEX.test(texto(titular.email).trim())
        || !TELEFONO_REGEX.test(telefono)
        || telefono.replace(/\D/g, "").length < 6
      ) {
        return false;
      }

      for (const integrante of estado.integrantes) {
        if (
          texto(integrante.nombre).trim().length < 2
          || texto(integrante.apellido).trim().length < 2
          || !DNI_REGEX.test(texto(integrante.dni).trim())
          || !texto(integrante.fecha_nacimiento)
          || texto(integrante.fecha_nacimiento) > HOY_ISO
          || !texto(integrante.parentesco).trim()
        ) {
          return false;
        }
      }

      const dnis = [
        texto(titular.dni).trim(),
        ...estado.integrantes.map((integrante) =>
          texto(integrante.dni).trim(),
        ),
      ].filter(Boolean);
      return new Set(dnis).size === dnis.length && ddjjValida();
    }

    if (paso === 2) {
      const domicilio = estado.domicilio;
      return Boolean(
        texto(domicilio.calle).trim().length >= 2
        && texto(domicilio.altura).trim().length >= 1
        && texto(domicilio.altura).trim().length <= 10
        && ALTURA_REGEX.test(texto(domicilio.altura).trim())
        && texto(domicilio.piso_depto).trim().length <= 30
        && texto(domicilio.localidad).trim().length >= 2
        && texto(domicilio.provincia).trim().length >= 2
        && CP_REGEX.test(texto(domicilio.codigo_postal).trim()),
      );
    }

    if (paso === 3) {
      if (!estado.plan_id || !estado.medio_pago) {
        return false;
      }
      if (!instrumentoPagoCompleto()) {
        return false;
      }
      if (estado.regimen_afiliacion !== "PARTICULAR") {
        if (!CUIL_REGEX.test(texto(estado.cuil_titular).trim())) {
          return false;
        }
        const aporte = Number(estado.aporte_estimado || 0);
        if (!Number.isInteger(aporte) || aporte < 0) {
          return false;
        }
        const base = baseBonificadaActual();
        if (base === null || aporte > base) {
          return false;
        }
      }
      return true;
    }

    return false;
  }

  function actualizarIndicadoresPaso() {
    indicadores.forEach((indicador) => {
      const numero = Number(indicador.dataset.indicador);
      const completo = pasoCompleto(numero);
      indicador.dataset.completo = completo ? "true" : "false";

      if (numero === estado.paso) {
        indicador.dataset.estado = "activo";
        indicador.setAttribute("aria-current", "step");
      } else {
        indicador.dataset.estado = completo ? "completado" : "pendiente";
        indicador.removeAttribute("aria-current");
      }
    });
  }

  function actualizarDDJJDetalle() {
    const hayIndicadores = ddjjConIndicadores();
    const requerido = document.querySelector("#ddjj-detalle-required");
    const detalle = document.querySelector("#ddjj-detalle");
    const hint = document.querySelector("#ddjj-detalle-hint");

    requerido?.classList.toggle("hidden", !hayIndicadores);
    if (detalle) {
      detalle.required = hayIndicadores;
    }
    if (hint) {
      hint.textContent = hayIndicadores
        ? "La descripción es obligatoria porque marcaste al menos un Sí."
        : "Si todas las respuestas son No, podés continuar sin descripción.";
    }
  }

  function actualizarFormularioRegimen() {
    const desregulado = estado.regimen_afiliacion !== "PARTICULAR";
    const wrap = document.querySelector("#regimen-aportes");
    wrap?.classList.toggle("hidden", !desregulado);

    if (!desregulado) {
      estado.aporte_estimado = "";
      const aporte = document.querySelector("#aporte-estimado");
      if (aporte) {
        aporte.value = "";
      }
    }
  }

  function baseBonificadaActual() {
    const plan = document.querySelector('input[name="plan_id"]:checked');
    const medio = document.querySelector('input[name="medio_pago"]:checked');
    if (!plan || !medio) {
      return null;
    }
    const subtotal =
      Number(plan.dataset.precioTitular)
      + Number(plan.dataset.precioAdherente) * estado.integrantes.length;
    const descuentoPct = Number(medio.dataset.descuento || 0);
    const descuentoMonto = Math.round(subtotal * (descuentoPct / 100));
    return Math.max(0, subtotal - descuentoMonto);
  }

  function inicializarDDJJ() {
    const campos = [
      ["ddjj-preexistencias", "preexistencias"],
      ["ddjj-internaciones", "internaciones_ultimos_12m"],
      ["ddjj-embarazo", "embarazo_actual"],
      ["ddjj-medicacion", "medicacion_cronica"],
      ["ddjj-discapacidad", "discapacidad_declarada"],
    ];

    campos.forEach(([nombre, clave]) => {
      const radios = Array.from(
        document.querySelectorAll(`input[name="${nombre}"]`),
      );
      radios.forEach((radio) => {
        if (estado.ddjj[clave] === true) {
          radio.checked = radio.value === "si";
        } else if (estado.ddjj[clave] === false) {
          radio.checked = radio.value === "no";
        }
        radio.addEventListener("change", () => {
          if (!radio.checked) {
            return;
          }
          estado.ddjj[clave] = radio.value === "si";
          guardarEstado();
          actualizarDDJJDetalle();
          actualizarResumen();
          actualizarIndicadoresPaso();
        });
      });
    });

    const detalle = document.querySelector("#ddjj-detalle");
    if (detalle) {
      detalle.value = estado.ddjj.detalle;
      detalle.addEventListener("input", () => {
        estado.ddjj.detalle = detalle.value;
        guardarEstado();
        actualizarIndicadoresPaso();
      });
    }

    const confirmada = document.querySelector("#ddjj-confirmada");
    if (confirmada) {
      confirmada.checked = Boolean(estado.ddjj.declaracion_confirmada);
      confirmada.addEventListener("change", () => {
        estado.ddjj.declaracion_confirmada = confirmada.checked;
        guardarEstado();
        actualizarResumen();
        actualizarIndicadoresPaso();
      });
    }

    actualizarDDJJDetalle();
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

    if (legajoDDJJ) {
      if (!ddjjCompleta()) {
        legajoDDJJ.textContent = "Pendiente";
      } else if (!estado.ddjj.declaracion_confirmada) {
        legajoDDJJ.textContent = "Sin confirmar";
      } else if (ddjjRequiereRevision()) {
        legajoDDJJ.textContent = "Revisión médica";
      } else {
        legajoDDJJ.textContent = "Completa";
      }
    }

    if (legajoRegimen) {
      const etiquetas = {
        PARTICULAR: "Particular",
        RELACION_DEPENDENCIA: "Rel. dependencia",
        MONOTRIBUTO: "Monotributo",
      };
      legajoRegimen.textContent =
        etiquetas[estado.regimen_afiliacion] || "Particular";
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
    const filaAporteEl = document.querySelector("#fila-aporte");
    const aporteEl = document.querySelector("#cotizacion-aporte");
    const totalEl = document.querySelector("#cotizacion-total");
    const planSeleccionado = document.querySelector('input[name="plan_id"]:checked');
    const medioSeleccionado = document.querySelector('input[name="medio_pago"]:checked');

    actualizarFormularioRegimen();
    actualizarContador();
    actualizarResumen();
    actualizarIndicadoresPaso();

    if (cantidadEl) {
      cantidadEl.textContent = String(cantidad);
    }

    if (!planSeleccionado) {
      if (titularEl) titularEl.textContent = "—";
      if (subtotalEl) subtotalEl.textContent = "—";
      if (baseEl) baseEl.textContent = "—";
      if (filaDescuentoEl) filaDescuentoEl.classList.add("hidden");
      if (filaAporteEl) filaAporteEl.classList.add("hidden");
      if (totalEl) totalEl.textContent = "—";
      btnConfirmar.disabled = !document.querySelector(
        'input[name="plan_id"]',
      );
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
    const baseBonificada = subtotalBase - descuentoMonto;
    const desregulado = estado.regimen_afiliacion !== "PARTICULAR";
    const aporte = desregulado
      ? Math.max(0, Number(estado.aporte_estimado) || 0)
      : 0;
    const total = Math.max(0, baseBonificada - aporte);

    if (descuentoPct > 0 && filaDescuentoEl) {
      filaDescuentoEl.classList.remove("hidden");
      if (descuentoPctEl) descuentoPctEl.textContent = `${descuentoPct}% OFF`;
      if (descuentoEl) descuentoEl.textContent = `- ${formatoMoneda.format(descuentoMonto)}`;
    } else if (filaDescuentoEl) {
      filaDescuentoEl.classList.add("hidden");
    }

    if (desregulado && filaAporteEl) {
      filaAporteEl.classList.remove("hidden");
      if (aporteEl) {
        aporteEl.textContent = aporte > 0
          ? `- ${formatoMoneda.format(aporte)}`
          : formatoMoneda.format(0);
      }
    } else if (filaAporteEl) {
      filaAporteEl.classList.add("hidden");
    }

    if (totalEl) {
      totalEl.textContent = formatoMoneda.format(total);
    }

    btnConfirmar.disabled = !document.querySelector('input[name="plan_id"]');
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

      const ddjjConfirmada = document.querySelector("#ddjj-confirmada");
      const ddjjDetalle = document.querySelector("#ddjj-detalle");
      if (!ddjjCompleta()) {
        registrarError(
          null,
          "Respondé Sí o No en las cinco preguntas de salud.",
          errores,
        );
      }
      if (!estado.ddjj.declaracion_confirmada) {
        registrarError(
          ddjjConfirmada,
          "Tenés que confirmar la declaración jurada de salud.",
          errores,
        );
      }
      if (
        ddjjConIndicadores()
        && texto(ddjjDetalle?.value).trim().length < 5
      ) {
        registrarError(
          ddjjDetalle,
          "Describí brevemente la situación de salud declarada.",
          errores,
        );
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
      } else {
        validarInstrumentoPago(errores);
      }

      const privacidad = document.querySelector("#privacidad-aceptada");
      if (!privacidad?.checked) {
        registrarError(
          privacidad,
          "Tenés que aceptar el aviso de privacidad para confirmar la venta.",
          errores,
        );
      }

      const regimen = document.querySelector("#regimen-afiliacion");
      const cuil = document.querySelector("#cuil-titular");
      const aporte = document.querySelector("#aporte-estimado");
      const regimenes = [
        "PARTICULAR",
        "RELACION_DEPENDENCIA",
        "MONOTRIBUTO",
      ];
      if (!regimenes.includes(estado.regimen_afiliacion)) {
        registrarError(regimen, "Seleccioná un régimen de afiliación.", errores);
      }

      if (estado.regimen_afiliacion !== "PARTICULAR") {
        if (!CUIL_REGEX.test(texto(cuil?.value).trim())) {
          registrarError(cuil, "El CUIL del titular debe tener 11 dígitos.", errores);
        }
        const valorAporte = Number(estado.aporte_estimado || 0);
        if (!Number.isInteger(valorAporte) || valorAporte < 0) {
          registrarError(aporte, "El aporte estimado debe ser un entero mayor o igual a 0.", errores);
        } else {
          const base = baseBonificadaActual();
          if (base !== null && valorAporte > base) {
            registrarError(aporte, "El aporte no puede superar la base bonificada.", errores);
          }
        }
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

    actualizarIndicadoresPaso();

    actualizarCotizacion();
    window.scrollTo({
      top: 0,
      behavior: movimientoReducido.matches ? "auto" : "smooth",
    });
  }

  function irAPaso(paso) {
    if (![1, 2, 3].includes(paso)) {
      return;
    }
    limpiarErrores();
    estado.paso = paso;
    guardarEstado();
    mostrarPaso();
  }

  function avanzar(paso) {
    irAPaso(paso);
  }

  function retroceder(paso) {
    irAPaso(paso);
  }

  function construirPayload() {
    const titular = estado.titular;
    const domicilio = estado.domicilio;
    const payload = {
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
      ddjj: {
        preexistencias: estado.ddjj.preexistencias === true,
        internaciones_ultimos_12m:
          estado.ddjj.internaciones_ultimos_12m === true,
        embarazo_actual: estado.ddjj.embarazo_actual === true,
        medicacion_cronica: estado.ddjj.medicacion_cronica === true,
        discapacidad_declarada: estado.ddjj.discapacidad_declarada === true,
        detalle: ddjjConIndicadores()
          ? texto(estado.ddjj.detalle).trim() || null
          : null,
        declaracion_confirmada: estado.ddjj.declaracion_confirmada,
      },
      regimen_afiliacion: estado.regimen_afiliacion || "PARTICULAR",
      consentimiento_privacidad: Boolean(
        document.querySelector("#privacidad-aceptada")?.checked,
      ),
      cuil_titular:
        estado.regimen_afiliacion === "PARTICULAR"
          ? null
          : texto(estado.cuil_titular).trim() || null,
      aporte_estimado:
        estado.regimen_afiliacion === "PARTICULAR"
          ? 0
          : Number(estado.aporte_estimado) || 0,
      integrantes: estado.integrantes.map((integrante) => ({
        nombre: texto(integrante.nombre).trim(),
        apellido: texto(integrante.apellido).trim(),
        dni: texto(integrante.dni).trim(),
        fecha_nacimiento: texto(integrante.fecha_nacimiento),
        parentesco: texto(integrante.parentesco),
      })),
    };

    if (modoEdicion && Number.isInteger(Number(edicion?.version))) {
      payload.version = Number(edicion.version);
    }

    if (estado.medio_pago === "TARJETA_CREDITO") {
      if (
        !hayInstrumentoActual("TARJETA_CREDITO")
        || !formularioPagoVacio("TARJETA_CREDITO")
      ) {
        payload.tarjeta = datosTarjeta();
      }
    } else if (estado.medio_pago === "CBU") {
      if (!hayInstrumentoActual("CBU") || !formularioPagoVacio("CBU")) {
        payload.cbu = datosCbu();
      }
    }

    return payload;
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

    const instrumentoEl = document.querySelector("#comprobante-instrumento");
    if (instrumentoEl) {
      if (venta.medio_pago === "TARJETA_CREDITO" && venta.pago_ultimos_4) {
        const vencimiento = venta.pago_vencimiento
          ? ` · Vto ${venta.pago_vencimiento}`
          : "";
        instrumentoEl.textContent = `${venta.pago_marca_entidad} •••• ${venta.pago_ultimos_4}${vencimiento}`;
      } else if (venta.medio_pago === "CBU" && venta.pago_ultimos_4) {
        const cuil = venta.pago_cuil ? ` · CUIL ${venta.pago_cuil}` : "";
        instrumentoEl.textContent = `${venta.pago_marca_entidad} · CBU •••• ${venta.pago_ultimos_4}${cuil}`;
      } else {
        instrumentoEl.textContent = "—";
      }
    }

    const ddjjEl = document.querySelector("#comprobante-ddjj");
    if (ddjjEl) {
      if (!venta.ddjj_completada) {
        ddjjEl.textContent = "Sin declaración";
      } else if (
        venta.ddjj_preexistencias
        || venta.ddjj_internaciones
        || venta.ddjj_discapacidad
      ) {
        ddjjEl.textContent = "Recibida · requiere revisión médica";
      } else {
        ddjjEl.textContent = "Recibida";
      }
    }

    const etiquetasRegimen = {
      PARTICULAR: "Particular",
      RELACION_DEPENDENCIA: "Relación de dependencia",
      MONOTRIBUTO: "Monotributo",
    };
    const regimenEl = document.querySelector("#comprobante-regimen");
    if (regimenEl) {
      regimenEl.textContent = etiquetasRegimen[venta.regimen_afiliacion] || venta.regimen_afiliacion || "—";
    }

    const filaCuilEl = document.querySelector("#comprobante-fila-cuil");
    const cuilEl = document.querySelector("#comprobante-cuil");
    if (filaCuilEl && cuilEl && venta.cuil_titular) {
      cuilEl.textContent = `${venta.cuil_titular.slice(0, 2)}••••••${venta.cuil_titular.slice(-2)}`;
      filaCuilEl.classList.remove("hidden");
    } else if (filaCuilEl) {
      filaCuilEl.classList.add("hidden");
    }

    const subtotalBaseEl = document.querySelector("#comprobante-subtotal-base");
    const subtotalBase = venta.subtotal_base || venta.precio_total;
    if (subtotalBaseEl) {
      subtotalBaseEl.textContent = formatoMoneda.format(subtotalBase);
    }

    const filaAporteEl = document.querySelector("#comprobante-fila-aporte");
    const aporteEl = document.querySelector("#comprobante-aporte");
    if (filaAporteEl && aporteEl && venta.aporte_estimado > 0) {
      aporteEl.textContent = `- ${formatoMoneda.format(venta.aporte_estimado)}`;
      filaAporteEl.classList.remove("hidden");
    } else if (filaAporteEl) {
      filaAporteEl.classList.add("hidden");
    }

    const filaDescuentoEl = document.querySelector("#comprobante-fila-descuento");
    const descuentoEl = document.querySelector("#comprobante-descuento");
    if (venta.descuento_porcentaje > 0 && filaDescuentoEl && descuentoEl) {
      const montoDescuento = Math.round(
        subtotalBase * (venta.descuento_porcentaje / 100),
      );
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
    document.querySelector("#wizard-sidebar")?.classList.add("hidden");
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
      const url = modoEdicion ? `/api/ventas/${edicion.id}` : "/api/ventas";
      const method = modoEdicion ? "PUT" : "POST";
      const respuesta = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": CSRF_TOKEN,
        },
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

  indicadores.forEach((indicador) => {
    const ir = () => irAPaso(Number(indicador.dataset.indicador));
    indicador.addEventListener("click", ir);
    indicador.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        ir();
      }
    });
  });

  document.querySelector("#btn-siguiente-1").addEventListener("click", () => avanzar(2));
  document.querySelector("#btn-siguiente-2").addEventListener("click", () => avanzar(3));
  document.querySelector("#btn-volver-2").addEventListener("click", () => retroceder(1));
  document.querySelector("#btn-volver-3").addEventListener("click", () => retroceder(2));
  btnConfirmar.addEventListener("click", confirmarVenta);
  document.querySelector("#btn-nueva-venta").addEventListener("click", () => {
    sessionStorage.removeItem(STORAGE_KEY);
    if (modoEdicion) {
      window.location.href = "/ventas";
      return;
    }
    window.location.reload();
  });

  formWizard.addEventListener("submit", (evento) => {
    evento.preventDefault();
  });

  if (modoEdicion) {
    const btnNuevaVenta = document.querySelector("#btn-nueva-venta");
    if (btnNuevaVenta) {
      btnNuevaVenta.textContent = "Volver al panel";
    }
  }

  inicializarDDJJ();
  inicializarCampos();
  inicializarValidacionPago();
  renderizarIntegrantes();
  inicializarPlanes();
  inicializarMediosPago();
  mostrarPaso();
})();
