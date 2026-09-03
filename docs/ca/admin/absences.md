[Català](absences.md) | [Castellano](../../es/admin/absences.md) | [English](../../en/admin/absences.md)

---

# Configurar les absències del personal

**Rol necessari:** Administrador/a

---

## Els dos paràmetres

**Ajustos > EMS > Configuració d'absències del personal**:

| Paràmetre | Per defecte | Què fa |
|---|---|---|
| Absència de dia sencer | 7:30 | Hores que val una absència de dia sencer. Sempre compta aquestes hores, tingui la persona les classes que tingui programades aquell dia |
| Crèdit d'hores per motius de salut | 15:00 | Hores d'absència per motius de salut que pot fer servir cada persona per curs |

El crèdit **avisa, no bloqueja**: qui el supera rep un avís i la sol·licitud queda marcada per al cap d'estudis, però es tramita igual.

---

## El catàleg de tipus d'absència

**Absències > Configuració > Tipus d'absència**. N'hi ha nou, i el nom de cadascun és el text complet del permís que es concedeix.

Cada tipus porta quatre indicadors que decideixen com surten proposades les sol·licituds noves:

| Indicador | Marcat a |
|---|---|
| Suma les hores a l'informe mensual | Tots menys `Baixa laboral` |
| Consumeix el crèdit de salut | Només `Salut` |
| Dia sencer per defecte | `Salut` i `Prova mèdica invasiva` |
| Es tramita per ATRI | Només `ATRI` |

Són **valors proposats**: el gestor de les absències els pot canviar sol·licitud a sol·licitud.

---

## Qui aprova

No es configura aquí. Surt de l'organigrama: l'aprovador de cada persona és **el responsable del seu departament de nivell superior**, que es defineix al formulari del departament (camp *Responsable d'àrea*).

Si les absències d'una àrea es queden sense aprovador, comprova que aquesta persona **tingui usuari a l'EMS**: l'aprovador ha de ser un usuari, no només una fitxa d'empleat.
