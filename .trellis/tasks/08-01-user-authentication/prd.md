# Add user authentication

## Goal

Add first-party user authentication and authorization so users can register,
log in, and log out, while keeping each user's stories private. Administrator
accounts can access content belonging to every user.

## Requirements

- Visitors can create an account, log in, and log out from the Vue application.
- Authentication is enforced by the FastAPI API; the frontend alone must not be
  trusted to protect data.
- Ordinary users can create, read, update, delete, and generate content only
  for novels they own, including associated characters, relations, and chapters.
- Administrator accounts can access and manage every user's novels and their
  associated content.
- Administrators are identified by an `ADMIN_EMAILS` environment variable;
  a user whose registered email matches that allowlist receives administrator
  access automatically.
- Existing SQLite data must remain usable after the schema upgrade and receive
  an explicit ownership policy: the first administrator to register or log in
  automatically claims all legacy novels that have no owner.
- Passwords must never be stored in plaintext.
- Successful login persists for 30 days unless the user explicitly logs out.
- The application provides usable login and registration views and redirects
  unauthenticated visitors away from protected views.
- The story workspace must remain usable on narrow mobile viewports without
  horizontal overflow.
- Each chapter's default continuation must be distinguishable from its
  alternative branches, and users must be able to change that choice.

## Acceptance Criteria

- [ ] A visitor can register, log in, and log out.
- [ ] Unauthenticated API requests to protected resources are rejected.
- [ ] A normal user cannot list, retrieve, mutate, or generate against another
      user's novel or its child resources.
- [ ] An administrator can list and operate on all users' novels.
- [ ] An email listed in `ADMIN_EMAILS` receives administrator access after
      registration.
- [ ] Existing SQLite databases upgrade without data loss and their historical
      novels are claimed by the first administrator account.
- [ ] Password storage uses a one-way password hash.
- [ ] A successful login remains valid for 30 days and logout invalidates the
      current session.
- [ ] The frontend presents authentication screens and prevents access to the
      library, creation, and novel routes until authenticated.
- [ ] Mobile story views have no horizontal overflow and preserve access to
      chapter navigation, writing, and reading controls.
- [ ] The chapter directory identifies a default next chapter, shows the
      active path, and labels alternative siblings as branches.
- [ ] Existing chapter trees retain every node and receive a deterministic
      default continuation; users can choose a different continuation later.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
