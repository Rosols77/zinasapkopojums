# Ziņu apkopotājs

## Projekta apraksts
Ziņu apkopotājs ir tīmekļa lietotne, kuras mērķis ir apkopot un strukturēt svarīgāko informāciju no dažādām starptautiskām, reģionālām un nacionālām ziņu aģentūrām. Lietotne palīdz lietotājiem iegūt daudzveidīgu skatījumu uz aktuālajiem notikumiem, salīdzināt dažādu mediju ziņu atspoguļojumu un ietaupīt laiku, meklējot informāciju no vairākiem avotiem atsevišķi.

## Autori
- Beatrise Helmane  
- Marta Liepiņa  
- Ričards Ozols  

---

## Lietotāji
Lietotne ir paredzēta plašam lietotāju lokam:
- skolēniem un studentiem, kuriem nepieciešams sekot līdzi aktuālajiem notikumiem un dažādiem viedokļiem;
- ikdienas ziņu lasītājiem, kuri vēlas ātri iegūt pārskatu par galvenajām tēmām;
- lietotājiem, kuri vēlas salīdzināt, kā dažādi mediji atspoguļo vienus un tos pašus notikumus;
- lietotājiem, kuri interesējas par konkrētām tēmām (piem., politika, klimats, tehnoloģijas, mākslīgais intelekts).

Reģistrētiem lietotājiem būs pieejama personalizācija, piemēram, saglabātas tēmas, meklēšanas vēsture un atzīmētās ziņas.

---

## Izmantotās tehnoloģijas
Projekts tiek veidots kā tīmekļa lietotne ar klienta–servera arhitektūru.

**Frontend:**
- HTML, CSS, JavaScript  
- Mūsdienīgs GUI ar meklēšanas, filtrēšanas un kārtošanas funkcijām  
- Tumšais / gaišais režīms un citi lietotāja saskarnes stila varianti  

**Backend:**
- Servera puses programmēšanas valoda (piem., JavaScript ar Node.js vai Python)  
- Ziņu datu iegūšana, izmantojot:
  - oficiālos ziņu aģentūru API;
  - RSS plūsmas;
  - drošu datu scraping (ja API nav pieejams).  

**Datu apstrāde un uzglabāšana:**
- Datu bāze ziņu, lietotāju preferenču un saglabāto ierakstu glabāšanai  
- Periodiska datu atjaunošana un strukturēšana  

**Papildu funkcijas (pēc iespējas):**
- Automātiska ziņu kopsavilkumu ģenerēšana  
- Ziņu tulkošana dažādās valodās  

---

## Piegādes formāts
Projekta gala rezultāts tiek piegādāts kā:
- funkcionējoša tīmekļa lietotne, kas pieejama pārlūkprogrammā;
- projekta pirmkods strukturētā repozitorijā (piem., GitHub);
- dokumentācija (README fails), kurā aprakstīts:
  - projekta mērķis;
  - galvenās funkcijas;
  - izmantotās tehnoloģijas;
  - lietotāja iespējas.

Nepieciešamības gadījumā projekta darbība var tikt demonstrēta ar prezentāciju vai tiešsaistes demonstrāciju.

---
## Specifikācija

**1. Mērķis**
Izveidot mācību vajadzībām paredzētu tīmekļa lietotni, kas apkopo ziņas no vairākiem avotiem (RSS), strukturē tās pēc tēmām, ļauj meklēt, filtrēt un salīdzināt, kā dažādi mediji atspoguļo vienu tēmu.

**2. Mērķa auditorija**
Skolēni un studenti, kuri apgūst datu iegūšanu, tīmekļa lietotņu izstrādi un informācijas analīzi.

**3. Funkcionālās prasības**
**3.1. Ziņu iegūšana un glabāšana**
- Sistēma periodiski ielādē ziņas no konfigurētiem RSS avotiem.
- Ziņas tiek saglabātas datubāzē ar laukiem:
  - virsraksts, kopsavilkums, avots, publicēšanas laiks, URL, tēma, atrašanās vieta (ja pieejama).
- Dublikāti (tāds pats URL) netiek pievienoti atkārtoti.

**3.2. Ziņu saraksts un filtrēšana**
- Galvenajā skatā redzams jaunāko ziņu saraksts.
- Meklēšana pēc atslēgvārdiem (virsraksts, kopsavilkums, tēma).
- Filtri:
  - laika periods (piem., 24h, 7 dienas, mēnesis),
  - avots,
  - kārtošana pēc publikācijas laika vai tēmas atspoguļojuma apjoma.

**3.3. Tēmu salīdzinājums**
- Lietotājs var izvēlēties tēmu un redzēt, kā dažādi avoti to atspoguļo.
- Salīdzinājumā parādās vismaz 5 jaunākie virsraksti uz avotu.

**3.4. Lietotāja darbības**
- “Lasīt vēlāk” – pievienot rakstu saglabātajiem.
- “Atzīmēt kā svarīgu” – pievienot svarīgo sarakstam.
- “Ignorēt avotu” – paslēpt visus rakstus no konkrētā avota.
- “Ignorēt rakstu” – paslēpt konkrēto rakstu.
- Meklējumu vēsture un saglabātie meklējumi.
- Vienkāršs konts bez paroles (mācību režīmā).

**3.5. Lietotāja interfeiss**
- Tīmekļa GUI ar responsīvu dizainu.
- Tēmu pārslēdzējs (gaišais, tumšais, “rave”).

**4. Nefunkcionālās prasības**
- Lietojamība: lietotājam skaidra navigācija un ātra filtrēšana.
- Datu drošība: netiek glabātas paroles vai sensitīvi dati.
- Veiktspēja: RSS ielādes jāveic ar saprātīgu ātrumu (mācību vajadzībām pietiekami).

**5. Tehniskā arhitektūra**
- Backend: Python Flask.
- Datu glabāšana: SQLite.
- Datu iegūšana: RSS (feedparser).
- Frontend: HTML + Jinja2 + Bootstrap 5 + pielāgots CSS/JS.

**6. Galvenie moduļi**
- `app.py`: maršruti, datu iegūšana, datubāzes loģika.
- `templates/`: UI skati.
- `static/`: stili un tēmu pārslēgšanas skripti.

**7. Ierobežojumi un pieņēmumi**
- Projekts ir mācību nolūkiem un netiek publiski izplatīts.
- Ziņu avoti var atšķirties pēc datu struktūras, un ne visiem būs pilns metadatu komplekts.

**8. Nākotnes uzlabojumi (pēc izvēles, cik atļaus laiks)**
- Automātiska kopsavilkumu ģenerēšana.
- Valodu tulkošana.
- Lietotāju brīdinājumi par saglabātām tēmām.
- Papildu avoti un valstu sabiedriskie mediji.
- Tēmu klāsta paplašināšana.
- Dizaina uzlabošana.


---

## Literatūra un informācijas avoti
- Edgara, Riharda un Bruno zoles mājaslapa (skat. iepriekšējo gadu projektus)
