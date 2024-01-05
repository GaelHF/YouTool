@echo off
echo Installing Packages
pip install -r packages.txt
python download.py
exit