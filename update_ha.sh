#! /bin/bash
git pull
rsync -av --delete pyscript/ /homeassistant/pyscript/
~/.reload-python.sh 

