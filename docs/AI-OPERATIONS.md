# Structured AI Board Operations

`POST /api/ai/board` is an authenticated backend route. It sends the current
board, the user's question, and validated conversation history to OpenRouter.
The model must return JSON matching this contract:

```json
{
  "response": "I moved the research card into progress.",
  "operations": [
    {
      "op": "move_card",
      "card_id": "card-research",
      "column_id": "column-progress",
      "position": 0
    }
  ]
}
```

`operations` is optional and may contain up to 20 operations. Supported
operation shapes are:

- `create_card`: `column_id`, `title`, and optional `details`.
- `edit_card`: `card_id` and one or both of `title` and `details`.
- `move_card`: `card_id`, `column_id`, and optional non-negative `position`.
- `delete_card`: `card_id`.
- `rename_column`: `column_id` and `name`.

The backend rejects unknown IDs, non-owned columns/cards, blank values,
unknown operation types, extra fields, duplicate card targets, duplicate
column renames, invalid positions, and conflicting batches. It validates the
complete operation list against the current board before applying anything.

All valid operations run in one SQLite transaction. If any validation or
database step fails, no operation from the batch is persisted. A successful
response returns the assistant text and the updated board.
