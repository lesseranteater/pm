# Backend API

All board routes require the authenticated `pm_session` cookie created by
`POST /api/auth/login`. Responses contain the current user's board after every
successful mutation. The frontend uses same-origin `/api` requests.

## Board Response

```json
{
  "id": "board-mvp",
  "name": "Spring launch",
  "columns": [
    {
      "id": "column-backlog",
      "name": "Backlog",
      "position": 0,
      "cards": [
        {
          "id": "card-brief",
          "title": "Shape the product brief",
          "details": "...",
          "position": 0
        }
      ]
    }
  ]
}
```

## Routes

### `GET /api/board`

Returns the authenticated user's board, columns, and ordered cards.

### `PATCH /api/board/columns/{column_id}`

Request:

```json
{ "name": "Ready for review" }
```

Renames an owned column. Columns cannot be added or removed.

### `POST /api/board/cards`

Request:

```json
{
  "column_id": "column-backlog",
  "title": "Prepare demo",
  "details": "Confirm the walkthrough"
}
```

Appends a card to the selected column.

### `PATCH /api/board/cards/{card_id}`

Updates one or both editable fields:

```json
{ "title": "Updated title", "details": "Updated details" }
```

### `DELETE /api/board/cards/{card_id}`

Deletes an owned card and compacts the source column's positions.

### `POST /api/board/cards/{card_id}/move`

Request:

```json
{ "column_id": "column-done", "position": 0 }
```

Moves an owned card and compacts both source and destination columns. Omit
`position` to append to the destination column.

### `POST /api/ai/board`

Request:

```json
{
  "question": "Move the research card into progress.",
  "history": [
    { "role": "user", "content": "What should I do next?" },
    { "role": "assistant", "content": "Review the planned work." }
  ]
}
```

Returns the assistant response and updated board. The structured response
contract and supported operations are documented in
[`AI-OPERATIONS.md`](AI-OPERATIONS.md).

## Errors

- `401`: no valid authenticated session.
- `404`: board, column, or card is missing or belongs to another user.
- `422`: invalid fields or an invalid destination position.

Mutations use one SQLite transaction. A failed mutation does not partially
change board state.
