[Català](course-transition.md) | [Castellano](../../es/admin/course-transition.md) | [English](../../en/admin/course-transition.md)

---

# Preparar el curs següent

Al final del curs, una sola operació tanca el curs que acaba i obre el següent: **Configuració → EMS Management → Preparar el curs següent**.

Arxiva el curs que acaba, converteix en exalumnes els estudiants que ja estiguin marcats com a graduats i col·loca la resta al grup on s'han matriculat per al curs vinent.

> Aquest botó **només el veuen els administradors**, i part del que fa **no es pot desfer**. Llegeix aquesta pàgina abans d'utilitzar-lo.

---

## Abans de començar

Hi ha quatre coses que han d'estar resoltes. L'auxiliar comprova les tres primeres i es nega a executar-se si en falta alguna.

1. **El curs entrant existeix** i és diferent de l'actual.
2. **Les avaluacions estan tancades.** L'última convocatòria de cada grup de l'abast ha d'estar en estat *Finalitzada*. Si n'hi ha d'obertes, l'auxiliar te les llista; tanca-les des de **Notes → Canviar estat de sessió d'avaluació**.
3. **Cap graduat matriculat al curs següent.** Un alumne no pot marxar i tornar en la mateixa execució; o la marca de graduació o la matrícula és errònia.
4. **Una còpia de seguretat de la base de dades.** L'auxiliar et demana que confirmis que la tens, i no aplica res fins que marquis la casella.

Marca els alumnes que es graduen *abans*, amb l'auxiliar de graduació des de la llista d'alumnes. La transició no decideix qui es gradua: només executa marques que ja hi són.

---

## Estudi per estudi, no tot alhora

Els estudis no acaben alhora: un cicle formatiu pot estar tancat al juny mentre un nivell d'ESO encara avalua. Per això tries **quins estudis** vols transicionar, i pots executar l'auxiliar tantes vegades com calgui.

El **curs actual només canvia en l'execució que no deixa cap estudi pendent**. Fins llavors, tot el que hagis transicionat ja està fet i el centre continua treballant amb el curs sortint per a la resta. La previsualització sempre t'indica quin dels dos casos tens al davant.

---

## Pas 1 — Previsualització

Obre l'auxiliar, revisa el curs entrant i els estudis, i fes clic a **Previsualitzar**. No s'escriu res: és un assaig.

Obtindràs un quadre vermell si alguna cosa bloqueja l'execució, un quadre blau amb tot allò que val la pena saber, un panell de comptadors i la **llista d'alumnes un per un** amb l'acció que rebrà cadascun:

| Acció | Què significa |
|---|---|
| **Es gradua** | Marcat com a graduat: passa a exalumne i s'arxiva |
| **Col·locar al grup destí** | Té matrícula confirmada amb grup: s'hi trasllada |
| **Matriculat sense grup** | Matrícula confirmada sense grup destí: **se saltarà** |
| **Sense destí** | No té cap matrícula per al curs següent |

Dues d'aquestes mereixen la teva atenció:

- **Matriculat sense grup** — la matrícula existeix però ningú n'ha triat el grup, així que l'alumne es queda on és. Assigna'l (l'acció *Suggerir grup* t'ajuda) i torna a previsualitzar.
- **Sense destí** — l'alumne no s'ha matriculat. **No** se'l dona de baixa: simplement es queda sense grup. És deliberat, perquè al juliol no hi ha manera de distingir qui se'n va a un altre institut de qui es matricula tard. Guarda aquesta llista: és la que revisaràs després per decidir qui ha marxat de debò.

---

## Pas 2 — Aplicar

Marca **He fet una còpia de seguretat** i fes clic a **Aplicar la transició**. Se't demanarà una confirmació més.

Què passa, i en quin ordre:

1. Es congela **l'historial acadèmic** de tots els alumnes. Si això falla, no s'executa res més.
2. Els graduats passen a **exalumnes**, se'ls revoca l'accés al portal i **s'arxiven**.
3. S'arxiven les plantilles d'assistència del curs sortint.
4. **S'esborren els registres operatius**: inscripcions a mòduls, notes, assistència i sessions d'avaluació. Aquesta és la part irreversible — l'historial acadèmic desat al pas 1 és el que els substitueix.
5. Els alumnes es col·loquen al **grup destí** i s'hi inscriuen a les assignatures.
6. Es marquen els estudis com a transicionats i, si no en queda cap de pendent, **canvia el curs actual**.
7. Es tanquen les matrícules sortints: les confirmades es bloquegen (són un registre legal i no es cancel·len mai), les que mai es van confirmar es cancel·len.

---

## Després

L'auxiliar deixa un **registre amb la llista d'alumnes i el seu grup destí**, descarregable en acabar i també adjunt a la conversa de l'empresa. Guarda'l: és el que et permet desfer un cas concret a mà.

Dos serrells per resoldre els dies següents:

- **Alumnes sense destí.** Revisa la llista i registra la baixa dels que han marxat de debò, des de la fitxa de l'alumne. Els que es matriculin tard no necessiten res: en confirmar-se la matrícula, se'ls col·loca al grup automàticament.
- **Alumnes matriculats sense grup**, si vas aplicar sense resoldre'ls: assigna el grup i confirma; es col·loquen igual.

---

[← Tornar a l'índex d'administrador](index.md)
