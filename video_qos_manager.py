import gi
import cv2
import numpy as np
import time
import threading
import matplotlib.pyplot as plt
from gi.repository import Gst, GstRtspServer, GObject, GLib
import os

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, video_path, dynamic=True):
        super(SensorFactory, self).__init__()
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            print(f"Error: Unable to open video file {video_path}")
            return

        self.number_frames = 0
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_duration = 1 / self.fps if self.fps > 0 else 0
        self.initial_bitrate = 5000
        self.bitrate = self.initial_bitrate
        self.max_bitrate = 10000
        self.min_bitrate = 1000
        self.bitrate_adjustment_interval = 5

        self.video_size = self.get_video_size(video_path)
        self.file_size = self.get_file_size(video_path)

        self.launch_string = (
            'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME '
            'caps=video/x-raw,format=BGR,width=640,height=480,framerate={}/1 '
            '! videoconvert '
            '! video/x-raw,format=I420 '
            '! x264enc speed-preset=ultrafast tune=zerolatency bitrate={} key-int-max=15 '
            '! rtph264pay config-interval=1 name=pay0 pt=96 '.format(int(self.fps), self.bitrate)
        )

        self.set_shared(True)
        self.frame_times = []
        self.latency = []
        self.jitter = []
        self.prev_timestamp = None
        self.packets_sent = 0
        self.packets_received = 0
        
        # Thread safety locks
        self.latency_lock = threading.Lock()
        self.bitrate_lock = threading.Lock()

        if dynamic:
            self.bitrate_thread = threading.Thread(target=self.adjust_bitrate)
            self.bitrate_thread.daemon = True
            self.bitrate_thread.start()

    def get_video_size(self, video_path):
        cap = cv2.VideoCapture(video_path)
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        cap.release()
        return size

    def get_file_size(self, video_path):
        size = os.path.getsize(video_path)  # Size in bytes
        return self.format_size(size)

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def on_need_data(self, src, length):
        start_time = time.time()
        ret, frame = self.cap.read()
        if not ret:
            print(f"Video {self.video_path} finished or cannot be read. Restarting...")
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return

        resized_frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_LINEAR)
        data = resized_frame.tobytes()
        buf = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        buf.duration = int(self.frame_duration * Gst.SECOND)
        timestamp = self.number_frames * self.frame_duration
        buf.pts = buf.dts = int(timestamp * Gst.SECOND)
        buf.offset = timestamp
        src.emit('push-buffer', buf)
        self.number_frames += 1
        self.packets_sent += 1

        end_time = time.time()
        frame_time = end_time - start_time
        self.frame_times.append(frame_time)

        if self.prev_timestamp is not None:
            latency = (end_time - start_time) * 1e9  # Convert to nanoseconds
            with self.latency_lock:
                self.latency.append(latency)
                jitter = abs(latency - self.prev_timestamp)  # Calculate the absolute difference
                self.jitter.append(jitter)
        else:
            latency = 0  # Initialize latency if it's the first frame

        self.prev_timestamp = latency  # Update to the current latency

    def on_new_sample(self, src):
        self.packets_received += 1
        return Gst.FlowReturn.OK

    def adjust_bitrate(self):
        while True:
            time.sleep(self.bitrate_adjustment_interval)
            with self.latency_lock:
                if self.latency:
                    avg_latency = np.mean(self.latency)
                    
                    #hysteresis thresholds
                    high_threshold = 500000000  
                    low_threshold = 200000000    
                    hysteresis_band = 50000000   

                    if avg_latency > (high_threshold + hysteresis_band) and self.bitrate > self.min_bitrate:
                        with self.bitrate_lock:
                            self.bitrate = max(self.min_bitrate, self.bitrate - 1000)

                    elif avg_latency < (low_threshold - hysteresis_band) and self.bitrate < self.max_bitrate:
                        with self.bitrate_lock:
                            self.bitrate = min(self.max_bitrate, self.bitrate + 1000)

                    if hasattr(self, 'pipeline'):
                        x264enc = self.pipeline.get_by_name('x264enc')
                        if x264enc:
                            with self.bitrate_lock:
                                x264enc.set_property('bitrate', self.bitrate)

    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)

    def do_configure(self, rtsp_media):
        self.pipeline = rtsp_media.get_element()
        self.appsrc = self.pipeline.get_by_name('source')
        self.appsrc.connect('need-data', self.on_need_data)
        self.appsrc.set_property('do-timestamp', True)
        self.appsrc.set_property('qos', True)

        sink = Gst.ElementFactory.make('fakesink', 'sink')
        sink.set_property('signal-handoffs', True)
        self.pipeline.add(sink)
        self.appsrc.link(sink)
        sink.connect('handoff', self.on_new_sample)

