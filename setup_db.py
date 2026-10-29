#!/usr/bin/env python3
"""Initialise the MongoDB database: validators, indexes, RBAC seed data."""
import os
from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
from storyweaver.schema import init_database

def main():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/storyweaver")
    db_name = uri.rsplit("/", 1)[-1].split("?")[0] or "storyweaver"
    client = MongoClient(uri)
    db = client[db_name]
    print("Setting up database:", db_name)
    init_database(db, verbose=True)
    print("Done.")

if __name__ == "__main__":
    main()
