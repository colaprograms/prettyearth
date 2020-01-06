from numpy import pi, sqrt, copysign, sin, log, tan, arcsin, arctan2, clip

def qf(a, b, c):
    "One solution to ax^2 + bx + c = 0."
    if b < 0:
        # This formula is more numerically stable when -b > 0,
        # because we don't have to add two numbers of different signs.
        return 2 * c / (-b + sqrt(b*b - 4*a*c))
    else:
        # This one is more stable when -b < 0 for the same reason.
        return (-b - sqrt(b*b - 4*a*c)) / 2 / a

def _cubic_mangle(a, b, c):
    b2 = b * b
    c2 = c * c
    return a * sqrt(1 - b2 / 2 - c2 / 2 + b2 * c2 / 3)

def _sphere_to_pt1(x, y):
    xplane = qf(1/2, y*y - 3/2 - x*x, 3 * x*x)
    yplane = qf(1/2, x*x - 3/2 - y*y, 3 * y*y)
    return copysign(sqrt(xplane), x), copysign(sqrt(yplane), y)

class convert:
    @staticmethod
    def pt_to_sphere(x, y, z):
        "Map the boundary of the cube -1 <= x, y, z <= 1 onto the unit sphere"
        # we don't do projection, we do something fancier with less distortion
        return (
            _cubic_mangle(x, y, z),
            _cubic_mangle(y, z, x),
            _cubic_mangle(z, x, y)
        )
    
    @staticmethod
    def sphere_to_pt(x, y, z):
        "Inverse of pt_to_sphere: map the unit sphere onto the boundary of -1 <= x, y, z <= 1"
        # again, this is not inverse projection, we do something fancier with less distortion
        # NOT VECTORIZED
        X, Y, Z = abs(x), abs(y), abs(z)
        if Z >= max(X, Y):
            a, b = _sphere_to_pt1(x, y)
            c = 1 if z > 0 else -1
            return (a, b, c)
        elif X >= max(Y, Z):
            b, c = _sphere_to_pt1(y, z)
            a = 1 if x > 0 else -1
            return (a, b, c)
        else:
            c, a = _sphere_to_pt1(z, x)
            b = 1 if y > 0 else -1
            return (a, b, c)

    @staticmethod
    def sphere_to_latlon(x, y, z):
        "point on a unit sphere to latlon"
        if (abs(x*x + y*y + z*z - 1) > 1e-12).any():
            raise Exception("radius isn't 1")
        lat = 180 / pi * arcsin(z)
        lon = 180 / pi * arctan2(y, x)
        return lat, lon
    
    @staticmethod
    def latlon_to_mercator(lat, lon):
        "map latitude and longitude to mercator coordinates in the unit square 0 <= x, y <= 1"
        x = (lon + 180) / 360
        y1 = log(tan(pi/4 + pi * lat / 360)) / pi
        y = 0.5 - y1/2
        # clip at +-85 degrees
        return x, clip(y, 0, 1)

    @staticmethod
    def pt_to_mercator(x, y, z):
        x, y, z = convert.pt_to_sphere(x, y, z)
        lat, lon = convert.sphere_to_latlon(x, y, z)
        return convert.latlon_to_mercator(lat, lon)

def test(many = 300000):
    import random
    r = lambda: 2 * random.random() - 1
    def che(x, y, z):
        a, b, c = convert.pt_to_sphere(x, y, z)
        x1, y1, z1 = convert.sphere_to_pt(a, b, c)
        if abs(x - x1) > 1e-12 or abs(y - y1) > 1e-12 or abs(z - z1) > 1e-12:
            print("error")
        print(f"\t {x} {y} {z}")
        print(f"\t {x1} {y1} {z1}")

    for i in range(many):
        che(r(), r(), 1)
        che(r(), r(), -1)
        che(r(), 1, r())
        che(r(), -1, r())
        che(1, r(), r())
        che(-1, r(), r())
        "whee"