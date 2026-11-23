[Català](../../ca/admin/uploaded-files-compression.md) | [Castellano](uploaded-files-compression.md) | [English](../../en/admin/uploaded-files-compression.md)

---

# Compresión automática de los ficheros subidos

EMS reduce el peso de los PDF y de las imágenes (JPG, PNG) que se suben, para que los escaneos y las fotos de móvil no llenen el servidor. Ocurre solo, en segundo plano, unos segundos después de la subida: nadie tiene que hacer nada.

**Rol necesario:** ninguno (automático). El ajuste de abajo es para el Administrador.

---

## Qué ocurre

- El fichero se guarda tal como se ha subido y se puede abrir enseguida. En unos segundos o un minuto, EMS lo sustituye por una copia más ligera si así se ahorra al menos un 10 %. El original **no** se conserva.
- Los PDF se vuelven a guardar con calidad de pantalla (150 ppp): siguen siendo perfectamente legibles e imprimibles, pero las imágenes que llevan dentro pesan mucho menos.
- Las imágenes se ponen en vertical, se reducen a un máximo de 1920 píxeles en el lado largo y se guardan como JPG con la misma nitidez a simple vista. Un PNG sin transparencia pasa a JPG (su nombre acaba en `.jpg`). Se eliminan los datos ocultos de la foto (como el lugar donde la hizo el móvil).

## Qué no se cambia nunca

- Los PDF con **firma digital** y los PDF protegidos (cifrados): modificarlos invalidaría la firma.
- Los ficheros de menos de 300 kB y cualquier fichero cuya versión comprimida no sea al menos un 10 % más pequeña.
- Los documentos que genera EMS (registros de calidad aprobados, informes) y las plantillas de Erasmus+.

> La compresión se introdujo en la versión 18.0.0.51.0. Los ficheros subidos antes no se modifican.

## Ajuste

En **Ajustes → Técnico → Parámetros del sistema**, el parámetro `ems.compress_min_kb` (por defecto `300`) es el tamaño mínimo en kB a partir del cual se comprime un fichero.

Si el servidor no tiene Ghostscript instalado, los PDF se dejan como se subieron y solo se comprimen las imágenes.
