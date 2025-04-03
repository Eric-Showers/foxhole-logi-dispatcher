import time
import sqlite3
import csv
import difflib

TSV_HEADER = 'Stockpile Title	Stockpile Name	Structure Type	Quantity	Name	Crated?	Per Crate	Total	Description	CodeName'

class DbHandler():
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()

    # Checks if a guild is registered with the bot
    def checkRegistration(self, guild_id):
        self.cur.execute("SELECT 1 FROM guilds WHERE id = ?", (guild_id,))
        result = self.cur.fetchone()
        if not result or result[0] is None:
            return False
        else:
            return True
    
    # Checks if a stockpile exists for this id and is accessible by this guild
    def checkStockIdAccess(self, guild_id, stock_id):
        self.cur.execute("SELECT 1 FROM stockpiles WHERE id = ? AND guild_id = ?", (stock_id, guild_id))
        result = self.cur.fetchone()
        if not result or result[0] is None:
            return False
        else:
            return True
        
    def checkPresetAccess(self, guild_id, preset_name):
        self.cur.execute("SELECT 1 FROM presets WHERE name = ? AND guild_id = ?", (preset_name, guild_id))
        result = self.cur.fetchone()
        if not result or result[0] is None:
            return False
        else:
            return True

    # Given a list of a members roles in the guild, return the highest access level
    def getAccessLevel(self, guild_id, role_ids):
        if not role_ids:
            return 0
        self.cur.execute("""
            SELECT MAX(access_level) FROM role_access
            WHERE guild_id = ? AND role_id IN ({})
            """.format(','.join('?' * len(role_ids))),
            (guild_id, *role_ids)
        )
        result = self.cur.fetchone()
        return result[0] if result and result[0] is not None else 0
    
    # Takes a row (list) from the items table and returns a dict
    def _getItemInfoDict(self, display_name):
        self.cur.execute("""
            SELECT * FROM items WHERE display_name = ?
            """, (display_name,)
        )
        item_row = self.cur.fetchone()
        if not item_row:
            raise ValueError(f"Internal Error (notify dev): Item {display_name} not found")
        return {
            'id': item_row[0],
            'code_name': item_row[1],
            'display_name': item_row[2],
            'category': item_row[3],
            'per_crate': item_row[4],
            'factory_queue': item_row[5],
            'mpf_queue': item_row[6],
            'faction': item_row[7],
            'reserve_max_quantity': item_row[8],
            'shippable_type': item_row[9],
            'ingredients': item_row[10],
            'description': item_row[11]
        }
    
    # Finds the closest matching item display_names to a list of strings
    def findClosestNames(self, item_names):
        self.cur.execute("SELECT display_name FROM items")
        all_names = [row[0] for row in self.cur.fetchall()]
        matches = {}
        for name in item_names:
            fuzzy_match = difflib.get_close_matches(name, all_names, n=1, cutoff=0.6)
            if fuzzy_match:
                matches[name] = fuzzy_match[0]
            else:
                # Fallback to substring search
                substring_matches = [item for item in all_names if name.lower() in item.lower()]
                if substring_matches:
                    matches[name] = substring_matches[0]
                else:
                    matches[name] = None
        return matches

    # Adds a new guild (discord server)
    def addGuild(self, guild_id, name):
        # Insert the new guild
        self.cur.execute(
            "INSERT INTO guilds (id, name) VALUES (?, ?) ON CONFLICT (id) DO NOTHING", 
            (guild_id, name)
        )
        self.conn.commit()

    # Sets the access level of a role associated with this guild
    def setAccess(self, guild_id, role_id, access_level):
        self.cur.execute("""
            INSERT INTO role_access (guild_id, role_id, access_level)
            VALUES (?,?,?)
            ON CONFLICT(guild_id, role_id) DO UPDATE SET access_level = EXCLUDED.access_level
            """, (guild_id, role_id, access_level)
        )
        self.conn.commit()

    # Fetches all stockpiles for a guild
    def fetchStockpiles(self, guild_id):
        self.cur.execute("""
            SELECT stock.id, stock.name, stock.last_update, struct.type, t.name 
            FROM stockpiles stock 
            JOIN structures struct ON stock.structure_id = struct.id
            JOIN towns t ON struct.town_id = t.id
            WHERE stock.guild_id = ?
            """, (guild_id,)
        )
        res = self.cur.fetchall()
        
        stockpiles = []
        for r in res:
            stockpiles.append({
                'id': r[0],
                'name': r[1],
                'last_update': r[2],
                'type': r[3],
                'town': r[4],
            })
        return stockpiles

    # Creates a new stockpile
    def create(self, guild_id, town, type, name):
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
            raise ValueError(f"Stockpile {name} already exists at the {type} in {town}")
        
        # Insert new stockpile
        self.cur.execute("""
            INSERT INTO stockpiles (name, guild_id, structure_id)
            VALUES (?, ?, ?)
            """, (name, guild_id, structure_id)
        )
        self.conn.commit()

    # Deletes a stockpile and it's related inventory and quotas
    def delete(self, stock_id):
        self.cur.execute("DELETE FROM inventory WHERE stock_id = ?", (stock_id,))
        self.cur.execute("DELETE FROM quotas WHERE stock_id = ?", (stock_id,))
        self.cur.execute("DELETE FROM stockpiles WHERE id = ?", (stock_id,))
        self.conn.commit()

    # Updates inventories
    def updateInventory(self, stock_id, tsv_file):
        # Read TSV file
        reader = csv.reader(tsv_file, delimiter='\t')
        header = next(reader)
        if header != TSV_HEADER.split('\t'):
            raise ValueError('Invalid TSV file, headers do not match expected FIR format')
        # Save code_name, name, quantity, crated
        data = [
            {
                'code_name': r[9], 
                'display_name': r[4], 
                'crated': True if r[5] == 'true' else False, 
                'amount': int(r[3])
            } 
            for r in reader
        ]
        if len(data) == 0:
            raise ValueError('TSV file has no items')
        
        # Get item_id for each item
        for d in data:
            self.cur.execute("""
                SELECT id FROM items WHERE code_name = ?
                """, (d['code_name'],)
            )
            item_id = self.cur.fetchone()
            if not item_id:
                raise ValueError(f"Item {d['display_name']} not found (notify dev)")
            else:
                d['item_id'] = item_id[0]

        # Update inventory by deleting previous values, then adding new ones
        self.cur.execute("DELETE FROM inventory WHERE stock_id = ?", (stock_id,))
        for d in data:
            if d['crated']:
                self.cur.execute("""
                    INSERT INTO inventory (item_id, stock_id, crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (item_id, stock_id)
                    DO UPDATE SET crates = ?
                    """,
                    (d['item_id'], stock_id, d['amount'], d['amount'])
                )
            else:
                self.cur.execute("""
                    INSERT INTO inventory (item_id, stock_id, non_crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (item_id, stock_id)
                    DO UPDATE SET non_crates = ?
                    """,
                    (d['item_id'], stock_id, d['amount'], d['amount'])
                )

        # Update stockpile timestamp
        self.cur.execute("UPDATE stockpiles SET last_update = ? WHERE id = ?", (int(time.time()),stock_id))
        self.conn.commit()

    # Handles a TSV file with multiple stockpiles
    def updateMulti(self, stock_ids, tsv_file):
        # Read TSV file
        reader = csv.reader(tsv_file, delimiter='\t')
        header = next(reader)
        if header != TSV_HEADER.split('\t'):
            raise ValueError("Invalid TSV file, headers do not match")
        
        # Save stock_id, code_name, name, quantity, crated
        data = []
        file_stock_ids = []
        for r in reader:
            item_data = {
                'stock_id': int(r[0].split('.')[0]),
                'code_name': r[9], 
                'display_name': r[4], 
                'crated': True if r[5] == 'true' else False, 
                'amount': int(r[3])
            }
            if item_data['stock_id'] not in file_stock_ids:
                if item_data['stock_id'] not in stock_ids:
                    raise ValueError(f"Stock ID {item_data['stock_id']} read from file but was not listed in command")
                file_stock_ids.append(item_data['stock_id'])
            data.append(item_data)
        for id in stock_ids:
            if id not in file_stock_ids:
                raise ValueError(f"Stock ID {id} listed in command but not found in file")
        if len(data) == 0:
            raise ValueError('TSV files have no items')

        # Get item_id for each item
        for d in data:
            self.cur.execute("""
                SELECT id FROM items WHERE code_name = ?
                """, (d['code_name'],)
            )
            item_id = self.cur.fetchone()
            if not item_id:
                raise ValueError(f"Item {d['display_name']} not found (notify dev)")
            else:
                d['item_id'] = item_id[0]

        # Update inventory by deleting previous values, then adding new ones
        for id in stock_ids:
            self.cur.execute("DELETE FROM inventory WHERE stock_id = ?", (id,))
        for d in data:
            if d['crated']:
                self.cur.execute("""
                    INSERT INTO inventory (item_id, stock_id, crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (item_id, stock_id)
                    DO UPDATE SET crates = ?
                    """,
                    (d['item_id'], d['stock_id'], d['amount'], d['amount'])
                )
            else:
                self.cur.execute("""
                    INSERT INTO inventory (item_id, stock_id, non_crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (item_id, stock_id)
                    DO UPDATE SET non_crates = ?
                    """,
                    (d['item_id'], d['stock_id'], d['amount'], d['amount'])
                )

        # Update stockpile timestamps
        for id in stock_ids:
            self.cur.execute("UPDATE stockpiles SET last_update = ? WHERE id = ?", (int(time.time()),id))
        self.conn.commit()
        return stock_ids

    # Updates quotas
    # quota_data is a string of the form "display_name:quantity, display_name:quantity, ..."
    def addQuotas(self, stock_id, quota_data):
        # Parse quota_data
        quotas = {}
        for q in quota_data.split(', '):
            name, quantity = q.split(':')
            quotas[name] = int(quantity)

        # Get item_id for each item
        quota_ids = {}
        wrong_names = []
        for display_name, quantity in quotas.items():
            self.cur.execute("""
                SELECT id FROM items WHERE display_name = ?
                """, (display_name,)
            )
            item_id = self.cur.fetchone()
            if item_id:
                quota_ids[item_id[0]] = quantity
            else:
                wrong_names.append(display_name)

        # Return name suggestions if any don't match
        if wrong_names:
            similar_names = self.findClosestNames(wrong_names)
            suggestions = []
            for name, suggestion in similar_names.items():
                if suggestion:
                    suggestions.append(f"{name} -> {suggestion}")
                else:
                    suggestions.append(f"{name} -> No match found")
            raise ValueError("Incorrect item names. Possible matches: \n```{}```".format(
                '\n'.join(suggestions)
            ))
        
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
    def deleteQuotas(self, stock_id):
        self.cur.execute("DELETE FROM quotas WHERE stock_id = ?", (stock_id,))
        self.conn.commit()

    # Fetches the quotas set on a stockpile
    def fetchQuotas(self, stock_id):
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
            return []
        
        return [{'info': self._getItemInfoDict(r[0]), 'quantity': r[1]} for r in res]
    
    # Adds a quota preset string to the database
    def createPreset(self, guild_id, preset_name, quota_data):
        # Check if a preset already exists with this name
        self.cur.execute("SELECT name FROM presets WHERE guild_id = ? AND name = ?", (guild_id,preset_name))
        if self.cur.fetchone():
            raise ValueError(f"Preset named {preset_name} already exists")

        # Validate item data in the quota string
        quotas = {}
        for q in quota_data.split(', '):
            display_name, quantity = q.split(':')
            quotas[display_name] = int(quantity)
        quota_ids = {}
        wrong_names = []
        for display_name, quantity in quotas.items():
            self.cur.execute("""
                SELECT id FROM items WHERE display_name = ?
                """, (display_name,)
            )
            item_id = self.cur.fetchone()
            if item_id:
                quota_ids[item_id[0]] = quantity
            else:
                wrong_names.append(display_name)
        # Return name suggestions if any don't match
        if wrong_names:
            similar_names = self.findClosestNames(wrong_names)
            suggestions = []
            for name, suggestion in similar_names.items():
                if suggestion:
                    suggestions.append(f"{name} -> {suggestion}")
                else:
                    suggestions.append(f"{name} -> No match found")
            raise ValueError("Incorrect item names. Possible matches: \n```{}```".format(
                '\n'.join(suggestions)
            ))

        # Add preset to DB
        self.cur.execute(
            "INSERT INTO presets (name, quota_string, guild_id) VALUES (?,?,?)"
            , (preset_name, quota_data, guild_id)
        )
        self.conn.commit()

    # Deletes a named preset from the database
    def deletePreset(self, guild_id, preset_name):
        self.cur.execute("DELETE FROM presets WHERE name = ? AND guild_id = ?", (preset_name, guild_id))
        self.conn.commit()
    
    # Adds a preset quota to a stockpile
    def applyPreset(self, guild_id, stock_id, preset_name):
        # Parse quota string and get item ids
        self.cur.execute(
            "SELECT quota_string FROM presets WHERE name = ? AND guild_id = ?",
            (preset_name, guild_id)
        )
        quota_data = self.cur.fetchone()
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
                raise ValueError(f"Internal error (notify dev): Could not find item {name}")
            
        # Update quotas, add to existing values
        for item_id, quantity in quota_ids.items():
            self.cur.execute("""
                INSERT INTO quotas (stock_id, item_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (stock_id, item_id)
                DO UPDATE SET amount = amount + ?
                """, (stock_id, item_id, quantity, quantity)
            )
        self.conn.commit()

    # Fetches all presets for a guild
    def fetchPresets(self, guild_id):
        # Get all presets for this guild
        self.cur.execute("""
            SELECT name FROM presets WHERE guild_id = ?
            """, (guild_id,)
        )
        resp = self.cur.fetchall()
        if not resp:
            return []
        return [r[0] for r in resp]
    
    # Fetches all quotas in a preset, returns dict of quotas, dict of item info
    def fetchPresetList(self, guild_id, preset_name):
        # Get quota string
        self.cur.execute("""
            SELECT quota_string FROM presets WHERE name = ? AND guild_id = ?
            """, (preset_name, guild_id)
        )
        res = self.cur.fetchone()
        # Parse quota string
        quotas = {}
        for q in res[0].split(', '):
            display_name, quantity = q.split(':')
            quotas[display_name] = int(quantity)

        quota_list = []
        for display_name, quantity in quotas.items():
            quota_list.append({
                'quantity': quantity,
                'info': self._getItemInfoDict(display_name)
            })
        
        return quota_list

    # Fetches the requirements to meet quotas for a stockpile
    def getRequirements(self, stock_id):
        # Get stockpile info
        self.cur.execute("""
            SELECT stock.name, stock.last_update, town.name, struc.type
            FROM stockpiles stock
            JOIN structures struc ON stock.structure_id = struc.id
            JOIN towns town ON struc.town_id = town.id
            WHERE stock.id = ?
            """, (stock_id,)
        )
        stock_name, last_update, stock_town, stock_struct = self.cur.fetchall()[0]
        req_dict = {
            'name': stock_name,
            'last_update': last_update,
            'town': stock_town,
            'type': stock_struct,
            'requirements': []
        }

        # Get item quotas and inventories
        self.cur.execute("""
            SELECT item.display_name, quota.amount, inv.crates, inv.non_crates
            FROM quotas quota
            JOIN items item ON quota.item_id = item.id
            LEFT JOIN inventory inv ON quota.item_id = inv.item_id AND quota.stock_id = inv.stock_id
            WHERE quota.stock_id = ?
            """, (stock_id,)
        )
        reqs = self.cur.fetchall()
        if not reqs:
            return {}

        # Get item info and calculate required amounts to meet quotas
        for r in reqs:
            display_name, quota_amount, inv_crates, inv_non_crates = r
            # Missing items can be treated as inventory of 0
            inv_crates = 0 if inv_crates is None else inv_crates
            inv_non_crates = 0 if inv_non_crates is None else inv_non_crates
            item_info = self._getItemInfoDict(display_name)
            if 'VehicleProfileType' in item_info['category'] or item_info['category'] == 'Structures':
                required_amount = quota_amount - (inv_crates * item_info['per_crate'] + inv_non_crates)
            else:
                required_amount = quota_amount - inv_crates
            if required_amount < 1:
                continue    # Ignore quotas that are already satisfied
            req_dict['requirements'].append({
                'quantity': required_amount,
                'info': item_info
            })
        
        return req_dict

