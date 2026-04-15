# Habit Tracker (Django + React)

Habit Tracker is a full-stack application to manage personal routines, track daily completion, and analyze consistency over time.

This repository contains:

- Backend API: Django + Django REST Framework (JWT auth)
- Frontend SPA: React + Vite + Axios + Recharts

## Tech Stack

### Backend

- Python 3.11+
- Django 6
- Django REST Framework
- SimpleJWT
- django-cors-headers

### Frontend

- React 19
- Vite
- Axios
- Recharts
- ESLint

## Project Structure

```text
habit-tracker/
	config/                # Django settings, URL routing, WSGI/ASGI
	habits/                # Domain app: models, serializers, views, tests
	media/                 # User uploaded files (avatars)
	manage.py
	requirements.txt

habit-tracker-frontend/
	src/
		api/                 # HTTP clients and API wrappers
		components/          # UI components
		hooks/               # Reusable React hooks
		utils/               # UI helpers and formatting utils
	package.json
	vite.config.js
```

## Installation (Step by Step)

### 1. Backend Setup

From `habit-tracker`:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend default URL: `http://127.0.0.1:8000`

### 2. Frontend Setup

From `habit-tracker-frontend`:

```bash
pnpm install
pnpm dev
```

Frontend default URL: `http://127.0.0.1:5173`

## Environment Variables

### Backend (`habit-tracker/.env`)

Required for production:

- `ENV`: `development` or `production`
- `SECRET_KEY`: strong secret key (50+ chars recommended)
- `DEBUG`: `true` or `false`
- `ALLOWED_HOSTS`: comma-separated hosts
- `TIME_ZONE`: example `America/Bogota`
- `CORS_ALLOW_ALL_ORIGINS`: `true` or `false`
- `CORS_ALLOWED_ORIGINS`: comma-separated frontend origins
- `CSRF_TRUSTED_ORIGINS`: comma-separated trusted origins
- `DRF_THROTTLE_ANON`: API rate for anonymous traffic (default `60/min`)
- `DRF_THROTTLE_USER`: API rate for authenticated traffic (default `180/min`)

Optional JWT settings:

- `JWT_ROTATE_REFRESH_TOKENS`
- `JWT_BLACKLIST_AFTER_ROTATION`

### Frontend (`habit-tracker-frontend/.env`)

- `VITE_API_BASE_URL`: API base URL (example `http://127.0.0.1:8000/api`)

## Development Commands

### Backend

```bash
python manage.py test
python manage.py runserver
```

### Frontend

```bash
pnpm lint
pnpm build
pnpm preview
```

## Production Build

### Frontend

```bash
pnpm build
```

Build output is generated in `habit-tracker-frontend/dist`.

### Backend

Use production settings via `.env` and run with Gunicorn/Uvicorn behind Nginx.

## Deployment Guide (Reference)

### Option A: VPS + Nginx + Gunicorn

1. Provision Ubuntu server
2. Install Python, Node, Nginx
3. Deploy backend and frontend source
4. Build frontend (`pnpm build`) and serve static files via Nginx
5. Run backend with Gunicorn:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
```

6. Configure Nginx reverse proxy:
   - `/api/` -> Gunicorn
   - `/media/` -> media folder
   - `/` -> frontend `dist`

### Option B: Docker

Recommended container strategy:

- `backend` service: Django + Gunicorn
- `frontend` service: built static assets
- `nginx` service: reverse proxy and static serving
- `postgres` service for production-grade DB

## API Endpoints (Main)

Base path: `/api`

### Authentication

- `POST /register/`
- `POST /token/`
- `POST /token/refresh/`

### Profile

- `GET /profile/`
- `PATCH /profile/`

### Habits

- `GET /habits/`
- `POST /habits/`
- `PATCH /habits/{id}/`
- `DELETE /habits/{id}/`
- `GET /habits/by-date/?date=YYYY-MM-DD`
- `GET /habits/weekly/?start_date=YYYY-MM-DD`
- `GET /habits/tracker-metrics/?start_date=YYYY-MM-DD`
- `GET /habits/history/?days=90`
- `GET /habits/leaderboard/`

### Logs

- `POST /logs/` (upsert by `habit + date`)

## Business Rules (Current)

- Habit edit/delete is allowed only on Sundays.
- Habit creation is allowed any day.
- Weekly navigation is constrained by registration week and current week.
- Daily log updates are only allowed for today.

## Security Notes

- Use HTTPS in production.
- Keep `SECRET_KEY` private and strong.
- Keep `DEBUG=false` in production.
- Restrict CORS and CSRF trusted origins.
- Consider HttpOnly refresh token strategy for frontend auth hardening.

## Testing Strategy

Current automated coverage includes API behavior for:

- Authentication and registration
- User data isolation
- Habit log ownership and upsert flow
- Weekly/history/tracker metrics shape and constraints

Recommended next step:

- Add frontend unit/integration tests (Vitest + Testing Library).
