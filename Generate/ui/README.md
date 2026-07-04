# Generate/ui - PyQt5 UI for GMP Generator Engine

This package contains the MotorAI desktop UI.

Layout:
- Top: horizontal toolbar
- Middle: central area split horizontally; left = 1/3, right = 2/3
- Bottom: horizontal information/status bar

Source layout:
- `main.py`: application entrypoint
- `ui_main.py`: main window assembly and project actions
- `core/`: shared path/bootstrap helpers
- `dialogs/`: settings and project dialogs
- `widgets/`: reusable UI widgets such as chat bubbles and workers
- `panels/`: main workspace panels and workflow-specific UI
- `workflow/`: agent-style dialog routing and workflow policy helpers
- `run_agent.py`: optimization agent launcher

Run:

Windows / general:
```powershell
pip install -r Generate/ui/requirements.txt
python Generate/ui/main.py
```

Notes:
- Keep `ui_main.py` focused on application assembly. Put new UI features in
  `widgets/`, `panels/`, `workflow/`, or `dialogs/` according to their responsibility.
