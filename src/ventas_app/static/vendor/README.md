# Assets externos pineados

- `tailwindcss-3.4.17.js`: copia self-hosted de `https://cdn.tailwindcss.com/3.4.17`.
  Licencia MIT de Tailwind Labs.
- `../fonts/font-*.ttf`: Bricolage Grotesque y Public Sans, descargadas de
  Google Fonts (SIL Open Font License 1.1).

Los hashes SHA-256 están en `../ASSETS.lock` y se validan en la suite. Para
actualizar un asset: descargarlo, recalcular el hash, actualizar `ASSETS.lock` y
revisar CSP/regresión visual. No se carga ningún asset de CDN en runtime.
