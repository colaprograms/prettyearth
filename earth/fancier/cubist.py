from PIL import Image
from projec import convert
import math
import numpy as np
import time
import ephem
import datetime

Image.MAX_IMAGE_PIXELS = 300000000

def _sca(x, w):
    return (x * (w-1)).astype(int)

class sphereimage:
    def __init__(self, img):
        self.img = img
        self.width, self.height = self.img.size
        assert self.width == self.height # it has to be square
    
    def map(self, x, y, z):
        raise NotImplementedError()
    
    def get_pixel(self, x, y, z):
        arr = np.array(self.img)
        j, i, *extra = self.map(x, y, z)
        if extra:
            (mask,) = extra
            if self.img.mode in ["LA", "RGBA"]:
                out = arr[i, j, :]
                out[np.logical_not(mask), :] = 0
                #out[mask, :] = 0
                return out
            else:
                raise Exception("mode has to be LA or RGBA to use the mask")
        else:
            return arr[i, j, :]
        
    def imagefromgrid(self, g):
        g = np.transpose(g, (1, 0, 2)) # y, x, xyz
        pix = self.get_pixel(g[:, :, 0], g[:, :, 1], g[:, :, 2])
        return Image.fromarray(pix, self.img.mode)
    
class mercator_on_sphere (sphereimage):
    def map(self, x, y, z):
        x, y = convert.pt_to_mercator(x, y, z)
        return _sca(x, self.width), _sca(y, self.height)

class cybermercator (sphereimage):
    def __init__(self, img):
        super().__init__(img)
    
    def map(self, x, y, z):
        x, y = convert.pt_to_mercator(x, y, z)
        return _sca(x, self.width), _sca(y, self.height)
    
    def imagefromgrid(self, g):
        g = np.transpose(g, (1, 0, 2)) # y, x, xyz
        x, y, z = convert.pt_to_sphere(g[:, :, 0], g[:, :, 1], g[:, :, 2])
        pix = self.get_pixel(g[:, :, 0], g[:, :, 1], g[:, :, 2])
        R, G, B = pix[:, :, 0], pix[:, :, 1], pix[:, :, 2]
        L = R * 299/1000 + G * 587/1000 + B * 114/1000
        pix[:, :, 0] = 0
        pix[:, :, 1] = L
        pix[:, :, 2] = 0
        lat = np.remainder(z[:, :], 0.02)
        pix[lat < 0.005] = [0, 20, 0]
        return Image.fromarray(pix, self.img.mode)

class darkearth (sphereimage):
    """Shades the part of the earth opposite the sun by half."""
    def __init__(self, time):
        self.sun = ephem.Sun()
        self.observer = ephem.Observer()
        self.observer.lon = "90"
        self.observer.date = datetime.datetime.fromtimestamp(time)
        self.sun.compute(self.observer)
        az, alt = self.sun.az, self.sun.alt
        azs, azc = np.sin(az), np.cos(az)
        alts, altc = np.sin(alt), np.cos(alt)
        # i think maybe the x should be minus?
        self.vec = np.array([-azs * altc, alts, azc * altc])
        print("direction of sun:", self.vec)
        
    def get_pixel(self, x, y, z):
        x, y, z = convert.pt_to_sphere(x, y, z)
        out = x * self.vec[0] + y * self.vec[1] + z * self.vec[2]
        #print(np.min(out), np.max(out))
        buf = np.zeros(out.shape + (4,), dtype=np.uint8)
        tra = 191 * (1 - out) ** 9
        tra = np.clip(tra, 0, 191)
        buf[..., 3] = tra.astype(np.uint8)
        return buf
    
    def imagefromgrid(self, g):
        g = np.transpose(g, (1, 0, 2)) # y, x, xyz
        pix = self.get_pixel(g[:, :, 0], g[:, :, 1], g[:, :, 2])
        return Image.fromarray(pix, "RGBA")
        
class disk_on_sphere (sphereimage):
    def __init__(self, img, degre):
        super().__init__(img)
        self.rad = degre / 180 * np.pi
    
    def map(self, x, y, z):
        x, y, z = convert.pt_to_sphere(x, y, z)
        x, y = (
            np.cos(self.rad) * x - np.sin(self.rad) * y,
            np.sin(self.rad) * x + np.cos(self.rad) * y
        )
        x = (x + 1) / 2
        z = (1 - z) / 2
        # add projection?
        return _sca(x, self.width), _sca(z, self.height), y <= 0
        
def grid(m, o, x, y):
    o, x, y = [np.array(z)[None, None, :] for z in (o, x, y)]
    l = np.linspace(-1, 1, m)
    return o + l[:, None, None] * x + l[None, :, None] * y

def _broadcast(o):
    return np.array(o)[None, None, :]
    
