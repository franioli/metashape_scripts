# Metashape scripts

This is a collection of scripts for adding funtionalities to Agisoft Metashape.

These scripts are intended to be used inside the Metashape app.
The easiest way to use them is to clone this repository (or manually download the scripts) to the Metashape `scripts` folder within the Metashape installation directory (if the `scripts` folder does not exist, create it).
Doing that, all the scripts will be run at the start of the Metashape app and will be available as menu items within Metashape GUI.

Alternatively, you can manually download the scripts and run them from them using the Metashape `tools-> run script` menu (note that some scripts depends on functions defined in other scripts, so you may need to run some scripts before others).

### Install external modules in Metashape built-in pyhton environment

If you want to install external modules in Metashape built-in python environment, you can follow the official guide [https://agisoft.freshdesk.com/support/solutions/articles/31000136860-how-to-install-external-python-module-to-metashape-professional-package](https://agisoft.freshdesk.com/support/solutions/articles/31000136860-how-to-install-external-python-module-to-metashape-professional-package)

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
