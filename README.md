# notion-db

A small Python wrapper around the [official Notion SDK](https://github.com/ramnes/notion-sdk-py) (`notion-client`) that makes working with a Notion database feel like working with a simple key-value store — no model classes to declare. Point it at a database id and use plain dicts of property name → value; property types are resolved automatically from the database's own schema.

- **No schema classes to write** — types are read from the database itself, once, and cached.
- **Sync and async, both first-class** — `NotionDB` and `AsyncNotionDB` share the exact same logic; the sync client is a thin wrapper around the async one.
- **Automatic pagination** — iterate a query and every page is fetched transparently.
- **A small query builder** — plain dicts for simple equality filters, `F(...)` for comparisons/`&`/`|`.

## Install

```bash
pip install -e ".[dev]"
```

Set a Notion integration token in the `NOTION_TOKEN` environment variable, or pass `token=...` explicitly.

## Usage

```python
import os
from notion_db import NotionDB, F

db = NotionDB(database_id=os.environ["TASKS_DB_ID"])

# create / update / delete: database id + property name + value, nothing else
page = db.create({"Name": "Ship notion-db v0.1", "Status": "Not Started", "Priority": "High"})
db.update(page.id, {"Status": "Done"})
db.delete(page.id)  # archives -- Notion has no hard delete via the API

# query: simple equality filters are just a dict
for page in db.query(filter={"Status": "Done"}):
    print(page["Name"])

# richer conditions use F(...); each comparison must be parenthesized
# because Python evaluates == before & / |
for page in db.query(
    filter=(F("Status") == "In Progress") & (F("Priority") == "High"),
    sort=[("Due Date", "asc")],
):
    print(page["Name"], page["Due Date"])
```

### Async

```python
from notion_db import AsyncNotionDB, F

adb = AsyncNotionDB(database_id=os.environ["TASKS_DB_ID"])

page = await adb.create({"Name": "Ship notion-db v0.1", "Status": "Not Started"})

query = await adb.query(filter={"Status": "Done"})
async for page in query:
    print(page["Name"])
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

All tests run against a mocked `notion_client`, so no live Notion workspace or token is required.