class grid:
    dirs = np.eye(3)
    X, Y, Z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
    what = (
        (Z, X, -Y),
        (-Z, -X, -Y),
        (Y, -X, -Z),
        (-Y, X, -Z),
        (-X, -Y, -Z),
        (X, Y, -Z)
    )
    
    @staticmethod
    def grid(m, o, x, y):
        o, x, y = map(_broadcast, (o, x, y))
        l = np.linspace(-1, 1, m)
        lx = l[:, None, None]
        ly = l[None, :, None]
        return o + lx * x + ly * y
    
    @staticmethod
    def makegrid(m, d):
        return grid.grid(m, *grid.what[d])
    
    @staticmethod
    def makegrids(m):
        return tuple(grid.grid(m, *_) for _ in grid.what)

def composecubemap(projs, m, out):
    gr = grid.makegrids(m)
    for i in range(6):
        print("image %d" % i)
        for (j, p) in enumerate(projs):
            if j == 0:
                img = p.imagefromgrid(gr[i])
            elif p == "dark_to_transparent":
                buf = np.array(img)
                M = buf[:, :, 0:3].max(axis=2)
                buf[:, :, 0:3] += 255 - M[:, :, None]
                trans = buf[:, :, 3].astype(np.float64)
                trans *= M / 255
                buf[:, :, 3] = trans.astype(np.uint8)
                img = Image.fromarray(buf, 'RGBA')
   
            else:
                tmp = p.imagefromgrid(gr[i])
                if img.mode == "RGB" and tmp.mode == "RGBA":
                    img = img.convert("RGBA")
                img.alpha_composite(tmp)
                
        # dark to transparent
        img.save(out % i)

def cut_out_disc(im, radius=1):
    out = im.convert('RGBA')
    buf = np.array(out)
    h, w, _ = buf.shape
    y, x = np.meshgrid(np.linspace(-1, 1, h), np.linspace(-1, 1, w))
    r = (y**2 + x**2) ** 0.5
    #buf[r > radius, -1] = 0
    mask = np.clip((radius - r) / radius, 0, 1)
    mask = 255 * mask**(1/3)
    # atashi iya ne
    #mask[r > radius] = 0
    #mask[r <= radius] = 255 * ((radius - r[r <= radius]) / radius) ** 0.2
    buf[..., -1] = mask.astype(np.int)
    return Image.fromarray(buf, 'RGBA')

def makeregular():
    imgs = "satellite.png",
    projs = [mercator_on_sphere(Image.open(_)) for _ in imgs]
    composecubemap(projs, 1024, "satellite-%d.png")

def makedynamic():
    imgs = (
        ("satellite-goes-east.png", 1),
        ("satellite-goes-west.png", 1),
        ("satellite-himawaris.png", 0.9803),
        ("satellite-meteosat8.png", 0.9692)
    )
    disc = [cut_out_disc(Image.open(a), b) for (a, b) in imgs]
    projs = [
        disk_on_sphere(disc[0], 75 - 90),
        disk_on_sphere(disc[1], 135 - 90),
        disk_on_sphere(disc[2], -140.7 - 90),
        disk_on_sphere(disc[3], -41.5 - 90)
        , "dark_to_transparent"#disk_on_sphere(disc[0], 0)
        #disk_on_sphere(disc[0], np.pi / 2),
        #disk_on_sphere(disc[1], +1)
    ]
    composecubemap(projs, 1024, "satellite-goes-%d.png")

"""
if __name__ == "__main__":
    print("Make regular cubemap? [y/N] ", end="")
    if input().strip() in ["y", "yes"]:
        imgs = "satellite.png",
        projs = [mercator_on_sphere(Image.open(_)) for _ in imgs]
        composecubemap(projs, 1024, "satellite-%d.png")
        
    print("Make GOES? [y/N] ", end="")
    if input().strip() in ["y", "yes"]:
        imgs = (
            ("satellite-goes-east.png", 1),
            ("satellite-goes-west.png", 1),
            ("satellite-himawaris.png", 0.9803),
            ("satellite-meteosat8.png", 0.9692)
        )
        disc = [cut_out_disc(Image.open(a), b) for (a, b) in imgs]
        projs = [
            disk_on_sphere(disc[0], 75 - 90),
            disk_on_sphere(disc[1], 135 - 90),
            disk_on_sphere(disc[2], -140.7 - 90),
            disk_on_sphere(disc[3], -41.5 - 90)
            , "dark_to_transparent"#disk_on_sphere(disc[0], 0)
            #disk_on_sphere(disc[0], np.pi / 2),
            #disk_on_sphere(disc[1], +1)
        ]
        composecubemap(projs, 1024, "satellite-goes-%d.png")
    
    pass
"""


if __name__ == "__main__":
    print("Make regular cubemap? [y/N] ", end="")
    if input().strip() in ["y", "yes"]:
        makeregular()
        
    print("Make GOES? [y/N] ", end="")
    if input().strip() in ["y", "yes"]:
        makedynamic()
    pass
    