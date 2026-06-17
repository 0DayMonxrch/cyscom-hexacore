# Hexacore - CYSCOM Webinar Registration Portal

Welcome to the **Hexacore** project repository! This is a cyberpunk-themed, interactive registration portal designed for CYSCOM's Cybersecurity webinars and events. It features a high-performance Python backend and a lightweight, dependency-free vanilla frontend.

## 🚀 Tech Stack

**Frontend:**
* HTML5 / CSS3 (Custom Cyberpunk / Terminal UI)
* Vanilla JavaScript (DOM manipulation, asynchronous API calls, seamless transitions)
* Google Fonts (`Anton`, `Inter`, `Roboto Mono`)

**Backend:**
* Python 3.8+
* [FastAPI](https://fastapi.tiangolo.com/) (High-performance API framework)
* Uvicorn (ASGI web server)
* SQLAlchemy (ORM for database interactions)

**Database:**
* PostgreSQL (Hosted via [Supabase](https://supabase.com/))

---

## 📂 Project Structure

```text
/
├── main.py               # The FastAPI backend server and database routing
├── requirements.txt      # Python dependencies
├── index.html            # The main landing page / portal gateway
└── register.html         # The primary registration form and transition logic



🛠️ Local Development Setup
To run this project locally and make changes, follow these steps:

1. Prerequisites
Ensure you have Python 3.8+ installed.

You will need a code editor like VS Code with the "Live Server" extension installed to serve the frontend files.

2. Backend Setup
Open your terminal in the project root directory and run the following commands:

Create a Virtual Environment (Recommended):

Bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
Install Dependencies:
(If you do not have a requirements.txt, you can install them directly)

Bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic email-validator
3. Database Configuration
This project uses a cloud-hosted Supabase PostgreSQL database.

Open main.py.

Locate the SQLALCHEMY_DATABASE_URL variable.

Ensure it is populated with your active Supabase connection string.
(Format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres)

4. Ignite the Server
Start the FastAPI backend server:

Bash
uvicorn main:app --reload
The API will now be running at http://127.0.0.1:8000. You can view the automatic API documentation by visiting http://127.0.0.1:8000/docs.

5. Launch the Frontend
Open index.html or register.html using the Live Server extension in VS Code.
Note: Because CORS is configured in main.py to allow all origins (["*"]), your local frontend will successfully communicate with your local backend without security blocks.



🧑‍💻 Making Changes to the Project
Modifying the Database Schema
If you need to add new questions to the registration form (e.g., "Expected Graduation Year"):

Backend (main.py): Add the new column to the User SQLAlchemy class and the CompetitionRegister Pydantic model. Update the mapping in the /register-participant route.

Database: You must drop the existing users table in your Supabase dashboard so SQLAlchemy can rebuild it with the new columns on the next server restart.

Frontend (register.html): Add the new HTML input element, extract its .value in the JavaScript submit event listener, and add it to the JSON.stringify payload.

Modifying the Theme / Aesthetics
The visual identity of Hexacore is strictly controlled by CSS variables found at the top of the <style> block in the HTML files.

Light Mode/Dark Mode: Toggle logic is handled via the .dark class appended to the <body> tag.

To change the primary accent colors, locate and modify --accent-yellow and --accent-blue in the :root pseudo-class.




🔒 Security Notes
Environment Variables: Currently, the database connection string is hardcoded. Before pushing to a public GitHub repository, move the SQLALCHEMY_DATABASE_URL to a .env file and use the python-dotenv library to load it securely.