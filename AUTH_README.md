# Sistema d'autenticació BarQuina

## Accés al sistema

### Credencials per defecte

**Administrador:**
- Usuari: `admin`
- Contrasenya: `admin123`

### Rols d'usuari

1. **ADMIN** - Accés complet:
   - Quadre de control (dashboard)
   - Gestió de taules i comandes
   - Catàleg (productes, extres, inventari)
   - Caixa (sessions, moviments)
   - Resultats (informes de beneficis)
   - Gestió d'usuaris
   - Terminal mòbil
   - Control de cuina

2. **STAFF** - Accés limitat:
   - Terminal mòbil (presa de comandes)
   - Control de cuina
   - **NO** té accés a: administració, caixa, informes, usuaris

## Gestió d'usuaris (només admins)

### Crear nou usuari
1. Anar a **Usuaris** al menú de navegació
2. Clicar **Crear usuari**
3. Omplir formulari:
   - Nom d'usuari (únic)
   - Contrasenya (mínim 4 caràcters)
   - Rol (Staff o Admin)
4. Clicar **Crear usuari**

### Editar usuari existent
1. A la llista d'usuaris, clicar **Editar**
2. Modificar camps necessaris:
   - Nom
   - Rol
   - Nova contrasenya (opcional - deixar buit per mantenir l'actual)
3. Clicar **Guardar canvis**

### Activar/desactivar usuari
- Clicar **Canvia estat** a la fila de l'usuari
- Els usuaris inactius no poden iniciar sessió

## Flux d'autenticació

### Primera vegada
1. Accedir a `http://localhost:5000`
2. Serà redirigit a `/auth/login`
3. Introduir credencials
4. Si és admin → Dashboard
5. Si és staff → Terminal mòbil

### Tancar sessió
- Clicar al botó **Tancar sessió** a la barra de navegació

## Script de creació d'admin

Per crear un nou administrador des de la terminal:

```bash
python scripts/create_admin.py
```

El script demanarà:
- Nom d'usuari
- Contrasenya
- Confirmació de contrasenya

## Desenvolupament

### Desactivar autenticació en tests

Els tests automàticament desactiven l'autenticació amb:

```python
TestConfig.LOGIN_DISABLED = True
```

### Protegir noves rutes

**Per rutes d'admin:**
```python
from ...auth_utils import admin_required

@bp.before_request
@admin_required
def require_admin():
    pass
```

**Per rutes que requereixen login (staff o admin):**
```python
from flask_login import login_required

@bp.before_request
@login_required
def require_login():
    pass
```

## Base de dades

Les contrasenyes s'emmagatzemen hashejades amb `werkzeug.security`:
- `generate_password_hash()` per crear hash
- `check_password_hash()` per verificar

Mai s'emmagatzemen contrasenyes en text pla.
