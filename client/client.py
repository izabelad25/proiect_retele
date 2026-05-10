import json
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from datetime import datetime

#default: host=127.0.0.1, port=9000
 
SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
 
# ── Color palette ──────────────────────────────────────────────────────────────
BG        = "#1a1a2e"
BG2       = "#16213e"
BG3       = "#0f3460"
ACCENT    = "#e94560"
ACCENT2   = "#f5a623"
TEXT      = "#eaeaea"
TEXT_DIM  = "#888899"
SUCCESS   = "#4caf7d"
WARN      = "#ff9800"
RARITY_COLORS = {
    "common":   "#9e9e9e",
    "uncommon": "#4caf50",
    "rare":     "#2196f3",
    "epic":     "#9c27b0",
    "legendary":"#ff9800",
}
 
 
class StickerClient:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sticker DB Client")
        self.root.configure(bg=BG)
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
 
        self.sock: socket.socket | None = None
        self.connected = False
        self.recv_thread: threading.Thread | None = None
        self.selected_stickers: dict[str, dict] = {}  
 
        self._build_ui()
        self._connect()
 
    # interfata user
 
    def _build_ui(self):
        #header
        header = tk.Frame(self.root, bg=BG3, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
 
        tk.Label(
            header, text="  Sticker Database Manager",
            font=("Courier New", 16, "bold"), bg=BG3, fg=TEXT
        ).pack(side="left", padx=20, pady=12)
 
        self.conn_label = tk.Label(
            header, text=" Disconnected",
            font=("Courier New", 10), bg=BG3, fg=WARN
        )
        self.conn_label.pack(side="right", padx=20)
 
        # main
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=10, pady=10)
 
        #lista stickere
        left = tk.Frame(main, bg=BG, width=600)
        left.pack(side="left", fill="both", expand=True)
        left.pack_propagate(False)
 
        # detalii + edit 
        right = tk.Frame(main, bg=BG2, width=360)
        right.pack(side="right", fill="both", padx=(10, 0))
        right.pack_propagate(False)
 
        self._build_query_bar(left)
        self._build_sticker_table(left)
        self._build_detail_panel(right)
        self._build_log_panel(right)
 
    def _build_query_bar(self, parent):
        bar = tk.Frame(parent, bg=BG2, pady=8)
        bar.pack(fill="x", pady=(0, 6))
 
        tk.Label(bar, text="Filter:", bg=BG2, fg=TEXT_DIM,
                 font=("Courier New", 10)).pack(side="left", padx=(10, 4))
 
        #filtre
        self.filter_var = tk.StringVar(value="all")
        opts = [("All", "all"), ("By Key", "key"), ("Key Prefix", "key_prefix"),
                ("Name", "name_contains"), ("Tag", "tag")]
        for label, val in opts:
            tk.Radiobutton(
                bar, text=label, variable=self.filter_var, value=val,
                bg=BG2, fg=TEXT, selectcolor=BG3, activebackground=BG2,
                activeforeground=ACCENT, font=("Courier New", 9),
                command=self._on_filter_change
            ).pack(side="left", padx=3)
 
        self.filter_entry = tk.Entry(
            bar, font=("Courier New", 10), bg=BG3, fg=TEXT,
            insertbackground=TEXT, width=16, state="disabled",
            relief="flat", highlightthickness=1, highlightbackground=BG3,
            highlightcolor=ACCENT
        )
        self.filter_entry.pack(side="left", padx=6)
 
        self._btn(bar, " SELECT", self._do_select, ACCENT).pack(side="left", padx=4)
 
    def _build_sticker_table(self, parent):
        lf = tk.LabelFrame(parent, text=" Stickers ", bg=BG, fg=TEXT_DIM,
                           font=("Courier New", 9), bd=1, relief="solid")
        lf.pack(fill="both", expand=True)
 
        cols = ("key", "name", "pack", "rarity", "price", "animated", "tags")
        self.tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse")
 
        widths = {"key": 80, "name": 130, "pack": 120, "rarity": 80,
                  "price": 60, "animated": 65, "tags": 130}
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=widths[c], minwidth=40, anchor="w")
 
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
            background=BG2, foreground=TEXT, fieldbackground=BG2,
            rowheight=24, font=("Courier New", 9))
        style.configure("Treeview.Heading",
            background=BG3, foreground=ACCENT2, font=("Courier New", 9, "bold"))
        style.map("Treeview", background=[("selected", BG3)],
                  foreground=[("selected", ACCENT)])
 
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
 
        # butoane pt edit si delete
        btn_bar = tk.Frame(lf, bg=BG, pady=6)
        btn_bar.pack(fill="x")
        self._btn(btn_bar, "Edit Selected", self._open_edit_dialog, ACCENT2).pack(side="left", padx=8)
        self._btn(btn_bar, "Delete Selected", self._do_delete, ACCENT).pack(side="left")
 
    def _build_detail_panel(self, parent):
        lf = tk.LabelFrame(parent, text=" Sticker Detail ", bg=BG2, fg=TEXT_DIM,
                           font=("Courier New", 9), bd=1, relief="solid")
        lf.pack(fill="x", padx=6, pady=(6, 4))
 
        self.detail_text = tk.Text(
            lf, height=14, bg=BG, fg=TEXT, font=("Courier New", 9),
            relief="flat", wrap="word", state="disabled",
            insertbackground=TEXT
        )
        self.detail_text.pack(fill="both", padx=4, pady=4)
 
        # Tag colors
        for rarity, color in RARITY_COLORS.items():
            self.detail_text.tag_configure(rarity, foreground=color)
        self.detail_text.tag_configure("key",   foreground=ACCENT2, font=("Courier New", 9, "bold"))
        self.detail_text.tag_configure("label", foreground=TEXT_DIM)
        self.detail_text.tag_configure("val",   foreground=TEXT)
        self.detail_text.tag_configure("anim",  foreground=SUCCESS)
 
    def _build_log_panel(self, parent):
        lf = tk.LabelFrame(parent, text=" Activity Log ", bg=BG2, fg=TEXT_DIM,
                           font=("Courier New", 9), bd=1, relief="solid")
        lf.pack(fill="both", expand=True, padx=6, pady=(0, 6))
 
        self.log_text = tk.Text(
            lf, bg=BG, fg=TEXT_DIM, font=("Courier New", 8),
            relief="flat", wrap="word", state="disabled"
        )
        self.log_text.tag_configure("notify", foreground=ACCENT2)
        self.log_text.tag_configure("error",  foreground=ACCENT)
        self.log_text.tag_configure("ok",     foreground=SUCCESS)
        self.log_text.tag_configure("info",   foreground=TEXT_DIM)
 
        vsb2 = ttk.Scrollbar(lf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
 
    def _btn(self, parent, text, cmd, color=ACCENT):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg="white", activebackground=BG3, activeforeground=TEXT,
            font=("Courier New", 9, "bold"), relief="flat",
            padx=10, pady=4, cursor="hand2", bd=0
        )
 
    # conectare
 
    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER_HOST, SERVER_PORT))
            self.connected = True
            self.conn_label.config(text=f"Conectat la {SERVER_HOST}:{SERVER_PORT}", fg=SUCCESS)
            self._log(f"Conectat la {SERVER_HOST}:{SERVER_PORT}", "ok")
            self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self.recv_thread.start()
        except Exception as e:
            self._log(f"Conexiune esuata: {e}", "error")
            messagebox.showerror("Connection Error", f"Cannot connect to server:\n{e}")
 
    def _send(self, payload: dict):
        if not self.connected or not self.sock:
            self._log("Not connected", "error")
            return
        try:
            data = json.dumps(payload, ensure_ascii=False) + "\n"
            self.sock.sendall(data.encode())
        except Exception as e:
            self._log(f"Send error: {e}", "error")
 
    def _recv_loop(self):
        buf = b""
        while self.connected:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            self.root.after(0, self._handle_server_msg, msg)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                break
        self.connected = False
        self.root.after(0, lambda: self.conn_label.config(
            text="Deconectat !", fg=WARN))
        self.root.after(0, lambda: self._log("Deconectat de la server", "error"))
 
    def _handle_server_msg(self, msg: dict):
        t = msg.get("type", "")
        if t == "SELECT_RESULT":
            self._on_select_result(msg)
        elif t == "UPDATE_RESULT":
            ok = msg.get("ok", False)
            self._log(msg.get("message", ""), "ok" if ok else "error")
        elif t == "DELETE_RESULT":
            ok = msg.get("ok", False)
            self._log(msg.get("message", ""), "ok" if ok else "error")
            if ok:
                key = None
                # find deleted key from message
                text = msg.get("message", "")
                if "'" in text:
                    key = text.split("'")[1]
                if key:
                    self.selected_stickers.pop(key, None)
                    self._remove_tree_row(key)
        elif t == "NOTIFY_UPDATE":
            key = msg.get("key")
            sticker = msg.get("sticker", {})
            self._log(f"NOTIFICATION: Sticker '{key}' a fost actualizat!", "notify")
            self.selected_stickers[key] = sticker
            self._update_tree_row(key, sticker)
            self._refresh_detail(key)
            messagebox.showinfo(
                " Sticker actualizat !",
                f"Sticker '{key}' ({sticker.get('name')}) a fost actualizat de alt client!"
            )
        elif t == "NOTIFY_DELETE":
            key = msg.get("key")
            self._log(f"NOTIFICATION: Sticker '{key}' a fost sters!", "notify")
            self.selected_stickers.pop(key, None)
            self._remove_tree_row(key)
            messagebox.showwarning(
                "Sticker sters",
                f"Sticker '{key}' a fost sters de alt client!"
            )
        elif t == "ERROR":
            self._log(f"Server error: {msg.get('message')}", "error")
 
    # ACTIUNI
 
    def _on_filter_change(self):
        state = "normal" if self.filter_var.get() != "all" else "disabled"
        self.filter_entry.config(state=state)
 
    def _do_select(self):
        filter_type = self.filter_var.get()
        value = self.filter_entry.get().strip()
 
        payload: dict = {"type": "SELECT", "filter": {}}
        if filter_type != "all" and value:
            payload["filter"][filter_type] = value
 
        self._send(payload)
        self._log(f"SELECT filter={payload['filter']}", "info")
 
    def _on_select_result(self, msg: dict):
        stickers = msg.get("stickers", [])
        self._log(f"Received {len(stickers)} stickers", "ok")
        
        for s in stickers:
            self.selected_stickers[s["key"]] = s
        
        self._populate_tree(stickers)
 
    def _do_delete(self):
        key = self._get_selected_key()
        if not key:
            messagebox.showwarning("No selection", "Selecteaza un sticker prima data...")
            return
        if messagebox.askyesno("Confirm Delete", f"Delete sticker '{key}'?"):
            self._send({"type": "DELETE", "key": key})
            self._log(f"DELETE key={key}", "info")
 
    def _open_edit_dialog(self):
        key = self._get_selected_key()
        if not key:
            messagebox.showwarning("No selection", "Selecteaza un sticker prima data...")
            return
        sticker = self.selected_stickers.get(key, {})
        EditDialog(self.root, sticker, self._submit_update)
 
    def _submit_update(self, key: str, data: dict):
        self._send({"type": "UPDATE", "key": key, "data": data})
        self._log(f"UPDATE key={key} data={data}", "info")
 
    # tree helpers
 
    def _populate_tree(self, stickers: list):
        self.tree.delete(*self.tree.get_children())
        for s in stickers:
            self._insert_tree_row(s)
 
    def _insert_tree_row(self, s: dict):
        tags_str = ", ".join(s.get("tags", []))
        rarity = s.get("rarity", "common")
        values = (
            s["key"], s.get("name", ""), s.get("pack", ""),
            rarity, f"${s.get('price', 0):.2f}",
            "Animat (GIF)" if s.get("animated") else "x", tags_str
        )
        self.tree.insert("", "end", iid=s["key"], values=values,
                         tags=(rarity,))
        rcolor = RARITY_COLORS.get(rarity, TEXT)
        self.tree.tag_configure(rarity, foreground=rcolor)
 
    def _update_tree_row(self, key: str, s: dict):
        if self.tree.exists(key):
            tags_str = ", ".join(s.get("tags", []))
            rarity = s.get("rarity", "common")
            self.tree.item(key, values=(
                s["key"], s.get("name", ""), s.get("pack", ""),
                rarity, f"${s.get('price', 0):.2f}",
                "Animat (GIF)" if s.get("animated") else "x", tags_str
            ))
 
    def _remove_tree_row(self, key: str):
        if self.tree.exists(key):
            self.tree.delete(key)
 
    def _get_selected_key(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None
 
    def _on_tree_select(self, _event=None):
        key = self._get_selected_key()
        if key and key in self.selected_stickers:
            self._refresh_detail(key)
 
    def _refresh_detail(self, key: str):
        s = self.selected_stickers.get(key)
        if not s:
            return
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", "end")
 
        rarity = s.get("rarity", "common")
        lines = [
            ("label", "KEY:        "), ("key", s.get("key", "")), ("val", "\n"),
            ("label", "Name:       "), ("val", s.get("name", "") + "\n"),
            ("label", "Pack:       "), ("val", s.get("pack", "") + "\n"),
            ("label", "Rarity:     "), (rarity, s.get("rarity", "").upper() + "\n"),
            ("label", "Price:      "), ("val", f"${s.get('price', 0):.2f}\n"),
            ("label", "Animated:   "), ("anim" if s.get("animated") else "val",
                                         "DA \n" if s.get("animated") else "NU \n"),
            ("label", "Tags:       "), ("val", ", ".join(s.get("tags", [])) + "\n"),
            ("label", "\nDescription:\n"), ("val", s.get("description", "") + "\n"),
            ("label", "\nImage URL:\n"), ("val", s.get("image_url", "") + "\n"),
            ("label", "\nCreated:    "), ("val", s.get("created_at", "") + "\n"),
            ("label", "Updated:    "), ("val", s.get("updated_at", "") + "\n"),
        ]
        for tag, text in lines:
            self.detail_text.insert("end", text, tag)
        self.detail_text.config(state="disabled")
 
    # log
 
    def _log(self, message: str, tag: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}] {message}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")
 
 
