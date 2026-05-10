import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
 
from motor.motor_asyncio import AsyncIOMotorClient
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("sticker-server")
 
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "sticker_db"
COLLECTION = "stickers"
HOST = os.getenv("SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("SERVER_PORT", "9000"))
 

sticker_cache: dict[str, dict] = {}
 

client_selections: dict[asyncio.StreamWriter, set[str]] = {}
client_selections_lock = asyncio.Lock()
 

mongo_client: AsyncIOMotorClient = None
db_collection = None
 
 
async def db_connect():
    global mongo_client, db_collection
    mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    await mongo_client.server_info()  
    db_collection = mongo_client[DB_NAME][COLLECTION]
    await db_collection.create_index("key", unique=True)
    log.info("Conectat la MongoDB  %s", MONGO_URI)
 
 
async def db_load_all() -> dict[str, dict]:
    """incarca stickerele din db in memorie"""
    cache = {}
    async for doc in db_collection.find({}, {"_id": 0}):
        cache[doc["key"]] = doc
    return cache
 
 
async def db_upsert(sticker: dict):
    await db_collection.replace_one(
        {"key": sticker["key"]}, sticker, upsert=True
    )
 
 
async def db_delete(key: str):
    await db_collection.delete_one({"key": key})
 
 
#client handler
 
async def send_json(writer: asyncio.StreamWriter, payload: dict):
    try:
        data = json.dumps(payload, ensure_ascii=False) + "\n"
        writer.write(data.encode())
        await writer.drain()
    except Exception:
        pass  
 
 
async def handle_select(writer: asyncio.StreamWriter, msg: dict):
    """
    filtreaza stickerele in functie de key, name, tag
    
    """
    f = msg.get("filter", {})
    results = []
    for sticker in sticker_cache.values():
        if "key" in f and sticker["key"] != f["key"]:
            continue
        if "key_prefix" in f and not sticker["key"].startswith(f["key_prefix"]):
            continue
        if "name_contains" in f and f["name_contains"].lower() not in sticker.get("name", "").lower():
            continue
        if "tag" in f and f["tag"] not in sticker.get("tags", []):
            continue
        results.append(sticker)
 
    
    selected_keys = {s["key"] for s in results}
    async with client_selections_lock:
        client_selections[writer] = client_selections.get(writer, set()) | selected_keys
 
    await send_json(writer, {"type": "SELECT_RESULT", "stickers": results})
    log.info("SELECT -> %d stickere, client abonat la %s", len(results), selected_keys)
 
 
async def handle_update(writer: asyncio.StreamWriter, msg: dict):
    key = msg.get("key")
    data = msg.get("data", {})
 
    if not key:
        await send_json(writer, {"type": "UPDATE_RESULT", "ok": False, "message": "Missing key"})
        return
 
    if key not in sticker_cache:
        await send_json(writer, {"type": "UPDATE_RESULT", "ok": False, "message": f"Sticker '{key}' not found"})
        return
 
    
    updatable = {"name", "description", "image_url", "price", "tags", "pack", "rarity", "animated"}
    sticker = dict(sticker_cache[key])
    for field, value in data.items():
        if field in updatable:
            sticker[field] = value
    sticker["updated_at"] = datetime.utcnow().isoformat()
 
    
    sticker_cache[key] = sticker
 
    
    await db_upsert(sticker)
 
    await send_json(writer, {"type": "UPDATE_RESULT", "ok": True, "message": f"Sticker '{key}' updated"})
    log.info("UPDATE key=%s", key)
 
    # notificare clienti (mai putin sender)
    await notify_update(key, sticker, exclude=writer)
 
 
async def handle_delete(writer: asyncio.StreamWriter, msg: dict):
    key = msg.get("key")
 
    if not key:
        await send_json(writer, {"type": "DELETE_RESULT", "ok": False, "message": "Missing key"})
        return
 
    if key not in sticker_cache:
        await send_json(writer, {"type": "DELETE_RESULT", "ok": False, "message": f"Sticker '{key}' not found"})
        return
 
    del sticker_cache[key]
    await db_delete(key)
 
    await send_json(writer, {"type": "DELETE_RESULT", "ok": True, "message": f"Sticker '{key}' deleted"})
    log.info("DELETE key=%s", key)
 
    
    await notify_delete(key, exclude=writer)
 
    
    async with client_selections_lock:
        for w, keys in client_selections.items():
            keys.discard(key)
 
 
#NOTIFICARI
 
async def notify_update(key: str, sticker: dict, exclude: asyncio.StreamWriter = None):
    async with client_selections_lock:
        targets = [w for w, keys in client_selections.items() if key in keys and w is not exclude]
    for w in targets:
        await send_json(w, {"type": "NOTIFY_UPDATE", "key": key, "sticker": sticker})
        log.info("NOTIFY_UPDATE key=%s -> client", key)
 
 
async def notify_delete(key: str, exclude: asyncio.StreamWriter = None):
    async with client_selections_lock:
        targets = [w for w, keys in client_selections.items() if key in keys and w is not exclude]
    for w in targets:
        await send_json(w, {"type": "NOTIFY_DELETE", "key": key})
        log.info("NOTIFY_DELETE key=%s -> client", key)
 
 
# HANDLER CONEXIUNE
 
async def client_connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    log.info("Client conectat: %s", addr)
 
    async with client_selections_lock:
        client_selections[writer] = set()
 
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                await send_json(writer, {"type": "ERROR", "message": "Invalid JSON"})
                continue
 
            msg_type = msg.get("type", "").upper()
            if msg_type == "SELECT":
                await handle_select(writer, msg)
            elif msg_type == "UPDATE":
                await handle_update(writer, msg)
            elif msg_type == "DELETE":
                await handle_delete(writer, msg)
            else:
                await send_json(writer, {"type": "ERROR", "message": f"Unknown message type: {msg_type}"})
 
    except asyncio.IncompleteReadError:
        pass
    except ConnectionResetError:
        pass
    finally:
        async with client_selections_lock:
            client_selections.pop(writer, None)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        log.info("Client deconectat: %s", addr)
 
 
# DATA
 
SEED_STICKERS = [
    {"key": "STK-001", "name": "Happy Cat", "description": "A very happy cartoon cat", "image_url": "https://example.com/stickers/happy_cat.png", "price": 0.99, "tags": ["cat", "happy", "animal"], "pack": "Animals Vol.1", "rarity": "common", "animated": False},
    {"key": "STK-002", "name": "Fire Dragon", "description": "Breathing fire dragon sticker", "image_url": "https://example.com/stickers/fire_dragon.gif", "price": 2.49, "tags": ["dragon", "fire", "fantasy"], "pack": "Fantasy Pack", "rarity": "rare", "animated": True},
    {"key": "STK-003", "name": "Pizza Slice", "description": "Delicious cheesy pizza slice", "image_url": "https://example.com/stickers/pizza.png", "price": 0.49, "tags": ["food", "pizza", "yummy"], "pack": "Food Fun", "rarity": "common", "animated": False},
    {"key": "STK-004", "name": "Rainbow Star", "description": "A sparkling rainbow star", "image_url": "https://example.com/stickers/rainbow_star.gif", "price": 1.99, "tags": ["star", "rainbow", "sparkle"], "pack": "Magic Collection", "rarity": "uncommon", "animated": True},
    {"key": "STK-005", "name": "Sleepy Panda", "description": "Panda taking a peaceful nap", "image_url": "https://example.com/stickers/sleepy_panda.png", "price": 1.29, "tags": ["panda", "sleepy", "animal", "cute"], "pack": "Animals Vol.2", "rarity": "uncommon", "animated": False},
    {"key": "STK-006", "name": "Cyber Robot", "description": "Futuristic cyber robot head", "image_url": "https://example.com/stickers/cyber_robot.gif", "price": 3.99, "tags": ["robot", "cyber", "tech", "futuristic"], "pack": "Tech World", "rarity": "epic", "animated": True},
    {"key": "STK-007", "name": "Sunflower Smile", "description": "Bright smiling sunflower", "image_url": "https://example.com/stickers/sunflower.png", "price": 0.79, "tags": ["flower", "smile", "nature", "happy"], "pack": "Nature Pack", "rarity": "common", "animated": False},
    {"key": "STK-008", "name": "Thunder Bolt", "description": "Electric thunder bolt with sparks", "image_url": "https://example.com/stickers/thunder.gif", "price": 2.99, "tags": ["thunder", "electric", "power"], "pack": "Elements", "rarity": "rare", "animated": True},
]
 
 
async def seed_database():
    count = await db_collection.count_documents({})
    if count == 0:
        now = datetime.utcnow().isoformat()
        docs = [{**s, "created_at": now, "updated_at": now} for s in SEED_STICKERS]
        await db_collection.insert_many(docs)
        log.info("Baza de date populata cu %d stickers", len(docs))
    else:
        log.info("Baza de date este deja populata cu cele %d stickers..", count)
 
 
# MAIN
 
async def main():
    await db_connect()
    await seed_database()
 
    global sticker_cache
    sticker_cache = await db_load_all()
    log.info("Au fost incarcate %d stickere in memoria cache", len(sticker_cache))
 
    server = await asyncio.start_server(client_connected, HOST, PORT)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    log.info("Sticker Server: %s", addrs)
 
    loop = asyncio.get_running_loop()
 
    def _stop():
        log.info("Inchidere server...")
        server.close()
 
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass  
 
    async with server:
        await server.serve_forever()
 
 
if __name__ == "__main__":
    asyncio.run(main())