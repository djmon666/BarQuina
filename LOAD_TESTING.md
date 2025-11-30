# Load Testing Guide for BarQuina

Aquest document explica com executar tests d'estrès professionals a l'aplicació BarQuina amb monitorització de recursos del sistema.

## 📋 Requisits

Instal·la les dependències necessàries:

```bash
pip install -r requirements-dev.txt
```

Això instal·larà:
- **Locust**: Framework de load testing
- **psutil**: Monitorització de recursos del sistema
- **py-spy**: Profiling de Python (opcional)

## 🚀 Execució Ràpida

### Preparar dades de test (primer cop)

Abans d'executar els tests, assegura't que tens dades a la base de dades:

```bash
# Crear taules, categories i productes de test
python scripts/prepare_test_data.py
```

Això crearà:
- 20 taules (T1-T20)
- 5 categories (Begudes, Entrants, Plats, Postres, Cafès)
- 21 productes realistes amb preus

### Test ràpid (10 usuaris, 60 segons)

```bash
python scripts/run_load_test.py --quick
```

### Test estàndard (50 usuaris, 5 minuts)

```bash
python scripts/run_load_test.py --users 50 --duration 300
```

### Test intensiu (100 usuaris, 10 minuts)

```bash
python scripts/run_load_test.py --users 100 --duration 600 --spawn-rate 10
```

### Test en servidor remot

```bash
python scripts/run_load_test.py --host http://codebany.ddns.net:5000 --users 50
```

## 📊 Components del Sistema

### 1. Locust Load Testing (`tests/locustfile.py`)

Simula diferents tipus d'usuaris:

- **MobileTerminalUser** (weight=3): Cambrer usant terminal mòbil
- **KitchenStaffUser** (weight=2): Personal de cuina
- **BarStaffUser** (weight=2): Personal de barra
- **AdminUser** (weight=1): Administrador

#### Tasques simulades:
- Visualització de taules i comandes
- Creació de noves comandes
- Toggle d'estats de productes
- Accés a dashboards i reports
- Gestió de productes i caixa

### 2. Monitor de Recursos (`scripts/monitor_resources.py`)

Monitoritza en temps real:
- **CPU**: Ús total i per procés
- **RAM**: Memòria total i per procés
- **Disc I/O**: Velocitat de lectura/escriptura
- **Xarxa I/O**: Tràfic de xarxa

#### Ús independent:

```bash
# Monitoritzar durant 5 minuts
python scripts/monitor_resources.py --duration 300 --output results/monitor.csv

# Monitoritzar indefinidament (Ctrl+C per parar)
python scripts/monitor_resources.py --output results/monitor.csv
```

### 3. Script Integrat (`scripts/run_load_test.py`)

Executa automàticament:
1. Inicia monitorització de recursos
2. Executa test de càrrega amb Locust
3. Atura monitorització
4. Genera informe complet

### 4. Analitzador de Resultats (`scripts/analyze_results.py`)

Analitza i visualitza resultats:

```bash
# Només estadístiques
python scripts/analyze_results.py results/loadtest_20231201_120000

# Amb gràfiques
python scripts/analyze_results.py results/loadtest_20231201_120000 --plot
```

## 📁 Estructura de Resultats

Cada test crea un directori amb timestamp:

```
results/
└── loadtest_20231201_120000/
    ├── test_report.txt           # Resum del test
    ├── system_monitor.csv        # Mètriques del sistema
    ├── locust_report.html        # Informe HTML de Locust
    ├── locust_output.txt         # Output complet de Locust
    └── system_resources_plot.png # Gràfiques (si s'activa)
```

## 🔬 Ús Avançat

### Executar Locust amb interfície web

```bash
locust -f tests/locustfile.py --host=http://localhost:5000
```

Accedeix a http://localhost:8089 per controlar el test visualment.

### Monitoritzar un procés específic

Modifica `monitor_resources.py` per apuntar al PID del teu servidor Flask.

### Usar patró de tràfic personalitzat

El `RestaurantTrafficShape` a `locustfile.py` simula patrons realistes:
- Rush del migdia/sopar
- Períodes de baixa activitat
- Tancament progressiu

Descomenta la classe per activar-la.

### Test distribuït amb múltiples workers

```bash
# Terminal 1: Master
locust -f tests/locustfile.py --master --host=http://localhost:5000

# Terminal 2+: Workers
locust -f tests/locustfile.py --worker --master-host=localhost
```

## 📈 Mètriques Clau

### Rendiment de l'aplicació (Locust)
- **Requests per segon (RPS)**
- **Temps de resposta** (min/avg/max/percentils)
- **Taxa d'error**
- **Distribució per endpoint**

### Recursos del sistema (Monitor)
- **CPU**: Detecta colls d'ampolla de computació
- **RAM**: Detecta fuites de memòria
- **Disc I/O**: Detecta problemes de BD
- **Xarxa**: Detecta problemes de connectivitat

## 🎯 Objectius Recomanats

Per a BarQuina (aplicació d'un restaurant):

| Mètrica | Objectiu | Acceptable |
|---------|----------|------------|
| Temps resposta avg | < 200ms | < 500ms |
| P95 temps resposta | < 500ms | < 1000ms |
| Taxa d'error | < 0.1% | < 1% |
| RPS | > 100 | > 50 |
| CPU (càrrega) | < 70% | < 85% |
| RAM (ús) | < 80% | < 90% |

## 🐛 Troubleshooting

### Error: "Connection refused"
Assegura't que el servidor Flask està executant-se:
```bash
python barquina.py
```

### Error: "Too many open files"
Augmenta el límit de fitxers oberts:
```bash
ulimit -n 10000
```

### Resultats inconsistents
- Assegura't que no hi ha altres processos pesats
- Executa múltiples tests i fes la mitjana
- Usa `--duration` més llarg per estabilitzar resultats

### Errors d'autenticació
Configura `LOGIN_DISABLED=True` a `config.py` per tests:
```python
class Config:
    LOGIN_DISABLED = True  # Only for load testing!
```

## 📚 Exemples de Comandes

```bash
# Test complet amb anàlisi
python scripts/run_load_test.py --users 50 --duration 300
python scripts/analyze_results.py results/loadtest_* --plot

# Test progressiu (escalat gradual)
python scripts/run_load_test.py --users 100 --spawn-rate 2 --duration 600

# Test de resistència (llarga durada)
python scripts/run_load_test.py --users 30 --duration 3600

# Només monitorització (servidor ja en execució)
python scripts/monitor_resources.py --duration 600 --output results/manual_monitor.csv
```

## 🔐 Seguretat

⚠️ **IMPORTANT**: Mai executis tests de càrrega contra entorns de producció sense permís explícit!

- Tests locals: OK
- Tests en servidor de desenvolupament: OK
- Tests en producció: **Requereix planificació i aprovació**

## 📞 Suport

Per problemes o millores, obre un issue al repositori o contacta amb l'equip de desenvolupament.

---

**Última actualització**: 30 de novembre de 2025
