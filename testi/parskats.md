# Projekta pārskats un novērtējums
Vērtējis Kārlis Svaža.

Dokumenta mērķis ir sniegt pārskatu par projekta struktūru, koda kvalitāti un drošības aspektiem, kā arī noteikt potenciālos trūkumus.

## Struktūra

Projekta kods ir koncentrēts vienā lielā failā `app.py`, kas apvieno visu. Šis apgrūtina koda pārskatāmību un uzturēšanu.

Priekšgals iedalīts `templates/` un `static/` mapītēs, kas ir laba prakse.

Repozitorijā ir iekļauti bināri/ģenerēti faili (`data.db`, `users_secure.enc`, `users_secure.key`, `venv/`), kas padara projektu pārvietojamu un viegli palaižamu jebkur, tomēr to klātbūtne var rada drošības riskus.

## Koda kvalitāte

Mainīgie ir rakstīti čūskveida stilā.

Kods izmanto skaidrus funkciju un mainīgo nosaukumus, kas ļauj to lasīt. Komentāri neeksistē, taču kods ir lasāms arī bez tiem.

Tiek pielietotas palīgfunkcijas, kas ir laba prakse modulārai loģikai, kā arī palīdz koda lasāmībai.

Datu bāzes vaicājumi izmanto `sqlite3` ar parametrizētām SQL komandām, kas samazina SQL injekcijas risku, ja parametri tiek izmantoti pareizi.

## Nefunkcionālie testi

`app.py` satur galveno lietotnes loģiku, un tā darbība ir atkarīga no failu sistēmas, sesiju stāvokļa un ārēju funkciju izsaukumiem. Šeit runa nav par pieņēmumu līmeņa integrācijas testiem, bet gan par faktiskām nefunkcionālu scenāriju validācijām — piemēram, vai dati tiek uzglabāti droši, vai šifrēšana darbojas, vai ievade tiek apstrādāta pareizi un vai SQL vaicājumi nav pakļauti injekcijām.

Vien koda pārskats nav pietiekams, lai šo uzvedību pierādītu. Koda audits `app.py` var identificēt problēmas, taču tas neatbild uz jautājumu, vai aplikācija patiešām saglabā un nolasīs datus pareizi reālajā izpildes laikā. Tāpēc ir noderīgi definēt konkrētus validācijas testus, kas apraksta inputus un gaidāmos rezultātus, nevis paļauties tikai uz vispārinātu «pēc izjūtām» secinājumu.

### Testa apraksti

- Testa apraksts: Datu glabāšana (drošā veidā)
  - Ievade: reģistrē jaunu lietotāju caur `app.py` un saglabā ar to saistītos datus, pēc tam pārbauda `data.db`, `users_secure.enc` un `users_secure.key` pieejamību un derīgumu.
  - Sagaidāmais rezultāts: `app.py` veiksmīgi saglabā lietotāja datus bez kļūdām; faili ir atpazīstami un nolasāmi no lietotnes, un tie nav bojāti.
  - Patiesais rezultāts: pašreizējie testi `tests/test_observability.py` neaptver šo uzvedību, tāpēc nepieciešams izpildes tests uz `app.py`.

- Testa apraksts: Datu šifrēšana
  - Ievade: izveido lietotāju ar `app.py`, pēc tam mēģina izlasīt un atšifrēt `users_secure.enc` ar `users_secure.key`.
  - Sagaidāmais rezultāts: `users_secure.enc` nav skaidrs teksta fails; tas atšifrējas ar atslēgu un rezultāts ir derīgs JSON, bet neatslēdzas bez atslēgas.
  - Patiesais rezultāts: nav pārbaudīts ar esošajiem testiem, nepieciešama faktiska `app.py` izpildes pārbaude.

- Testa apraksts: Ievades validācija
  - Ievade: nosūta pieprasījumus uz `app.py` maršrutiem, kas apstrādā formas datus (`/save`, `/unsave`, `/ignore-article`, `/remove-saved-search` u.c.), tostarp nederīgas un ļaunprātīgas `article_id`, `search_id`, `query` un `source` vērtības.
  - Sagaidāmais rezultāts: aplikācija atgriež drošu kļūdu vai validācijas ziņu bez 500 kļūdām; netiek veiktas nevēlamas darbības.
  - Patiesais rezultāts: `app.py` pašlaik var izraisīt `ValueError` un 500 kļūdas, tāpēc nepieciešama praktiska testēšana un kodu uzlabošana.

- Testa apraksts: SQL injekciju novēršana
  - Ievade: nosūta ieeju ar SQL speciālajiem simboliem uz `app.py` meklēšanas un datubāzes saglabāšanas ceļiem (`search query`, `source`, `article_id`, `display_name` utt.).
  - Sagaidāmais rezultāts: `app.py` izmanto parametrizētus SQL vaicājumus, ievade tiek apstrādāta kā dati, un nav iespējams injicēt papildu SQL komandas.
  - Patiesais rezultāts: kods izmanto `sqlite3` parametrizētus vaicājumus, kas samazina risku, bet jāveic dzīvais tests, lai pārliecinātos par šo uzvedību.

