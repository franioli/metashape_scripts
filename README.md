# Metashape scripts

Collection of python scripts for Metashape.

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
    

## Use Metashape as external module

### Create Environment with anaconda

Download the [current .whl file](https://www.agisoft.com/downloads/installer/) and install it following [these instructions](https://agisoft.freshdesk.com/support/solutions/articles/31000148930-how-to-install-metashape-stand-alone-python-module) (using the name of the .whl file that you downloaded).

```bash
conda create -n metashape python=3.10
conda activate metashape
pip3 install Metashape-"XX".whl
pip3 install -r requirements.txt
```

### License

Metashape license: You need a license (and associated license file) for Metashape. The easiest way to get the license file, is by installing the Metashape Professional Edition GUI software (distinct from the Python module) and registering it following the prompts in the software (you need to purchase a license first). Once you have a license file (whether a node-locked or floating license), you need to set the agisoft_LICENSE environment variable (search onilne for instructions for your OS; look for how to permanently set it) to the path to the folder containing the license file (metashape.lic).

With Linux (Ubuntu 22.04), to permanently setup agisoft_LICENSE environment variable for floating license, modify your .bashrc file:

```bash
sudo nano ~/.bashrc
```

add the line (replace port and address with your values)

```bash
export agisoft_LICENSE="port"@"address"
```

```bash
source ~/.bashrc
```

Check if the new environmental variable is present:

```bash
printenv | grep agisoft
```

Refer to [this guide](https://agisoft.freshdesk.com/support/solutions/articles/31000169378--metashape-2-x-linking-client-machine-to-the-license-server).

### Install external modules in Metashape built-in pyhton environment

Follow the official guide [https://agisoft.freshdesk.com/support/solutions/articles/31000136860-how-to-install-external-python-module-to-metashape-professional-package](https://agisoft.freshdesk.com/support/solutions/articles/31000136860-how-to-install-external-python-module-to-metashape-professional-package)

For Linux:

```bash
./metashape-pro/python/bin/python3.8 -m pip install "python_module_name"
```

### Issues

##### Reach Python Console

In Metashape app, if Reach Python Console does not work and gives the following error

```bash
Failed to import qtconsole.inprocess: libffi.so.6: cannot open shared object file: No such file or directory
Construction of rich console failed - using simple console
```

You need to manually install libffi6 with

```bash
wget https://mirrors.kernel.org/ubuntu/pool/main/libf/libffi/libffi6_3.2.1-8_amd64.deb
sudo apt install ./libffi6_3.2.1-8_amd64.deb
```
