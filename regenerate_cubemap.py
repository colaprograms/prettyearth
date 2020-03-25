import os, os.path, pics.regens
if not os.path.exists("pics/satellite.png"):
    print("Can't find the static satellite picture, pics/satellite.png")
    print("You may be running the program from the wrong directory.")
    raise FileNotFoundError()
else:
    os.chdir("pics")
    pics.regens.regenerate()
