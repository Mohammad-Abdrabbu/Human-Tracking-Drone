# Running the SAHTD Backend

This document covers how to set up and run the SAHTD backend with the SQLite user database.

## Quick Start

### 1. Initialize the Database

```bash
cd web/backend
python scripts/init_db.py --seed
```

This creates `~/sahtd/data/db/sahtd.db` and seeds default users:
- **operator@uop.edu.jo** / secret123 (role: operator)
- **viewer@uop.edu.jo** / viewer123 (role: viewer)

### 2. Start the Server

```bash
cd web/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Test Login

```bash
# Login as operator
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"operator@uop.edu.jo","password":"secret123"}'

# Expected response:
# {"access_token":"eyJ...","token_type":"bearer","role":"operator"}
```

## Environment Variables

### Database Seeding

| Variable | Default | Description |
|----------|---------|-------------|
| `SAHTD_OPERATOR_EMAIL` | operator@uop.edu.jo | Operator account email |
| `SAHTD_OPERATOR_PASSWORD` | secret123 | Operator account password |
| `SAHTD_VIEWER_EMAIL` | viewer@uop.edu.jo | Viewer account email |
| `SAHTD_VIEWER_PASSWORD` | viewer123 | Viewer account password |

### JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | change-me-in-.env | JWT signing key (CHANGE IN PRODUCTION!) |
| `JWT_ALGORITHM` | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | Token expiration in minutes |

## User Management

### List Users (Operator Only)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"operator@uop.edu.jo","password":"secret123"}' | jq -r .access_token)

curl -s http://localhost:8000/auth/users \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Create User (Operator Only)

```bash
curl -X POST http://localhost:8000/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"securepass","role":"viewer"}'
```

### Disable User / Reset Password (Operator Only)

```bash
# Disable a user (revokes all their tokens)
curl -X PATCH http://localhost:8000/auth/users/2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active":false}'

# Reset password (revokes all their tokens)
curl -X PATCH http://localhost:8000/auth/users/2 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password":"newpassword123"}'
```

## Token Versioning

Each user has a `token_version` field. When this is incremented:
- All existing JWTs for that user become invalid
- User must re-authenticate

Token version is incremented when:
- User is disabled (`is_active=false`)
- Password is reset
- Role is changed

## Database Location

The SQLite database is stored at:
```
~/sahtd/data/db/sahtd.db
```

You can inspect it with:
```bash
sqlite3 ~/sahtd/data/db/sahtd.db ".schema users"
sqlite3 ~/sahtd/data/db/sahtd.db "SELECT id, email, role, is_active FROM users;"
```

## Resetting the Database

To completely reset the database and reseed users:

```bash
cd web/backend
python scripts/init_db.py --force-reseed
```

> ⚠️ **Warning**: This deletes all users and recreates the default ones.
