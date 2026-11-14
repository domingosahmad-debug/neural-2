"""User-invoked native file chooser. Returns paths without reading media contents."""
import json
import tkinter as tk
from tkinter import filedialog
root=tk.Tk();root.withdraw();root.attributes('-topmost',True)
paths=filedialog.askopenfilenames(title='Neural Posthouse — choose project sources',parent=root)
print(json.dumps({'paths':list(paths)}));root.destroy()
