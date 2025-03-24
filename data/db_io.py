import sqlite3
import asyncio
import csv

TSV_HEADER = 'Stockpile Title	Stockpile Name	Structure Type	Quantity	Name	Crated?	Per Crate	Total	Description	CodeName'

class DbHandler():
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()

    # Checks if a guild is registered with the bot
    def checkRegistration(self, guild_id):
        self.cur.execute("SELECT 1 FROM guilds WHERE id = ?", (guild_id,))
        if not self.cur.fetchone():
            raise ValueError("Server not registered with this bot")
    
    # Checks if a stockpile exists for this id
    def checkStockId(self, stock_id):
        self.cur.execute("SELECT 1 FROM stockpiles WHERE id = ?", (stock_id,))
        if not self.cur.fetchone():
            raise ValueError("Stockpile not found")

    # Adds a new guild (discord server)
    def addGuild(self, guild_id, name):
        # Check if guild already exists
        self.cur.execute("SELECT id FROM guilds WHERE id = ?", (guild_id,))
        if self.cur.fetchone():
            raise ValueError(f"Guild {name} is already registered.")
        # Insert the new guild
        self.cur.execute("INSERT INTO guilds (id, name) VALUES (?, ?)", (guild_id, name))
        self.conn.commit()

    # Fetches all stockpiles for a guild
    def fetchStockpiles(self, guild_id):
        self.checkRegistration(guild_id)
        self.cur.execute("""
            SELECT id, name, structure_id FROM stockpiles WHERE guild_id = ?
            """, (guild_id,)
        )
        res = self.cur.fetchall()
        
        if not res:
            raise ValueError("No stockpiles exist")
        
        stockpiles = []
        for r in res:
            self.cur.execute("SELECT type, town_id FROM structures WHERE id = ?", (r[2],))
            struct_type, struct_id = self.cur.fetchone()
            self.cur.execute("SELECT name FROM towns WHERE id = ?", (struct_id,))
            town = self.cur.fetchone()[0]
            stockpiles.append({
                'id': r[0],
                'name': r[1],
                'town': town,
                'type': struct_type
            })
        return stockpiles
    
    # Creates a new stockpile
    def create(self, guild_id, town, type, name):
        self.checkRegistration(guild_id)
        # Get town_id and structure_id
        self.cur.execute("""
            SELECT id FROM towns WHERE name = ?
            """, (town,)
        )
        town_id = self.cur.fetchone()
        if not town_id:
            raise ValueError(f"Town '{town}' not found")
        else:
            town_id = town_id[0]
        self.cur.execute("""
            SELECT id FROM structures WHERE town_id = ? AND type = ?
            """, (town_id, type)
        )
        structure_id = self.cur.fetchone()
        if not structure_id:
            raise ValueError(f"Structure {type} not found in {town}")
        else:
            structure_id = structure_id[0]
        
        # Check for duplicate stockpile
        self.cur.execute("""
            SELECT 1 FROM stockpiles
            WHERE guild_id = ? AND structure_id = ? AND name = ?
            """, (guild_id, structure_id, name)
        )
        if self.cur.fetchone():
            raise ValueError(f"Stockpile {name} already exists in {town}")
        
        # Insert new stockpile
        self.cur.execute("""
            INSERT INTO stockpiles (name, guild_id, structure_id)
            VALUES (?, ?, ?)
            """, (name, guild_id, structure_id)
        )
        self.conn.commit()

    # Deletes a stockpile and it's related inventory and quotas
    def delete(self, guild_id, stock_id):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)
        
        # Delete related inventory and quotas, then stockpile
        self.cur.execute("DELETE FROM inventory WHERE stock_id = ?", (stock_id,))
        self.cur.execute("DELETE FROM quotas WHERE stock_id = ?", (stock_id,))
        self.cur.execute("DELETE FROM stockpiles WHERE id = ?", (stock_id,))
        self.conn.commit()

    # Updates inventories
    def updateInventory(self, guild_id, stock_id, tsv_file):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)
        
        # Read TSV file
        reader = csv.reader(tsv_file, delimiter='\t')
        header = next(reader)
        if header != TSV_HEADER.split('\t'):
            raise ValueError("Invalid TSV file, headers do not match")
        # Save code_name, name, quantity, crated
        data = [
            {
                'code_name': r[9], 
                'display_name': r[4], 
                'crated': int(r[3]) if r[5] == 'true' else 0, 
                'non_crated': int(r[3]) if r[5] == 'false' else 0
            } 
            for r in reader
        ]
        
        # Get item_id for each item
        for d in data:
            self.cur.execute("""
                SELECT id FROM items WHERE code_name = ?
                """, (d['code_name'],)
            )
            item_id = self.cur.fetchone()
            if not item_id:
                raise ValueError(f"Item {d['display_name']} not found")
            else:
                d['item_id'] = item_id[0]

        # Update inventory, overwrite existing values
        for d in data:
            self.cur.execute("""
                INSERT INTO inventory (item_id, stock_id, crates, non_crates)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (item_id, stock_id)
                DO UPDATE SET crates = ?, non_crates = ?
                """, (d['item_id'], stock_id, d['crated'], d['non_crated'], d['crated'], d['non_crated'])
            )
        self.conn.commit()

    # Updates quotas
    # quota_data is a string of the form "display_name:quantity, display_name:quantity, ..."
    def addQuotas(self, guild_id, stock_id, quota_data):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)

        # Parse quota_data
        quotas = {}
        for q in quota_data.split(', '):
            name, quantity = q.split(':')
            quotas[name] = int(quantity)

        # Get item_id for each item
        quota_ids = {}
        for name, quantity in quotas.items():
            self.cur.execute("""
                SELECT id FROM items WHERE display_name = ?
                """, (name,)
            )
            item_id = self.cur.fetchone()
            if item_id:
                quota_ids[item_id[0]] = quantity
            else:
                # Search for similar names
                self.cur.execute("""
                    SELECT display_name FROM items
                    WHERE display_name LIKE ?
                    """, (f'%{name}%',))
                similar_name = self.cur.fetchone()
                if similar_name:
                    raise ValueError(f"Item {name} not found, did you mean {similar_name[0]}?")
                else:
                    raise ValueError(f"Item {name} not found")
        
        # Update quotas, overwrite existing values
        for item_id, quantity in quota_ids.items():
            self.cur.execute("""
                INSERT INTO quotas (stock_id, item_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (stock_id, item_id)
                DO UPDATE SET amount = ?
                """, (stock_id, item_id, quantity, quantity)
            )
        self.conn.commit()


    # Deletes all quotas set on a stockpile
    def deleteQuotas(self, guild_id, stock_id):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)
        self.cur.execute("DELETE FROM quotas WHERE stock_id = ?", (stock_id,))
        self.conn.commit()


    # Fetches the quotas set on a stockpile
    def fetchQuotas(self, guild_id, stock_id):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)
        # Get quota data
        self.cur.execute("""
            SELECT i.display_name, q.amount
            FROM quotas q
            JOIN items i ON q.item_id = i.id
            WHERE q.stock_id = ?
            """, (stock_id,)
        )
        res = self.cur.fetchall()
        if not res:
            raise ValueError('No quotas found')
        
        return [{'display_name': r[0], 'quantity': r[1]} for r in res]
    
    # Adds a quota preset string to the database
    def createPreset(self, guild_id, preset_name, quota_data):
        self.checkRegistration(guild_id)
        # Check if a preset already exists with this name
        self.cur.execute("SELECT name FROM presets WHERE name = ?", (preset_name,))
        if self.cur.fetchone():
            raise ValueError(f"Preset named {preset_name} already exists")

        # Validate item data in the quota string
        quotas = {}
        for q in quota_data.split(', '):
            name, quantity = q.split(':')
            quotas[name] = int(quantity)
        quota_ids = {}
        for name, quantity in quotas.items():
            self.cur.execute("""
                SELECT id FROM items WHERE display_name = ?
                """, (name,)
            )
            item_id = self.cur.fetchone()
            if item_id:
                quota_ids[item_id[0]] = quantity
            else:
                # Search for similar names
                self.cur.execute("""
                    SELECT display_name FROM items
                    WHERE display_name LIKE ?
                    """, (f'%{name}%',))
                similar_name = self.cur.fetchone()
                if similar_name:
                    raise ValueError(f"Item {name} not found, did you mean {similar_name[0]}?")
                else:
                    raise ValueError(f"Item {name} not found")
        # Add preset to DB
        self.cur.execute(
            "INSERT INTO presets (name, quota_string, guild_id) VALUES (?,?,?)"
            , (preset_name, quota_data, guild_id)
        )

    # Deletes a named preset from the database
    def deletePreset(self, guild_id, preset_name):
        self.checkRegistration(guild_id)
        # Check if a preset already exists with this name
        self.cur.execute("SELECT name FROM presets WHERE name = ?", (preset_name,))
        if not self.cur.fetchone():
            raise ValueError(f"No preset named {preset_name} exists")
        self.cur.execute("DELETE FROM presets WHERE name=?", (preset_name,))

    
    # Adds a preset quota to a stockpile
    def applyPreset(self, guild_id, stock_id, preset_name):
        self.checkRegistration(guild_id)
        self.checkStockId(stock_id)
        # Parse quota string and get item ids
        self.cur.execute(
            "SELECT quota_string FROM presets WHERE name = ?",
            (preset_name,)
        )
        quota_data = self.cur.fetchone()
        if not quota_data:
            raise ValueError(f"No preset named {preset_name} exists")
        print(quota_data)
        quotas = {}
        for q in quota_data[0].split(', '):
            name, quantity = q.split(':')
            quotas[name] = int(quantity)
        quota_ids = {}
        for name, quantity in quotas.items():
            self.cur.execute("""
                SELECT id FROM items WHERE display_name = ?
                """, (name,)
            )
            item_id = self.cur.fetchone()
            if item_id:
                quota_ids[item_id[0]] = quantity
            else:
                raise ValueError(f"Could not find item {name}")
            
        # Update quotas, add to existing values
        for item_id, quantity in quota_ids.items():
            self.cur.execute("""
                INSERT INTO quotas (stock_id, item_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (stock_id, item_id)
                DO UPDATE SET amount = amount + ?
                """, (stock_id, item_id, quantity, quantity)
            )


    # Fetches the requirements to meet quotas for all stockpiles
    def getRequirements(self, guild_id):
        self.checkRegistration(guild_id)
        # Get guild's stockpiles
        self.cur.execute("""
            SELECT id, name FROM stockpiles WHERE guild_id = ?
            """, (723282644271366194,)
        )
        res = self.cur.fetchall()
        if not res:
            raise ValueError("No stockpiles exist")
        
        req_dict = {}
        for stockpile_info in res:
            stock_id, stock_name = stockpile_info
            self.cur.execute("""
                SELECT i.display_name, q.amount, inv.crates
                FROM quotas q
                JOIN items i ON q.item_id = i.id
                LEFT JOIN inventory inv ON q.item_id = inv.item_id AND q.stock_id = inv.stock_id
                WHERE q.stock_id = ?
                """, (stock_id,)
            )
            reqs = self.cur.fetchall()
            req_dict[stock_id] = {
                'stock_id': stock_id,
                'stock_name': stock_name,
                'requirements': {quota[0]: quota[1] - quota[2] if quota[2] else quota[1] for quota in reqs}
            }
        
        return req_dict

