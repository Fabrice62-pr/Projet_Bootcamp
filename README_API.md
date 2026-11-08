# README API — HospiPlan

Ce document explique comment l'API REST de HospiPlan est construite, comment
le front-end l'appelle et comment les données circulent entre les couches.

---

## 1. Architecture générale

```
Navigateur (HTML/JS)
       │
       │  HTTP JSON  (fetch / apiFetch)
       ▼
Django views → URLs → Django REST Framework ViewSets
                              │
                              │  ORM Django
                              ▼
                        PostgreSQL (hospiplandb)
```

Le projet est découpé en **applications Django indépendantes**.
Chaque app expose ses propres endpoints via DRF.
Le front-end est une app Django supplémentaire (`frontend`) qui rend des
templates HTML + JavaScript vanilla ; le JavaScript appelle l'API REST en JSON.

---

## 2. Technologies utilisées

| Composant | Technologie |
|-----------|-------------|
| Serveur web | Django 6.0.3 (WSGI) |
| API REST | Django REST Framework 3.17.1 |
| Base de données | PostgreSQL (hospiplandb) |
| Sérialisation | `ModelSerializer` (DRF) |
| Front-end | Templates Django + Bootstrap 5 + JavaScript vanilla |

---

## 3. Comment les URLs sont enregistrées

Toutes les APIs sont préfixées par `/api/`.
Chaque app déclare ses routes via un **`DefaultRouter`** DRF qui génère
automatiquement les endpoints CRUD (liste, détail, création, modification,
suppression).

**`hospiplan/urls.py`** (routeur principal) :
```python
path('api/', include('staff.urls')),
path('api/', include('scheduling.urls')),
path('api/', include('services.urls')),
path('api/', include('absences.urls')),
path('api/', include('preferences.urls')),
path('api/', include('rules.urls')),
```

Chaque `urls.py` d'app utilise `DefaultRouter` :
```python
router = DefaultRouter()
router.register(r'staff', StaffViewSet, basename='staff')
urlpatterns = router.urls
```

---

## 4. Référence complète des endpoints

Pour chaque ressource enregistrée, DRF génère automatiquement ces routes :

| Méthode | URL | Action |
|---------|-----|--------|
| GET | `/api/<ressource>/` | Lister tous les objets |
| POST | `/api/<ressource>/` | Créer un objet |
| GET | `/api/<ressource/{id}/` | Lire un objet précis |
| PUT | `/api/<ressource>/{id}/` | Modifier complètement |
| PATCH | `/api/<ressource>/{id}/` | Modifier partiellement |
| DELETE | `/api/<ressource>/{id}/` | Supprimer |

### App `staff` — Personnel

| Endpoint | Description |
|----------|-------------|
| `/api/staff/` | Soignants (liste = `StaffSerializer`, détail = `StaffDetailSerializer` enrichi) |
| `/api/roles/` | Rôles professionnels |
| `/api/staff-roles/` | Liaison soignant ↔ rôle |
| `/api/specialties/` | Spécialités médicales |
| `/api/staff-specialties/` | Liaison soignant ↔ spécialité |
| `/api/contract-types/` | Types de contrat (CDI, CDD…) |
| `/api/contracts/` | Contrats des soignants |
| `/api/certifications/` | Catalogue de certifications |
| `/api/certification-dependencies/` | Dépendances entre certifications |
| `/api/staff-certifications/` | Certifications détenues par les soignants |

> **Note** : `GET /api/staff/{id}/` retourne un objet enrichi contenant les
> rôles, spécialités, contrats et certifications du soignant (via
> `StaffDetailSerializer`).

### App `scheduling` — Planning

| Endpoint | Description |
|----------|-------------|
| `/api/shift-types/` | Types de gardes (matin, nuit, soirée…) |
| `/api/shifts/` | Créneaux / postes de garde |
| `/api/shift-certifications/` | Certifications requises par poste |
| `/api/assignments/` | Affectations soignant ↔ poste **(logique contraintes)** |

> **Note** : `GET /api/shifts/{id}/` retourne les certifications requises et
> les affectations existantes via `ShiftDetailSerializer`.

### App `services` — Services hospitaliers

| Endpoint | Description |
|----------|-------------|
| `/api/services/` | Services (Urgences, Cardiologie…) |
| `/api/care-units/` | Unités de soins rattachées à un service |
| `/api/service-statuses/` | Statuts opérationnels d'un service |
| `/api/service-assignments/` | Affectations de soignants à un service |

### App `absences` — Absences

| Endpoint | Description |
|----------|-------------|
| `/api/absence-types/` | Types d'absence (congé, maladie, formation…) |
| `/api/absences/` | Absences déclarées par soignant |

### App `preferences` — Préférences

| Endpoint | Description |
|----------|-------------|
| `/api/preferences/` | Préférences et indisponibilités des soignants |

