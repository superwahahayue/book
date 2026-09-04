# Authentication Guidelines

## Session model

- Use opaque, cryptographically random session tokens in the `novel_session`
  `HttpOnly`, `SameSite=Lax` cookie. Do not put authentication tokens in
  localStorage or return raw tokens in API payloads.
- Store only the SHA-256 digest of a token in `auth_sessions`; logout deletes
  the corresponding row and therefore immediately revokes the session.
- Session duration comes from `AUTH_SESSION_DAYS`. Set `AUTH_COOKIE_SECURE=true`
  when serving the application through HTTPS.

## Passwords and users

- Store passwords only with `pwdlib`'s recommended Argon2 hash.
- User emails are trimmed and lower-cased before lookup and persistence.
- `ADMIN_EMAILS` is the only source of administrator access. Re-evaluate this
  allowlist when resolving the current user so configuration changes take
  effect without a database migration.

## Resource authorization

- Every content endpoint must depend on `get_current_user`.
- A normal user may access a `Novel` only when `novel.owner_id == user.id`; an
  administrator may access any novel.
- Character, relation, and chapter endpoints must authorize via their parent
  novel, not merely by receiving a resource ID.
- Return 404, not 403, when an ordinary user requests another user's resource
  so resource existence is not disclosed.
- New novels always receive the authenticated creator as `owner_id`.

## Legacy data

- `novels.owner_id` remains nullable only to support old SQLite databases.
- The first administrator who registers or logs in claims all unowned legacy
  novels. Never expose unowned novels to ordinary users.
