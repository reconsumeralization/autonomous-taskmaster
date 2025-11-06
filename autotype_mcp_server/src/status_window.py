# region StatusWindow Description
# INPUT: None (standalone window, but exposes update methods)
# OUTPUT: Real-time accessible status window for listening, TTS, DD detection, and live log streaming.
import tkinter as tk
from tkinter import StringVar, scrolledtext
import os
import threading
import time

# Color mapping for status
STATUS_COLORS = {
    'Idle': 'red',
    'Not Detected': 'red',
    'Off': 'red',
    'Inactive': 'red',
    'Active': 'yellow',
    'Starting': 'yellow',
    'Detecting': 'yellow',
    'Processing': 'yellow',
    'Speaking': 'yellow',
    'In Use': 'green',
    'Running': 'green',
    'Detected': 'green',
    'Listening': 'green',
    'Speaking': 'green',
    'On': 'green'
}

# Minimum width/height for compact mode
COMPACT_WIDTH = 120
COMPACT_HEIGHT = 60

# Directory where logs are stored
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../logs"))

class StatusWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Accessibility Status Window")
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        self.root.attributes('-topmost', True)
        self.status_vars = {
            'Listening': StringVar(value='Idle'),
            'TTS': StringVar(value='Idle'),
            'DD': StringVar(value='Not Detected')
        }
        self.compact_mode = False
        self._build_ui()
        self.root.bind('<Configure>', self._on_resize)
        self.log_files = self._discover_log_files()
        self.log_positions = {log: 0 for log in self.log_files}
        self.log_streaming = True
        self.log_thread = threading.Thread(target=self._stream_logs, daemon=True)
        self.log_thread.start()

    def _build_ui(self):
        # Main containers
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill='both', expand=True)
        # Expanded UI
        self.header_label = tk.Label(self.main_frame, text="Accessibility Status", font=("Arial", 16, "bold"))
        self.header_label.pack(pady=8)
        self.status_frames = {}
        for key, var in self.status_vars.items():
            frame = tk.Frame(self.main_frame)
            frame.pack(fill='x', padx=20, pady=4)
            tk.Label(frame, text=f"{key}:", font=("Arial", 12, "bold"), width=12, anchor='w').pack(side='left')
            tk.Label(frame, textvariable=var, font=("Arial", 12), fg='blue', anchor='w').pack(side='left')
            self.status_frames[key] = frame
        # ARIA live region simulation for screen readers
        self.aria_live = tk.Label(self.main_frame, text="", font=("Arial", 10), fg='green')
        self.aria_live.pack(pady=8)
        # Log streaming area
        self.log_label = tk.Label(self.main_frame, text="Live Project Logs", font=("Arial", 12, "bold"))
        self.log_label.pack(pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(self.main_frame, height=10, state='disabled', font=("Consolas", 10))
        self.log_text.pack(fill='both', expand=True, padx=10, pady=5)
        # Compact UI (traffic light)
        self.compact_frame = tk.Frame(self.root)
        self.traffic_lights = {}
        for idx, key in enumerate(['Listening', 'TTS', 'DD']):
            light = tk.Canvas(self.compact_frame, width=30, height=30, highlightthickness=0)
            light.grid(row=0, column=idx, padx=5, pady=5)
            # Draw initial red circle
            oval = light.create_oval(5, 5, 25, 25, fill='red', outline='black')
            self.traffic_lights[key] = (light, oval)
        self.compact_frame.pack_forget()  # Hide initially

    def _on_resize(self, event):
        # Switch to compact mode if window is small
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if width <= COMPACT_WIDTH or height <= COMPACT_HEIGHT:
            if not self.compact_mode:
                self._show_compact()
        else:
            if self.compact_mode:
                self._show_expanded()

    def _show_compact(self):
        self.compact_mode = True
        self.main_frame.pack_forget()
        self.compact_frame.pack(fill='both', expand=True)
        self._update_traffic_lights()

    def _show_expanded(self):
        self.compact_mode = False
        self.compact_frame.pack_forget()
        self.main_frame.pack(fill='both', expand=True)

    def _update_traffic_lights(self):
        for key, (canvas, oval) in self.traffic_lights.items():
            status = self.status_vars[key].get()
            color = self._status_to_color(status)
            canvas.itemconfig(oval, fill=color)

    def _status_to_color(self, status):
        # Normalize status to color
        status = status.strip().title()
        for k, v in STATUS_COLORS.items():
            if status.startswith(k):
                return v
        # Fallback
        if status.lower() in ['idle', 'not detected', 'off', 'inactive']:
            return 'red'
        if status.lower() in ['active', 'starting', 'detecting', 'processing', 'speaking']:
            return 'yellow'
        if status.lower() in ['in use', 'running', 'detected', 'listening', 'on']:
            return 'green'
        return 'red'

    # region update_status Description
    # INPUT: status_type (str): One of 'Listening', 'TTS', 'DD'.
    # INPUT: value (str): Status value to display.
    # OUTPUT: None. Updates the status window and ARIA live region.
    def update_status(self, status_type: str, value: str):
        if status_type in self.status_vars:
            self.status_vars[status_type].set(value)
            self.aria_live.config(text=f"{status_type} status: {value}")
            self.root.after(2000, lambda: self.aria_live.config(text=""))
            if self.compact_mode:
                self._update_traffic_lights()
    # endregion update_status Description

    # region _discover_log_files Description
    # INPUT: None
    # OUTPUT: List of absolute paths to all .log files in the logs directory.
    def _discover_log_files(self):
        log_files = []
        if os.path.isdir(LOGS_DIR):
            for fname in os.listdir(LOGS_DIR):
                if fname.endswith('.log'):
                    log_files.append(os.path.join(LOGS_DIR, fname))
        return log_files
    # endregion _discover_log_files Description

    # region _stream_logs Description
    # INPUT: None
    # OUTPUT: None. Continuously reads new lines from all log files and updates the log_text widget.
    def _stream_logs(self):
        while self.log_streaming:
            for log_file in self.log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self.log_positions[log_file])
                        new_lines = f.readlines()
                        if new_lines:
                            self._append_log_lines(log_file, new_lines)
                        self.log_positions[log_file] = f.tell()
                except Exception:
                    # Optionally print or log error
                    pass
            time.sleep(0.5)
    # endregion _stream_logs Description

    # region _append_log_lines Description
    # INPUT: log_file (str): Path to the log file.
    # INPUT: lines (list): List of new log lines.
    # OUTPUT: None. Appends lines to the log_text widget in a thread-safe way.
    def _append_log_lines(self, log_file, lines):
        def append():
            self.log_text.config(state='normal')
            for line in lines:
                display_line = f"[{os.path.basename(log_file)}] {line}"
                self.log_text.insert('end', display_line)
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        self.root.after(0, append)
    # endregion _append_log_lines Description

    # region run Description
    # INPUT: None
    # OUTPUT: None. Starts the Tkinter main loop.
    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.log_streaming = False
    # endregion run Description

# endregion StatusWindow Description

if __name__ == "__main__":
    win = StatusWindow()
    win.run()