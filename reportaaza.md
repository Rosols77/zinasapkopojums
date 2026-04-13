# Projekta novērtējums

## 1. Struktūra

- Projekta kods ir koncentrēts vienā lielā failā `app.py`. Tas padara uzturēšanu un paplašināšanu grūtāku, jo maršruti, datu bāzes loģika, autentifikācija un ziņu apstrāde ir vienā vietā.
- `templates/` un `static/` direktorijas ir pareizi organizētas, kas ir labs risinājums frontenda saturam.
- Ir jāņem vērā, ka repozitorijā jau ir iekļauti bināri/ģenerēti faili `data.db`, `users_secure.enc`, `users_secure.key` un `venv/`. Šie faili parasti nav jāglabā versiju kontroles sistēmā, jo tie satur datus, atšifrēšanas atslēgu un virtuālo vidi.
- Faila nosaukums `requirments.txt` ir nepareizs; tas tiek gaidīts kā `requirements.txt`.

## 2. Koda kvalitāte

- Kods bieži izmanto skaidrus funkciju un mainīgo nosaukumus, kas uzlabo lasāmību.
- Programmai ir daudz helper funkciju (`detect_topic`, `extract_image_url`, `fetch_articles`, utml.), kas ir labs solis uz moduļu loģiku, bet tās visas atrodas vienā failā.
- Nav daudz komentāru vai dokumentācijas pašā `app.py`, kas paver iespēju kļūdām vai neparedzētām funkcionalitātes interpretācijām.
- Nav plašu testu sistēmas, kas pārbaudītu Flask maršrutus, autentifikāciju un DB loģiku. Esošie testi (`tests/test_observability.py`) pārbauda tikai `observability_test_env.py` loģiku, kas nav galvenais lietotnes funkcionalitātes slānis.
- `app.run(debug=True)` norāda uz attīstības režīmu. Tas nav drošs, ja kāds palaistu lietotni ārpus lokālā attīstības uzstādījuma.
- Dažās vietās tiek izmantotas `request.referrer` novirzīšanai bez papildu pārbaudes, kas var būt neparedzams.

## 3. Drošības problēmas

- `app.config["SECRET_KEY"]` noklusējuma vērtība ir `dev-secret`, ja nav iestatīta vides mainīgā. Tas ir potenciāls drošības risks, ja lietotne tiek palaista vides režīmā bez konfigurācijas.
- `SecureUserStore` glabā lietotāju datus `users_secure.enc` ar atšifrēšanas atslēgu `users_secure.key` vienā repozitorijā. Ja abi faili ir pieejami, šifrēšana nenodrošina aizsardzību.
- Nav redzama CSRF aizsardzība formu POST metodes maršrutos (`/logout`, `/save`, `/unsave`, `/ignore-source`, `/ignore-article`, `/save-search`, `/remove-saved-search`, `/refresh` utt.). Tas nozīmē, ka formas varētu būt pakļautas CSRF uzbrukumiem.
- Nav īsta sesijas termiņa vai papildu aizsardzības pret sesiju nolaupīšanu.
- Nav redzamas IP limitēšanas, paroles neveidošanas ierobežojumu pēc neveiksmīgas pierakstīšanās vai citu aizsardzības mehānismu pret bruteforce uzbrukumiem.
- Repozitorijā iekļauts datubāzes fails `data.db`, kas var saturēt lietotāju datus un citas sensitīvas informācijas atkarībā no izpildes.

## 4. Kļūdas un potenciālie trūkumi

- Daži maršruti (`/compare`, `/saved`, `/important`, `/history`, utt.) izmanto `current_user_id()` tieši. Ja lietotājs nav autentificējies, tas rada `PermissionError` un var beigties ar 500 kļūdu, nevis pareizu pāradresāciju uz pieteikšanos.
- Maršrutos, kas apstrādā `article_id` no formas, nav validācija, kas pārliecinātos, ka parametrs ir skaitlis. Nepareizas vērtības var izraisīt `ValueError` un 500 kļūdu.
- `migrate_legacy_users_table` loģika var izraisīt datu zudumu, ja esošā `users` tabula nesatur prasītās kolonnas, jo tā izveido jaunu tabulu un noņem veco.
- `upsert_articles()` izmanto `feedparser.parse` bez laika ierobežojuma vai kļūdu apstrādes. Tas var radīt gaidīšanu vai atteikšanos no ārējiem RSS avotiem.
- `search_history` tiek ierakstīta katrā `index` apmeklējumā, arī reizēs, kad meklēšanas vaicājums var būt pats par sevi tukšs vai jau apstrādāts.
- `compare` maršrutā tiek izmantots `topic` vērtība `fetch_articles` vaicājumā, kas faktiski meklē arī `topic` sadaļu; tas var darboties, bet nav atklāti dokumentēts un var radīt neskaidrību.

## 5. Ieteikumi uzlabošanai

- Sadalīt `app.py` loģiku pa atsevišķiem moduļiem: `routes.py`, `models.py`, `services.py`, `security.py` vai līdzīgi.
- Pievienot `requirements.txt` ar pareizu nosaukumu un reālu atkarību sarakstu.
- Izmantot vides mainīgos visiem noslēpumiem (`SECRET_KEY`, `USER_DATA_KEY`) un neglabāt atslēgas repozitorijā.
- Pievienot CSRF aizsardzību, piemēram, izmantojot `Flask-WTF` vai `Flask-SeaSurf`.
- Pievienot testus, kas pārbauda galvenos maršrutus, autorizāciju, datubāzes saglabāšanu un kļūdu apstrādi.
- Izveidot `.gitignore`, lai nepieņemtu `data.db`, `users_secure.enc`, `users_secure.key`, `venv/` un citus lokālos/bindos failus.
- Noņemt `app.run(debug=True)` produkcijas vai prezentācijas režīmā.

## 6. Kopsavilkums

Projekts ir funkcionāls prototipa līmenī un satur pamatfunkcijas lietotāju reģistrācijai, pieteikšanai, ziņu izgūšanai un saglabāšanai. Tomēr kods ir pārāk koncentrēts vienā failā, trūkst nopietnas drošības prakses, nav pietiekamas kļūdu apstrādes un tests ir ierobežots. Lai uzlabotu kvalitāti, ir nepieciešama modulāra pārbūve, nopietnākas drošības korekcijas un papildu automatizēta testēšana.
