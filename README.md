# Habit Tracker Backend

REST API to manage user habits with JWT authentication.

## Features

- User registration.
- JWT login with access and refresh tokens.
- Authenticated user profile endpoint.
- User-scoped habit CRUD.
- Daily habit status tracking (`done`, `missed`, `skip`, `pending`).
- Weekly metrics per habit and per day.
- Historical metrics for daily, weekly, and monthly comparisons.
- Case-insensitive login for username.
- User profile fields: first name, last name, avatar URL, birth date, weight, and gender.
- Avatar file upload support (JPG, PNG, WEBP up to 2MB).
- Baseline-aware metrics to avoid showing fake historical percentages before account/habit start.

## Requirements

- Python 3.11+
- pip

## Setup

1. Create a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Start the server.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment Variables

Create a `.env` file (or export these values in your shell):

- `SECRET_KEY`: Django secret key.
- `DEBUG`: `true` or `false`.
- `ALLOWED_HOSTS`: comma-separated hosts. Example: `127.0.0.1,localhost`.
- `CORS_ALLOW_ALL_ORIGINS`: `true` or `false`.
- `CORS_ALLOWED_ORIGINS`: comma-separated origins. Example: `http://127.0.0.1:5173,http://localhost:5173`.

## Main Endpoints

Base URL: `/api`

### Auth

- `POST /register/`: register a new user.
- `POST /token/`: returns `access` and `refresh`.
- `POST /token/refresh/`: refreshes `access`.
- `GET /profile/`: returns the authenticated user profile.

### Habits

- `GET /habits/`
- `POST /habits/`
- `PATCH /habits/{id}/`
- `DELETE /habits/{id}/`
- `GET /habits/by-date/?date=YYYY-MM-DD`
- `GET /habits/weekly/?start_date=YYYY-MM-DD`
- `GET /habits/history/?days=90`

### Logs

- `POST /logs/` (upsert by `habit + date`)

Rules:

- You can only view and modify your own habits and logs.
- You cannot write logs for another user's habit.
- You cannot mark `done` on a future date.
- Sending `pending` removes the existing log for that date.
- Editing habit days preserves historical applicability using schedule snapshots.

## Weekly Metrics

`GET /habits/weekly/` returns:

- `habits`: list of habits with `week` and `completion_rate`.
- `daily_percentages`: percentage for each day.
- `average_completion`: true weekly average across applicable days.

## Historical Metrics

`GET /habits/history/` returns:

- `daily`: completion trend by date.
- `weekly`: aggregated completion per week.
- `monthly`: aggregated completion per month.
- `summary`: average daily completion and active day count.

## Profile

`GET /profile/` and `PATCH /profile/` include:

- `username` (read-only)
- `email`
- `first_name`
- `last_name`
- `avatar_url`
- `avatar` (uploaded image)
- `avatar_file_url` (resolved media URL)
- `birth_date`
- `weight_kg`
- `gender`

Validation:

- Avatar file types: JPG, PNG, WEBP.
- Avatar max size: 2MB.

## Admin

Django admin is already available at `/admin/`.

Create an admin user with:

```bash
python manage.py createsuperuser
```

## Tests

```bash
python manage.py test
```

Includes tests for:

- User registration.
- Per-user data isolation.
- Log ownership protection.
- Log upsert behavior.
- Weekly metrics response shape.
