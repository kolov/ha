#! /bin/bash
git pull
rsync -av --delete pyscript/ /homeassistant/pyscript/
~/homeassistant/reload-python.sh

