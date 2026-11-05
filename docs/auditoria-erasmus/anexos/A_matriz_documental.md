# Anexo A. Matriz documental por defecto (generada desde el código)

> Generada el 2026-10-25 ejecutando en la copia aislada `ems_auditoria` el script `int_scripts/audit_document_matrix.py`, que crea (y deshace) una convocatoria de alumnos, una de personal y lee `EmsErasmusGroupMobility._ems_default_requirements()`. Refleja los **valores por defecto** de `EmsErasmusCall._ems_preparation_documents()`, `_ems_staff_documents()` y `_ems_default_requirements()` en el commit `7b99cfaf`. Cada convocatoria o movilidad de grupo puede editar su lista después: lo que exige cada expediente real es lo que tenga configurado su convocatoria o movilidad.

Estado: **IMPLEMENTADO** (valores por defecto verificados ejecutando el código).

## A.1 Convocatoria de alumnos (prácticas, KA121-VET y KA131-HED)

Puntuación mínima por defecto: 50.0. Carta de compromiso por defecto: sí (anexo 3).

| # | Etapa | Documento | Requisito | Proyecto | Gestión | Firmantes | Confidencial | Categoría del expediente | Plazo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Antes de salir | European Health Insurance Card | Obligatorio | Ambos | Participante sube | — | **Sí** | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 2 | Antes de salir | OLS certificate | Obligatorio | Ambos | Participante sube | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días tras fijar destino |
| 3 | Antes de salir | Inclusion documentation | Opcional | Ambos | Participante sube | — | **Sí** | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 4 | Antes de salir | Family authorisation to travel | Obligatorio si menor | Ambos | Participante sube | legal guardian | No | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 5 | Antes de salir | Authorisation for minors to travel abroad | Obligatorio si menor | Ambos | Participante sube | — | No | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 6 | Antes de salir | Grant agreement | Obligatorio | Ambos | Equipo prepara, participante firma y sube | participant, legal guardian, director | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 7 | Antes de salir | Learning agreement | Obligatorio | Ambos | Equipo prepara, participante firma y sube | participant, legal guardian, Erasmus coordinator, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 8 | Antes de salir | sBID agreement (REF5) | Obligatorio si FCT curricular (sBID) | Ambos | Equipo aporta | participant, director, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 9 | Antes de salir | sBID activity plan (REF6) | Obligatorio si FCT curricular (sBID) | Ambos | Equipo aporta | participant, centre's tutor, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 10 | Antes de salir | Insurance policy | Obligatorio | Ambos | Equipo aporta | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 11 | Antes de salir | Virtual component | Solo movilidad corta combinada (KA131, ≤30 días) | KA131-HED | Participante sube | — | No | 02_Abans_de_la_mobilitat (por etapa) | 1 día antes de salir; se abre 30 días antes de salir |
| 12 | Al regreso | Certificate of stay | Obligatorio | Ambos | Equipo prepara, participante firma y sube | host entity | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 13 | Al regreso | Europass mobility document | Obligatorio | KA121-VET | Equipo aporta | Erasmus coordinator | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 14 | Al regreso | Recognition of ECTS credits | Obligatorio si FCT curricular (sBID) | KA131-HED | Equipo aporta | — | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 15 | Al regreso | Tickets or boarding passes | Opcional | Ambos | Participante sube | — | No | 03_Durant_la_mobilitat | 30 días tras regresar |

Checklist (pasos sin documento, marcados por el equipo):

| Etapa | Paso | Requisito | Proyecto |
|---|---|---|---|
| Antes de salir | Preparation sessions | Obligatorio | Ambos |
| Al regreso | Final report (EU Survey) | Obligatorio | Ambos |
| Al regreso | Dissemination activities | Obligatorio | Ambos |

Autoevaluación semanal por defecto: «What did you do this week?» (texto); «What have you learned?» (texto); «How do you rate your week?» (valoración 1-5); «What was hardest for you, and what would you improve?» (texto).

## A.2 Convocatoria de personal (KA121-VET y KA131-HED)

Puntuación mínima por defecto: 0.0. Carta de compromiso por defecto: no.

Modalidades creadas por defecto: FP staff (KA121-VET) (KA121-VET); Higher education staff (KA131-HED) (KA131-HED).

