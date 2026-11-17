"""Aplicación de carga de ventas de obra social."""

from ventas_app.config import cargar_entorno

# Se carga al importar el paquete para que la app, el auditor y los scripts
# compartan la misma configuración local.
cargar_entorno()

__version__ = "0.1.0"
