# modified from librealsense/wrappers/python/examples/opencv_viewer_example.py
# and http://dlib.net/face_landmark_detection.py.html

import camera
import numpy as np
import time
import dlib
import socket
import os
import traceback as tb
import struct
import threading

class average:
    def __init__(self):
        self.count = 0
        self.accum = 0

    def add(self, j):
        self.count += 1
        self.accum += j

    def get(self):
        return self.accum / self.count if self.count >= 1 else 0

class timeaverage:
    def __init__(self):
        self.avg = average()
        self.t = None

    def start(self):
        if self.t is not None:
            raise Exception("started twice")
        self.t = time.time()

    def stop(self):
        if self.t is None:
            return #raise Exception("already stop")
        self.avg.add(time.time() - self.t)
        self.t = None

    def get(self):
        return self.avg.get()

facebbtimer = timeaverage()

shapestimer = timeaverage()

shortftimer = timeaverage()

otherstimer = timeaverage()

def decompose(r):
    return r.top(), r.bottom(), r.left(), r.right()

class midavg:
    def __init__(self, lth):
        self.last = np.zeros(lth)
        self.idx = 0
        self.valid = 0
        assert lth & 3 == 0

    def add(self, t, z):
        self.last[self.idx] = z
        self.idx += 1
        l = self.last.shape[0]
        if self.valid < l:
            self.valid += 1
        if self.idx >= l:
            self.idx -= l
        return self.get()

    def get(slf):
        out = np.sort(slf.last)
        l4 = slf.last.shape[0] >> 2
        return np.mean(out[l4: 3*l4])

class dampve:
    def __init__(self, damp0, damp1):
        self.x0 = None
        self.v0 = None
        self.t0 = None
        self.damp0 = damp0
        self.damp1 = damp1

    def add(self, t, z):
        if t == self.t0:
            return self.x0
        if self.x0 is None:
            self.x0 = z
        elif self.v0 is None:
            self.v0 = (z - self.x0) / (t - self.t0)
        else:
            dt = t - self.t0
            v = (z - self.x0) / dt
            dv = v - self.v0
            self.x0 += dt * (self.v0 + v) * 0.5
            self.v0 = self.damp0 * self.v0 + self.damp1 * dv
        self.t0 = t
        return self.x0

class whatev:
    def __init__(self):
        self.last = None
        pass

    def add(self, t, z):
        if self.last is None:
            self.last = z
            return z
        avg = z * 0.75 + self.last * 0.25
        self.last = z
        return avg

class predicteyes:
    def __init__(self):
        self.stop()
        self.out = np.zeros(3)
        self.reset = True

    def stop(self):
        self.reset = True

    def __call__(self, t, x, y, z):
        if self.reset:
        #    self.mids = [
        #        dampve(1, 0.1),
        #        dampve(1, 0.1),
        #        dampve(1, 0.1)
        #   ]
            self.mids = [
                whatev(), whatev(), whatev()
            ]
            self.reset = False
        for (j, c) in enumerate([x, y, z]):
            self.out[j] = self.mids[j].add(t, c) #(c)
        return t, self.out

    """
    def __call__(self, t, l, le, r, re):
        if self.t0 is None:
            self.t0 = t
        t -= self.t0
        scale = ((le[0]**2 + re[0]**2) / 2) ** 0.5
        print("t = %6.2f   scale = %6.2f   l = %9.2f %9.2f"% (t, scale, l[0], l[1]))
    """

PARTS_L_EYE = range(36, 42)
PARTS_R_EYE = range(42, 48)
PARTS_NOSE_TOP = 27
def average_on_box_around_point(img, x, y, scale):
    x = int(x)
    y = int(y)
    scale = int(scale + 0.5)
    scale //= 2
    l = max(0, x - scale)
    r = min(img.shape[1], x + scale)
    t = max(0, y - scale)
    b = min(img.shape[0], y + scale)
    img = img[t:b, l:r]
    ret = np.mean(img[img != 0])
    return ret

def meanof(shape, ix):
    sp = [shape.part(i) for i in ix]
    v = np.array([[p.x, p.y] for p in sp])
    return np.mean(v, axis=0), np.std(v, axis=0)

def coordinates(t, depthimage, colorimage, shape):
    eyes = shape.eyes()
    left = eyes[0, :]
    right = eyes[1, :]
    #print("left", left, "right", right)
    lscale = 4
    rscale = 4
    ld = average_on_box_around_point(depthimage, left[0], left[1], lscale)
    rd = average_on_box_around_point(depthimage, right[0], right[1], rscale)
    return np.array([
        (left[0] + right[0]) / 2,
        (left[1] + right[1]) / 2,
        (ld + rd) / 2
    ])

