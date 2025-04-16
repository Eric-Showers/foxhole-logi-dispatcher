import time
import sqlite3
import csv
import difflib

from data.objects.item import Item

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
    
    # Given a list of display names, returns a list of Item objects or raises ValueError for incorrect names
    def getItems(self, display_name_list):
        wrong_names = []
        items = []
        for display_name in display_name_list:
            self.cur.execute("""
                SELECT * FROM items WHERE display_name = ?
                """, (display_name,)
            )
            result = self.cur.fetchone()
            if result:
                items.append(Item(result))
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
        else:
            return items
    
    # Fetches all item categories
    def getCategories(self):
        self.cur.execute("SELECT DISTINCT category FROM items")
        return [category[0] for category in self.cur.fetchall()]

    # Fetches all items with matching category string
    def getCategoryItems(self, category, faction):
        if not faction:
            self.cur.execute("SELECT * from items WHERE category = ?", (category,))
        elif faction == 'Wardens':
            self.cur.execute("SELECT * from items WHERE category = ? AND faction != 'Colonials'", (category,))
        elif faction == 'Colonials':
            self.cur.execute("SELECT * from items WHERE category = ? AND faction != 'Wardens'", (category,))
            
        return [Item(row) for row in self.cur.fetchall()]
    
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

    # Fetches the inventory of a stockpile
    def viewInventory(self, stock_id):
        self.cur.execute("""
            SELECT ite.display_name, inv.crates, inv.non_crates
            FROM inventory inv
            JOIN items ite
            ON inv.item_id = ite.id
            WHERE inv.stock_id = ?""",
            (stock_id,))
        result = self.cur.fetchall()
        if not result:
            return []
        inventory_dict = {r[0]: [r[1], r[2]] for r in result}
        items = self.getItems(inventory_dict.keys())
        for item in items:
            item.crates, item.non_crates = inventory_dict[item.display_name]
        return items
    
    def setInventory(self, stock_id, crates_list, non_crates_list):
        # Parse item list
        item_amounts = {}
        for i in crates_list.split(','):
            name, amount = i.strip().split(':')
            if name not in item_amounts:
                item_amounts[name] = {'crates':0, 'non_crates':None}
            item_amounts[name]['crates'] = int(amount)
        for i in non_crates_list.split(','):
            name, amount = i.strip().split(':')
            if name not in item_amounts:
                item_amounts[name] = {'crates':None, 'non_crates':0}
            item_amounts[name]['non_crates'] = int(amount)
        
        # Get Item for each display name
        items = self.getItems(item_amounts.keys())
        for item in items:
            item.crates = item_amounts[item.display_name]['crates']
            item.non_crates = item_amounts[item.display_name]['non_crates']

        # Update inventory rows, overwrite existing values
        for item in items:
            if item.crates is not None:
                self.cur.execute("""
                    INSERT INTO inventory (stock_id, item_id, crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (stock_id, item_id)
                    DO UPDATE SET crates = ?
                    """, (stock_id, item.id, item.crates, item.crates)
                )
            if item.non_crates is not None:
                self.cur.execute("""
                    INSERT INTO inventory (stock_id, item_id, non_crates)
                    VALUES (?, ?, ?)
                    ON CONFLICT (stock_id, item_id)
                    DO UPDATE SET non_crates = ?
                    """, (stock_id, item.id, item.non_crates, item.non_crates)
                )
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

    # Updates quotas
    # quota_data is a string of the form "display_name:quantity, display_name:quantity, ..."
    def addQuotas(self, stock_id, quota_data):
        # Parse quota_data
        quotas = {}
        for q in quota_data.split(','):
            name, quantity = q.strip().split(':')
            quotas[name] = {'crates': int(quantity)}
        items = self.getItems(quotas.keys())
        
        # Update quotas, overwrite existing values
        for item in items:
            item.crates = quotas[item.display_name]['crates']
            self.cur.execute("""
                INSERT INTO quotas (stock_id, item_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (stock_id, item_id)
                DO UPDATE SET amount = ?
                """, (stock_id, item.id, item.crates, item.crates)
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
        result = self.cur.fetchall()
        if not result:
            return []
        quota_dict = {r[0]:r[1] for r in result}
        items = self.getItems(quota_dict.keys())
        for item in items:
            item.crates = quota_dict[item.display_name]
        return items
    
    # Adds a quota preset string to the database
    def createPreset(self, guild_id, preset_name, quota_data):
        # Check if a preset already exists with this name
        self.cur.execute("SELECT name FROM presets WHERE guild_id = ? AND name = ?", (guild_id,preset_name))
        if self.cur.fetchone():
            raise ValueError(f"Preset named {preset_name} already exists")
        
        # Parse quota_data
        quotas = {}
        for q in quota_data.split(','):
            name, quantity = q.strip().split(':')
            quotas[name] = {'crates': int(quantity)}
        # Get items (to validate display names)
        items = self.getItems(quotas.keys())

        # Add preset to DB
        self.cur.execute(
            "INSERT INTO presets (name, quota_string, guild_id) VALUES (?,?,?)"
            , (preset_name, quota_data, guild_id)
        )
        self.conn.commit()

    # Edit the quotas in a preset
    def editPreset(self, guild_id, preset_name, new_quota_str):
        # Get existing quotas
        self.cur.execute("""
            SELECT quota_string FROM presets WHERE name = ? AND guild_id = ?
            """, (preset_name, guild_id)
        )
        old_quota_str = self.cur.fetchone()

        # Parse previous quota string
        old_quotas = {}
        for q in old_quota_str[0].split(','):
            display_name, quantity = q.strip().split(':')
            old_quotas[display_name] = int(quantity)
        
        # Validate item data in the new quota string and overwrite previous quota quantities
        for q in new_quota_str.split(','):
            display_name, quantity = q.strip().split(':')
            old_quotas[display_name] = int(quantity)
        items = self.getItems(old_quotas.keys())    # Validate display names
        edited_quotas = []
        for item in items:
            edited_quotas.append(f"{item.display_name}:{old_quotas[item.display_name]}")
        edited_quota_str = ', '.join(edited_quotas)
        
        # Update preset in DB
        self.cur.execute("""
                         INSERT INTO presets (name, quota_string, guild_id)
                         VALUES (?,?,?)
                         ON CONFLICT (name, guild_id)
                         DO UPDATE SET quota_string = ?
                         """, (preset_name, edited_quota_str, guild_id, edited_quota_str)
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
        for q in quota_data[0].split(','):
            name, quantity = q.strip().split(':')
            quotas[name] = int(quantity)
        items = self.getItems(quotas.keys())
            
        # Update quotas, add to existing values
        for item in items:
            item.crates = quotas[item.display_name]
            self.cur.execute("""
                INSERT INTO quotas (stock_id, item_id, amount)
                VALUES (?, ?, ?)
                ON CONFLICT (stock_id, item_id)
                DO UPDATE SET amount = amount + ?
                """, (stock_id, item.id, item.crates, item.crates)
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
    
    # Fetches all quotas in a preset, returns dict of quotas and item info
    def fetchPresetList(self, guild_id, preset_name):
        # Get quota string
        self.cur.execute("""
            SELECT quota_string FROM presets WHERE name = ? AND guild_id = ?
            """, (preset_name, guild_id)
        )
        res = self.cur.fetchone()
        # Parse quota string
        quotas = {}
        for q in res[0].split(','):
            display_name, quantity = q.strip().split(':')
            quotas[display_name] = int(quantity)
        items = self.getItems(quotas.keys())
        for item in items:
            item.crates = quotas[item.display_name]
        
        return items

    # Fetches the requirements to meet quotas for a stockpile
    def getStatus(self, guild_id, stock_id, show_locked):
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
        stock_info = {
            'name': stock_name,
            'last_update': last_update,
            'town': stock_town,
            'type': stock_struct
        }

        # Get item quotas and inventories
        self.cur.execute("""
            SELECT item.id, item.display_name, quota.amount, inv.crates, inv.non_crates
            FROM quotas quota
            JOIN items item ON quota.item_id = item.id
            LEFT JOIN inventory inv ON quota.item_id = inv.item_id AND quota.stock_id = inv.stock_id
            WHERE quota.stock_id = ?
            """, (stock_id,)
        )
        result = self.cur.fetchall()
        if not result:
            return {}
        
        # Get locked items
        self.cur.execute("SELECT item_id FROM locked_items WHERE guild_id = ?", (guild_id,))
        locked_ids = self.cur.fetchall()
        if locked_ids:
            locked_ids = [id[0] for id in locked_ids]
        if not show_locked:
            items = self.getItems([r[1] for r in result if r[0] not in locked_ids])
        else:
            items = self.getItems([r[1] for r in result])
        quotas = {}
        required_items = []
        required_amounts = {}
        for item, r in zip(items, result):
            quotas[item.display_name] = r[2]
            if r[3] is not None:
                item.crates = r[3]
            if r[4] is not None:
                item.non_crates = r[4]
            if item.category in ['Vehicles', 'Structures']:
                quantity = item.getTotal()
            else:
                quantity = item.crates
            required_amount = r[2] - quantity
            if required_amount > 0:
                required_items.append(item)
                required_amounts[item.display_name] = required_amount
        
        return stock_info, required_items, quotas, required_amounts

    # Updates locked_items table. Adds rows for newly locked items, deletes rows for unlocked items
    # Rows are set with guild_id to maintain tech confidentiality
    def setTechLock(self, guild_id, item_list, is_locked):
        # Parse item list and get ids
        display_names = [name.strip() for name in item_list.split(',')]
        items = self.getItems(display_names)
        for item in items:
            if is_locked:
                self.cur.execute("""
                    INSERT INTO locked_items (item_id, guild_id)
                    VALUES (?, ?)
                    ON CONFLICT (item_id, guild_id) DO NOTHING
                    """, (item.id, guild_id)
                )
            elif is_locked == False:
                self.cur.execute(
                    "DELETE FROM locked_items WHERE item_id = ? AND guild_id = ?", 
                    (item.id, guild_id)
                )
        self.conn.commit()

    # Fetches all locked items. Returns dict of display_name: item info
    def fetchLockedItems(self, guild_id):
        self.cur.execute("""
            SELECT item.display_name
            FROM locked_items lock
            JOIN items item
            ON lock.item_id = item.id
            WHERE lock.guild_id = ?
            """, (guild_id,)
        )
        result = self.cur.fetchall()
        if result:
            return self.getItems([r[0] for r in result])
        else:
            return []
