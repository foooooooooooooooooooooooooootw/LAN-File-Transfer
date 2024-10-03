import subprocess
import sys

# Function to check and install missing dependencies
def check_and_install(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

def install_dependencies():
    packages = ['Pillow', 'tkinterdnd2', 'opencv-python','imageio', 'imageio[ffmpeg]']
    for package in packages:
        check_and_install(package)

install_dependencies()
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk
import io
import os
import socket
import threading
import time
import cv2
import numpy as np
import imageio

# Multicast configuration
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 5004
BUFFER_SIZE = 1024
FILE_TRANSFER_PORT = 5001  # Default port for file transfers
SOCKET_TIMEOUT = None  # Removed timeout for the receiver to wait indefinitely


class FileTransferApp(TkinterDnD.Tk):  # Inherit from TkinterDnD.Tk for drag-and-drop
    def __init__(self):
        super().__init__()
        
        self.title("File Sharing Application")
        self.geometry("800x600")  # Set initial window size

        # Layout - 2 columns for now (left and middle)
        self.left_frame = tk.Frame(self, width=250, bg='#f0f0f0')  # Sidebar for conversation history
        self.middle_frame = tk.Frame(self, width=550, bg='#ffffff')  # Main chat window
        
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Left box: Conversation history with clients (like Telegram chat list)
        self.client_history_label = tk.Label(self.left_frame, text="Conversations", bg='#f0f0f0')
        self.client_history_label.pack(padx=10, pady=5)
        
        self.client_history_listbox = tk.Listbox(self.left_frame, bg='#ffffff', selectbackground='#0078d7', highlightthickness=0)
        self.client_history_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Button to discover new clients and start new chat
        self.new_chat_button = tk.Button(self.left_frame, text="Start New Chat", command=self.toggle_peer_discovery, bg='#0078d7', fg='#ffffff')
        self.new_chat_button.pack(pady=10)

        # Middle box: Chat/File transfer log (like Telegram chat window)
        self.chat_log_label = tk.Label(self.middle_frame, text="Transfer Log", bg='#ffffff')
        self.chat_log_label.pack(padx=10, pady=5)
        
        self.chat_log_frame = tk.Frame(self.middle_frame, bg='#f7f7f7')
        self.chat_log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.chat_log_frame.drop_target_register(DND_FILES)
        self.chat_log_frame.dnd_bind('<<Drop>>', self.on_drop_file)

        # File transfer controls below chat log
        self.file_button = tk.Button(self.middle_frame, text="Send File", command=self.open_file_dialog, bg='#0078d7', fg='#ffffff')
        self.file_button.pack(pady=5)
        
        self.progress_bar = tk.Label(self.middle_frame, text="", bg='#ffffff')
        self.progress_bar.pack()

        # The cancel button starts hidden and only appears when a file is uploading
        self.cancel_button = tk.Button(self.middle_frame, text="Cancel Upload", command=self.cancel_upload, bg='#d9534f', fg='#ffffff')
        self.cancel_button.pack_forget()  # Initially hidden

        # Hidden right pane for peer discovery (shown on 'Start New Chat')
        self.right_frame = tk.Frame(self, width=250, bg='#e7e7e7')

        self.clients_online_label = tk.Label(self.right_frame, text="Clients Online", bg='#e7e7e7')
        self.clients_online_label.pack(padx=10, pady=5)
        
        self.clients_online_listbox = tk.Listbox(self.right_frame, bg='#ffffff', selectbackground='#0078d7', highlightthickness=0)
        self.clients_online_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # "Start Chat" button for selecting client to chat with
        self.start_chat_button = tk.Button(self.right_frame, text="Start Chat", command=self.start_chat_with_client, bg='#0078d7', fg='#ffffff')
        self.start_chat_button.pack(pady=10)
        
        self.is_right_frame_open = False  # Track if the right pane is open or collapsed

        # Initialize peer discovery and file transfer
        self.peer_discovery = PeerDiscovery(self)
        self.file_transfer = FileTransfer(self)

        # Start peer discovery
        self.peer_discovery.start_discovery()

        # Start receiver immediately to listen for incoming connections
        self.file_transfer.start_receiver()

    def on_drop_file(self, event):
        """Handle file drop into the chat log area."""
        file_path = event.data
        self.start_file_transfer(file_path.strip('{}'))  # Stripping braces around the file path

    def open_file_dialog(self):
        """Open file dialog to select a file for transfer."""
        file_path = filedialog.askopenfilename()
        if file_path:
            self.start_file_transfer(file_path)
    
    def start_file_transfer(self, file_path):
        """Start file transfer process."""
        selected_client = self.clients_online_listbox.get(tk.ACTIVE)
        if selected_client:
            print(f"[DEBUG] Starting file transfer to {selected_client}")
            self.file_transfer.send_file(file_path, selected_client)
            self.cancel_button.pack(pady=5)  # Show the cancel button
            self.cancel_button.config(state=tk.NORMAL)

    def cancel_upload(self):
        """Cancel the file upload."""
        self.file_transfer.cancel_transfer()  # Trigger the cancel operation
        self.cancel_button.pack_forget()  # Hide the cancel button
        self.progress_bar.config(text="File transfer cancelled.")

    def update_clients_online(self, client_ip):
        """Update the Clients Online list in the right pane."""
        if client_ip not in self.clients_online_listbox.get(0, tk.END):
            self.clients_online_listbox.insert(tk.END, client_ip)

    def start_chat_with_client(self):
        """Start a chat or file transfer with the selected client."""
        selected_client = self.clients_online_listbox.get(tk.ACTIVE)
        if selected_client:
            print(f"[DEBUG] Starting chat with {selected_client}")
            
            # Get the local hostname
            hostname = socket.gethostname()
            
            # Update the chat log label with the client's name and IP in brackets
            self.chat_log_label.config(text=f"{hostname} [{selected_client}] Transfer Log")
            
            # Add the selected client to conversation history
            self.client_history_listbox.insert(tk.END, selected_client)
            self.toggle_peer_discovery()  # Hide the peer discovery pane once chat starts

    def toggle_peer_discovery(self):
        """Toggle the peer discovery pane when 'Start New Chat' or 'Hide Clients' is clicked."""
        if not self.is_right_frame_open:
            self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
            self.new_chat_button.config(text="Hide Clients")
            self.is_right_frame_open = True
        else:
            self.right_frame.pack_forget()
            self.new_chat_button.config(text="Start New Chat")
            self.is_right_frame_open = False

    def update_transfer_progress(self, progress, speed, remaining_time):
        """Update the progress bar, speed, and estimated time remaining."""
        speed_str = self._format_speed(speed)
        time_remaining_str = self._format_time(remaining_time)
        self.progress_bar.config(text=f"Progress: {progress:.2f}% | Speed: {speed_str} | ETA: {time_remaining_str}")

    def _format_speed(self, speed):
        """Format transfer speed in a human-readable format."""
        if speed < 1024:
            return f"{speed:.2f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.2f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.2f} MB/s"

    def _format_time(self, remaining_time):
        """Format the estimated time remaining."""
        if remaining_time < 60:
            return f"{remaining_time:.2f} sec"
        else:
            minutes, seconds = divmod(remaining_time, 60)
            return f"{int(minutes)} min {int(seconds)} sec"

    def hide_progress_bar(self):
        """Hide the progress bar and cancel button when transfer completes."""
        self.cancel_button.pack_forget()  # Hide cancel button
        self.progress_bar.config(text="")  # Clear progress text

    def add_file_to_log(self, filename, file_size, file_data, is_image=False, is_video=False, sent=False, cancelled=False, thumbnail=None):
        """Add a file to the transfer log with optional thumbnail and metadata."""
        formatted_size = self.format_file_size(file_size)  # Format the file size
        file_metadata = f"{filename} ({formatted_size})"
        
        # Create a frame for the file entry
        file_frame = tk.Frame(self.chat_log_frame, bg='#f7f7f7', padx=5, pady=5)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Thumbnail or icon
        if thumbnail:
            thumb = ImageTk.PhotoImage(thumbnail)
            thumb_label = tk.Label(file_frame, image=thumb, bg='#f7f7f7')
            thumb_label.image = thumb  # Keep a reference to avoid garbage collection
            thumb_label.pack(side=tk.LEFT, padx=5)
            thumb_label.bind("<Button-1>", lambda event: self.on_save_file(filename, file_data))

        elif is_image and file_data:
            # Generate a thumbnail for the image
            image = Image.open(file_data)
            image.thumbnail((50, 50))
            thumb = ImageTk.PhotoImage(image)
            thumb_label = tk.Label(file_frame, image=thumb, bg='#f7f7f7')
            thumb_label.image = thumb  # Keep a reference to avoid garbage collection
            thumb_label.pack(side=tk.LEFT, padx=5)
            thumb_label.bind("<Button-1>", lambda event: self.on_save_file(filename, file_data))

        elif is_video and file_data:
            # Generate a thumbnail for the video
            image = self.file_transfer.generate_video_thumbnail(file_data)
            if image:
                thumb = ImageTk.PhotoImage(image)
                thumb_label = tk.Label(file_frame, image=thumb, bg='#f7f7f7')
                thumb_label.image = thumb  # Keep a reference to avoid garbage collection
                thumb_label.pack(side=tk.LEFT, padx=5)
                thumb_label.bind("<Button-1>", lambda event: self.on_save_file(filename, file_data))

        else:
            # File icon (non-image, non-video)
            file_icon_label = tk.Label(file_frame, text="📄", font=('Arial', 24), bg='#f7f7f7')
            file_icon_label.pack(side=tk.LEFT, padx=5)
            file_icon_label.bind("<Button-1>", lambda event: self.on_save_file(filename, file_data))

        # File metadata and status
        file_metadata_label = tk.Label(file_frame, text=file_metadata, bg='#f7f7f7')
        file_metadata_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        file_metadata_label.bind("<Button-1>", lambda event: self.on_save_file(filename, file_data))

        # Status label
        if cancelled:
            status_label = tk.Label(file_frame, text="Cancelled", fg='#d9534f', bg='#f7f7f7')
        elif sent:
            status_label = tk.Label(file_frame, text="Sent", fg='#5cb85c', bg='#f7f7f7')
        else:
            status_label = tk.Label(file_frame, text="Received", fg='#5bc0de', bg='#f7f7f7')
        status_label.pack(side=tk.RIGHT, padx=5)

    def save_file(self, filename, file_data):
        """Save the file to disk."""
        # Extract the file extension
        file_parts = filename.split('.')
        file_extension = file_parts[-1] if len(file_parts) > 1 else ''
        
        # Set the default file extension and file types
        filetypes = [("All Files", "*.*")]
        if file_extension:
            filetypes.insert(0, (f"{file_extension.upper()} files", f"*.{file_extension}"))

        save_path = filedialog.asksaveasfilename(
            initialfile=filename,
            defaultextension=f".{file_extension}",  # Set default extension
            filetypes=filetypes,  # Use the updated filetypes list
            title="Save File"  # Optional: Set a title for the dialog
        )
        
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(file_data.getvalue())  # Write the file content to disk
            print(f"[DEBUG] File saved to {save_path}")

    def update_conversation_history(self, peer_ip):
        """Add a peer to the conversation history (on the receiver's side)."""
        if peer_ip not in self.client_history_listbox.get(0, tk.END):
            # Get the local hostname
            hostname = socket.gethostname()
            # Update the conversation history with hostname and IP
            self.client_history_listbox.insert(tk.END, f"{hostname} [{peer_ip}]")

    def on_save_file(self, filename, file_data):
        """Handle saving the file when thumbnail or metadata is clicked."""
        self.save_file(filename, file_data)

    def format_file_size(self, size):
        """Convert bytes to a human-readable format."""
        if size < 1024:
            return f"{size} Bytes"
        elif size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        else:
            return f"{size / (1024 * 1024):.2f} MB"

# A placeholder class for PeerDiscovery logic (implement as per your network environment)
class PeerDiscovery:
    def __init__(self, gui_app):
        self.gui_app = gui_app  # Reference to the GUI to update the peer list
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        self.sock.bind(('', MULTICAST_PORT))

        # Join the multicast group
        mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton('0.0.0.0')
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    def announce_presence(self):
        """Announce this client's presence to the network."""
        while True:
            message = "FileSharingClient"
            print(f"[DEBUG] Announcing presence: {message}")
            self.sock.sendto(message.encode('utf-8'), (MULTICAST_GROUP, MULTICAST_PORT))
            time.sleep(5)  # Send announcement every 5 seconds

    def listen_for_peers(self):
        """Listen for announcements from other peers."""
        while True:
            try:
                data, addr = self.sock.recvfrom(BUFFER_SIZE)
                peer_message = data.decode('utf-8')
                if peer_message == "FileSharingClient":
                    # Update the GUI with the new peer (only if not already listed)
                    print(f"[DEBUG] Discovered peer: {addr[0]}")
                    self.gui_app.update_clients_online(addr[0])
            except Exception as e:
                print(f"[ERROR] Peer discovery error: {e}")

    def start_discovery(self):
        """Start peer discovery in separate threads."""
        threading.Thread(target=self.announce_presence, daemon=True).start()
        threading.Thread(target=self.listen_for_peers, daemon=True).start()

# A placeholder class for FileTransfer logic
class FileTransfer:
    def __init__(self, gui_app, network_type='wired'):
        self.gui_app = gui_app  # Reference to the GUI to update the progress bar and handle transfer
        self.packet_size = 64000 if network_type == 'wired' else 8192  # Packet size based on network type
        self.buffer_size = 128 * 1024
        self.cancelled = False  # To track if a transfer is cancelled
        self.received_files = {}  # Store received files in memory for now

    def start_receiver(self, port=FILE_TRANSFER_PORT):
        """Start the receiver to always listen for incoming file transfers."""
        print(f"[DEBUG] Starting receiver on port {port}")
        threading.Thread(target=self._receive_file_thread, args=(port,), daemon=True).start()

    def _receive_file_thread(self, port):
        """Background thread to receive a file via TCP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)  # Wait 10 seconds before starting keepalive probes
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Send keepalive probes every 10 seconds
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

                # Bind and listen for incoming connections
                s.bind(('0.0.0.0', port))
                s.listen(1)
                s.settimeout(None)
                
                print(f"[DEBUG] Listening for incoming connections on port {port}")
                self.gui_app.progress_bar.config(text="Waiting for file...")

                while True:
                    conn, addr = s.accept()
                    print(f"[DEBUG] Connection accepted from {addr[0]}")

                    with conn:
                        self.gui_app.progress_bar.config(text=f"Receiving file from {addr[0]}")

                        # Read the filename from the sender
                        filename_size = int(conn.recv(16).decode('utf-8'))
                        filename = conn.recv(filename_size).decode('utf-8')
                        print(f"[DEBUG] Receiving file: {filename}")

                        # Read the file size
                        file_size_data = conn.recv(16)
                        file_size = int(file_size_data.decode('utf-8'))
                        print(f"[DEBUG] File size: {file_size} bytes")

                        # Store the file content in memory
                        file_data = io.BytesIO()
                        total_bytes = 0

                        start_time = time.time()

                        # Receiving the file data
                        while total_bytes < file_size:
                            remaining_bytes = file_size - total_bytes
                            chunk = conn.recv(min(self.packet_size, remaining_bytes))
                            if not chunk:
                                break
                            file_data.write(chunk)
                            total_bytes += len(chunk)

                            elapsed_time = time.time() - start_time
                            speed = total_bytes / elapsed_time if elapsed_time > 0 else 0
                            remaining_time = (file_size - total_bytes) / speed if speed > 0 else 0

                            # Update progress on receiver side
                            progress = min((total_bytes / file_size) * 100, 100)
                            self.gui_app.update_transfer_progress(progress, speed, remaining_time)

                        if total_bytes != file_size:
                            print(f"[ERROR] File size mismatch: received {total_bytes} bytes, expected {file_size} bytes.")
                            return

                        file_data.seek(0)  # Reset pointer to start of the file
                        first_bytes = file_data.read(16)  # Read the first 16 bytes to inspect the content
                        print(f"[DEBUG] First 16 bytes of file: {first_bytes}")
                        print(f"[DEBUG] Generating thumbnail for {filename}")
                        thumbnail_image = self.generate_video_thumbnail(file_data)
                        if thumbnail_image:
                            print(f"[DEBUG] Thumbnail generated successfully for {filename}")
                        else:
                            print(f"[ERROR] Thumbnail generation failed for {filename}")

                        if not self.cancelled:
                            self.gui_app.add_file_to_log(
                                filename=filename,
                                file_size=file_size,
                                file_data=file_data,
                                thumbnail=thumbnail_image,
                                is_image=self._is_image_file(filename),
                                is_video=self._is_video_file(filename)
                            )
                            self.received_files[filename] = file_data
                            self.gui_app.progress_bar.config(text="File transfer completed.")
                        else:
                            self.gui_app.add_file_to_log(
                                filename=filename,
                                file_size=total_bytes,
                                file_data=None,
                                cancelled=True
                            )
                            print(f"[DEBUG] Transfer cancelled.")
                        self.gui_app.hide_progress_bar()
        except Exception as e:
            print(f"[ERROR] File reception error: {e}")
            self.gui_app.progress_bar.config(text=f"Error: {e}")


    def send_file(self, file_path, peer_ip, port=FILE_TRANSFER_PORT):
        """Send a file to the selected peer via TCP with tuned socket options in a separate thread."""
        self.cancelled = False  # Reset cancel status
        print(f"[DEBUG] Initiating file send to {peer_ip}:{port}")
        threading.Thread(target=self._send_file_thread, args=(file_path, peer_ip, port)).start()

    def _send_file_thread(self, file_path, peer_ip, port):
        """Background thread to send a file via TCP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)  # Wait 10 seconds before starting keepalive probes
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)  # Send keepalive probes every 10 seconds
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5) 

                # Connect to the peer
                print(f"[DEBUG] Attempting to connect to {peer_ip}:{port}")
                s.connect((peer_ip, port))
                self.gui_app.progress_bar.config(text=f"Connected to {peer_ip}. Sending {file_path}...")
                s.settimeout(None)

                # Send the file name first
                filename = os.path.basename(file_path)  # Get just the filename, not the full path
                filename_bytes = filename.encode('utf-8')
                s.sendall(f"{len(filename_bytes):08d}".encode('utf-8'))  # Send length of filename
                s.sendall(filename_bytes)  # Send filename

                # Send the file size
                file_size = os.path.getsize(file_path)
                s.sendall(f"{file_size:16d}".encode('utf-8'))  # Send the file size
                print(f"[DEBUG] Sending file size: {file_size}")

                # Initialize a variable to hold the file data
                file_data = io.BytesIO()

                # Read file content
                with open(file_path, 'rb') as f:
                    file_data.write(f.read())
                    start_time = time.time()
                file_data.seek(0)  # Reset the buffer position for later use

                # Log the file sending action
                if self._is_image_file(filename):
                    self.gui_app.add_file_to_log(
                        filename=filename,
                        file_size=file_size,
                        file_data=file_data,
                        is_image=True,
                        sent=True
                    )
                elif self._is_video_file(filename):
                    self.gui_app.add_file_to_log(
                        filename=filename,
                        file_size=file_size,
                        file_data=file_data,
                        is_video=True,
                        sent=True
                    )

                # Send the file content
                total_bytes = 0
                file_data.seek(0)  # Reset buffer position to start sending file content
                while chunk := file_data.read(self.packet_size):
                    s.sendall(chunk)
                    total_bytes += len(chunk)

                   
                    # Calculate transfer speed and remaining time
                    elapsed_time = time.time() - start_time
                    speed = total_bytes / elapsed_time if elapsed_time > 0 else 0
                    remaining_time = (file_size - total_bytes) / speed if speed > 0 else 0

                    progress = (total_bytes / file_size) * 100
                    self.gui_app.update_transfer_progress(progress, speed, remaining_time)

                print(f"[DEBUG] File transfer completed.")
                self.gui_app.progress_bar.config(text="File transfer completed.")
        except Exception as e:
            print(f"[ERROR] File transfer error: {e}")
            self.gui_app.progress_bar.config(text=f"Error: {e}")


    def _is_image_file(self, filename):
        """Check if a file is an image based on its extension."""
        return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))

    def _is_video_file(self, filename):
        """Check if a file is a video based on its extension."""
        return filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'))

    def generate_video_thumbnail(self, file_data):
        """Generate a thumbnail from a video file."""
        try:
            file_data.seek(0)  
            video_bytes = file_data.read() 

            # Use imageio to read the video from memory
            video_reader = imageio.get_reader(video_bytes, 'mp4')  # Specify mp4 format

            # Get video metadata
            video_duration = video_reader.get_meta_data()['duration']  # Get total video duration in seconds

            # Seek to the middle of the video
            middle_time = video_duration / 2  # Time in seconds (middle of the video)

            # Get the frame at the middle of the video
            middle_frame = video_reader.get_data(int(video_reader.get_meta_data()['fps'] * middle_time))

            image = Image.fromarray(middle_frame)
            image.thumbnail((50, 50))  # Create thumbnail
            return image
        except Exception as e:
            print(f"[ERROR] Failed to generate video thumbnail: {e}")
            return None


    def cancel_transfer(self):
        """Cancel an ongoing file transfer."""
        print("[DEBUG] Cancelling file transfer...")
        self.cancelled = True
        
if __name__ == "__main__":
    app = FileTransferApp()
    app.mainloop()
