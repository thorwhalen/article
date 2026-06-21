"""Built-in platform adapters.

Importing this package has the side effect of registering every built-in
adapter in :mod:`article.registry`. The top-level :mod:`article` package
imports it, so the registry is populated as soon as ``article`` is imported.

To add a platform: drop a new module here that decorates an async function with
``@register_adapter("<name>")``, then import it below. No core code changes.
"""

from __future__ import annotations

# Side-effect imports: each module registers its adapter on import.
from . import substack  # noqa: F401
from . import medium  # noqa: F401
from . import dev_to  # noqa: F401
from . import hashnode  # noqa: F401
