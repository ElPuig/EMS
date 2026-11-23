[Català](uploaded-files-compression.md) | [Castellano](../../es/admin/uploaded-files-compression.md) | [English](../../en/admin/uploaded-files-compression.md)

---

# Compressió automàtica dels fitxers pujats

EMS redueix el pes dels PDF i de les imatges (JPG, PNG) que es pugen, perquè els escaneigs i les fotos de mòbil no omplin el servidor. Passa sol, en segon pla, uns segons després de la pujada: ningú no ha de fer res.

**Rol necessari:** cap (automàtic). L'ajust de sota és per a l'Administrador.

---

## Què passa

- El fitxer es desa tal com s'ha pujat i es pot obrir de seguida. En uns segons o un minut, EMS el substitueix per una còpia més lleugera si així s'estalvia almenys un 10 %. L'original **no** es conserva.
- Els PDF es tornen a desar amb qualitat de pantalla (150 ppp): continuen sent perfectament llegibles i imprimibles, però les imatges que porten a dins pesen molt menys.
- Les imatges es posen en vertical, es redueixen a un màxim de 1920 píxels al costat llarg i es desen com a JPG amb la mateixa nitidesa a simple vista. Un PNG sense transparència passa a JPG (el seu nom acaba en `.jpg`). S'eliminen les dades amagades de la foto (com el lloc on la va fer el mòbil).

## Què no es canvia mai

- Els PDF amb **signatura digital** i els PDF protegits (xifrats): modificar-los invalidaria la signatura.
- Els fitxers de menys de 300 kB i qualsevol fitxer la versió comprimida del qual no sigui almenys un 10 % més petita.
- Els documents que genera EMS (registres de qualitat aprovats, informes) i les plantilles d'Erasmus+.

> La compressió es va introduir a la versió 18.0.0.51.0. Els fitxers pujats abans també es comprimeixen, en segon pla i a poc a poc, després d'aquesta actualització: pot trigar unes hores.

## Ajust

A **Configuració → Tècnic → Paràmetres del sistema**, el paràmetre `ems.compress_min_kb` (per defecte `300`) és la mida mínima en kB a partir de la qual es comprimeix un fitxer.

Si el servidor no té Ghostscript instal·lat, els PDF es deixen tal com es van pujar i només es comprimeixen les imatges.
