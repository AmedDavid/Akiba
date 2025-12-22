# Akiba - Smart Savings Goal Tracker

A production-ready Django application for tracking savings goals, analyzing M-Pesa statements, and building a community around smart saving habits.

## Features

- **User Authentication**: Register, login, logout, and profile management
- **Savings Goals**: Create, track, and achieve savings goals with progress visualization
- **Daily Saving Log**: Track daily savings with streak tracking
- **M-Pesa Analysis**: Upload PDF statements and get automatic spending insights
- **Tribes (Communities)**: Join or create savings communities, share posts, and compete on leaderboards
- **Leaderboards**: National and tribe-specific leaderboards for top savers and streak champions
- **Freemium Model**: Free tier with core features, Pro tier (KSh 199/month) with unlimited access
- **Payment Integration**: M-Pesa (Daraja API) and Stripe payment support

## Tech Stack

- Django 5.x
- SQLite (default database)
- Bootstrap 5 (via CDN)
- Tailwind CSS (via CDN)
- Chart.js for visualizations
- PyPDF2 for M-Pesa statement parsing
- Pillow for image handling

## Setup Instructions

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

### 5. Configure Environment Variables

Create a `.env` file in the project root (copy from `.env.example` if available):

```bash
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True

# Ngrok Configuration (for local development with ngrok)
# Add your ngrok domain here (e.g., abc123.ngrok-free.app)
# This will be automatically added to ALLOWED_HOSTS
NGROK_DOMAIN=your-ngrok-domain.ngrok-free.app

# Pro Plan Pricing
# Set to 199 for production (KSh 199/month)
# Set to 1 for testing
PRO_MONTHLY_PRICE=199

# M-Pesa Daraja API (Sandbox)
MPESA_CONSUMER_KEY=your_consumer_key_here
MPESA_CONSUMER_SECRET=your_consumer_secret_here
MPESA_SHORTCODE=174379
MPESA_PASSKEY=your_passkey_here
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
MPESA_CALLBACK_URL=

# Stripe (Test keys)
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_secret_here
```

**Important Configuration Notes:**

- **NGROK_DOMAIN**: If you're using ngrok for local development, add your ngrok domain here (e.g., `abc123.ngrok-free.app`). This will automatically be added to `ALLOWED_HOSTS`. Leave empty if not using ngrok.

- **PRO_MONTHLY_PRICE**: Set the Pro plan subscription price in Kenyan Shillings. Default is `199` for production. Set to `1` for testing purposes.

- **Payment Credentials**: For development/testing, you can use sandbox/test credentials. The app will work without payment configuration, but payment features won't function.

### 6. Run Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` to see the application.

## Project Structure

```
Akiba/
├── akiba_project/          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   # Main application
│   ├── models.py          # UserProfile, Goal, DailySaving, MpesaStatement, Tribe, TribePost
│   ├── views.py           # All view functions
│   ├── forms.py           # Django forms
│   ├── urls.py            # URL routing
│   ├── admin.py           # Admin panel configuration
│   └── signals.py         # Auto-create UserProfile
├── templates/             # HTML templates
│   ├── base.html          # Base template with vintage design
│   └── core/              # App-specific templates
├── media/                 # User-uploaded files
│   ├── statements/        # M-Pesa PDF statements
│   └── avatars/           # User avatars
├── static/                # Static files (if any)
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## Key Models

- **UserProfile**: Extended user profile with avatar, phone, total_saved, streaks
- **Goal**: Savings goals with target amount, deadline, category, progress tracking
- **DailySaving**: Daily savings log with amount and notes
- **MpesaStatement**: Uploaded PDF statements with parsed spending data
- **Tribe**: Community groups for savers
- **TribePost**: Posts within tribes

## Features in Detail

### Savings Goals
- Create goals with title, target amount, deadline, and category
- Visual progress indicators (progress bars and circles)
- Daily check-in functionality
- Automatic achievement detection with confetti celebration
- Projected finish date calculation

### M-Pesa Analysis
- Upload PDF statements
- Automatic transaction parsing and categorization:
  - Betting
  - Airtime
  - Fuliza/M-Shwari
  - Bars/Restaurants
  - Till withdrawals
  - Other spending
- Spending insights with visual charts
- "You spent X on betting — that's a PS5" style callouts

### Streaks
- Daily check-in system
- Current streak tracking
- Longest streak record
- Visual flame icon for active streaks

### Tribes
- Create public or private tribes
- Join/leave functionality
- Post sharing within tribes
- Tribe-specific leaderboards
- Member lists

### Leaderboards
- National top savers
- Streak champions
- Fastest goal achievers
- Tribe-specific rankings

## Design System

The application has:
- Vintage color palette (cream, dark brown, deep red, gold)
- Playfair Display for headings, DM Sans for body text, Cinzel for display
- Aged paper texture background
- Vintage photo filters
- Specific button styles with shadows and hover effects
- Card designs with border styles and hover animations

## Admin Panel

Access the admin panel at `/admin/` after creating a superuser. All models are registered and can be managed through the Django admin interface.

## Media Files

User-uploaded files are stored in:
- `media/statements/` - M-Pesa PDF statements
- `media/avatars/` - User profile pictures

These directories are excluded from Git via `.gitignore`.

## Development Notes

- The project uses SQLite by default (suitable for development)
- All templates extend `base.html`
- Forms use manual Bootstrap styling to match the vintage aesthetic
- M-Pesa PDF parsing uses regex patterns (may need adjustment for different statement formats)
- Confetti animation uses canvas-confetti library for goal achievements

## Documentation

Comprehensive documentation is available:

- **[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)** - Complete project documentation with all features, setup, and usage
- **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** - Detailed API endpoint reference
- **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** - Developer guide for extending the project
- **[docs/FEATURE_COMPARISON.md](docs/FEATURE_COMPARISON.md)** - Comparison of planned vs implemented features
- **[docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)** - Production deployment guide

## Future Enhancements

- Email notifications for goal deadlines
- Export savings reports
- Mobile app integration
- Advanced M-Pesa statement parsing
- AI integration (Gemini) for personalized financial advice
- Merchant blocking feature
- Voice notes from top savers

## License

This project is part of a bootcamp final project.

## Author

Built as a production-ready Django application for smart savings tracking.

