from .stitch import disk
from .cubist import *

def regenerate():
    disk.east()
    disk.west()
    disk.himawari()
    disk.meteosat8()
    makeregular()
    makedynamic()

if __name__ == "__main__":
    regenerate()
