# Blueprint Health Dashboard

Dashboard santé personnel alimenté par les données Apple Watch. Affiche les tendances hebdomadaires et génère des recommandations IA actionnables via un pipeline multi-modèles.

## Aperçu

| Page | Description |
|---|---|
| 📊 Dashboard | Graphiques hebdomadaires : sommeil, HRV, FC repos, VO2max, entraînements |
| 🤖 Recommandations | 3 modèles IA en parallèle → arbitrage judge → score/10 + recos priorisées |
| 📥 Import | Upload JSON Health Auto Export (iOS) |

## Stack

- **Frontend** : Streamlit 1.45.0
- **IA** : OpenRouter — `claude-sonnet-4-6`, `grok-3`, `gpt-4.1` + judge `claude-sonnet-4-6`
- **BDD** : PostgreSQL — vue `agg.health_weekly` générée par dbt
- **Deploy** : Docker, Traefik (reverse proxy + TLS), Dokploy (orchestration)
- **Auth** : Basic auth Traefik

## Architecture IA — Pipeline Recommandations

```
health_weekly (12 sem)
        │
        ▼
┌───────────────────────────────────┐
│  3 modèles en parallèle (async)   │
│  claude-sonnet │ grok-3 │ gpt-4.1 │
└───────────┬───────────────────────┘
            │  3 analyses JSON
            ▼
     Judge (claude-sonnet-4-6)
            │  synthèse fusionnée
            ▼
   raw.health_recommendations
            │
            ▼
   Affichage Streamlit
   score/10 · wins · warnings · recos
```

Chaque modèle reçoit les 12 dernières semaines de données + cibles de référence (HRV ≥ 50ms, sommeil ≥ 7h, VO2max ≥ 52...). Le judge fusionne les 3 analyses, conserve les recommandations convergentes (≥ 2 modèles), et produit un score pondéré.

## Structure

```
health-dashboard/
├── app/
│   ├── main.py                        # Page d'accueil Streamlit
│   ├── lib/
│   │   ├── ai.py                      # Pipeline IA (appels OpenRouter, judge)
│   │   ├── db.py                      # Connexion PostgreSQL, requêtes
│   │   └── config.py                  # Settings (pydantic-settings) + cibles métriques
│   └── pages/
│       ├── 1_📊_Dashboard.py
│       ├── 2_🤖_Recommandations.py
│       └── 3_📥_Import.py
├── .streamlit/config.toml
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Variables d'environnement

| Variable | Description |
|---|---|
| `SUPABASE_DB_PASSWORD` | Mot de passe PostgreSQL |
| `OPENROUTER_API_KEY` | Clé API OpenRouter |
| `MODEL_1` | Modèle 1 (défaut : `anthropic/claude-sonnet-4-6`) |
| `MODEL_2` | Modèle 2 (défaut : `x-ai/grok-3`) |
| `MODEL_3` | Modèle 3 (défaut : `openai/gpt-4.1`) |
| `MODEL_JUDGE` | Modèle arbitre (défaut : `anthropic/claude-sonnet-4-6`) |
| `DB_HOST` | Host PostgreSQL (défaut : `localhost`) |
| `DB_PORT` | Port PostgreSQL (défaut : `5433`) |

Copier `.env.example` vers `.env` et remplir les valeurs.

## Déploiement (VPS)

Le projet tourne via Dokploy sur `health.patronusguardian.org`.

```bash
# Build image
docker build -t health-dashboard:latest .

# Redéployer via Dokploy
dokploy compose.deploy --data '{"composeId":"A2-4jDj1giUISkrriYhso"}'
```

Les variables d'environnement sensibles sont gérées dans Dokploy (pas dans le repo).

## Prérequis données

La vue `agg.health_weekly` doit exister dans PostgreSQL. Elle est générée par le projet dbt `data-platform` à partir des données brutes ingérées via la page Import ou le Health Report Bot.

## Notes importantes

- `asyncio.run()` ne fonctionne pas directement dans Streamlit (event loop déjà actif). Le pipeline IA utilise un `ThreadPoolExecutor` pour contourner ça.
- Le parser JSON utilise `json-repair` comme fallback si le modèle retourne du JSON malformé.
- Le champ `score` dans la réponse du judge peut être un dict `{"value": N, "rationale": "..."}` ou un simple nombre — les deux sont gérés.
