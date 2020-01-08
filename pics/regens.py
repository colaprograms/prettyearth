from stitch import disk
import cubist

sats = "east west himawari meteosat8"
for name in sats.split(" "):
    getattr(disk, name)()

cubist.makeregular()
cubist.makedynamic()