class GstServer:
    def __init__(self, video_files):
        GObject.threads_init()
        Gst.init(None)

        self.server = GstRtspServer.RTSPServer()
        self.server.set_service("8554")

        self.factories = [
            SensorFactory(video_files[0], dynamic=False),  # Video 1: Static
            SensorFactory(video_files[0], dynamic=True),   # Video 1: Dynamic
            SensorFactory(video_files[1], dynamic=False),  # Video 2: Static
            SensorFactory(video_files[1], dynamic=True),   # Video 2: Dynamic
            SensorFactory(video_files[2], dynamic=False),  # Video 3: Static
            SensorFactory(video_files[2], dynamic=True)    # Video 3: Dynamic
        ]

        self.mounts = self.server.get_mount_points()
        for i, factory in enumerate(self.factories):
            self.mounts.add_factory(f"/video{i+1}", factory)

        self.server.attach(None)
        print("GStreamer RTSP server started at rtsp://localhost:8554/video1 to rtsp://localhost:8554/video6")

    def start(self):
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        static_factories = self.factories[::2]  # Static factories
        dynamic_factories = self.factories[1::2]  # Dynamic factories

        self.plot_combined_metrics(static_factories, "Static Videos Metrics")
        self.plot_combined_metrics(dynamic_factories, "Dynamic Videos Metrics")
        self.plot_comparison(static_factories, dynamic_factories)

    def plot_combined_metrics(self, factories, title):
        plt.figure(figsize=(16, 12))
        colors = plt.cm.viridis(np.linspace(0, 1, len(factories)))

        # Frame Stacking
        plt.subplot(3, 1, 1)
        for idx, factory in enumerate(factories):
            if factory.frame_times:
                cumulative_times = np.cumsum(factory.frame_times)
                cumulative_frame_transfers = np.cumsum([1 for _ in factory.frame_times])  # Cumulative frames transferred
                plt.plot(cumulative_times[:len(cumulative_frame_transfers)], cumulative_frame_transfers,
                        label=f'{os.path.basename(factory.video_path)} ({factory.file_size})',
                        linestyle='-', linewidth=2, color=colors[idx])

        plt.xlabel('Time (s)', fontsize=14, labelpad=15)
        plt.ylabel('Frame Stacking (s)', fontsize=14, labelpad=15)
        plt.title(f'{title} - Frame Stacking', fontsize=16, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=12)
        plt.tight_layout()
        plt.ylim(0, None)

        # Latency
        plt.subplot(3, 1, 2)
        for idx, factory in enumerate(factories):
            if factory.latency:
                times = np.cumsum(factory.frame_times)[:len(factory.latency)]
                plt.plot(times, np.array(factory.latency) / 1e9,  # Convert latency from ns to s
                        label=f'{os.path.basename(factory.video_path)} ({factory.file_size})',
                        linestyle='-', linewidth=2, color=colors[idx])

        plt.xlabel('Time (s)', fontsize=14, labelpad=15)
        plt.ylabel('Latency (s)', fontsize=14, labelpad=15)
        plt.title(f'{title} - Latency Over Time', fontsize=16, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=12)
        plt.tight_layout()
        plt.ylim(0, None)

        # Jitter
        plt.subplot(3, 1, 3)
        for idx, factory in enumerate(factories):
            if factory.jitter:
                times = np.cumsum(factory.frame_times)[:len(factory.jitter)]
                plt.plot(times, np.array(factory.jitter) / 1e9,  # Convert jitter from ns to s
                        label=f'{os.path.basename(factory.video_path)} ({factory.file_size})',
                        linestyle='-', linewidth=2, color=colors[idx])

        plt.xlabel('Time (s)', fontsize=14, labelpad=15)
        plt.ylabel('Jitter (s)', fontsize=14, labelpad=15)
        plt.title(f'{title} - Jitter Over Time', fontsize=16, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=12)
        plt.tight_layout()
        plt.ylim(0, None)

        plt.show()

    def plot_comparison(self, static_factories, dynamic_factories):
        plt.figure(figsize=(16, 12))
        plt.subplots_adjust(hspace=0.5)

    
        plt.subplot(3, 1, 1)
        colors = plt.cm.viridis(np.linspace(0, 1, len(static_factories) + len(dynamic_factories)))

        for idx, factory in enumerate(static_factories + dynamic_factories):
            if factory.frame_times:
                cumulative_times = np.cumsum(factory.frame_times)
                cumulative_frame_transfers = np.cumsum([1 for _ in cumulative_times])
                linestyle = '-' if idx < len(static_factories) else '--'
                plt.plot(cumulative_times, cumulative_frame_transfers,
                        label=f'{os.path.basename(factory.video_path)} ({factory.file_size})',
                        linestyle=linestyle, linewidth=2, color=colors[idx])

        plt.xlabel('Time (s)', fontsize=14)
        plt.ylabel('Cumulative Frames', fontsize=14)
        plt.title('Cumulative Frame Stacking - Static vs Dynamic Videos', fontsize=16, fontweight='bold')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=12)
        plt.tight_layout()

        # Jitter Bar Graph
        plt.subplot(3, 1, 2)
        static_jitter_avg = [np.mean(factory.jitter) / 1e9 for factory in static_factories if factory.jitter]  
        dynamic_jitter_avg = [np.mean(factory.jitter) / 1e9 for factory in dynamic_factories if factory.jitter] 

        index = np.arange(len(static_factories))
        bar_width = 0.35

        plt.bar(index, static_jitter_avg, bar_width, label='Static', color='#1f77b4')  
        plt.bar(index + bar_width, dynamic_jitter_avg, bar_width, label='Dynamic', color='#ff7f0e')  

        plt.xlabel('Videos', fontsize=14)
        plt.ylabel('Average Jitter (s)', fontsize=14)
        plt.title('Jitter Comparison - Static vs Dynamic Videos', fontsize=16, fontweight='bold')
        plt.xticks(index + bar_width / 2, [os.path.basename(f.video_path) for f in static_factories])
        plt.legend()
        plt.tight_layout()

        # Latency Bar Graph
        plt.subplot(3, 1, 3)
        static_latency_avg = [np.mean(factory.latency) / 1e9 for factory in static_factories if factory.latency]
        dynamic_latency_avg = [np.mean(factory.latency) / 1e9 for factory in dynamic_factories if factory.latency]

        plt.bar(index, static_latency_avg, bar_width, label='Static', color='#1f77b4')
        plt.bar(index + bar_width, dynamic_latency_avg, bar_width, label='Dynamic', color='#ff7f0e')

        plt.xlabel('Videos', fontsize=14)
        plt.ylabel('Average Latency (s)', fontsize=14)
        plt.title('Latency Comparison - Static vs Dynamic Videos', fontsize=16, fontweight='bold')
        plt.xticks(index + bar_width / 2, [os.path.basename(f.video_path) for f in static_factories])
        plt.legend()
        plt.tight_layout()

        plt.show()

if __name__ == '__main__':
    video_files = ['your_file_name_here', 'your_file_name_here', 'your_file_name_here']  
    #ex:--> video_files = ['forest.mp4', 'flash.mp4', 'chase.mp4']  
    server = GstServer(video_files)
    server.start()
