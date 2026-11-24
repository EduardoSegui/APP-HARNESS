"use strict";

(() => {
  const csrf =
    document.querySelector('meta[name="csrf-token"]')?.content || "";

  async function ejecutar(boton) {
    const accion = boton.dataset.adminVenta;
    const ventaId = boton.dataset.ventaId;
    const version = Number(boton.dataset.version);
    if (!accion || !ventaId || !Number.isInteger(version)) {
      return;
    }

    const esReapertura = accion === "reabrir";
    const motivo = window.prompt(
      esReapertura
        ? "Esta venta está APROBADA. Editar la reabre y requerirá una nueva auditoría. Indicá el motivo:"
        : "La venta se dará de baja lógica; se conservará el historial. Indicá el motivo:",
    );
    if (motivo === null) {
      return;
    }
    if (motivo.trim().length < 5) {
      window.alert("El motivo debe tener al menos 5 caracteres.");
      return;
    }
    if (
      !window.confirm(
        esReapertura
          ? "¿Confirmás reabrir y volver a auditar esta venta?"
          : "¿Confirmás la baja lógica de esta venta?",
      )
    ) {
      return;
    }

    boton.disabled = true;
    try {
      const respuesta = await fetch(
        esReapertura
          ? `/api/ventas/${ventaId}/reabrir`
          : `/api/ventas/${ventaId}`,
        {
          method: esReapertura ? "POST" : "DELETE",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
          },
          body: JSON.stringify({ motivo: motivo.trim(), version }),
        },
      );
      if (!respuesta.ok) {
        const datos = await respuesta.json().catch(() => ({}));
        window.alert(
          typeof datos.detail === "string"
            ? datos.detail
            : "No se pudo completar la acción.",
        );
        return;
      }
      window.location.href = esReapertura
        ? `/ventas/${ventaId}/editar`
        : "/ventas";
    } catch (_error) {
      window.alert("No se pudo conectar con el servidor.");
    } finally {
      boton.disabled = false;
    }
  }

  document.querySelectorAll("[data-admin-venta]").forEach((boton) => {
    boton.addEventListener("click", () => ejecutar(boton));
  });
})();
