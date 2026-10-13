# Smart Campus Hub (Render edition)
Flask app serving the website and API together. Postgres for data.

## Deploy on Render
1. Push this folder to a GitHub repo (repo root = this folder).
2. Render dashboard -> New -> Blueprint -> pick the repo.
3. When asked, set ADMIN_EMAIL to your email, then Apply.
4. Open the URL, Create account using that same email -> you are admin.

## Run locally
pip install -r requirements.txt && python app.py   (http://localhost:5000, uses SQLite)
