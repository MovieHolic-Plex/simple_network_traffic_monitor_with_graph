import tkinter as tk
from psutil import net_io_counters
from datetime import datetime, timedelta
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import sqlite3
class NetworkBandwidthMonitor:
    WINDOW_SIZE = (600, 400)
    REFRESH_DELAY = 500  # 0.5 second
    GRAPH_POINTS = 120  # 1 minute of data when updating every 0.5 seconds


    KB = float(1024)
    MB = float(KB ** 2)
    GB = float(KB ** 3)
    TB = float(KB ** 4)

    INTERVALS = {
        "1 Second": timedelta(seconds=1),
        "1 Minute": timedelta(minutes=1),
        "1 Hour": timedelta(hours=1),
        "1 Day": timedelta(days=1),
        "1 Week": timedelta(weeks=1),
        "1 Month": timedelta(days=30)  # Approximation
    }

    def __init__(self):
        self.window = tk.Tk()
        self.last_upload, self.last_download = 0, 0
        self.start_time = datetime.now()
        self.data = {}
        self.traffic_data = np.zeros(self.GRAPH_POINTS)
        self.setup_database()
        self.setup_ui()
        self.update_labels()
        self.update_graph()
        self.current_interval = self.INTERVALS["1 Day"]  # 기본값 설정
        self.update_traffic_labels()  # 초기 실행
        self.timer_id = None  # timer_id 속성 초기화 추가

    def size(self, bytes_):
        if bytes_ < self.KB:
            return f"{bytes_} Bytes"
        elif self.KB <= bytes_ < self.MB:
            return f"{bytes_ / self.KB:.2f} KB"
        elif self.MB <= bytes_ < self.GB:
            return f"{bytes_ / self.MB:.2f} MB"
        elif self.GB <= bytes_ < self.TB:
            return f"{bytes_ / self.GB:.2f} GB"
        else:
            return f"{bytes_ / self.TB:.2f} TB"

    def setup_ui(self):
        self.window.title("Network Bandwidth Monitor")
        self.window.geometry(f"{self.WINDOW_SIZE[0]}x{self.WINDOW_SIZE[1]}")
        self.window.resizable(width=False, height=False)

        self.label_monitoring_period = tk.Label(self.window, font="Quicksand 10 italic")
        self.label_monitoring_period.pack()

        self.label_total_upload = tk.Label(self.window, text="Upload: Calculating...", font="Quicksand 12")
        self.label_total_upload.pack()

        self.label_total_download = tk.Label(self.window, text="Download: Calculating...", font="Quicksand 12")
        self.label_total_download.pack()

        # Horizontal layout for buttons
        btn_frame = tk.Frame(self.window)
        btn_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        for interval, _ in self.INTERVALS.items():
            btn = tk.Button(btn_frame, text=f"{interval} Traffic", command=lambda i=interval: self.show_traffic(i))
            btn.pack(side=tk.LEFT)

        # Graph setup
        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, self.window)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def update_labels(self):
        counters = net_io_counters(pernic=True)
        total_upload = sum([nic.bytes_sent for nic in counters.values()])
        total_download = sum([nic.bytes_recv for nic in counters.values()])

        # Save the data with timestamp
        now = datetime.now()
        self.data[now] = (total_upload, total_download)

        # Remove outdated data
        for time, _ in list(self.data.items()):
            if now - time > max(self.INTERVALS.values()):
                del self.data[time]

        self.update_traffic_labels()  # 실시간으로 트래픽 레이블 업데이트
        self.window.after(self.REFRESH_DELAY, self.update_labels)

    def update_graph(self):
        # Shift old data
        self.traffic_data[:-1] = self.traffic_data[1:]
        counters = net_io_counters(pernic=True)
        total_download = sum([nic.bytes_recv for nic in counters.values()])

        # Convert bytes to Mbps (1 Byte = 8 bits, 1 MB = 1024^2 Bytes)
        # 차이량을 0.5초로 나누어 속도를 계산
        self.traffic_data[-1] = ((total_download - self.last_download) * 8 / (1024 ** 2)) / 0.5
        self.last_download = total_download

        self.ax.clear()
        self.ax.plot(self.traffic_data)
        self.ax.set_title("Real-time Traffic (Mbps)")
        self.ax.set_xlim(0, self.GRAPH_POINTS)
        self.ax.set_ylim(0, max(self.traffic_data) + 1)
        self.canvas.draw()

        self.window.after(self.REFRESH_DELAY, self.update_graph)

    def show_traffic(self, interval_name):
        if self.timer_id:  # 이전 타이머가 있다면 취소
            self.window.after_cancel(self.timer_id)
        self.current_interval = self.INTERVALS[interval_name]
        self.update_traffic_labels()
        self.timer_id = self.window.after(self.REFRESH_DELAY, self.update_traffic_labels)

    def update_traffic_labels(self):
        total_upload, total_download = self.get_traffic_from_database(self.current_interval)
        now = datetime.now()
        start_time = now - self.current_interval
        self.label_total_upload["text"] = f"Upload (Last {self.current_interval}): {self.size(total_upload)}"
        self.label_total_download["text"] = f"Download (Last {self.current_interval}): {self.size(total_download)}"
        self.label_monitoring_period[
            "text"] = f"Monitoring from {start_time.strftime('%Y-%m-%d %H:%M:%S')} to {now.strftime('%Y-%m-%d %H:%M:%S')}"
        self.window.after(self.REFRESH_DELAY, self.update_traffic_labels)  # 주기적 호출 추가

    def setup_database(self):
        self.conn = sqlite3.connect('traffic_data.db')
        self.cursor = self.conn.cursor()

        # Create table if it doesn't exist
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS traffic
                                (timestamp DATETIME, upload BIGINT, download BIGINT)''')
        self.conn.commit()

    def save_to_database(self, timestamp, upload, download):
        self.cursor.execute("INSERT INTO traffic (timestamp, upload, download) VALUES (?, ?, ?)",
                            (timestamp, upload, download))
        self.conn.commit()

    def get_traffic_from_database(self, interval):
        now = datetime.now()
        start_time = now - interval
        self.cursor.execute("SELECT upload, download FROM traffic WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 1",
                            (start_time,))
        first_data = self.cursor.fetchone()

        self.cursor.execute("SELECT upload, download FROM traffic WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
                            (now,))
        last_data = self.cursor.fetchone()

        if not first_data or not last_data:  # 해당 기간의 데이터가 없을 경우 0 반환
            return (0, 0)

        total_upload = last_data[0] - first_data[0]
        total_download = last_data[1] - first_data[1]
        return (total_upload, total_download)

    def update_labels(self):
        counters = net_io_counters(pernic=True)
        total_upload = sum([nic.bytes_sent for nic in counters.values()])
        total_download = sum([nic.bytes_recv for nic in counters.values()])
        # Save the data with timestamp
        now = datetime.now()
        self.data[now] = (total_upload, total_download)
        self.save_to_database(now, total_upload, total_download)  # 데이터를 DB에 저장
        # Remove outdated data
        for time, _ in list(self.data.items()):
            if now - time > max(self.INTERVALS.values()):
                del self.data[time]
        self.window.after(self.REFRESH_DELAY, self.update_labels)


    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    monitor = NetworkBandwidthMonitor()
    monitor.run()
