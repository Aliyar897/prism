# Prism

**Smart link-in-bio for creators who are more than one thing.**

Prism lets creators run multiple personas from a single link — Fan, Brand, and Professional — and automatically serves the right one to each visitor based on where they came from, what device they're on, and when they arrive.

---

## Features

- **Smart audience detection** — automatically shows Fan, Brand, or Professional persona based on referrer, device, and time signals
- **Multi-persona dashboard** — manage bio, avatar, links, and CTA for each persona independently
- **AI bio generator** — generate tailored bios per persona using Groq (llama-3.1-8b-instant)
- **Brand Kit** — niche tags, collaboration formats, and past brand partners (Pro)
- **Media Kit Stats** — engagement rate, avg views, audience age, growth rate (Pro)
- **Stripe billing** — Pro plan at $9/mo with Stripe Checkout and Customer Portal
- **Google OAuth + email/password** auth via django-allauth
- **User feedback** — in-app feedback modal saved to database and emailed to admin
- **Coming soon** — Auto Stats: pull cumulative stats from all social platforms automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.5 |
| Auth | django-allauth 65.16.1 (email + Google OAuth) |
| Payments | Stripe 15.1.0 |
| AI | Groq API (llama-3.1-8b-instant) |
| Database | SQLite (dev) → PostgreSQL (production) |
| Email | Gmail SMTP |
| Frontend | Vanilla JS + Tabler Icons + DM Sans |

---

## Local Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd prism
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file in the project root (see `.env.example`):

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

# Gmail SMTP
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Groq AI
GROQ_API_KEY=gsk_...

# Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

### 3. Run migrations and start the server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Start Stripe webhook listener (separate terminal)

```bash
.\stripe listen --forward-to localhost:8000/stripe/webhook/
```

---

## Project Structure

```
prism/
├── accounts/               # Main app
│   ├── models.py           # Profile, Persona, PersonaLink, Feedback, VisitEvent
│   ├── views.py            # All views including Stripe webhooks and AI bio
│   ├── urls.py
│   ├── adapter.py          # Google OAuth adapter (auto-connects existing accounts)
│   ├── detector.py         # Audience detection logic
│   ├── forms.py            # Custom signup form with username validation
│   ├── templates/
│   │   └── accounts/
│   │       ├── dashboard.html
│   │       ├── profile.html       # Public link-in-bio page
│   │       ├── landing.html
│   │       ├── onboarding.html
│   │       ├── pricing.html
│   │       ├── settings.html
│   │       └── partials/
│   │           └── persona_panel.html
│   └── static/accounts/
│       ├── css/dashboard.css
│       └── css/profile.css
├── prism/                  # Django project settings
│   ├── settings.py
│   └── urls.py
├── templates/              # allauth templates (login, signup, email)
├── manage.py
└── requirements.txt
```

---

## Personas

| Persona | Audience | Active on Free |
|---|---|---|
| Fan | General followers / social media | Yes |
| Brand | Sponsors and brand partners | Pro only |
| Professional | Recruiters / collaborators | Coming soon |

---

## Plans

| Feature | Free | Pro |
|---|---|---|
| Active personas | 1 (Fan only) | All 3 |
| Links per persona | 3 | Unlimited |
| Brand Kit | — | Yes |
| Media Kit Stats | — | Yes |
| AI bio generation | Yes | Yes |

---

## Admin

Access the Django admin at `/admin/` to view:
- **Feedback** — all user feedback with rating and message
- **Profiles** — plan status, Stripe IDs
- **Personas & Links** — all persona content
- **Visit Events** — audience detection logs

---

## Deployment (Railway / Render)

Before deploying:
1. Set `DEBUG=False`
2. Add your domain to `ALLOWED_HOSTS`
3. Switch to PostgreSQL (`dj-database-url`)
4. Add `whitenoise` for static files
5. Switch Stripe to live mode keys
6. Register the live webhook endpoint in Stripe dashboard

---

## License

Private — all rights reserved.
