# FastAPI authentication research

Date: 2026-08-01

## Sources

- [FastAPI: OAuth2 with password hashing and JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

## Findings applied to this task

- Passwords must be stored as one-way hashes. The FastAPI guide recommends
  `pwdlib` with the Argon2 algorithm for new password hashes.
- Authentication should be a FastAPI dependency so API authorization is
  enforced by the server, not only by Vue route guards.
- The guide notes that invalid credentials should have a uniform response and
  verifies a dummy hash for unknown users to avoid timing-based account
  enumeration.

## Design decision

The application will use opaque random session tokens rather than JWTs:

- A 30-day token is issued in an `HttpOnly`, `SameSite=Lax` cookie.
- Only a SHA-256 digest of the random token is stored in SQLite, together with
  the user, creation time, and expiry time.
- Logout deletes the matching session record, immediately revoking the token.
- This gives the requested server-side logout/revocation behavior without
  exposing a bearer token to browser JavaScript.

`pwdlib[argon2]` will be added to the Python dependencies. No email
verification, password reset flow, OAuth login, or rate-limiting service is in
scope for this first authentication release.
