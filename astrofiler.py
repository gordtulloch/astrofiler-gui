"""AstroFiler GUI launcher.

Thin wrapper around ``astrofiler.main`` so ``python astrofiler.py`` works from a
source checkout without installing the package. The launcher logic itself lives
in ``src/astrofiler/main.py`` (also exposed as the ``astrofiler`` console script).
"""

import os
import sys

# Put the src path first so `import astrofiler` resolves to the package, not this file.
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

if src_path in sys.path:
    sys.path.remove(src_path)
sys.path.insert(0, src_path)

if __name__ == "__main__":
    from astrofiler.main import main

    sys.exit(main())
