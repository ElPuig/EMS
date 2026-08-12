[Català](student-update-csv.md) | [Castellano](../../es/secretary/student-update-csv.md) | [English](../../en/secretary/student-update-csv.md)

---

# Actualitzar dades de l'alumnat des d'un CSV

Aquesta guia explica com actualitzar massivament camps de l'**alumnat ja matriculat** des de qualsevol fitxer CSV — sense estar lligat al format d'un sistema extern concret, a diferència de les importacions d'Esfera o GEDAC.

---

## Contingut

1. [Quan fer servir això en lloc de la importació d'Esfera](#quan-fer-servir-això-en-lloc-de-la-importació-desfera)
2. [Executar l'actualització](#executar-lactualització)
3. [Mapejar les columnes](#mapejar-les-columnes)
4. [Actualitzar el compte bancari](#actualitzar-el-compte-bancari)
5. [Llegir el resultat](#llegir-el-resultat)

---

## Quan fer servir això en lloc de la importació d'Esfera

Feu servir aquesta eina quan tingueu **qualsevol CSV** amb dades de l'alumnat per aplicar — per exemple, una llista corregida de telèfons/adreces, un fitxer rebut de manera informal — i no necessiteu (o no teniu) una exportació completa d'Esfera. **Només actualitza alumnat ja existent**: una fila l'ID de la qual no coincideixi amb ningú s'omet i queda reportada, mai s'utilitza per crear un alumne nou. Per a una actualització completa des del sistema oficial Esfera/SAGA (que també pot crear alumnat i contactes familiars nous), feu servir [Importar alumnat des d'Esfera (SAGA)](student-import-esfera.md).

## Executar l'actualització

Des de la llista d'**Alumnat**, obriu el menú d'accions (la icona de l'engranatge ⚙️) i trieu **Actualitzar alumnat des de CSV**. Pugeu el vostre fitxer i feu clic a **Carregar columnes**.

## Mapejar les columnes

Un cop carregades les columnes, primer trieu quina conté l'**identificador de l'alumne (IDALU/RALC)** — és obligatori, és com es fa coincidir cada fila amb un alumne. Després mapejeu tants o tan pocs dels altres camps com tingui realment el vostre fitxer (nom, telèfon, correu, adreça, documents…) — tot allò que quedi sense mapejar simplement no es toca.

## Actualitzar el compte bancari

Si mapegeu una columna d'**IBAN** i una fila té un valor, aquest esdevé el compte bancari actiu de l'alumne (qualsevol altre compte que tingués es desactiva). Deixeu l'IBAN sense mapejar, o deixeu la cel·la buida per a una fila concreta, i les seves dades bancàries queden intactes.

## Llegir el resultat

Després de fer clic a **Actualitzar alumnat**, veureu quants alumnes s'han actualitzat i quants IDs no s'han trobat, més qualsevol error a nivell de fila (per exemple, una data que no s'ha pogut interpretar). Un **CSV de resultat** descarregable — el vostre fitxer original amb una columna d'estat addicional — mostra exactament què ha passat amb cada fila, útil per a un fitxer gran.

---

[← Tornar a l'índex de Secretaria](index.md)