class imagewindow:
    def __init__(self, act = True):
        self.wi = dlib.image_window() if act else None
        self.framecount = 0

    def show(self, out):
        if not self.wi:
            return
        wi = self.wi
        t, depthimage, colorimage, shape = out
        wi.set_image(colorimage)
        wi.clear_overlay()
        self.framecount += 1
        if shape is not None:
            def topoint(dp):
                return dlib.point(dp.x, dp.y)
            if True:
                fobp = dlib.full_object_detection(shape.rect, [topoint(shape.part(i)) for i in range(shape.num_parts)])
                #for jj in range(fobp.num_parts):
                if False:
                    p = fobp.part(jj)
                    if jj > self.framecount % 68:
                        break
                    self.wi.add_overlay_circle(
                        dlib.dpoint(p.x, p.y),
                        2,
                        color = dlib.rgb_pixel(255, 255, 0)
                    )
                wi.add_overlay(fobp)
            #wi.add_overlay(shape.rect)

    def overlay_circle(self, x, y):
        if not self.wi:
            return
        self.wi.add_overlay_circle(dlib.dpoint(x, y), 3)

VERSION = 0x1000
PACKET_INVALID = 0
PACKET_VALID = 1

class facetracker:
    def __init__(self):
        self.camera = camera.facecam()
        self.predict = predicteyes()
        self.iw = None # imagewindow

    def setup_image_window(self):
        self.iw = imagewindow()

    def start(self):
        self.camera.start()
        self.framecount = -1
    
    def process(self):
        self.data = struct.pack('!II', VERSION, PACKET_INVALID)
        out = self.camera.get()
        if out is None:
            return
        t, depthimage, colorimage, shape = out
        if False:
            import cv2
            #cv2.imshow("camera picture", colorimage)
            d = depthimage.astype(np.float) / 4255
            d = np.minimum(d, 1)
            if shape.eyes() is not None:
                eyes = shape.eyes()
                x, y = eyes[0, 0], eyes[0, 1]
                x = int(x)
                y = int(y)
                d = cv2.circle(d, (x, y), 4, color=(255,))
            cv2.imshow("camera", d)
            #cv2.imshow("camera picture", np.minimum(d, 1))
            cv2.waitKey(1)
        foundeyes = False
        if shape.eyes() is not None:
            (x, y, z) = coordinates(t, depthimage, colorimage, shape)
            anynan = np.any(np.isnan([x, y, z]))
            if not anynan:
                foundeyes = True
                t, [x, y, z] = self.predict(t, x, y, z)
                z /= 1000
                SCREEN_HALF_WIDTH = 0.27
                CAMERA_HALF_WIDTH = 160
                SCALE = SCREEN_HALF_WIDTH / CAMERA_HALF_WIDTH
                x = (x - 320) * z * SCALE
                y = (y - 240) * z * SCALE
                """
                print("%6.2f    %6.2f    %6.2f" % (x, y, z))
                #print("facebb = %4f     shapes = %4f" % (facebb.
                print("facebb = %4f    shapes = %4f    shortf = %f    others = %f" % (
                    facebbtimer.get(),
                    shapestimer.get(),
                    shortftimer.get(),
                    otherstimer.get()
                ))
                """
                self.data = struct.pack('!IIdfff', VERSION, PACKET_VALID, t, x, y, z)
            else:
                print("DEPTH PROBLEMS")
        if not foundeyes:
            self.predict.stop()

    def stop(self):
        self.camera.stop()
        self.predict.stop()

CONNECT = ('127.0.0.1', 59942)

class socketmanage:
    #def __init__(self, fn="/tmp/facetracker"):
    def __init__(self, fn=CONNECT):
        self.so = socket.socket(
            family = socket.AF_INET,
            #family=socket.AF_UNIX,
            type=socket.SOCK_STREAM
        )
        self.so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #try:
        #    os.unlink(fn)
        #except FileNotFoundError:
        #    pass
        self.so.bind(fn)
        self.so.listen()
        self.ft = facetracker()

    def loop(self):
        conn =  None
        started = False
        try:
            conn, _ = self.so.accept()
            print("starting face tracker")
            self.ft.start()
            started = True
            while True:
                self.ft.process()
                try:
                    conn.send(self.ft.data)
                except ConnectionAbortedError:
                    break #windows
                except ConnectionResetError:
                    break #windows
                except BrokenPipeError:
                    break
        finally:
            if conn:
                conn.close()
            if started:
                pass
                print("stopping face tracker")
                self.ft.stop()

    def stop(self):
        self.so.close()

if __name__ == "__main__":
    sm = socketmanage()
    try:
        while True:
            sm.loop()
    finally:
        sm.stop()
