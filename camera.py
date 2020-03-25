import tensorflow as tf

import numpy as np
import cv2
import pyrealsense2 as rs
from PIL import Image
from time import time
import csv

def _tensor_from_details(getter, expectedlength):
    def f(self):
        details = getattr(self.itp, getter)()
        assert expectedlength == len(details)
        return [self._twi(which['index']) for which in details]
    return f

class interpreterwrapper:
    def __init__(self, MODEL_FILE = "face_detection_front.tflite"):
        self.itp = tf.lite.Interpreter(model_path = MODEL_FILE)
        self.itp.allocate_tensors()

    _tensor_i = _tensor_from_details("get_input_details", expectedlength=1) #("get_input_details")
    _tensor_o = _tensor_from_details("get_output_details", expectedlength=2) #("get_output_details")

    def _twi(self, ix):
        return self.itp.tensor(ix)()

    def _set(self, image):
        (ii,) = self._tensor_i()
        assert ii.shape == (1, 128, 128, 3)
        ii[0, ...] = image

    def _get(self):
        (o1, o2) = self._tensor_o()
        assert o1.shape == (1, 896, 16)
        assert o2.shape == (1, 896, 1)
        return np.copy(o1), np.copy(o2)

    def classify(self, image):
        image = image.astype(np.float)
        image = (image - 127.5) / 127.5
        self._set(image)
        self.itp.invoke()
        return self._get()

def _tensor_from_details(getter, expectedlength):
    def f(self):
        details = getattr(self.itp, getter)()
        assert expectedlength == len(details)
        return [self._twi(which['index']) for which in details]
    return f

class interpreterwrapper:
    def __init__(self, MODEL_FILE = "face_detection_front.tflite"):
        self.itp = tf.lite.Interpreter(model_path = MODEL_FILE)
        self.itp.allocate_tensors()

    _tensor_i = _tensor_from_details("get_input_details", expectedlength=1) #("get_input_details")
    _tensor_o = _tensor_from_details("get_output_details", expectedlength=2) #("get_output_details")

    def _twi(self, ix):
        return self.itp.tensor(ix)()

    def _set(self, image):
        (ii,) = self._tensor_i()
        assert ii.shape == (1, 128, 128, 3)
        ii[0, ...] = image

    def _get(self):
        (o1, o2) = self._tensor_o()
        assert o1.shape == (1, 896, 16)
        assert o2.shape == (1, 896, 1)
        return np.copy(o1), np.copy(o2)

    def classify(self, image):
        image = image.astype(np.float)
        image = (image - 127.5) / 127.5
        self._set(image)
        self.itp.invoke()
        return self._get()

class camera:
    def __init__(self):
        self.last = None
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 60)
        self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 60)

    def start(self):
        self.pipeline.start(self.config)
        self.alignment = rs.align(rs.stream.color)

    def get(self):
        waiting = True
        while waiting:
            frames = self.pipeline.wait_for_frames()
            frames = self.alignment.process(frames)
            color_frame = frames.get_color_frame()
            t = color_frame.get_frame_metadata(rs.frame_metadata_value.backend_timestamp)
            t /= 1000
            if t != self.last:
                waiting = False
            self.last = t
        depth_frame = frames.get_depth_frame()
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())
        color_image = color_image[:, :, [2,1,0]]
        return (t, depth_image, color_image)

    def stop(self):
        self.pipeline.stop()
        self.alignment = None
        self.last = None

def loadanchors(anchorfile):
    anchors = []
    import csv
    for row in csv.reader(open(anchorfile, newline=''), delimiter=','):
        x, y = row
        x = float(x) * 128
        y = float(y) * 128
        anchors.append((x, y))
    return anchors

anchors = np.array(loadanchors("boxers"))

class results:
    def __init__(self, shape):
        self.keypts = shape[0][0, ...]
        self.scores = shape[1][0, ...]

    def _convert(self, j):
        PTS = slice(4, 16)
        #print(self.keypts.shape)
        #print(anchors.shape)
        p = self.keypts[j, PTS].reshape(-1, 6, 2) + anchors[j, None, :]
        p[:, :, 0] *= 640 / 128
        p[:, :, 1] -= 16
        p[:, :, 1] *= 640 / 128
        return p

    def what(self, j):
        x, y = anchors[j]
        def f(xo, yo):
            xo += x
            yo += y
            xo = xo * 640 / 128
            yo = (yo - 16) * 640 / 128
            return int(xo), int(yo)
        xo, yo, w, h, *others = self.keypts[j]
        return f(xo, yo), w, h, [f(others[o], others[o+1]) for o in range(0, len(others), 2)]

    def large(self, threshold=3):
        return np.nonzero(self.scores > threshold)[0]

    def eyes(self):
        larges = self.large()
        if larges.shape[0] == 0:
            return
        weight = self.scores[larges, 0]
        weight = np.exp(weight)
        weight /= np.sum(weight)
        keypts = self._convert(larges)
        justey = keypts[:, 0:3, :]
        return np.sum(weight[:, None, None] * justey, axis=0)

class facecam:
    def __init__(self):
        self.camera = camera()
        self.iw = interpreterwrapper()
        self.anchors = loadanchors("boxers")

    def start(self):
        self.camera.start()

    def get(self):
        t, depth_image, color_image = self.camera.get()
        t0 = time()
        depth_image = depth_image[:, ::-1]
        scaled = cv2.resize(color_image, dsize=(128, 96), interpolation=cv2.INTER_LANCZOS4)
        scaled = scaled[:, ::-1, :]
        scaled = np.pad(scaled, ((16, 16), (0, 0), (0, 0)), mode='constant')
        shape = self.iw.classify(scaled)
        #print("took", time() - t0)
        return (
            t,
            depth_image,
            color_image[:, ::-1, [2,1,0]],
            results(shape)
        )

    def stop(self):
        self.camera.stop()

if __name__ == "__main__":
    fc = facecam()
    fc.start()
    #print(fc.anchors)
    while True:
        (t, depth, color, shape) = fc.get()
        eyes = shape.eyes()
        if eyes is None:
            print("EYES?")
        else:
            for (x, y) in eyes:
                color = cv2.circle(color, (int(x), int(y)  ), 6, (0, 0, 255))
        cv2.imshow("camera picture", color)
        if cv2.waitKey(1) & 0xFF == 113:
            break
