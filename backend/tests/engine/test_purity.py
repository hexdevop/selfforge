import subprocess
import sys
from pathlib import Path

import app.engine

ENGINE = Path(app.engine.__file__).parent


def test_engine_never_imports_infrastructure() -> None:
    modules = [f"app.engine.{p.stem}" for p in ENGINE.glob("*.py") if p.stem != "__init__"]
    check = (
        f"import sys; import {', '.join(modules)}; "
        "leaked = {'sqlalchemy', 'fastapi', 'redis'} & {m.split('.')[0] for m in sys.modules}; "
        "sys.exit(', '.join(sorted(leaked)))"
    )
    result = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True)
    assert result.returncode == 0, f"engine imports {result.stderr.strip()}"
