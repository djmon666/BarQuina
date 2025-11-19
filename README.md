# BarQuina POS

BarQuina és una aplicació web construïda amb Flask pensada per gestionar bars petits amb un servidor central i terminals mòbils connectats a la mateixa xarxa.

## Funcionalitats principals

- Gestió de productes (menjars i begudes) i inventari de compres.
- Creació de comandes per taula amb seguiment independent de servei (pendent de portar, servida) i cobrament (pendent de cobrar, cobrada).
- Subtotals i pagaments parcials per comanda per permetre pagaments separats.
- Caixa registradora amb sessions de caixa, moviments d'entrada/sortida i conciliació.
- Quadre de comandament per veure totes les taules, comandes i estat en temps real.
- Actualitzacions en temps (quasi) real via WebSocket perquè les pantalles es refresquin automàticament quan hi ha canvis.
- Recursos front-end empaquetats localment (Bootstrap, Socket.IO) per poder desplegar sense connexió a Internet.
- Gestió de personal per terminals mòbils i sessió ràpida sense contrasenya.
- Terminal web mòbil amb selectors +/− per afegir productes, veure totals instantanis i editar comandes existents (afegir/quitar línies).

## Requisits

- Python 3.11+
- Pip i un entorn virtual recomanat.

## Posada en marxa

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
set FLASK_APP=barquina.app:create_app
python barquina.py
```

El servidor escoltarà per defecte a `http://127.0.0.1:5000`. El script `barquina.py` arrenca el servidor de Flask-SocketIO perquè les connexions WebSocket funcionin; si prefereixes el `flask run`, pots utilitzar-lo però les actualitzacions deixaran d'emetre's fins que utilitzis un worker compatible (eventlet/gevent/gunicorn-eventlet).

### Recursos offline

Si vols actualitzar Bootstrap o la llibreria de Socket.IO, executa:

```powershell
.\.venv\Scripts\python.exe .\scripts\download_assets.py
```

El script descarrega els fitxers a `app/static/vendor/` perquè el servidor els serveixi en local. Per als paquets Python, pots preparar un repositori offline amb:

```powershell
pip download -r requirements.txt -d vendor\wheels
pip install --no-index --find-links vendor\wheels -r requirements.txt
```

Amb això podràs desplegar BarQuina en una xarxa sense accés a Internet.

### Flux dels terminals mòbils

1. Des del panell central ves a `/users/` per donar d'alta el personal autoritzat.
2. Els terminals mòbils accedeixen a `/mobile/`, seleccionen el seu nom i veuen la graella de taules.
3. Cada taula pot tenir diverses comandes en paral·lel; des del terminal es pot crear noves comandes, seleccionar-les i modificar-ne les línies (quantitats o eliminacions) abans de cobrar-les.
4. Les línies afegides o corregides es reflecteixen automàticament al panell central i es poden cobrar des de qualsevol dispositiu.

## Proves

```powershell
pytest
```

### Simulació de càrrega externa

Per provar el sistema des d'una màquina externa i mesurar latències reals, utilitza `scripts/external_stress.py`. Només cal tenir Python 3 i instal·lar `httpx`:

```bash
pip install httpx
python scripts/external_stress.py https://quina.local 3 7 12 20 --concurrency 5 --status-cycles 2
```

Arguments:

- `base_url`: URL pública del teu servidor.
- `user_id`: identificador d'un usuari actiu (pots veure'l a la base de dades `staff_users`).
- `table_id` i `product_id`: registres que ja existeixen.
- `orders`: nombre total d'escenaris a simular.

El script crearà noves comandes, afegirà productes i alternarà ràpidament l'estat de les línies. Al final mostrarà temps mitjans, p95 i màxims de cada etapa per ajudar-te a detectar colls d'ampolla de xarxa o servidor. Executa'l des d'un portàtil o altra màquina per apropar-te a un escenari realista.

## Properes passes suggerides

- Afegir autenticació i rols (cambrer, cuina, caixa).
- Afegir actualitzacions en temps real via WebSocket per sincronitzar terminals.
- Exportació d'informes PDF/Excel i integració amb sistemes comptables.
- Mode offline amb sincronització per a terminals fora de cobertura puntual.

