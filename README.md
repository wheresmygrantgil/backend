# Grand Grant Matcher Backend

A minimal FastAPI backend for storing likes and dislikes of researchers on grants.
This backend is private (frontend is public via GitHub Pages) and designed to be lightweight, secure, and scalable.


---

Features

Vote storage: Each researcher can like or dislike each grant (one vote per researcher per grant, can update).

Endpoints:

1. Total likes/dislikes per grant.


2. Specific researcher’s vote on a grant.


3. All votes by a researcher.


4. Submit or update a vote.



Security:

Rate limiting (5 requests/minute per IP).

Input validation (alphanumeric IDs).

CORS protection (only frontend + localhost allowed).


Database:

SQLite by default (file-based).

Postgres-ready for future scaling.




---

Repository Structure

grantscout-backend/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI entrypoint
│   ├── database.py    # DB connection
│   ├── models.py      # SQLAlchemy model
│   ├── schemas.py     # Pydantic schemas
│   └── routes.py      # API endpoints
├── requirements.txt
├── .env.example       # Example environment variables
├── Dockerfile         # For Render deployment
└── README.md          # This documentation


---

Tech Stack

FastAPI (API framework)

SQLAlchemy (ORM)

SQLite (default DB, easy local dev)

SlowAPI (rate limiting)

Docker (for deployment)

PostgreSQL (future migration target)



---

Setup Instructions

1. Clone the repository

git clone <repo-url>
cd grantscout-backend

2. Create and activate virtual environment

python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

3. Install dependencies

pip install -r requirements.txt

4. Configure environment variables

Copy .env.example to .env:

cp .env.example .env

By default:

DATABASE_URL=sqlite:///./votes.db

For Postgres later, use:

DATABASE_URL=postgresql://user:password@host:5432/dbname


---

Run Locally

uvicorn app.main:app --reload

Access API docs: http://127.0.0.1:8000/docs


---

## API Endpoints

All endpoints return JSON. The live API provides interactive docs at `/docs`.

### POST /vote
Create or update a researcher's vote for a grant.

Request body:
```json
{
  "grant_id": "123abc",
  "researcher_id": "gil",
  "action": "like"
}
```
Response:
```json
{"status": "success"}
```

### GET /votes/{grant_id}
Return total likes and dislikes for a grant.

Example response:
```json
{
  "grant_id": "123abc",
  "likes": 10,
  "dislikes": 3
}
```

### GET /vote/{grant_id}/{researcher_id}
Return a researcher's vote on a grant.

Example response:
```json
{
  "grant_id": "123abc",
  "researcher_id": "gil",
  "action": "like"
}
```

### GET /votes/researcher/{researcher_id}
List all votes submitted by a researcher.

Example response:
```json
[
  {"grant_id": "123abc", "action": "like"},
  {"grant_id": "456xyz", "action": "dislike"}
]
```

---

Security & Rate Limiting

Rate limit: 5 votes per minute per IP (configured with slowapi).

ID validation: grant_id and researcher_id must be alphanumeric, _, or -.

CORS: Only allows:

https://wheresmygrants.github.io

http://localhost:3000 (dev)




---

Deployment on Render

Docker-based deployment

1. Push repo to GitHub.


2. Create a new Web Service on Render:

Connect repo.

Select branch to deploy.

Build Command:

pip install -r requirements.txt

Start Command:

uvicorn app.main:app --host 0.0.0.0 --port 10000

Environment variable:

DATABASE_URL=sqlite:///./votes.db



3. Deploy → Render will provide a public API URL like:

https://grantscout-backend.onrender.com




---

Migrating to PostgreSQL

When traffic grows, move to Postgres in 3 steps:

1. Provision Postgres
Use Render, Neon, or Supabase free tier.


2. Update .env
Replace DATABASE_URL with Postgres URL:

DATABASE_URL=postgresql://user:password@host:5432/dbname


3. Redeploy
SQLAlchemy will create tables automatically.



Migrating existing SQLite data

sqlite3 votes.db .dump | psql <postgres-url>


---

Future Enhancements

Authentication: Restrict votes to logged-in researchers.

Analytics: Aggregate vote trends per grant.

Admin endpoints: Export votes for analysis.

Email notifications: Notify researchers of grant updates.



---

Development Notes

Keep backend private (votes are sensitive).

Frontend remains public on GitHub Pages.

Always store secrets in .env, never commit them.

Rate limiting & input validation are in place; review if adding new endpoints.
