"""Allow ``python -m ste100`` (portable across PATH / OS / venv layouts)."""

from ste100.cli import main

if __name__ == "__main__":
    main()
