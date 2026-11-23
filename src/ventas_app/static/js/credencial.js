"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const boton = document.querySelector("#btn-imprimir-credencial");
  if (!boton) {
    return;
  }
  boton.addEventListener("click", () => {
    window.print();
  });
});
