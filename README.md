# Massage Reservation System

This project is a web application for managing massage reservations. It allows users to create, edit, and delete reservations, as well as leave comments about their experience.

## Features

- User authentication and profile management
- Create, edit, and delete massage reservations
- Leave comments on the masseur's profile
- View working hours and available slots
- Responsive design for mobile and desktop

## Technologies Used

- Python
- Django
- JavaScript
- HTML/CSS

## Installation (Linux)

1. Clone the repository:
    ```bash
    git clone https://github.com/Yaneww11/massageProject.git
    ```

2. Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Apply migrations:
    ```bash
    python manage.py migrate
    ```

5. Create a superuser:
    ```bash
    python manage.py createsuperuser
    ```

6. Run the development server:
    ```bash
    python manage.py runserver
    ```

7. Open your browser and go to `http://127.0.0.1:8000/` to access the application.

## Usage

- Register a new user or log in with an existing account.
- Navigate to the reservation page to create a new reservation.
- Edit or delete existing reservations from your profile page.
- Leave comments on the masseur's profile page.

## Contributing

Contributions are welcome! Please fork the repository and create a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## Google OAuth setup ("Continue with Google")

1. In [Google Cloud Console](https://console.cloud.google.com/) create (or pick) a project, then
   **APIs & Services → Credentials → Create Credentials → OAuth client ID** (type: *Web application*).
   Configure the OAuth consent screen first if prompted (External, app name, support email).
2. Add **Authorized redirect URIs** for every language prefix and host:
   - `http://localhost:8000/bg/accounts/google/login/callback/`
   - `http://localhost:8000/en/accounts/google/login/callback/`
   - the same two paths on the production domain, over `https`.
3. Put the credentials in `.env`:

   ```
   GOOGLE_OAUTH_CLIENT_ID=<client id>.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
   ```

4. Restart the server. The button lives on the login/register modal.

# Ngrok
Stop:
pkill ngrok
pkill -f "manage.py runserver"

Run again later (two terminals, or one + background):
# Terminal 1
source venv/bin/activate
python manage.py runserver 8000

# Terminal 2
ngrok http 8000
