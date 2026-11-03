# BIKES Speech generator


## 1: Kokoro

This part uses 4 English (US,UK) voices from Kokoro.

Settings:

- speed: 0.75                 

- coupling_weight: 0.99


1.0 = no coupling (uses target voice prosody)
0.0 = all the same (forces complete reference prosody)

- Reference voice (Conductor)
Dictates the exact microsecond start/stop timing of the text blocks
reference_voice: "bm_george"


- run venv with **Python 3.12**

    python python/choir_generator.py -i texts/flock_speech.txt -c choirs/flock_choir.yml -o flock




## Setup

    1. install and activate python 3.12

        cd ~/BIKES_Speech_generator

        uv python install 3.12  

        uv venv --python 3.12 --seed .venv312

        source .venv312/bin/activate

    2. download all depdendencies
        
        python -m pip install -r requirements.txt  (Warning: this step will download over 8G of dependencies, do not copy that to the bikes with sync_folder)

    3. edit the speech sentences the user wants
        
        navigate to \texts\flock_speech.txt, and edit directly


   
# 1) Run Voice Generator

    $ python python/choir_generator.py -i texts/flock_speech.txt -c choirs/flock_choir.yml -o flock

