
# 🎥 RTSP Video Streaming System with Dynamic Bitrate (Python + GStreamer)

This project is a real-time **RTSP-based video streaming system** built using **Python** and **GStreamer**. It dynamically adjusts video bitrate based on **network latency** and provides a **graphical analysis** of streaming performance like **latency**, **jitter**, and **frame delivery**.

---

## 🚀 What This Project Can Do

- Stream **multiple video files** over RTSP using GStreamer
- Serve each video in two modes:
  - ✅ **Static bitrate**
  - 🔁 **Dynamic bitrate** (auto adjusts based on latency)
- Tracks:
  - ⏱️ **Latency** between frame processing
  - ⚖️ **Jitter** (variation in latency)
  - 📦 **Frame delivery time**
- Automatically generates:
  - 📈 Graphs for latency & jitter over time
  - 📊 Bar charts comparing static vs dynamic performance
- Works fully **offline**, tested using **VLC Media Player**

---

## 💻 Tech Stack

- **Python 3.x**
- **OpenCV (cv2)**
- **NumPy**
- **Matplotlib**
- **GStreamer**
- **GstRtspServer**
- **MSYS2 (MinGW64) for Windows**

---

## 🧑‍🏭 What You Need To Do Before Running

### 1. ✅ Install MSYS2

Download and install from:  
👉 https://www.msys2.org

> Make sure you open **MSYS2 MinGW 64-bit** terminal — not the default shell.

---

### 2. 📦 Install Dependencies

Open MSYS2 MinGW64 and run these one by one:

```bash
pacman -Syu
pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-python3-gobject
export PATH="/mingw64/bin:$PATH"
pacman -S mingw-w64-x86_64-python-pip
python3 -m pip install pygobject
pacman -S mingw-w64-x86_64-python-opencv
pacman -S mingw-w64-x86_64-python-numpy
pacman -S mingw-w64-x86_64-python-matplotlib
pacman -S mingw-w64-x86_64-gstreamer mingw-w64-x86_64-gst-plugins-base \
  mingw-w64-x86_64-gst-plugins-good mingw-w64-x86_64-gst-plugins-bad \
  mingw-w64-x86_64-gst-plugins-ugly mingw-w64-x86_64-gst-libav \
  mingw-w64-x86_64-gst-python mingw-w64-x86_64-gst-rtsp-server
```

---

### 3. 🎞️ Add Your Video Files

In `video_qos_manager.py`, locate:

```python
video_files = ['your_file_name_here', 'your_file_name_here', 'your_file_name_here']
```

➡️ Replace with your own video file names.  
📁 Make sure the videos are in the same folder as `st_dy_f.py`.

---

### 4. ▶️ Run the Server

Navigate to your project folder:

```bash
cd /c/Path/To/Your/Project
```

Then run the server:

```bash
GST_DEBUG=*:4 python video_qos_manager.py
```

✅ Output:

```
GStreamer RTSP server started at rtsp://localhost:8554/video1 to rtsp://localhost:8554/video6
```

---

### 5. 📺 View Streams in VLC

1. Download VLC from: [https://www.videolan.org/vlc/download-windows.html](https://www.videolan.org/vlc/download-windows.html)
2. Open VLC
3. Go to: `Media → Open Network Stream`
4. Paste one of the URLs below:

   * `rtsp://localhost:8554/video1`
   * `rtsp://localhost:8554/video2`
   * ...
   * `rtsp://localhost:8554/video6`
5. Click **Play** — video should start in a few seconds

---

## 📊 Metrics & Visualization

After pressing `Ctrl + C` to stop the server:

* 📈 Frame stacking graph
* ⏱️ Latency timeline
* ⚖️ Jitter variation
* 📊 Static vs Dynamic bar charts

Perfect for technical analysis or final-year project demos.

---

## 📌 RTSP Stream Endpoints

| Stream Type      | URL                            |
| ---------------- | ------------------------------ |
| Static Stream 1  | `rtsp://localhost:8554/video1` |
| Dynamic Stream 1 | `rtsp://localhost:8554/video2` |
| Static Stream 2  | `rtsp://localhost:8554/video3` |
| Dynamic Stream 2 | `rtsp://localhost:8554/video4` |
| Static Stream 3  | `rtsp://localhost:8554/video5` |
| Dynamic Stream 3 | `rtsp://localhost:8554/video6` |

---

## 👤 Author

**Logeshwaran U**    
If you found this project helpful, feel free to give it a ⭐
