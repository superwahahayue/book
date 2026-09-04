# Implementation plan: user authentication

1. Add `pwdlib[argon2]` and implement models for users, server-side sessions,
   and novel ownership, including idempotent SQLite migration and indexes.
2. Extend settings and `.env.example` with administrator allowlisting, the
   30-day session setting, and cookie security configuration.
3. Add authentication schemas and a focused backend auth module for password
   hashing, session lifecycle, current-user resolution, legacy ownership claim,
   and owner-or-admin authorization.
4. Add registration, login, logout, and current-user API endpoints. Protect
   every existing content endpoint and filter novel listings by ownership.
5. Add frontend auth API methods, reactive authenticated-user state, login and
   registration pages, router guards, and a signed-in account/logout control.
6. Update README with configuration, migration behavior, and HTTPS cookie
   guidance.
7. Add or update tests for authentication and authorization boundaries; run
   backend checks and `npm run build`.

8. Add the idempotent `chapters.is_primary` migration, expose it in chapter
   responses, and add an authorized operation to select the primary child.
9. Update generation so the first child is the default continuation and later
   siblings are branches; cover migration, ordering, and reassignment with
   backend tests.
10. Rework the story directory and reader around default continuation,
    branch labels, active-path context, and a direct next-chapter action.
11. Harden the mobile workspace CSS and validate it at a narrow viewport with
    long story and chapter titles, then run the full backend checks and
    frontend build.

## Review gates

- Verify no plaintext password or raw session token is stored in SQLite.
- Verify normal-user requests for another user's novel, character, relation,
  chapter, generation, and suggestion endpoints all fail with 404.
- Verify an administrator can perform those operations for any novel.
- Verify unclaimed legacy novels are assigned once, only by the first
  administrator, and are not visible to regular users.
