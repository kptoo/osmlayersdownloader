import tkinter as tk
from tkinter import messagebox

class OSMDownloaderDialog:
    def __init__(self, master):
        self.master = master
        self.master.title('OSM Layers Downloader')

        # State Variables
        self.layer_selection = tk.StringVar()  # Holds selected layer
        self.download_path = tk.StringVar()  # Holds path for downloads

        # UI Components
        self.create_widgets()

    def create_widgets(self):
        # Frame for Layer Selection
        layer_frame = tk.Frame(self.master)
        layer_frame.pack(padx=10, pady=10)

        tk.Label(layer_frame, text='Select OSM Layer:').pack(side=tk.LEFT)
        layer_options = ['Buildings', 'Roads', 'Land Use']  # Example options
        self.layer_menu = tk.OptionMenu(layer_frame, self.layer_selection, *layer_options)
        self.layer_menu.pack(side=tk.LEFT)

        # Frame for Download Path
        path_frame = tk.Frame(self.master)
        path_frame.pack(padx=10, pady=10)

        tk.Label(path_frame, text='Download Path:').pack(side=tk.LEFT)
        tk.Entry(path_frame, textvariable=self.download_path).pack(side=tk.LEFT)

        # Download Button
        download_button = tk.Button(self.master, text='Download', command=self.download_layer)
        download_button.pack(pady=20)

    def download_layer(self):
        layer = self.layer_selection.get()
        path = self.download_path.get()
        if layer and path:
            # Logic for downloading the selected layer to the specified path
            messagebox.showinfo('Download', f'Downloading {layer} to {path}')
        else:
            messagebox.showwarning('Input Error', 'Please select a layer and specify a download path.')

if __name__ == '__main__':
    root = tk.Tk()
    app = OSMDownloaderDialog(root)
    root.mainloop()