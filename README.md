# fastapi-node-auth

Full-stack authentication project using **FastAPI + SQLite + bcrypt** (Python) and **Express + sessions** (Node.js), with a dark/light themed frontend.

## Project Structure

```
fastapi-node-auth/
|-- main.py              # FastAPI backend (login, register, SQLite, bcrypt)
|-- server.js            # Express frontend server (sessions, routes)
|-- .gitignore
|-- public/
    |-- index.html       # Home page with navbar + dark/light toggle
    |-- login.html       # Login page (Gmail or phone number)
    |-- register.html    # Register page
```

## Setup

### Python (FastAPI backend)

```bash
pip install fastapi uvicorn sqlalchemy passlib[bcrypt] pydantic
python main.py
```

Runs on `http://127.0.0.1:8080`

### Node.js (Express frontend)

```bash
npm install express express-session body-parser
node server.js
```

Runs on `http://localhost:3000`

## Features

- Register with Gmail or phone number
- Passwords hashed with bcrypt (never stored in plain text)
- User data stored in SQLite via SQLAlchemy
- Session-based login/logout with Express
- Dark / Light theme toggle (saved to localStorage)
- Responsive, modern UI

## Security

- bcrypt password hashing via Passlib
- `httpOnly` + `sameSite` session cookies
- Input validation on both frontend and backend
- Passwords must be at least 8 characters
- `users.db` excluded from version control via `.gitignore`