# dialog edit
 
class EditDialog(tk.Toplevel):
    def __init__(self, parent, sticker: dict, on_submit):
        super().__init__(parent)
        self.sticker = sticker
        self.on_submit = on_submit
        self.title(f"Edit Sticker – {sticker.get('key', '')}")
        self.configure(bg=BG)
        self.geometry("500x520")
        self.resizable(False, False)
        self.grab_set()
        self._build()
 
    def _build(self):
        s = self.sticker
 
        tk.Label(self, text=f"In editare: {s.get('key')}", bg=BG, fg=ACCENT2,
                 font=("Courier New", 13, "bold")).pack(pady=(16, 8))
 
        form = tk.Frame(self, bg=BG)
        form.pack(fill="both", padx=24)
 
        self.fields = {}
        editable = [
            ("name",        "Name",        s.get("name", "")),
            ("description", "Description", s.get("description", "")),
            ("image_url",   "Image URL",   s.get("image_url", "")),
            ("price",       "Price (USD)", str(s.get("price", "0"))),
            ("pack",        "Pack",        s.get("pack", "")),
            ("rarity",      "Rarity",      s.get("rarity", "common")),
            ("tags",        "Tags (comma-separated)", ", ".join(s.get("tags", []))),
        ]
 
        for field, label, default in editable:
            row = tk.Frame(form, bg=BG)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label + ":", bg=BG, fg=TEXT_DIM,
                     font=("Courier New", 9), width=22, anchor="w").pack(side="left")
            if field == "rarity":
                var = tk.StringVar(value=default)
                menu = ttk.Combobox(row, textvariable=var, width=20,
                                    values=["common", "uncommon", "rare", "epic", "legendary"],
                                    state="readonly", font=("Courier New", 9))
                menu.pack(side="left", fill="x", expand=True)
                self.fields[field] = var
            else:
                entry = tk.Entry(row, font=("Courier New", 9), bg=BG3, fg=TEXT,
                                 insertbackground=TEXT, relief="flat",
                                 highlightthickness=1, highlightbackground=BG3,
                                 highlightcolor=ACCENT)
                entry.insert(0, default)
                entry.pack(side="left", fill="x", expand=True)
                self.fields[field] = entry
 
        # checkbox animat
        row = tk.Frame(form, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Animated:", bg=BG, fg=TEXT_DIM,
                 font=("Courier New", 9), width=22, anchor="w").pack(side="left")
        self.animated_var = tk.BooleanVar(value=self.sticker.get("animated", False))
        tk.Checkbutton(row, variable=self.animated_var, bg=BG, fg=TEXT,
                       selectcolor=BG3, activebackground=BG,
                       activeforeground=ACCENT).pack(side="left")
 
        btn_bar = tk.Frame(self, bg=BG)
        btn_bar.pack(pady=16)
        tk.Button(btn_bar, text="Salveaza modificarile: ", command=self._submit,
                  bg=SUCCESS, fg="white", font=("Courier New", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side="left", padx=8)
        tk.Button(btn_bar, text="✖ Cancel", command=self.destroy,
                  bg=ACCENT, fg="white", font=("Courier New", 10, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2").pack(side="left")
 
    def _submit(self):
        data = {}
        for field, widget in self.fields.items():
            if field == "rarity":
                data[field] = widget.get()
            elif field == "tags":
                raw = widget.get()
                data[field] = [t.strip() for t in raw.split(",") if t.strip()]
            elif field == "price":
                try:
                    data[field] = float(widget.get())
                except ValueError:
                    messagebox.showerror("Invalid", "Pretul este numeric")
                    return
            else:
                data[field] = widget.get()
        data["animated"] = self.animated_var.get()
 
        self.on_submit(self.sticker["key"], data)
        self.destroy()
 
 
# entry point
 
if __name__ == "__main__":
    root = tk.Tk()
    app = StickerClient(root)
    root.mainloop()