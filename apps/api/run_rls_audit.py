"""RLS audit runner: points the suite at settings.direct_url
(session-mode, DDL-safe) instead of DATABASE_URL, which often targets the
transaction pooler where DDL stalls. Use for audits against environments
where the primary DATABASE_URL is pooled."""
import os
import sys


def main() -> int:
    from app.core.config import get_settings

    os.environ["DATABASE_URL"] = get_settings().direct_url
    os.environ.setdefault("RLS_AUTO_BASELINE", "FORCE")
    import pytest

    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
