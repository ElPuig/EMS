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

![Bloc de configuració d'absències del personal, amb els camps de dia sencer i crèdit de salut](../../assets/admin/admin-absences-settings.png)

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

## Festius i dies de tancament

**Absències > Configuració > Festius públics**. L'EMS no porta cap calendari de festius: s'han d'entrar tots a mà, un cop per curs:

- Els **nacionals** (1 de novembre, 6 i 8 de desembre, Nadal, Cap d'Any, Reis, Divendres Sant, 1 de maig...).
- Els **de Catalunya** (Dilluns de Pasqua, Sant Joan, l'11 de setembre, Sant Esteve...).
- Els **dos locals del municipi del centre**: els de la població on és l'institut, no els de Barcelona.
- Els **dies que el centre és tancat** encara que no siguin festius oficials: dies de lliure disposició, vacances de Nadal i de Setmana Santa, agost... Un període de diversos dies es pot entrar en una sola línia.

Cada festiu s'aplica **a tot el personal**, sigui quin sigui el seu horari. Cal posar-hi el nom i les dates d'inici i de fi (per a un dia sencer, de les 00:00 a les 23:59).

Entra'ls **abans** que arribin. Cada nit, l'EMS registra una absència sense justificar (un fitxatge en vermell, que compta com a hores en negatiu) a qui no va fitxar el dia anterior, tret que aquell dia no tingués hores previstes. Si un festiu s'entra tard, en desar-lo s'esborren sols els fitxatges en vermell d'aquells dies i les hores en negatiu corresponents. El mateix passa quan s'aprova tard una absència de dia sencer.

---

## Qui aprova

No es configura aquí. Surt de l'organigrama: l'aprovador de cada persona és **el responsable del seu departament de nivell superior**, que es defineix al formulari del departament (camp *Responsable d'àrea*).

Si les absències d'una àrea es queden sense aprovador, comprova que aquesta persona **tingui usuari a l'EMS**: l'aprovador ha de ser un usuari, no només una fitxa d'empleat.
