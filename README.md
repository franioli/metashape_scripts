metashape_scripts/
  README.md
  LICENSE
  pyproject.toml                  # optional (lint/typecheck)
  metashape_tools/                # Python package (importable)
    __init__.py
    menu.py                       # single menu registration entry-point

    core/
      __init__.py
      compat.py                   # Metashape version checks (from utils.py)
      ui.py                       # small wrappers around getInt/getFloat/getBool
      report.py                   # common printing/format helpers

    tie_points_tools.py           # tie points stats + filters + bbox removal
    camera_tools.py               # camera utilities (keep existing, cleaned)
    markers_tools.py              # markers import/export + triangulation helpers
    incremental_alignment.py      # incremental alignment + transfer-oriented
    chunk_tools.py                # generic chunk utilities

    io/                           # NOTE: package name "io" shadows stdlib if used as `import io`
      __init__.py
      calibration.py              # from calib2colmap.py
      sparse.py                   # from export_sparse.py
      bundler.py                  # from project_from_bundler.py
      images.py                   # optional: image export helpers if you prefer IO grouping
      markers_io.py               # optional: CSV read/write for marker projections

  scripts/
    register_menu.py              # the only script you run/load in Metashape