### App `rules` — Règles métier

| Endpoint | Description |
|----------|-------------|
| `/api/rules/` | Règles de planning personnalisées |
| `/api/patient-loads/` | Charges patients par unité |
| `/api/staff-loans/` | Prêts de soignants entre services |

---

## 5. Format des réponses

Toutes les réponses sont en **JSON**.

### Réponse succès (GET liste)
```json
[
  { "id": 1, "first_name": "Marie", "last_name": "Dupont", "email": "...", "is_active": true },
  { "id": 2, "first_name": "Jean",  "last_name": "Martin",  "email": "...", "is_active": true }
]
```

### Réponse succès (GET détail enrichi — ex: `/api/staff/1/`)
```json
{
  "id": 1,
  "first_name": "Marie",
  "contracts": [
    { "id": 3, "contract_type": 1, "contract_type_name": "CDI Temps plein",
      "start_date": "2024-01-01", "end_date": null, "workload_percent": 100 }
  ],
  "certifications": [ ... ],
  "staff_roles": [ ... ]
}
```

### Réponse erreur de validation (400)
```json
{
  "error": {
    "constraint": "no_active_contract",
    "message": "Marie Dupont n'a aucun contrat actif le 16/04/2026."
  }
}
```

### Réponse erreur de champ (400 — sérialiseur)
```json
{
  "email": ["Ce champ doit être unique."],
  "start_date": ["Ce champ est obligatoire."]
}
```

---

## 6. Logique des contraintes — endpoint `/api/assignments/`

C'est l'endpoint le plus critique. Il ne fait pas que sauvegarder :
**il vérifie 8 contraintes dures** avant chaque création ou modification.

### Flux d'une création d'affectation

```
POST /api/assignments/
        │
        ▼
  Sérialisation + validation des champs (staff, shift existent ?)
        │
        ▼
  validate_assignment(staff, shift)   ← scheduling/constraints.py
        │
        ├── check_no_overlap()            Pas de chevauchement de gardes
        ├── check_certifications()        Certifications valides à la date
        ├── check_rest_after_night()      Repos réglementaire respecté
        ├── check_max_staff()             Poste non complet
        ├── check_contract_allows_shift() Contrat actif et compatible
        ├── check_no_absence()            Soignant non absent
        ├── check_weekly_hours()          Quota hebdomadaire non dépassé
        └── check_hard_preferences()      Contraintes impératives respectées
        │
        ├── Si une contrainte échoue → HTTP 400 + JSON { "error": { ... } }
        └── Si tout passe       → sauvegarde + HTTP 201 + objet créé
```

Chaque fonction de contrainte lève une `ValidationError(dict)` contenant :

| Clé | Contenu |
|-----|---------|
| `constraint` | Code machine (ex: `"no_active_contract"`) |
| `message` | Explication en français |
| Champs optionnels | `required_certification`, `required_rest_hours`, `absence_start`… |

---

## 7. Comment le front-end appelle l'API

Le JavaScript est embarqué directement dans les templates Django.
Toutes les pages utilisent la fonction utilitaire `apiFetch()` définie dans
`base.html`.

### La fonction `apiFetch()`

```javascript
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),          // ← jeton anti-CSRF obligatoire
    },
  };
  return fetch(url, {
    ...defaults,
    ...options,
    headers: { ...defaults.headers, ...(options.headers || {}) }
  });
}
```

Elle ajoute automatiquement :
- `Content-Type: application/json` sur toutes les requêtes
- `X-CSRFToken` lu depuis la balise `<meta name="csrf-token">` du HTML

### Le jeton CSRF

Django protège toutes les requêtes mutantes (POST, PUT, DELETE) par un
mécanisme anti-CSRF. Le jeton est injecté dans chaque page par le moteur de
templates :

```html
<!-- base.html -->
<meta name="csrf-token" content="{{ csrf_token }}">
```

```javascript
function getCsrf() {
  return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}
```

Sans ce jeton, Django retourne **HTTP 403 Forbidden**.

---

## 8. Exemples de flux complets

### Charger la liste des soignants (GET)

```javascript
const res  = await apiFetch('/api/staff/?format=json');
const data = await res.json();
const staff = data.results || data;  // compatible pagination DRF et liste brute
```

### Créer un soignant (POST)

```javascript
const res = await apiFetch('/api/staff/', {
  method: 'POST',
  body: JSON.stringify({
    first_name: 'Marie',
    last_name:  'Dupont',
    email:      'marie.dupont@hopital.fr',
    phone:      '0612345678',
    is_active:  true,
  }),
});

if (res.ok) {
  const nouveau = await res.json();   // objet créé avec son id
} else {
  const erreurs = await res.json();   // { "email": ["Ce champ doit être unique."] }
}
```

