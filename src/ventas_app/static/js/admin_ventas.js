"use strict";

(() => {
  const csrf =
    document.querySelector('meta[name="csrf-token"]')?.content || "";
  const dialogo = document.querySelector("#admin-venta-dialog");
  if (!dialogo) {
    return;
  }

  const titulo = document.querySelector("#admin-venta-titulo");
  const mensaje = document.querySelector("#admin-venta-mensaje");
  const motivo = document.querySelector("#admin-venta-motivo");
  const error = document.querySelector("#admin-venta-error");
  const cancelar = document.querySelector("#admin-venta-cancelar");
  const confirmar = document.querySelector("#admin-venta-confirmar");
  let accionActual = null;
  let ventaActual = null;

  function abrir(boton) {
    accionActual = boton.dataset.adminVenta;
    ventaActual = {
      id: boton.dataset.ventaId,
      version: Number(boton.dataset.version),
      reabrir: accionActual === "reabrir",
    };
    if (!accionActual || !ventaActual.id || !Number.isInteger(ventaActual.version)) {
      return;
    }
    titulo.textContent = ventaActual.reabrir
      ? "Editar venta aprobada"
      : "Eliminar venta";
    mensaje.textContent = ventaActual.reabrir
      ? "Esta venta está aprobada. Al reabrirla volverá a Pendiente y requerirá una nueva auditoría."
      : "La venta se dará de baja lógica. Se conservarán la fila y todo el historial de auditoría.";
    motivo.value = "";
    error.textContent = "";
    error.classList.add("hidden");
    dialogo.showModal();
    motivo.focus();
  }

  async function confirmarAccion() {
    const texto = motivo.value.trim();
    if (texto.length < 5) {
      error.textContent = "El motivo debe tener al menos 5 caracteres.";
      error.classList.remove("hidden");
      motivo.focus();
      return;
    }
    confirmar.disabled = true;
    try {
      const respuesta = await fetch(
        ventaActual.reabrir
          ? `/api/ventas/${ventaActual.id}/reabrir`
          : `/api/ventas/${ventaActual.id}`,
        {
          method: ventaActual.reabrir ? "POST" : "DELETE",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
          },
          body: JSON.stringify({
            motivo: texto,
            version: ventaActual.version,
          }),
        },
      );
      if (!respuesta.ok) {
        const datos = await respuesta.json().catch(() => ({}));
        error.textContent =
          typeof datos.detail === "string"
            ? datos.detail
            : "No se pudo completar la acción.";
        error.classList.remove("hidden");
        return;
      }
      dialogo.close();
      window.location.href = ventaActual.reabrir
        ? `/ventas/${ventaActual.id}/editar`
        : "/ventas";
    } catch (_error) {
      error.textContent = "No se pudo conectar con el servidor.";
      error.classList.remove("hidden");
    } finally {
      confirmar.disabled = false;
    }
  }

  document.querySelectorAll("[data-admin-venta]").forEach((boton) => {
    boton.addEventListener("click", () => abrir(boton));
  });
  cancelar.addEventListener("click", () => dialogo.close());
  confirmar.addEventListener("click", confirmarAccion);
})();
