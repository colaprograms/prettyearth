from faceserver import facetracker

ft = facetracker()
ft.setup_image_window()
ft.start()
try:
    while True:
        ft.process()
finally:
    ft.stop()
