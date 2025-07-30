## API Endpoints

All endpoints return JSON. The live API provides interactive docs at `/docs`.

### POST /vote
Create or update a researcher's vote for a grant.

Request body:
```json
{
  "grant_id": "abc-1234",
  "researcher_id": "Zeevi, Gil",
  "action": "like"
}
```
Response:
```json
{"status": "success"}
```
The backend adds a timestamp to each vote automatically; clients do not send it.

### GET /votes/{grant_id}
Return total likes and dislikes for a grant.

Example response:
```json
{
  "grant_id": "abc-1234",
  "likes": 10,
  "dislikes": 3
}
```

### GET /vote/{grant_id}/{researcher_id}
Return a researcher's vote on a grant.

Example response:
```json
{
  "grant_id": "abc-1234",
  "researcher_id": "Zeevi, Gil",
  "action": "like"
}
```
If the researcher has not voted on the grant, `action` will be `null` and the
request still returns HTTP 200.

### GET /votes/researcher/{researcher_id}
List all votes submitted by a researcher.

Example response:
```json
[
  {"grant_id": "abc-1234", "action": "like"},
  {"grant_id": "xyz-789", "action": "dislike"}
]
```
If the researcher has not voted yet, the response is an empty list.

### DELETE /vote/{grant_id}/{researcher_id}
Remove a researcher's vote on a grant.

Example response:
```json
{"status": "deleted"}
```

### GET /votes/top?limit=10
List top voted grants sorted by likes (descending).

Example response:
```json
[
  {"grant_id": "abc-1234", "likes": 15, "dislikes": 5},
  {"grant_id": "xyz-789", "likes": 10, "dislikes": 2}
]
```

### GET /votes/ratio/{grant_id}
Return like/dislike percentage for a grant.

Example response:
```json
{
  "grant_id": "abc-1234",
  "likes": 15,
  "dislikes": 5,
  "like_percentage": 75.0,
  "dislike_percentage": 25.0
}
```

### GET /researcher/{researcher_id}/summary
Summary of a researcher's voting activity.

Example response:
```json
{
  "total_votes": 12,
  "likes": 8,
  "dislikes": 4,
  "recent_votes": [
    {"grant_id": "abc-1234", "action": "like", "timestamp": "..."}
  ]
}
```

### GET /votes/export/json
Export all votes as JSON list.

Example response:
```json
[
  {"grant_id": "abc-1234", "researcher_id": "Zeevi, Gil", "action": "like", "timestamp": "2025-07-25T12:00:00Z"}
]
```

### GET /votes/export/csv
Download all votes as CSV file.

### GET /votes/trend/{grant_id}
Votes over time grouped by day for graphing.

### GET /health
Lightweight service check and basic voting stats.

Example response:
```json
{
  "status": "ok",
  "total_votes": 125,
  "unique_grants": 12,
  "unique_researchers": 8,
  "top_grant": {
    "grant_id": "abc123",
    "likes": 25,
    "dislikes": 2
  },
  "last_vote_timestamp": "2025-07-26T09:30:00Z"
}
```

---
