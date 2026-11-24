[Català](../../ca/admin/certificate-types.md) | [Castellano](certificate-types.md) | [English](../../en/admin/certificate-types.md)

---

# Tipos de certificado y circuitos de aprobación

Configura qué certificados puede pedir el alumnado, qué documentación exigen y quién hace cada paso hasta que se expiden.

**Rol necesario:** Administrador.

---

## Acceso

Navega a: **Gestión académica → Configuración → Certificados → Tipos de certificado**.

EMS ya incluye el tipo **FCT (Formació en Centres de Treball)**. Los cambios que hagas se mantienen al actualizar EMS.

![Tipo de certificado de FCT](../../assets/admin/certificats-07-tipus.png)

---

## Campos del tipo

- **Niveles que pueden pedirlo** — el alumnado actual de estos niveles puede pedirlo desde el portal, y la solicitud solo admite estudios de estos niveles. Si se deja vacío, el tipo no aparece en el portal y las solicitudes solo se registran desde secretaría.
- **Descripción** — el texto que lee la persona solicitante encima del formulario.

---

## Datos del certificado

Todos los certificados ya tienen el **nombre completo**, el **documento de identidad** y el **estudio** del alumno. En **Datos del certificado**, añade una línea por cada otro dato que necesite el certificado:

- **Detalle** — el nombre del dato, tal como lo leen la persona solicitante y el personal (por ejemplo, *Horas*).
- **Clave** — cómo lo escribe el texto del certificado, entre llaves: letras minúsculas, dígitos y `_` (por ejemplo, `horas`). No puede ser `name`, `document` ni `study`, que ya están cogidas. Si la cambia, el texto se actualiza en todos los idiomas.
- **Tipo de dato** — **Texto corto**, **Texto largo**, **Número** (puede tener decimales, como una nota media de 7,45), **Fecha**, **Sí/No**, **Curso escolar** (se escribe 2024-25 o 2024-2025, con años consecutivos, y se guarda como 2024-25; el formulario sugiere los cursos que tiene EMS) o **Empresa colaboradora** (la persona solicitante escribe su nombre y su NIF, y el centro vincula la empresa).
- **Solicitante** — **Obligatorio**: el formulario lo pide y hay que rellenarlo para enviar la solicitud; **Opcional**: el formulario lo pide; **No se pide**: solo lo rellena el centro.
- **Obligatorio antes de** — el paso del circuito que no se puede hacer hasta que esté rellenado (ni ninguno posterior). Déjalo vacío si el circuito nunca lo exige. Para elegir un paso, guarda primero el circuito.
- **Indicación** — qué hay que escribir y cómo, con un ejemplo (por ejemplo, *Formato AAAA-AA, por ejemplo 2024-25.*). La persona solicitante la lee bajo el dato, y el personal del centro, a su lado en la solicitud.
- **No anterior a** (columna opcional, solo para fechas) — otra fecha del tipo a la que no puede ser anterior: en la FCT, la fecha de finalización no puede ser anterior a la de inicio.

En una solicitud, el personal rellena estos datos en la pestaña **Datos del certificado**. Los que aún están vacíos y que exige el paso actual aparecen resaltados.

---

## Texto del certificado

**Texto del certificado** es lo que dice el certificado después de "CERTIFICA:". El encabezado con el nombre y el cargo de quien lo expide, el cierre, el lugar, la fecha y los sellos son iguales para todos los certificados.

- Escribe la clave de un dato entre llaves donde va su valor: `{horas}`. Bajo el texto están todas las claves que puedes usar. Un dato **Empresa colaboradora** también tiene el NIF: `{empresa_vat}` si la clave es `empresa`.
- Una parte entre corchetes solo se imprime cuando todos los datos que contiene tienen valor: `[, con NIF {empresa_vat}]`.
- Una línea en blanco empieza un párrafo nuevo.

El texto se traduce como los demás nombres: escríbelo en cada idioma con el selector de idioma del campo. EMS no deja guardar un texto que use una clave que el tipo no tiene.

Por ejemplo, el texto de FCT:

> Que {name}, con documento de identidad {document}, estudiante de {study}, realizó {hours} horas de formación en centros de trabajo (FCT) en el curso {school_year} en la empresa {company}[, con NIF {company_vat}], del {start} al {end}.

---

## Documentación adjunta obligatoria

Marca **Documentación adjunta obligatoria** y añade una línea por cada documento que se debe adjuntar antes de expedir el certificado:

- **Documento** — el nombre del documento (por ejemplo, *Convenio de FCT*).
- **Solicitante** — la persona solicitante puede adjuntarlo desde el portal o desde el enlace.
- **Cargos** — quien ocupa estos cargos puede adjuntarlo (solo se pueden elegir cargos del circuito).
- **Añadir al certificado** — las páginas del documento se añaden al final del PDF del certificado.

Si no se marca ni **Solicitante** ni ningún cargo, puede adjuntarlo cualquiera que participe. El administrador siempre puede adjuntarlo.

Además de los documentos obligatorios, cualquier solicitud admite **Otra documentación** opcional, que no se añade al certificado.

---

## Circuito de aprobación

Cada línea es un paso, por orden:

- **Nombre** — lo que ve quien tiene que hacer el paso.
- **Cargos** — uno o más cargos. Quien ocupa alguno de ellos recibe la tarea y puede hacer el paso; cuando uno lo hace, la tarea de los demás se cierra. Los cargos y quién los ocupa se configuran en [Cargos](teacher-roles.md).

Para dar un paso al personal de secretaría, añádale el cargo **Técnico/a de secretaría** y asigne ese cargo a cada una de esas personas. Quien lo ocupa también tiene acceso a la secretaría. El primer paso del tipo FCT ya lo lleva, junto con el coordinador de FP.
- **Acción**:
  - **Completar los datos** — completa la información y pasa la solicitud al paso siguiente.
  - **Expedir el certificado** — da el número al certificado y pone el sello de expedición.
  - **Aprobar** — pone el sello de visto bueno.

El circuito debe tener exactamente un paso **Expedir el certificado**, y los pasos **Aprobar** van después de este. El último paso genera el PDF y lo envía a la persona solicitante.

El administrador puede hacer cualquier paso de cualquier solicitud.
