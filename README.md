# FYP Local Development Notes

## Run the Django server

- Start server from `profyp` with `python manage.py runserver`
- Open app using `http://127.0.0.1:8000/`

## HTTPS warning in terminal

If you see messages like:

- `You're accessing the development server over HTTPS, but it only supports HTTP.`
- `code 400, message Bad request version (...)`

that means HTTPS traffic reached the local HTTP dev server.

Use HTTP locally (not HTTPS), and disable browser HTTPS-only/force-HTTPS behavior for localhost if needed.
