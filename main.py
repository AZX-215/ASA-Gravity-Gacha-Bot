import json
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / "json_files" / "settings.json"
BOT_PROGRAM = ROOT / "main_program.py"

def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_settings(data):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")

def infer_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if value is None:
        return "none"
    return "str"

class SettingsGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ASA Gravity Gacha Bot Launcher")
        self.root.geometry("1200x820")
        self.process = None
        self.settings = load_settings()
        self.vars = {}
        self.types = {}

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        root.configure(bg="#1f1f1f")
        style.configure(".", background="#1f1f1f", foreground="white")
        style.configure("TLabel", background="#1f1f1f", foreground="white")
        style.configure("TFrame", background="#1f1f1f")
        style.configure("TButton", padding=6)
        style.configure("TCheckbutton", background="#1f1f1f", foreground="white")
        style.configure("TEntry", fieldbackground="#2b2b2b", foreground="white")

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="Settings", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)

        canvas = tk.Canvas(body, bg="#1f1f1f", highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_fields()

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(10, 0))

        ttk.Button(btns, text="Save Settings", command=self.save).pack(side="left")
        ttk.Button(btns, text="Start Bot", command=self.start_bot).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Stop Bot", command=self.stop_bot).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Reload From Disk", command=self.reload).pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(10, 0))

    def _build_fields(self):
        for child in self.inner.winfo_children():
            child.destroy()

        for row, key in enumerate(sorted(self.settings.keys())):
            value = self.settings[key]
            val_type = infer_type(value)
            self.types[key] = val_type
            ttk.Label(self.inner, text=key).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)

            if val_type == "bool":
                var = tk.BooleanVar(value=value)
                widget = ttk.Checkbutton(self.inner, variable=var)
                widget.grid(row=row, column=1, sticky="w", pady=4)
            else:
                var = tk.StringVar(value="" if value is None else str(value))
                widget = ttk.Entry(self.inner, textvariable=var, width=60)
                widget.grid(row=row, column=1, sticky="ew", pady=4)

            self.vars[key] = var

        self.inner.columnconfigure(1, weight=1)

    def _collect(self):
        data = {}
        for key, var in self.vars.items():
            raw = var.get()
            typ = self.types[key]
            if typ == "bool":
                data[key] = bool(raw)
            elif typ == "int":
                data[key] = int(raw)
            elif typ == "float":
                data[key] = float(raw)
            elif typ == "none":
                data[key] = None if raw in ("", "None", "none", "null") else raw
            else:
                data[key] = raw
        return data

    def save(self):
        try:
            data = self._collect()
            save_settings(data)
            self.settings = data
            self.status_var.set("Settings saved")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def reload(self):
        self.settings = load_settings()
        self.vars.clear()
        self.types.clear()
        self._build_fields()
        self.status_var.set("Reloaded settings.json")

    def start_bot(self):
        try:
            self.save()
            if self.process and self.process.poll() is None:
                self.status_var.set("Bot already running")
                return
            self.process = subprocess.Popen([sys.executable, str(BOT_PROGRAM)], cwd=str(ROOT))
            self.status_var.set(f"Bot running (PID {self.process.pid})")
        except Exception as exc:
            messagebox.showerror("Start failed", str(exc))

    def stop_bot(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status_var.set("Bot stopped")
        else:
            self.status_var.set("No running bot process")

def main():
    root = tk.Tk()
    SettingsGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
