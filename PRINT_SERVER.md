# Servidor d'Impressió per Bar Quina

Aquest servidor permet imprimir tiquets a una impresora tèrmica Epson TM-T20 connectada per USB al Mac.

## Configuració Inicial

### 1. Verificar la impresora

Comprova que la impresora està connectada i reconeguda pel sistema:

```bash
lpstat -p -d
```

Anota el nom exacte de la impresora (per exemple: `TM-T20` o `EPSON_TM_T20`).

### 2. Configurar el nom de la impresora

Edita el fitxer `print_server.py` i canvia la variable `PRINTER_NAME` amb el nom exacte:

```python
PRINTER_NAME = "TM-T20"  # Canvia pel nom de la teva impresora
```

### 3. Instal·lar dependències

Des del directori del projecte:

```bash
pip install Flask flask-cors requests
```

## Executar el Servidor

### Al Mac (on està connectada la impresora)

```bash
python3 print_server.py
```

El servidor s'iniciarà a `http://192.168.1.36:5000`

**Important**: Assegura't que la IP del Mac és `192.168.1.36`. Si és diferent:
1. Canvia la IP al fitxer `print_server.py` (línia `app.run(host='0.0.0.0', port=5000)`)
2. Canvia també la IP a `app/print_utils.py` (variable `PRINT_SERVER_URL`)

## Provar la Impressió

### Test des del navegador

```
http://192.168.1.36:5000/test
```

Hauria d'imprimir un tiquet de prova.

### Test des de la terminal

```bash
curl http://192.168.1.36:5000/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "printer": "TM-T20",
  "message": "Servidor d'impressió actiu"
}
```

## Funcionament

### Des de l'aplicació BarQuina

1. Ves a una comanda a `/tables/numtable`
2. Veuràs dos botons d'impressió:
   - **🖨️ Cuina**: Imprimeix tiquet per la cuina amb tots els productes i extres
   - **🖨️ Caixa**: Imprimeix tiquet de pagament (només disponible si hi ha pagaments)

### Tiquet de Cuina

Inclou:
- Número de comanda en gran
- Taula
- Hora
- Llistat de productes amb quantitats
- **Extres per cada producte** (molt important)
- Notes si n'hi ha

### Tiquet de Caixa

Inclou:
- Capçalera "Bar Quina"
- Número de comanda i taula
- Nom del cambrer/a
- Data i hora
- Llistat de productes amb preus
- Extres amb preus
- Total
- Mètode de pagament
- Efectiu donat i canvi (si és pagament en efectiu)

## Solució de Problemes

### Error "No es pot connectar amb el servidor d'impressió"

1. Verifica que el servidor està executant-se al Mac
2. Comprova la IP del Mac: `ifconfig | grep inet`
3. Verifica que no hi ha firewall bloquejant el port 5000

### Error "Comanda lpr no trobada"

Instal·la CUPS:
```bash
brew install cups
```

### La impressora no imprimeix

1. Comprova que la impresora està encesa i amb paper
2. Verifica el nom de la impresora: `lpstat -p`
3. Prova d'imprimir directament: `echo "test" | lpr -P TM-T20`

### Error de permisos

Pot ser que necessitis afegir el teu usuari al grup d'impressió:
```bash
sudo dseditgroup -o edit -a $USER -t user lp
```

## Desactivar Impressió

Si vols deshabilitar temporalment la impressió sense aturar el servidor, edita `app/print_utils.py`:

```python
PRINT_ENABLED = False  # Canvia a False per deshabilitar
```

## API del Servidor

### POST /print

Imprimeix contingut personalitzat.

**Request:**
```json
{
  "content": "Text a imprimir\nAmb salts de línia"
}
```

**Response (èxit):**
```json
{
  "success": true,
  "message": "Imprès correctament"
}
```

**Response (error):**
```json
{
  "success": false,
  "error": "Descripció de l'error"
}
```

### GET /health

Comprova l'estat del servidor.

### GET /test

Imprimeix un tiquet de prova.

## Executar el Servidor en Producció

Per executar el servidor de forma persistent, pots usar `nohup`:

```bash
nohup python3 print_server.py > print_server.log 2>&1 &
```

O crear un servei amb `launchd` al Mac (més recomanat per producció).

## Notes

- El paper de 80mm permet aproximadament 48 caràcters per línia
- Els tiquets inclouen salts de línia al final per facilitar el tall del paper
- El servidor accepta peticions de qualsevol origen (CORS activat)
