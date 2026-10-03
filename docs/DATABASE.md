# Database Approach

## Storage

The MVP uses SQLite through Python's built-in `sqlite3` module. The database
path is read from `DATABASE_PATH`; if it is not set, the application uses
`data/app.db` at the repository root. The parent directory is created when the
application initializes.

SQLite is sufficient for this local, single-container MVP and avoids adding an
ORM or separate database service before the data model is validated.

## Initialization

`backend/app/database.py` owns schema creation and deterministic seed data.
FastAPI initializes the database during application startup. Initialization is
idempotent and uses `CREATE TABLE IF NOT EXISTS` plus `INSERT OR IGNORE` for
seed records.

The seed contains:

- One user: `user`.
- One board: `Spring launch`.
- Five fixed columns: Backlog, Planned, In progress, Review, and Done.
- Four demo cards distributed across the board.

The password representation is a deterministic PBKDF2 hash for the seeded
credential. Authentication and session behavior are implemented in Part 4, not
in this phase.

## Ownership And Ordering

- Each board belongs to one user, enforced by a unique `boards.user_id`.
- Columns belong to boards and use a zero-based `position`.
- Cards belong to columns and use a zero-based `position`.
- Foreign keys are enabled for every SQLite connection.
- Cascading deletes preserve ownership cleanup when later mutation behavior is
  implemented.

The machine-readable schema is in [`database-schema.json`](database-schema.json).

## Future Work

- Add authentication and session lifecycle in Part 4.
- Add API reads and mutations in Part 5.
- Add migration handling if the schema changes after the MVP.
- Add backup or export behavior only if explicitly required.