## Drošības problēmas, kļūdas un trūkumi

Testi īsti neeksistē, neskaitot `tests/test_observability.py`, kas pārbauda tikai `observability_test_env.py` loģiku, kas ir tikai neliela daļa no kopējās lietotnes funkcionalitātes. Šis ir brangs trūkums, jo nav pārbaudīti galvenie maršruti, autorizācija, datubāzes saglabāšana un kļūdu apstrāde, kas var novest pie neparedzētām kļūdām un lielām problēmām.

`app.run(debug=True)` ir nedrošs un laižot lietotni produkcijā šo ir manuāli jāpārslēdz uz `debug=False`, ko varētu automatizēt ar vides mainīgo produkcijas un testa vides nodalāmībai. `app.run(debug=True)` Flaskā ieslēdz izstrādes režīmu, kas ļauj redzēt pilnu kļūdu izsekošanu un pat ļauj izpildīt kodu caur pārlūkprogrammu, ja rodas kļūda. Tas ir ļoti noderīgi izstrādes laikā, bet ir liels drošības risks produkcijā.

Dažās vietās tiek izmantots `request.referrer` novirzīšanai bez papildu pārbaudes, kas izraisa, jo `request.referrer` var būt tukšs vai manipulēts.

Noklusēti `app.config["SECRET_KEY"]` vērtība ir `dev-secret`, ja tā netiek iestatīta ar vides mainīgo. Tas potenciāli palīdz lokāli testējot lietotni, taču tas ir riskanti, ja lietotne tiek palaista bez konfigurācijas, jo parole ir pieejama Githubā.

`SecureUserStore` glabā lietotāju datus `users_secure.enc` ar atšifrēšanas atslēgu `users_secure.key` vienā repozitorijā. Ja abi faili ir pieejami, šifrēšana nenodrošina aizsardzību.

Nav redzama CSRF (tīkla lietotņu pieprasījumu viltošana) aizsardzība formu POST metodes maršrutos (`/logout`, `/save`, `/unsave`, `/ignore-source`, `/ignore-article`, `/save-search`, `/remove-saved-search`, `/refresh` utt.). Tas nozīmē, ka formas varētu būt pakļautas CSRF uzbrukumiem.

Nav sesijas termiņa vai papildu aizsardzības pret sesiju nolaupīšanu.

Nav redzamas IP limitēšanas, paroles neveidošanas ierobežojumu pēc neveiksmīgas pierakstīšanās vai citu aizsardzības mehānismu pret bruteforce uzbrukumiem.

Repozitorijā iekļauts datubāzes fails `data.db`, kas satur datus, kurus nevajadzētu glabāt versiju kontroles sistēmā, lai gan tas ir nepieciešams projekta darbībai lokāli un pārvietojami.

Daži maršruti (`/compare`, `/saved`, `/important`, `/history`, utt.) izmanto `current_user_id()` pa tiešo. Ja lietotājs nav autentificējies, tas rada `PermissionError` un beidzas ar 500 kļūdu, nevis pareizu pāradresāciju uz pieteikšanos.

Maršrutos, kas apstrādā `article_id` no formas, nav pārbaude, vai parametrs ir skaitlis. Nepareizas vērtības var izraisīt `ValueError` un 500 kļūdu.

Nav redzama ievades validācija vai sanitācija, kas varētu novest pie XSS (starpvietņu programmu) uzbrukumiem, ja lietotāja ievade tiek attēlota bez attiecīgas apstrādes.

Nav redzama divfaktoru autentifikācija vai papildu drošības pasākumi lietotāju kontu aizsardzībai.

## Ieteikumi

Lai uzlabotu projektu, ieteicams:

- Sadalīt `app.py` vairākos failos pēc funkcionalitātes (modeļi, skati, formas, utilītas)
- Pievienot visaptverošus testus galvenajiem maršrutiem un funkcionalitātei
- Nodrošināt, ka `debug=False` produkcijas vidē
- Iestatīt `SECRET_KEY` caur vides mainīgo un neizmantot noklusējuma vērtības
- Pievienot CSRF aizsardzību visām formām
- Ieviest sesiju termiņa beigu un citus aizsardzības mehānismus pret sesiju nolaupīšanu
- Pievienot IP limitēšanu un paroles ierobežojumus pret bruteforce uzbrukumiem
- Pievienot pareizu autentifikācijas pārbaudi maršrutos, lai novērstu 500 kļūdas
- Pievienot ievades validāciju un sanitāciju
- Noņemt bināros failus no versiju kontroles vai pievienot tos `.gitignore`
- Pievienot divfaktoru autentifikāciju

## Secinājums

Projekts demonstrē pamata Flask lietotnes funkcionalitāti, taču tam ir vairāki būtiski drošības trūkumi, kas jānovērš pirms laišanas produkcijā. Koda lasāmība ir pieņemama, bet strukturāls sadalījums uzlabotu uzturēšanu ilgtermiņā.

