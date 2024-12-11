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

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Yaneww11/massage-reservation-system.git
    cd massage-reservation-system
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
