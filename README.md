# HospiPlan — Système de gestion du planning hospitalier

HospiPlan est une application web complète de planification du personnel soignant dans un établissement hospitalier. Elle automatise la création des plannings tout en garantissant le respect de la réglementation du travail et des règles métier complexes.

---

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture technique](#2-architecture-technique)
3. [Fonctionnalités](#3-fonctionnalités)
4. [Les 8 contraintes dures](#4-les-8-contraintes-dures--le-cœur-du-système)
5. [Générateur automatique de planning](#5-générateur-automatique-de-planning)
6. [Structure du projet](#6-structure-du-projet)
7. [Installation et démarrage](#7-installation-et-démarrage)
8. [Points forts](#8-points-forts)
9. [Points sensibles et limites connues](#9-points-sensibles-et-limites-connues)
10. [Workflow recommandé](#10-workflow-recommandé)

---

## 1. Vue d'ensemble

HospiPlan répond à un besoin concret des équipes RH hospitalières : **arrêter de faire le planning à la main**. Le système permet de :

- Gérer le personnel soignant (contrats, certifications, absences, préférences)
- Définir les créneaux de garde par unité de soins
- Affecter manuellement des soignants avec vérification automatique des contraintes légales
- **Générer automatiquement un planning hebdomadaire admissible** via une heuristique + recherche locale
- Visualiser le planning en grille (par soignant ou par service)

> Le principe fondamental : **aucune affectation illégale ne peut être enregistrée**, que ce soit manuellement ou via le générateur automatique.

---

## 2. Architecture technique

```
┌──────────────────────────────────────────────────────────┐
│                    Navigateur (HTML/JS)                  │
│         Bootstrap 5 · Vanilla JS · apiFetch()            │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP JSON
┌───────────────────────▼──────────────────────────────────┐
│                   Django 6.0.3 (WSGI)                    │
│         Django REST Framework 3.17.1 (API REST)          │
│         8 apps métier · 1 app frontend                   │
└───────────────────────┬──────────────────────────────────┘
                        │ ORM Django
┌───────────────────────▼──────────────────────────────────┐
│              PostgreSQL (hospiplandb)                     │
└──────────────────────────────────────────────────────────┘
```

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Serveur web | Django (WSGI) | 6.0.3 |
| API REST | Django REST Framework | 3.17.1 |
| Base de données | PostgreSQL | — |
| Interface | Templates Django + Bootstrap 5 | — |
| Scripts JS | Vanilla JavaScript (pas de framework) | — |

### Multi-applications Django

Le backend est découpé en **8 applications indépendantes**, chacune avec ses modèles, sérialiseurs, vues et URLs propres :

| App | Responsabilité |
|-----|---------------|
| `staff` | Soignants, rôles, contrats, certifications, spécialités |
| `scheduling` | Créneaux, affectations, générateur, contraintes |
| `services` | Services hospitaliers, unités de soins |
| `absences` | Déclarations d'absence |
| `preferences` | Préférences et indisponibilités des soignants |
| `rules` | Règles métier avancées, charges patients, prêts |
| `frontend` | Pages HTML (templates Django) |

---

## 3. Fonctionnalités

### Référentiels
- **Services & Unités de soins** — organisation hiérarchique (service → unités)
- **Types de garde** — durée, repos requis, garde de nuit, durée de repos réglementaire
- **Types de contrat** — heures max/semaine, jours de congés, autorisation gardes de nuit, **nuits consécutives max**

### Personnel soignant
- Fiche soignant avec rôles et spécialités
- Gestion des **contrats** directement sur la fiche (CDI/CDD, quotité, dates)
- Gestion des **certifications** avec dates d'obtention et d'expiration
- Indicateur de statut contrat : Actif / À venir / Expiré

### Postes de garde
- Création de créneaux avec unité de soins, type, horaires, effectif min/max
- Certifications requises par créneau

### Affectations manuelles
- Formulaire d'affectation avec **vérification en temps réel des 8 contraintes dures**
- Affichage clair du motif de refus en français
- Vue des soignants déjà affectés sur un créneau
- Suppression sécurisée (vérifie le seuil minimum)

### Planning
- Vue par soignant (ligne = soignant, colonnes = jours)
- Vue par service (ligne = unité de soins, colonnes = jours)
- Mise en évidence du jour courant
- Affichage des absences et des gardes de nuit
- **Brouillon généré automatiquement** visible en orange (pointillé) avant publication

### Génération automatique
- Panneau dédié sur la page Planning
- Sélection de la semaine courante
- Score global et détail des pénalités par contrainte molle
- Boutons : Publier / Annuler / Régénérer

---

## 4. Les 8 contraintes dures — le cœur du système

> Ces contraintes sont **non négociables**. Toute affectation — manuelle ou automatique — les respecte obligatoirement. Une violation entraîne un refus immédiat avec message explicatif.

Elles sont implémentées dans `scheduling/constraints.py` et appelées par `validate_assignment()`.

| # | Code | Description |
|---|------|-------------|
| 1 | `no_overlap` | Un soignant ne peut pas avoir deux gardes qui se chevauchent |
| 2 | `missing_certification` | Le soignant doit posséder toutes les certifications requises, valides à la date de la garde |
| 3 | `insufficient_rest` | Après une garde marquée "repos obligatoire", le soignant doit respecter un délai de repos réglementaire (ex : 11h après une nuit) |
| 4 | `shift_full` | Le créneau ne peut pas dépasser son effectif maximum |
| 5 | `no_active_contract` / `night_shift_not_allowed` | Le soignant doit avoir un contrat actif à la date de la garde ; les gardes de nuit nécessitent une autorisation contractuelle |
| 6 | `staff_absent` | Un soignant en absence déclarée ne peut pas être affecté |
| 7 | `weekly_hours_exceeded` | Le total d'heures sur la semaine ne peut pas dépasser le quota contractuel |
| 8 | `hard_preference_violated` | Les contraintes d'indisponibilité déclarées comme impératives sont respectées |

### Format des erreurs retournées (API)

```json
{
  "error": {
    "constraint": "insufficient_rest",
    "message": "Marie Dupont doit respecter 11h de repos après 'Garde de nuit' (fin le 17/04/2026 à 07:00). Repos disponible : 8.5h seulement.",
    "required_rest_hours": 11,
    "actual_rest_hours": 8.5
  }
}
```

---

## 5. Générateur automatique de planning

Le générateur (`scheduling/generator.py`) produit un **brouillon admissible** pour une semaine donnée, sans jamais violer de contrainte dure.

### Fonctionnement en 2 phases

```
Phase 1 : Heuristique gloutonne (construction)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pour chaque créneau (trié du plus contraint au moins contraint) :
  1. Lister les soignants éligibles (8 contraintes dures vérifiées)
  2. Calculer un score de pénalité pour chaque candidat
  3. Affecter celui avec le score le plus bas
  4. Si aucun éligible → créneau marqué "non pourvu", signalé

Phase 2 : Recherche locale (amélioration, 300 itérations)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Essayer des échanges aléatoires entre deux affectations :
  - Accepter si le score global diminue
  - Accepter si les contraintes dures restent respectées
  - Sinon, annuler l'échange
```

### Les 7 contraintes molles (pénalités)

Les contraintes molles ne bloquent pas — elles **orientent le choix** du soignant via un score de pénalité pondéré.

| Contrainte | Poids | Description |
|------------|-------|-------------|
| Nuits consécutives | 10 | Pénalise si le soignant dépasse son quota de nuits consécutives (configurable par type de contrat) |
| Préférences | 8 | Pénalise si le créneau tombe sur une indisponibilité non impérative déclarée |
| Équilibre de charge | 6 | Pénalise l'écart-type du nombre de gardes par soignant sur la semaine |
| Changements de service | 4 | Pénalise si un soignant travaille dans plusieurs services différents sur la même semaine |
| Équité week-ends | 5 | Pénalise si un soignant a déjà plus de gardes de week-end que la moyenne sur le trimestre |
| Service non familier | 3 | Pénalise si le soignant n'a jamais travaillé dans ce service |
| Continuité de soins | 2 | Pénalise si le soignant n'était pas dans la même unité la veille |

**Score final** = somme pondérée des pénalités. Plus le score est bas, meilleur est le planning.

### Workflow de génération

```
POST /api/plannings/generate/   →  Crée un brouillon (PlanningSession)
        ↓
  Vérification dans la grille (cellules orange pointillées)
        ↓
POST /api/plannings/{id}/publish/  →  Convertit en vrais ShiftAssignment
     OU
DELETE /api/plannings/{id}/        →  Annule et supprime le brouillon
```

> **Important :** le générateur affecte des soignants aux créneaux **existants**. Les créneaux (horaires, unités) doivent être créés au préalable dans la section "Postes / Gardes".

---

## 6. Structure du projet

```
hospiplan/
├── hospiplan/              ← Configuration Django
│   ├── settings.py         ← BDD, apps, langue (fr-FR), fuseau (Europe/Paris)
│   ├── urls.py             ← Routeur principal (/api/ + pages)
│   └── wsgi.py             ← Point d'entrée serveur
│
├── staff/                  ← Personnel soignant
│   ├── models.py           ← Staff, ContractType, Contract, Certification…
│   ├── serializers.py      ← JSON ↔ Python (ContractSerializer enrichi)
│   ├── views.py            ← ViewSets DRF
│   └── urls.py             ← /api/staff/, /api/contracts/, etc.
│
├── scheduling/             ← Cœur métier : gardes + affectations
│   ├── models.py           ← ShiftType, Shift, ShiftAssignment
│   │                          PlanningSession, DraftAssignment
│   ├── constraints.py      ← 8 fonctions de contraintes dures
│   ├── generator.py        ← Algorithme heuristique + recherche locale
│   ├── serializers.py      ← Sérialiseurs dont PlanningSessionSerializer
│   ├── views.py            ← CRUD + generate + publish
│   └── urls.py             ← /api/shifts/, /api/assignments/, /api/plannings/
│
├── services/               ← Services hospitaliers & unités de soins
├── absences/               ← Absences déclarées
├── preferences/            ← Préférences / indisponibilités
├── rules/                  ← Règles métier, charges patients, prêts
│
└── frontend/               ← Interface utilisateur (templates Django)
    ├── views.py            ← Rendu des pages HTML
    ├── urls.py             ← Routes des pages
    └── templates/frontend/
        ├── base.html                       ← Layout sidebar + utilitaires JS
        ├── dashboard.html                  ← Tableau de bord
        ├── staff/form.html                 ← Fiche soignant + gestion contrats
        ├── staff/list.html                 ← Liste soignants
        ├── shifts/form.html                ← Création/édition de créneau
        ├── shifts/list.html                ← Liste créneaux
        ├── assignments/form.html           ← Affectation manuelle + contraintes
        ├── planning/planning.html          ← Grille planning + générateur
        └── referentiel/
            ├── services.html              ← Services & unités de soins
            ├── shift_types.html           ← Types de garde
            └── contract_types.html        ← Types de contrat
```

---

## 7. Installation et démarrage

### Prérequis

- Python 3.12+
- PostgreSQL
- pip

### Configuration

```bash
# 1. Cloner le projet
git clone <url-du-repo>
cd hospiplan

# 2. Installer les dépendances
pip install django djangorestframework psycopg2-binary

# 3. Configurer la base de données (hospiplan/settings.py)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'hospiplandb',
        'USER': 'postgres',
        'PASSWORD': 'votre_mot_de_passe',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# 4. Appliquer les migrations
python manage.py migrate

# 5. Creer le compte d'acces (obligatoire : l'application est protegee)
python manage.py createsuperuser
#    Identifiant       : fabrice
#    Adresse e-mail    : fabrice@gmail.com
#    Mot de passe      : 123456
#    -> Django signale que ce mot de passe est trop court et trop courant :
#       repondre "y" a la question "Bypass password validation ?"

# 6. Lancer le serveur
python manage.py runserver
```

L'application est accessible sur `http://127.0.0.1:8000` et redirige vers
`/login/` tant qu'aucune session n'est ouverte.

### Compte de demonstration

| Champ | Valeur |
|-------|--------|
| Identifiant | `fabrice` |
| Adresse e-mail | `fabrice@gmail.com` |
| Mot de passe | `123456` |
| Droits | Superutilisateur (acces `/admin/` inclus) |

> **Compte de developpement uniquement.** Ce mot de passe ne respecte pas les
> `AUTH_PASSWORD_VALIDATORS` du projet (moins de 8 caracteres, figurant dans la
> liste des mots de passe courants). Il doit etre change avant toute mise en
> ligne, depuis `/admin/` ou via `python manage.py changepassword fabrice`.

### Authentification

L'integralite de l'application est protegee : aucune page ni aucun endpoint
de l'API n'est accessible sans session ouverte.

| Element | Comportement |
|---------|--------------|
| `/login/` | Page de connexion (seul point d'entree public) |
| `/logout/` | Deconnexion (POST, bouton dans la barre laterale) |
| Pages frontend | `@login_required` -> redirection vers `/login/?next=...` |
| API REST (`/api/...`) | `IsAuthenticated` + `SessionAuthentication` -> HTTP 403 si anonyme |
| Session | Expiration apres 8 h d'inactivite, prolongee a chaque requete |

Les comptes sont geres depuis l'admin Django (`/admin/`) ou via
`python manage.py createsuperuser`. Cote navigateur, `apiFetch()` intercepte
les reponses 401/403 et renvoie automatiquement vers la page de connexion
lorsque la session a expire.

### Ordre de saisie recommandé (première utilisation)

```
1. Référentiels → Services & Unités       (créer les services hospitaliers)
2. Référentiels → Types de garde          (matin, soir, nuit…)
3. Référentiels → Types de contrat        (CDI, CDD, temps partiel…)
4. Soignants → Nouveau soignant           (puis ajouter contrats sur la fiche)
5. Postes / Gardes → Nouveau poste        (créer les créneaux de la semaine)
6. Planning → Générer                     (ou affecter manuellement)
```

---

## 8. Points forts

### Garantie légale absolue
Aucune affectation ne peut être enregistrée en violation des 8 contraintes dures, **quel que soit le canal** (interface manuelle, API, générateur automatique). La validation est centralisée dans `constraints.py` et appelée systématiquement.

### Messages d'erreur exploitables
Les refus d'affectation retournent un message en français avec le détail précis : heures de repos manquantes, certification expirée, nom de l'absence… Les RH comprennent immédiatement la cause et la solution.

### Génération en mémoire (performances)
Le générateur pré-charge **toutes les données nécessaires en une seule série de requêtes SQL** avant la boucle principale. Les vérifications de contraintes sont ensuite entièrement in-memory. Pour une structure de 3 à 20 soignants, la génération est synchrone et s'exécute en moins de 2 secondes.

### Système de brouillon
Le planning généré est d'abord un **brouillon** (non publié), visible dans la grille en orange pointillé. Les RH peuvent le vérifier, le régénérer ou le modifier manuellement avant de le publier définitivement. Lors de la publication, chaque affectation est re-validée contre les contraintes dures.

### Score de qualité transparent
Le système calcule et affiche un **score de pénalité** détaillé par contrainte molle. Les RH savent exactement pourquoi le planning est "imparfait" (ex : 2 soignants ont plus de week-ends que les autres) et peuvent régénérer ou corriger manuellement.

### Architecture découplée
Le frontend appelle uniquement l'API REST. La logique métier est entièrement côté backend. Un futur changement d'interface (application mobile, autre framework) ne nécessite aucune modification des contraintes ou de l'algorithme.

### Interface sans rechargement de page
Toutes les opérations CRUD (soignants, contrats, créneaux, affectations) se font via `fetch()` en JSON. L'expérience utilisateur est fluide sans rechargement.

---

## 9. Points sensibles et limites connues

### Le générateur n'est pas un créateur de créneaux
**Point critique :** le générateur automatique affecte des soignants aux créneaux **existants**. Si aucun créneau n'est créé pour la semaine cible, la génération retourne 0 affectations. Les créneaux doivent être saisis au préalable dans "Postes / Gardes".

### Créneaux déjà complets
Un créneau dont l'effectif maximum est déjà atteint (par des affectations manuelles antérieures) sera marqué "non pourvu" par le générateur. Ce n'est pas un bug — c'est la contrainte dure n°4 qui s'applique.

### Contrainte molle n°7 (continuité de soins) simplifiée
Faute de modèle "patient" dans la base, la continuité de soins est interprétée comme : *le même soignant dans la même unité de soins sur des jours consécutifs*. Pour une continuité patient-niveau, il faudrait un modèle d'hospitalisation dédié.

### Contrainte molle n°4 (préférences) basée sur le texte
La détection des jours d'indisponibilité repose sur la présence de mots-clés français dans le champ `description` de la préférence (ex : "lundi", "mardi"…). Une préférence mal rédigée ne sera pas détectée.

### Métaheuristique limitée à des swaps simples
La recherche locale n'effectue que des **échanges de paires** (2-opt). Des techniques avancées (recuit simulé, algorithme génétique, ALNS) permettraient de meilleures solutions sur de grandes instances, mais sont hors scope pour une structure de moins de 20 soignants.

### Pas d'authentification
L'application ne comporte pas de système de connexion utilisateur. Toutes les pages et l'API sont accessibles sans authentification. À implémenter avant tout déploiement en production.

### CSRF et sessions Django
La protection CSRF est assurée via une balise `<meta name="csrf-token">` injectée dans `base.html`. Toutes les requêtes mutantes (`POST`, `PUT`, `DELETE`) passent par `apiFetch()` qui ajoute automatiquement le header `X-CSRFToken`. Sans ce mécanisme, Django retournerait HTTP 403.

### Performances sur grandes structures
L'algorithme est synchrone et conçu pour 3 à 20 soignants. Pour une structure de 50+ soignants avec des centaines de créneaux, la génération pourrait dépasser 10 secondes. Dans ce cas, il faudrait basculer vers une tâche asynchrone (Celery + Redis) avec retour de progression.

---

## 10. Workflow recommandé

### Mise en place initiale (une seule fois)

```
Référentiels
  └── Créer les types de contrat (CDI 35h, CDD 28h, nuits max 3…)
  └── Créer les types de garde (Matin 8h, Soir 8h, Nuit 12h + repos 11h…)
  └── Créer les services et unités de soins

Personnel
  └── Créer chaque soignant
  └── Ouvrir la fiche → ajouter son contrat actif
  └── Ajouter ses certifications si requis
  └── Déclarer ses préférences / indisponibilités
```

### Chaque semaine

```
Lundi ou vendredi précédent :
  1. Postes / Gardes → créer les créneaux de la semaine
     (ou dupliquer des créneaux types si la structure est stable)

  2. Planning → ouvrir la semaine → cliquer "Générer le planning"
     → vérifier le score et les créneaux non pourvus
     → si insatisfaisant : régénérer ou corriger manuellement

  3. Vérifier les créneaux non pourvus :
     - Soignant sans contrat actif ? → créer/renouveler le contrat
     - Créneau déjà plein ? → augmenter max_staff ou créer un 2e créneau
     - Absence ? → affecter un remplaçant manuellement

  4. Publier le planning
     → les affectations deviennent définitives
     → chaque affectation est re-vérifiée (contraintes dures)

  5. En cours de semaine : modifications manuelles possibles
     → toujours soumises aux 8 contraintes dures
```

---

## Résumé des URLs de l'application

| Page | URL |
|------|-----|
| Tableau de bord | `/` |
| Liste soignants | `/staff/` |
| Nouveau soignant | `/staff/add/` |
| Fiche soignant (+ contrats) | `/staff/{id}/edit/` |
| Liste postes de garde | `/shifts/` |
| Nouveau poste | `/shifts/add/` |
| Affectation manuelle | `/assignments/new/` |
| Planning + générateur | `/planning/` |
| Services & Unités | `/referentiel/services/` |
| Types de garde | `/referentiel/shift-types/` |
| Types de contrat | `/referentiel/contract-types/` |
| API REST (DRF) | `/api/` |
| Administration Django | `/admin/` |
