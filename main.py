import os
import sys
import subprocess as sp
import numpy as np
import json
from PyQt5 import QtGui, QtWidgets
import threading
from queue import Queue

# Add the path to ffmpeg executable to PATH
os.environ['PATH'] = "C:/Program Files/ffmpeg-2023-05-11-git-ceb050427c-full_build/ffmpeg-2023-05-11-git-ceb050427c-full_build/bin;" + os.environ['PATH']

frame_size = [270, 480, 3]  # Your frame size, modified to match the scaled video
frame_buffer_size = np.prod(frame_size)

# Load the RTSP links from the config file
try:
    with open('config.json', 'r') as file:
        config = json.load(file)
    rtsp_links = config['streams']
except Exception as e:
    print(f"Failed to load config file: {e}")
    sys.exit(1)

# Create queues for each camera
frame_queues = [Queue(maxsize=1) for _ in rtsp_links]

# Build the FFmpeg command for each RTSP link
commands = [
    [
        'ffmpeg',
        '-hwaccel', 'dxva2',
        '-rtsp_transport', 'tcp',
        '-i', rtsp_link,
        '-vf', 'scale=480:270',
        '-r', '25',
        '-pix_fmt', 'bgr24',
        '-vcodec', 'rawvideo',
        '-an', '-sn',
        '-f', 'image2pipe',
        '-'
    ]
    for rtsp_link in rtsp_links
]

app = QtWidgets.QApplication(sys.argv)
window = QtWidgets.QWidget()
layout = QtWidgets.QGridLayout()
labels = [QtWidgets.QLabel() for _ in rtsp_links]
for i, label in enumerate(labels):
    layout.addWidget(label, i // 2, i % 2)  # Assuming 2 columns
window.setLayout(layout)
window.show()

def read_frames(pipes):
    while True:
        for i, pipe in enumerate(pipes):
            try:
                # Read the raw frame bytes from FFmpeg pipe
                raw_frame = pipe.stdout.read(frame_buffer_size)

                # If the bytes are empty, break the loop
                if not raw_frame:
                    break

                # Put the frame into the corresponding queue
                frame_queues[i].put(raw_frame)
            except Exception as e:
                print(f"Failed to read frame: {e}")
                break

def update_image(labels):
    while True:
        for i, label in enumerate(labels):
            try:
                # Get the raw frame from the corresponding queue
                raw_frame = frame_queues[i].get()

                # Convert the raw frame bytes to a NumPy array
                frame = np.frombuffer(raw_frame, dtype='uint8').reshape(frame_size)
                # Convert BGR to RGB
                frame = frame[:, :, ::-1]
                # Convert the frame to QImage and display it
                image = QtGui.QImage(frame.tobytes(), frame.shape[1], frame.shape[0], QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(image)
                label.setPixmap(pixmap)
            except Exception as e:
                print(f"Failed to update image: {e}")
                break

# Start the FFmpeg subprocess for each RTSP link
pipes = []
for command in commands:
    try:
        pipe = sp.Popen(command, stdout=sp.PIPE, bufsize=10**8)
        pipes.append(pipe)
    except Exception as e:
        print(f"Failed to start subprocess: {e}")
        continue

# Start the read_frames function in a separate thread
read_thread = threading.Thread(target=read_frames, args=(pipes,))
read_thread.start()

# Start the update_image function in a separate thread
update_thread = threading.Thread(target=update_image, args=(labels,))
update_thread.start()

try:
    sys.exit(app.exec_())
except Exception as e:
    print(f"Failed to start Qt application: {e}")

# Release the resources
for pipe in pipes:
    try:
        pipe.terminate()
        # Wait for the process to terminate
        pipe.wait()
    except Exception as e:
        print(f"Failed to terminate subprocess: {e}")

# Join the threads
try:
    read_thread.join()
except Exception as e:
    print(f"Failed to join read_thread: {e}")

try:
    update_thread.join()
except Exception as e:
    print(f"Failed to join update_thread: {e}")
