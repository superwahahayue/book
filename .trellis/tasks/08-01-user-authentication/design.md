# Design: user authentication and ownership

## Scope

Implement self-service registration, email/password login, logout, and
per-user authorization. Administrators configured with `ADMIN_EMAILS` retain
access to all application content. Login lasts 30 days.

Out of scope: email verification, password reset, external identity providers,
multi-factor authentication, and account-management UI beyond the signed-in
identity and logout action.

## Data model and migration

```text
users
  id, email (unique), password_hash, is_admin, created_at

auth_sessions
  id, user_id -> users.id, token_hash (unique), expires_at, created_at

novels
  ... existing fields ..., owner_id -> users.id (nullable during migration)
```

`init_db()` continues to use its idempotent SQLite migration pattern:

1. Create the new `users` and `auth_sessions` tables via SQLAlchemy metadata.
2. Add nullable `novels.owner_id` to existing databases and index it.
3. On first registration or login by an administrator, atomically assign every
   legacy novel with a null owner to that administrator. New novels always get
   a non-null owner.

Keeping the column nullable during transition protects existing databases that
have no administrator yet. A normal user cannot access unclaimed novels;
administrators can claim them through the automatic first-admin rule.

## Authentication contract

`POST /api/auth/register`
: JSON `{ email, password }`; normalize email, hash password with Argon2,
  derive `is_admin` from `ADMIN_EMAILS`, create a session, set the session
  cookie, and return safe user fields.

`POST /api/auth/login`
: JSON `{ email, password }`; use a generic invalid-credentials response,
  create a 30-day session, set the same cookie, and return safe user fields.

`POST /api/auth/logout`
: Require the current session; delete it and clear the browser cookie.

`GET /api/auth/me`
: Return the authenticated user's id, email, and administrator flag.

The session cookie contains an opaque, cryptographically random token. SQLite
stores only its SHA-256 digest. Cookie settings are `HttpOnly`, `SameSite=Lax`,
path `/`, and a 30-day max age. `AUTH_COOKIE_SECURE` controls the Secure flag:
false for local HTTP development, true for HTTPS deployment.

## Authorization flow

```text
Browser cookie -> get_current_user dependency -> validated session + user
                                              -> route ownership helper
                                              -> resource/service operation
```

All existing novel, character, relation, and chapter APIs depend on the
current user. The authorization helper allows access when the user is an
administrator or owns the resource's parent novel. It returns 404 for a
resource outside a normal user's scope, avoiding cross-account resource
disclosure. The novel list query filters by `owner_id` for normal users and
returns all novels for administrators.

Chapter generation and option suggestion use the same protected novel lookup
before starting background work, so ownership is checked before any LLM call.

## Configuration

Add these settings and document them in `.env.example` and README:

- `ADMIN_EMAILS` — comma-separated, case-insensitive normalized email allowlist.
- `AUTH_SESSION_DAYS=30` — session lifetime.
- `AUTH_COOKIE_SECURE=false` — set `true` behind HTTPS.

## Frontend flow

- Add login and registration views plus an API module for auth endpoints.
- Keep authenticated user state in a small reactive module backed by
  `GET /api/auth/me`; never persist the token in localStorage because the
  browser manages the HttpOnly cookie.
- A global router guard loads the current user before entering library,
  creation, and novel routes, redirecting visitors to login and returning them
  to their original path after authentication.
- Add a login/register link and signed-in email/logout control to the top bar.
- Axios sends cookies with requests; a 401 response clears local auth state and
  redirects to login.

## Verification plan

- Backend tests cover password hashing, registration, login failure, session
  expiry/logout, owner isolation, administrator access, and legacy ownership
  claim.
- Run Python syntax/import checks and API tests with a temporary SQLite DB.
- Run `npm run build` to validate Vue routes and components.