### Créer une affectation avec gestion des contraintes (POST)

```javascript
const res = await apiFetch('/api/assignments/', {
  method: 'POST',
  body: JSON.stringify({ staff: 1, shift: 5 }),
});

if (res.ok) {
  // affectation enregistrée
} else {
  const data = await res.json();
  const err  = data.error || data;
  console.log(err.constraint); // "no_active_contract"
  console.log(err.message);    // "Marie Dupont n'a aucun contrat actif le 16/04/2026."
}
```

### Modifier partiellement (PATCH)

```javascript
await apiFetch('/api/staff/1/', {
  method: 'PATCH',
  body: JSON.stringify({ is_active: false }),
});
```

### Supprimer (DELETE)

```javascript
const res = await apiFetch('/api/assignments/12/', { method: 'DELETE' });
if (res.status === 204) {
  // supprimé avec succès (pas de corps dans la réponse)
}
```

---

## 9. Sérialiseurs : comment les données sont transformées

Les **sérialiseurs** (`serializers.py` dans chaque app) convertissent les
objets Python/Django en JSON et inversement.

### Lecture enrichie vs. écriture simple

Certains ViewSets utilisent deux sérialiseurs différents selon l'action :

```python
# staff/views.py
def get_serializer_class(self):
    if self.action == 'retrieve':   # GET /api/staff/{id}/
        return StaffDetailSerializer   # inclut contrats, certifs, rôles
    return StaffSerializer             # liste simple
```

### Champs calculés (lecture seule)

Certains champs sont ajoutés en lecture seule pour l'affichage :

```python
# staff/serializers.py
class ContractSerializer(serializers.ModelSerializer):
    contract_type_name  = serializers.CharField(source='contract_type.name', read_only=True)
    night_shift_allowed = serializers.BooleanField(source='contract_type.night_shift_allowed', read_only=True)
    max_hours_per_week  = serializers.IntegerField(source='contract_type.max_hours_per_week', read_only=True)
```

Ces champs sont présents dans les réponses JSON mais ignorés à l'écriture
(le front-end envoie uniquement l'`id` du type de contrat).

---

## 10. Structure des fichiers par app

```
hospiplan/
├── hospiplan/          ← configuration du projet
│   ├── settings.py     ← INSTALLED_APPS, base de données, langue
│   ├── urls.py         ← routeur principal (monte tous les /api/)
│   └── wsgi.py         ← point d'entrée WSGI
│
├── staff/              ← soignants, contrats, certifications
│   ├── models.py       ← Staff, Contract, ContractType, Certification…
│   ├── serializers.py  ← JSON ↔ Python
│   ├── views.py        ← ViewSets DRF
│   └── urls.py         ← router.register(...)
│
├── scheduling/         ← gardes, affectations, CONTRAINTES
│   ├── models.py       ← ShiftType, Shift, ShiftAssignment
│   ├── constraints.py  ← 8 fonctions de validation des affectations
│   ├── serializers.py
│   ├── views.py        ← ShiftAssignmentViewSet appelle constraints.py
│   └── urls.py
│
├── services/           ← services hospitaliers, unités de soins
├── absences/           ← absences déclarées
├── preferences/        ← préférences / indisponibilités soignants
├── rules/              ← règles métier avancées
│
└── frontend/           ← pages HTML (pas d'API propre)
    ├── views.py        ← renvoie simplement les templates
    ├── urls.py         ← routes des pages HTML
    └── templates/
        └── frontend/
            ├── base.html           ← sidebar + apiFetch() + CSRF
            ├── dashboard.html
            ├── staff/
            ├── shifts/
            ├── assignments/
            ├── planning/
            └── referentiel/
```

---

## 11. Résumé du cycle de vie d'une requête

```
1. L'utilisateur interagit avec une page HTML (clic, formulaire)
         │
2. JavaScript appelle apiFetch('/api/...', { method, body })
   → ajoute automatiquement Content-Type et X-CSRFToken
         │
3. Django reçoit la requête HTTP
   → vérifie le jeton CSRF (sinon 403)
   → route vers le bon ViewSet via urls.py
         │
4. Le ViewSet DRF
   → désérialise le JSON entrant (valide les types, champs requis)
   → exécute la logique métier (ex: validate_assignment pour les affectations)
   → interroge PostgreSQL via l'ORM Django
         │
5. Le ViewSet retourne une Response DRF
   → sérialise l'objet Python en JSON
   → HTTP 200/201/204 en cas de succès
   → HTTP 400 + { "error": {...} } en cas de contrainte violée
   → HTTP 400 + { "champ": ["erreur"] } en cas d'erreur de validation
         │
6. JavaScript reçoit la réponse
   → affiche un toast de succès ou la carte d'erreur contrainte
   → met à jour l'interface sans rechargement de page
```
