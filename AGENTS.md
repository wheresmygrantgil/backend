
AGENTS.md

This document explains how an automation agent should build, maintain, and extend the grantscout-backend repository.
The backend provides a minimal REST API for recording and retrieving likes/dislikes on grants by researchers.


---

Purpose of This Backend

Store votes (like or dislike) on grants.

Support:

1. Vote per researcher per grant (one record, can update).


2. Total likes/dislikes per grant.


3. Researcher’s vote on a specific grant.


4. All votes by a researcher across all grants.



Built with FastAPI + SQLite, Postgres-ready for future scaling.

Deployed as a private backend (frontend is public via GitHub Pages).



---

Agent Responsibilities

1. Repository Setup

Create repo grantscout-backend (private).

Use structure:


grantscout-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── routes.py
├── requirements.txt
├── .env.example
├── README.md
└── Dockerfile

Initialize Python virtual environment.

Install dependencies from requirements.txt.



---

2. Core Implementation

Database Layer

SQLite file votes.db via SQLAlchemy ORM.

Models defined in models.py:

Vote(grant_id, researcher_name, action)



Endpoints

POST /vote: Create or update vote.

GET /votes/{grant_id}: Total likes/dislikes for a grant.

GET /vote/{grant_id}/{researcher_name}: Researcher’s specific vote on a grant.

GET /votes/researcher/{researcher_name}: All votes by researcher.


Vote Logic

One vote per researcher per grant.

Can change from like → dislike (or vice versa).

Composite key (grant_id, researcher_name) ensures uniqueness.



---

3. Security

Rate Limiting

Limit 5 requests per minute per IP using slowapi.


Validation

grant_id must be alphanumeric, underscore or hyphen.
researcher_name may include letters, numbers, spaces, commas, apostrophes and hyphens.

Reject malformed IDs (HTTP 400).


CORS

Allow only GitHub Pages frontend and localhost.



---

4. Deployment

Render Deployment

Backend is containerized (Dockerfile).

Render build commands:

pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 10000


.env variable:

DATABASE_URL=sqlite:///./votes.db



---

5. Future Migration to PostgreSQL

Code already uses DATABASE_URL → switchable to Postgres by updating .env:

DATABASE_URL=postgresql://user:password@host:5432/dbname

Redeploy without code changes.

Data migration: sqlite3 votes.db .dump | psql <postgres-url>



---

Agent Tasks Checklist

1. Initialize Repo

Create folder structure.

Add Python environment files and .env.example.



2. Implement Backend

Create models, database connection, and routes.

Ensure rate limiting and ID validation are present.



3. Configure CORS

Allow https://wheresmygrants.github.io and http://localhost:3000.



4. Testing

Verify endpoints:

POST /vote (new vote and update).

GET /votes/{grant_id} (aggregate counts).

GET /vote/{grant_id}/{researcher_name} (specific vote).

GET /votes/researcher/{researcher_name} (all votes for researcher).




5. Prepare Deployment

Add Dockerfile.

Provide deployment instructions in README.md.



6. Document Postgres Migration

Include steps to migrate in README.





---

Agent Rules

Always validate inputs.

Do not expose database credentials in code (use .env).

Keep backend repo private, frontend can remain public.

Future features (authentication, analytics) must not break existing endpoints.

Use SQLAlchemy ORM for portability.



---

Endpoints Summary

POST /vote

Request Body:

{
  "grant_id": "123abc",
  "researcher_name": "gil",
  "action": "like"
}

GET /votes/{grant_id}

Response:

{
  "grant_id": "123abc",
  "likes": 10,
  "dislikes": 3
}

GET /vote/{grant_id}/{researcher_name}

Response:

{
  "grant_id": "123abc",
  "researcher_name": "gil",
  "action": "like"
}

GET /votes/researcher/{researcher_name}

Response:

[
  {"grant_id": "123abc", "action": "like"},
  {"grant_id": "456xyz", "action": "dislike"}
]
l
