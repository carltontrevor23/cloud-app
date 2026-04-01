# TaskFlow

TaskFlow is a simple Flask to-do list app built with SQLite. It supports creating, editing, deleting, and completing tasks, with a few small extras:

- Priority levels
- Optional due dates
- Search and filter controls

## Run locally

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Start the app:

```powershell
python app.py
```

4. Open the local URL shown in the terminal, usually:

```text
http://127.0.0.1:5000
```

## Features

- Add tasks with a title, description, due date, and priority
- Edit existing tasks
- Delete tasks
- Mark tasks as complete or open
- Filter by status and priority
- Search by title or description
