# Metashape scripts

This is a collection of scripts for adding funtionalities to Agisoft Metashape.

These scripts are intended to be used inside the Metashape app.
The easiest way to use them is to clone this repository (or manually download the scripts) to the Metashape `scripts` folder within the Metashape installation directory (if the `scripts` folder does not exist, create it).
Doing that, all the scripts will be run at the start of the Metashape app and will be available as menu items within Metashape GUI.

For example, in Linux, you can clone the repository with:

```bash
cd /opt/metashape-pro (or the directory where Metashape is installed)
git clone https://github.com/franioli/metashape_scripts.git ./scripts
```

Alternatively, you can manually download the scripts and run them from them using the Metashape `tools-> run script` menu.
Note, that some scripts depends on functions defined in other scripts (mostly the `utils.py` script), so you may need to run them before using other functions.

### Install external modules in Metashape built-in pyhton environment

For some scripts, it is required to install `numpy` package in the Metashape built-in python environment

If you want to install external pacakges in Metashape python environment, you can follow the official guide [official guide](https://agisoft.freshdesk.com/support/solutions/articles/31000136860-how-to-install-external-python-module-to-metashape-professional-package)

For Linux:

```bash
cd /opt/metashape-pro (or the directory where Metashape is installed)
./python/bin/python3.9 -m pip install "python_module_name"
```

In case Linux installation doesn't work due to any reason (like ImportError: cannot import name 'HTTPSHandler') please install libssl 0.9.8 (as shown below) and repeat pip install process:

```bash
wget http://snapshot.debian.org/archive/debian/20110406T213352Z/pool/main/o/openssl098/libssl0.9.8_0.9.8o-7_amd64.deb
sudo dpkg -i libssl0.9.8_0.9.8o-7_amd64.deb
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
