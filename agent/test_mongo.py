import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MDB_MCP_CONNECTION_STRING")
print("URI exists:", bool(uri))

client = MongoClient(uri, serverSelectionTimeoutMS=10000)
print(client.admin.command("ping"))
db = client["ride_agent_db"]
print("Collections:", db.list_collection_names())
client.close()
