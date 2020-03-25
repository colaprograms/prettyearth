from .stitch import disk
from .cubist import *

def regenerate():
    disk.east()
    disk.west()
    disk.himawari()
    disk.meteosat8()
    print("building the static cubemap")
    makeregular()
    print("building the dynamic cubemap")
    makedynamic()

if __name__ == "__main__":
    regenerate()
