import socket
import struct
import time
from threading import Thread

def RECEIVERFOR(ft):
    size = struct.calcsize(ft)
    def f(self):
        return struct.unpack(ft, self.so.recv(size))
    return f

VERSION = 0x1000
PACKET_VALID = 1
PACKET_INVALID = 0

#fn = "/tmp/facetracker"
CONNECT = ('127.0.0.1', 59942)

class faceclient:

    #def __init__(self, fn="/tmp/facetracker"):
    def __init__(self, fn=None):
        self.fn = fn or CONNECT
        self.so = None
        self.last_time = None

    def connect(self):
        if self.so is not None:
            raise Exception("already connected")
        self.so = socket.socket(
            family = socket.AF_INET,
            type = socket.SOCK_STREAM
        )
        self.so.connect(self.fn)

    get_header = RECEIVERFOR( "!II" )
    get_valid = RECEIVERFOR( "!dfff" )
    get_invalid = RECEIVERFOR( "" )

    def get(self):
        if not self.so:
            return
        version, packettype = self.get_header()
        if version != VERSION:
            raise Exception("wrong version")
        if packettype == PACKET_INVALID:
            self.current = None
        elif packettype == PACKET_VALID:
            t, x, y, z = self.get_valid()
            if self.last_time is None:
                self.last_time = t
            else:
                self.last_time = t
            self.current = t, x, y, z
        return self.current

    def stop(self):
        if self.so is not None:
            self.so.close()
            self.so = None

class faceclient_thread:
    def __init__(self):
        self.th = Thread(target=self.do)
        self.stop = False

    def run(self):
        self.th.start()

    def do(self):
        self.cur = None
        fc = faceclient()
        try:
            fc.connect()
            while not self.stop:
                self.cur = fc.get()
        finally:
            self.cur = None
            fc.stop()

if __name__ == "__main__":
    fc = faceclient()
    try:
        fc.connect()
        while True:
            print(fc.get())
    finally:
        fc.stop()
