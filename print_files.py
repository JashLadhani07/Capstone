from pathlib import Path

files = [
    "api/main.py",
    "api/routers/analysis.py",
    "api/routers/signals.py",
    "api/routers/memory.py",
    "api/routers/review.py",
    "api/schemas.py",
    "agents/supervisor.py",
    "graph/graph_builder.py",
    "graph/state.py",
    "config/logging_config.py",
    "memory/signal_database.py"
]

for file in files:
    path = Path(file)

    print("\n" + "=" * 80)
    print(f"FILE: {file}")
    print("=" * 80)

    if path.exists():
        try:
            print(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Could not read file: {e}")
    else:
        print("FILE NOT FOUND")