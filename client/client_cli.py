"""
COMMAND LINE CLIENT
"""

import json
import socket
import sys
import threading

SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
SERVER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9000

HELP = """
Comenzi disponibile:
  select                       = selecteaza TOATE stickerele
  select key <KEY>             = selecteaza in functie de KEY
  select prefix <PREFIX>       = selecteaza in functie de KEY PREFIX
  select name <TEXT>           = selecteaza in functie de NUME
  select tag <TAG>             = selecteaza in functie de TAG
  update <KEY> <FIELD> <VALUE> = ACTUALIZEAZA un camp al unui STICKER
  delete <KEY>                 = STERGE un sticker
  help                         = afiseaza instructiuni
  quit / exit                  = deconectare / exit

Campurile care pot fi actualizate: name, description, image_url, price, pack, rarity, animated, tags
Pentru tags: use comma-separated values                   ex:  update STK-001 tags cat,happy,new
Pentru campul ``animated``: foloseste true/false          ex: update STK-002 animated true
"""


def send_json(sock: socket.socket, payload: dict):
    data = json.dumps(payload) + "\n"
    sock.sendall(data.encode())


def recv_loop(sock: socket.socket):
    buf = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                print("\n[DISCONNECTED]")
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    handle_message(msg)
                except json.JSONDecodeError:
                    pass
        except Exception:
            break


def handle_message(msg: dict):
    t = msg.get("type", "")
    if t == "SELECT_RESULT":
        stickers = msg.get("stickers", [])
        print(f"\n[SELECT_RESULT] {len(stickers)} sticker(s):")
        for s in stickers:
            print(f"  [{s['key']}] {s['name']} | Pack: {s['pack']} | "
                  f"Rarity: {s['rarity']} | Price: ${s.get('price', 0):.2f} | "
                  f"Animated: {s.get('animated')} | Tags: {s.get('tags')}")
    elif t == "UPDATE_RESULT":
        ok = msg.get("ok")
        status = "✓ OK" if ok else "✗ FAIL"
        print(f"\n[UPDATE_RESULT] {status}: {msg.get('message')}")
    elif t == "DELETE_RESULT":
        ok = msg.get("ok")
        status = "✓ OK" if ok else "✗ FAIL"
        print(f"\n[DELETE_RESULT] {status}: {msg.get('message')}")
    elif t == "NOTIFY_UPDATE":
        key = msg.get("key")
        s = msg.get("sticker", {})
        print(f"\n  *** NOTIFICATION: Sticker '{key}' ({s.get('name')}) was UPDATED by another client! ***")
    elif t == "NOTIFY_DELETE":
        key = msg.get("key")
        print(f"\n  *** NOTIFICATION: Sticker '{key}' was DELETED by another client! ***")
    elif t == "ERROR":
        print(f"\n[ERROR] {msg.get('message')}")
    print(">> ", end="", flush=True)


def parse_command(line: str, sock: socket.socket):
    parts = line.strip().split(None, 3)
    if not parts:
        return

    cmd = parts[0].lower()

    if cmd in ("quit", "exit"):
        print("Goodbye!")
        sock.close()
        sys.exit(0)

    elif cmd == "help":
        print(HELP)

    elif cmd == "select":
        if len(parts) == 1:
            send_json(sock, {"type": "SELECT", "filter": {}})
        elif len(parts) >= 3:
            ftype = parts[1].lower()
            value = parts[2]
            fmap = {
                "key": "key",
                "prefix": "key_prefix",
                "name": "name_contains",
                "tag": "tag",
            }
            if ftype in fmap:
                send_json(sock, {"type": "SELECT", "filter": {fmap[ftype]: value}})
            else:
                print(f"Unknown filter type: {ftype}. Use: key, prefix, name, tag")
        else:
            print("Usage: select [key|prefix|name|tag] [value]")

    elif cmd == "update":
        if len(parts) < 4:
            print("Usage: update <KEY> <FIELD> <VALUE>")
            return
        key, field, value = parts[1], parts[2], parts[3]
        # Type coercion
        if field == "price":
            try:
                value = float(value)
            except ValueError:
                print("Price must be a number")
                return
        elif field == "animated":
            value = value.lower() in ("true", "1", "yes")
        elif field == "tags":
            value = [t.strip() for t in value.split(",") if t.strip()]
        send_json(sock, {"type": "UPDATE", "key": key, "data": {field: value}})

    elif cmd == "delete":
        if len(parts) < 2:
            print("Usage: delete <KEY>")
            return
        send_json(sock, {"type": "DELETE", "key": parts[1]})

    else:
        print(f"Unknown command: {cmd}  (type 'help' for available commands)")


def main():
    print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_HOST, SERVER_PORT))
        print(f"Connected! Type 'help' for commands.\n")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    t = threading.Thread(target=recv_loop, args=(sock,), daemon=True)
    t.start()

    print(">> ", end="", flush=True)
    try:
        for line in sys.stdin:
            parse_command(line, sock)
            print(">> ", end="", flush=True)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        sock.close()


if __name__ == "__main__":
    main()
