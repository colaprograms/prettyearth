import socket
import struct

def RECEIVERFOR(ft):
    size = struct.calcsize(ft)
    def f(self):
        return struct.unpack(ft, self.so.recv(size))
    return f

VERSION = 0x1000
PACKET_VALID = 1
PACKET_INVALID = 0

fn = "/tmp/facetracker"

class faceclient:

    def __init__(self, fn="/tmp/facetracker"):
        self.fn = fn
        self.so = None
        self.last_time = None

    def connect(self):
        if self.so is not None:
            raise Exception("already connected")
        self.so = socket.socket(
            family = socket.AF_UNIX,
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
                print(t - self.last_time)
                self.last_time = t
            self.current = t, x, y, z
        return self.current

    def stop(self):
        if self.so is not None:
            self.so.close()
            self.so = None

if __name__ == "__main__":
    fc = faceclient()
    try:
        fc.connect()
        while True:
            print(fc.get())
    finally:
        fc.stop()
