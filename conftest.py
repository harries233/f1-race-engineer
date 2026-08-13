"""pytest 全局配置：把 src/ 与 tests/ 加入 sys.path，使扁平 import 可用。

- src/ 提供 store / protocol / ingest 等包。
- tests/ 提供 mock 包（tests/mock/factory.py，MOCK_DATA）。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (ROOT / "src", ROOT / "tests"):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