| # | Etapa | Documento | Requisito | Proyecto | Gestión | Firmantes | Confidencial | Categoría del expediente | Plazo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Solicitud | Identity document | Obligatorio | Ambos | Participante sube | — | No | 01_Dades_i_autoritzacions (por etapa) | — |
| 2 | Solicitud | Europass CV in English | Obligatorio | Ambos | Participante sube | — | No | 01_Dades_i_autoritzacions (por etapa) | — |
| 3 | Solicitud | Language certificates | Opcional | Ambos | Participante sube | — | No | 01_Dades_i_autoritzacions (por etapa) | — |
| 4 | Antes de salir | European Health Insurance Card | Obligatorio | Ambos | Participante sube | — | **Sí** | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 5 | Antes de salir | Grant agreement | Obligatorio | Ambos | Equipo prepara, participante firma y sube | participant, director | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 6 | Antes de salir | Insurance policy | Obligatorio | Ambos | Equipo aporta | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 7 | Antes de salir | Learning agreement | Obligatorio | KA121-VET | Participante sube | participant, Erasmus coordinator, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 8 | Antes de salir | Mobility agreement | Obligatorio | KA131-HED | Participante sube | participant, Erasmus coordinator, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 9 | Al regreso | Certificate of stay or attendance | Obligatorio | KA131-HED | Participante sube | host entity | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 10 | Al regreso | Certificate of stay or attendance | Opcional | KA121-VET | Participante sube | host entity | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 11 | Al regreso | Europass mobility document | Obligatorio | KA121-VET | Equipo aporta | Erasmus coordinator | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 12 | Al regreso | Tickets or boarding passes | Opcional | Ambos | Participante sube | — | No | 03_Durant_la_mobilitat | 30 días tras regresar |
| 13 | Al regreso | Report with evidence | Obligatorio | Ambos | Participante sube | participant | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |

Checklist (pasos sin documento, marcados por el equipo):

| Etapa | Paso | Requisito | Proyecto |
|---|---|---|---|
| Antes de salir | Preparation meetings | Obligatorio | Ambos |
| Antes de salir | Activities left for your groups | Obligatorio | Ambos |
| Al regreso | Final report (EU Survey) | Obligatorio | Ambos |
| Al regreso | News item on the centre's website, following the Erasmus+ visual identity | Obligatorio | Ambos |
| Al regreso | Share it at a department or cycles meeting, if it is considered necessary | Obligatorio | Ambos |

Autoevaluación semanal: ninguna pregunta por defecto (el equipo puede añadirlas).

## A.3 Movilidad de grupo (KA121-VET)

| # | Etapa | Para | Documento | Requisito | Gestión | Firmantes | Confidencial | Categoría | Plazo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Antes de salir | Grupo (compartido) | Group learning agreement | Obligatorio | Equipo aporta | Erasmus coordinator, host entity | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 2 | Antes de salir | Grupo (compartido) | Final list of participants and accompanying teachers | Obligatorio | Equipo aporta | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 3 | Antes de salir | Grupo (compartido) | Agreements with the host entity | Opcional | Equipo aporta | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días tras fijar destino |
| 4 | Antes de salir | Grupo (compartido) | Group travel documents | Opcional | Equipo aporta | — | No | 03_Durant_la_mobilitat | 30 días tras fijar destino |
| 5 | Antes de salir | Grupo (compartido) | Group inclusion documentation | Opcional | Equipo aporta | — | **Sí** | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 6 | Al regreso | Grupo (compartido) | Common evidence of the stay | Opcional | Equipo aporta | — | No | 03_Durant_la_mobilitat | 30 días tras regresar |
| 7 | Antes de salir | Todos los participantes | Grant agreement | Obligatorio | Equipo prepara, participante firma y sube | participant, legal guardian, director | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 8 | Antes de salir | Cada alumno | European Health Insurance Card | Obligatorio | Participante sube | — | **Sí** | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 9 | Antes de salir | Cada alumno | Authorisation for minors to travel abroad | Obligatorio si menor | Participante sube | — | No | 01_Dades_i_autoritzacions | 30 días tras fijar destino |
| 10 | Antes de salir | Cada alumno | Insurance policy | Obligatorio | Equipo aporta | — | No | 02_Abans_de_la_mobilitat (por etapa) | 30 días antes de salir |
| 11 | Al regreso | Cada alumno | Europass mobility document | Obligatorio | Equipo aporta | Erasmus coordinator | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 12 | Al regreso | Cada docente | Certificate of stay | Obligatorio | Participante sube | host entity | No | 04_Despres_de_la_mobilitat (por etapa) | 30 días tras regresar |
| 13 | Antes de salir | Cada docente | Travel and accommodation documents | Opcional | Participante sube | — | No | 03_Durant_la_mobilitat | 30 días tras fijar destino |

Además, para cada alumno seleccionado: la carta de compromiso aceptada en el portal (y por la familia si es menor), que no es una línea documental sino un registro de `ems.erasmus.commitment` (ver [09_compromiso_familias.md](../09_compromiso_familias.md)).

