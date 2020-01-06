from PIL import Image
from urllib.request import urlopen
import time, numpy, json, pickle

def _img(u):
    r = urlopen(u)
    assert r.headers.get_content_type() in ["image/jpeg", "image/png"]
    img = Image.open(r)
    #print("got", img)
    return img
    
class stitch:
    def __init__(self, zoomlevel):
        self.zoomlevel = zoomlevel
        self.ntiles = 1 << zoomlevel
        self.tilesize = None
    
    def makeimage_once_tilesize_known(self, tile):
        size = tile.size
        mode = tile.mode
        
        if size[0] != size[1]:
            raise Exception("tiles are not square!?")
        if size[0] > 1024:
            raise Exception("tiles are too big.")
        
        self.tilesize = size[0]
        self.img = Image.new(mode, (self.tilesize * self.ntiles, self.tilesize * self.ntiles))
        #print("created (%s, (%d, %d))" % (mode, self.img.size[0], self.img.size[1]))
        
    def pastetile(self, i, j, tile):
        # if the image is RGBA and totally blank, then we ignore it
        if tile.mode == "RGBA" and numpy.all(numpy.array(tile) == 0):
            return
        if self.tilesize is None:
            self.makeimage_once_tilesize_known(tile)
        else:
            assert tile.size == (self.tilesize, self.tilesize)
            if tile.mode != self.img.mode:
                raise Exception("modes differ. tile.mode %s, self.img.mode %s" % (tile.mode, self.img.mode))
        self.img.paste(
            tile,
            box = (self.tilesize * j, self.tilesize * i),
            mask = tile.split()[-1]
        )
        
    def paste(self, i, j, url):
        u = url % (self.zoomlevel, i, j)
        #print("loading %s" % u)
        tile = _img(u)
        self.pastetile(i, j, tile)
    
    #def get(self, url, bbox=None):
    def get(self, url, bbox=None, callback=None):
        if bbox is None:
            i0 = 0
            i1 = self.ntiles
            j0 = 0
            j1 = self.ntiles
        else:
            i0, j0, i1, j1 = bbox
            i1 += 1
            j1 += 1
        
        for i in range(i0, i1):
            for j in range(j0, j1):
                self.paste(i, j, url)
                callback(i, j, url)
                
    def save(self, fn):
        self.img.save(fn)

class disk:
    JSON = "https://rammb-slider.cira.colostate.edu/data/json/goes-%s/full_disk/geocolor/latest_times.json"
    IMG = "https://rammb-slider.cira.colostate.edu/data/imagery/%%s/goes-%s---full_disk/geocolor/%%s/%%%%02d/%%%%03d_%%%%03d.png"
    
    GOESEAST = dict(
        json = JSON % 16,
        img = IMG % 16,
        zoomlevel = 2,
        filename = "satellite-goes-east.png"
    )
    
    GOESWEST = dict(
        json = JSON % 17,
        img = IMG % 17,
        zoomlevel = 2,
        filename = "satellite-goes-west.png"
    )
    
    HIMAWARI = dict(
        json = "https://rammb-slider.cira.colostate.edu/data/json/himawari/full_disk/geocolor/latest_times.json",
        img = "https://rammb-slider.cira.colostate.edu/data/imagery/%s/himawari---full_disk/geocolor/%s/%%02d/%%03d_%%03d.png",
        zoomlevel = 2,
        filename = "satellite-himawaris.png"
    )
    
    METEOSAT8 = dict(
        json = "https://rammb-slider.cira.colostate.edu/data/json/meteosat-8/full_disk/geocolor/latest_times.json",
        img = "https://rammb-slider.cira.colostate.edu/data/imagery/%s/meteosat-8---full_disk/geocolor/%s/%%02d/%%03d_%%03d.png",
        zoomlevel = 2,
        filename = "satellite-meteosat8.png"
    )
    
        
    staticmethod
    def get_last_timestamp(u):
        r = urlopen(u)
        assert r.headers.get_content_type() == "application/json"
        return str(json.load(r)['timestamps_int'][0])
        
    @staticmethod
    def goes(zz):
        json, img, zoomlevel, filename = zz['json'], zz['img'], zz['zoomlevel'], zz['filename']
        last = disk.get_last_timestamp(json)
        
        try:
            oldlast = open(filename + ".last-updated").read()
            if oldlast.strip() == last:
                print("%s up to date" % filename) #print("no new image, skipping")
                return
        except FileNotFoundError:
            pass
        
        url = img % (last[:8], last)
        
        z = stitch(zoomlevel)
        ntiles = 1 << zoomlevel
        #print("building %s" % filename, end="")
        print("building %s" % filename, end="", flush=True)
        def callback(i, j, url):
            print(".", end="", flush=True)
            time.sleep(1)
        z.get(url, callback=callback)
        #z.img.save(filename)
        z.save(filename) # atashi iya ne
        
        open(filename + ".last-updated", "w").write("%s" % last)
        
        print("")
    
    @staticmethod
    def east():
        disk.goes(disk.GOESEAST)
    
    @staticmethod
    def west():
        disk.goes(disk.GOESWEST)
    
    @staticmethod
    def himawari():
        disk.goes(disk.HIMAWARI)
    
    @staticmethod
    def meteosat8():
        disk.goes(disk.METEOSAT8)
        

if __name__ == "__main__":
    disk.east()
    disk.west()
    disk.himawari()
    disk.meteosat8()
    pass