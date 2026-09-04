# Chapter Tree Guidelines

## Default continuation

- `chapters.is_primary` identifies the one default child of a chapter. It is a
  local parent-child choice, not a global chapter order.
- A root chapter must never be marked primary. A parent may have zero or one
  primary child; every other child is an alternative branch.
- New generation marks the first child as primary. Later children under the
  same parent are branches.

## Migration and mutation

- SQLite upgrades must preserve every existing chapter. When older sibling
  groups have no primary child, select the lowest `(index, id)` child.
- Selecting a primary child must clear the flag from every sibling in the same
  transaction. Do not allow a generic chapter patch to create multiple primary
  children.
- Tree API responses order the primary child before its branch siblings, then
  preserve chronological `(index, id)` ordering.

## Frontend contract

- Chapter detail and tree responses both expose `is_primary`.
- The UI must label the default continuation distinctly from branches and offer
  an explicit action to choose another child as the default. Never present all
  child chapters as indistinguishable "branches".
