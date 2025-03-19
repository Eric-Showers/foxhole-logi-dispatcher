import sqlite3
import asyncio

class DbHandler():
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()

    # Adds a new guild (discord server)
    def addGuild(self, guild_id, name):
        # TODO: - Add error handling for duplicate guilds
        # Check if guild already exists
        self.cur.execute("SELECT id FROM guilds WHERE id = ?", (guild_id,))
        if self.cur.fetchone():
            raise ValueError(f"Guild {name} is already registered.")
        # Insert the new guild
        self.cur.execute("INSERT INTO guilds (id, name) VALUES (?, ?)", (guild_id, name))
        self.conn.commit()

    # Fetches all stockpiles for a guild
    def fetchStockpiles(self, guild_id):
        self.cur.execute("""
            SELECT id, name, town_id FROM stockpiles WHERE guild_id = ?
            """, (guild_id,)
        )
        res = self.cur.fetchall()
        
        if not res:
            return []
        
        stockpiles = []
        for r in res:
            self.cur.execute("SELECT name FROM towns WHERE id = ?", (r[2],))
            town = self.cur.fetchone()
            stockpiles.append({
                'id': r[0],
                'name': r[1],
                'town': town[0] if town else 'Unknown'
            })
        return stockpiles
    
    # Creates a new stockpile
    def create(self, guild_id, town, type, name):
        # TODO: - Add error handling for nonexistent towns and structures
        #       - Add error handling for duplicate stockpiles
        self.cur.execute("""
            SELECT id FROM towns WHERE name = ?
            """, (town,)
        )
        town_id = self.cur.fetchone()[0]
        self.cur.execute("""
            SELECT id FROM structures WHERE town_id = ? AND type = ?
            """, (town_id, type)
        )
        structure_id = self.cur.fetchone()[0]
        self.cur.execute("""
            INSERT INTO stockpiles (name, guild_id, town_id, structure_id)
            VALUES (?, ?, ?, ?)
            """, (name, guild_id, town_id, structure_id)
        )
        self.conn.commit()

    # Deletes a stockpile
    def delete(self, guild_id, town, type, name):
        # TODO: - Add error handling for when the stockpile doesn't exist
        #       - Delete invetory and quotas for the stockpile first
        self.cur.execute("""
            SELECT id FROM towns WHERE name = ?
            """, (town,)
        )
        town_id = self.cur.fetchone()[0]
        self.cur.execute("""
            SELECT id FROM structures WHERE town_id = ? AND type = ?
            """, (town_id, type)
        )
        structure_id = self.cur.fetchone()[0]
        self.cur.execute("""
            DELETE FROM stockpiles
            WHERE guild_id = ? AND town_id = ? AND structure_id = ? AND name = ?
            """, (guild_id, town_id, structure_id, name)
        )
        self.cur
        self.conn.commit()

    # Updates inventories
    def updateInventory(self, guild_id, stock_id, item_data):
        # TODO: - Finish integration with bot command
        #       - Add error handling for nonexistent stockpiles/items
        self.cur.executemany("""
            INSERT OR REPLACE INTO inventory (item_id, stock_id, crates, items)
            VALUES (?, ?, ?, ?)
            """, [(item['id'], stock_id, item['crates'], item['items']) for item in item_data]
        )
        self.conn.commit()

    