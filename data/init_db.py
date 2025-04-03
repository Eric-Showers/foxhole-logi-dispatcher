import sqlite3
import json
import csv

from foxapi import FoxAPI

CATALOG_PATH = './infantry-59/'
DB_PATH = "test.db"
api = FoxAPI(shard='1')

# Taken from https://github.com/clapfoot/warapi?tab=readme-ov-file#map-icons
ICON_TYPES = {
    17: 'Refinery', 
    33: 'Storage Depot', 
    34: 'Factory', 
    51: 'Mass Production Factory', 
    52: 'Seaport'
}

# Fetches town & structure data from the Foxhole API and writes to CSV files
def getTownsAndStructures():
    hexes = api.get_maps_sync()
    major_labels = {}

    for hexname in hexes:
        hex_static = api.get_static_sync(hexname)
        hex_dynamic = api.get_dynamic_sync(hexname)

        # Get map labels
        hex_labels = {}
        if len(hex_static['mapTextItems']) == 0:
            print(f'No labels found for {hexname}')
        for location in hex_static['mapTextItems']:
            if location['mapMarkerType'] == 'Major':
                hex_labels[location['text']] = {
                    'structures':[],'x':location['x'],'y':location['y']
                }

        # Find relevant structures and attach them to major labels
        for icon in hex_dynamic['mapItems']:
            if icon['iconType'] in ICON_TYPES.keys():
                closest_town = ''
                shortest_dist = float('inf')
                # Find structure's town
                for k,v in hex_labels.items():
                    dist_to_town = abs(v['x']-icon['x']) + abs(v['y']-icon['y'])
                    if dist_to_town < shortest_dist:
                        closest_town = k
                        shortest_dist = dist_to_town
                hex_labels[closest_town]['structures'].append(
                    {'type':ICON_TYPES[icon['iconType']],'x':icon['x'],'y':icon['y']}
                )
        major_labels.update(hex_labels)

    # Write csv files
    towns_headers = ['name','x','y']
    with open(CATALOG_PATH+'towns.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(towns_headers)
        for k, v in major_labels.items():
            if v['structures'] == []:
                continue
            row = [k,v['x'],v['y']]
            writer.writerow(row)
    print('Towns CSV created')

    structures_headers = ['town_name','type','x','y']
    with open(CATALOG_PATH+'structures.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(structures_headers)
        for k,v in major_labels.items():
            for struct in v['structures']:
                row = [k,struct['type'],struct['x'],struct['y']]
                writer.writerow(row)
    print('Structures CSV created')


# Parses item catalog json and writes CSV file
# Catalog json copied from https://github.com/GICodeWarrior/fir
# ^^ MUST BE UPDATED MANUALLY ^^
def getItems():
    with open(CATALOG_PATH+'catalog.json', 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    headers = [
        'code_name', 'display_name', 'category', 'per_crate', 'factory_queue',
        'mpf_queue', 'faction', 'reserve_max_quantity',
        'shippable_type', 'ingredients', 'description'
    ]
    with open(CATALOG_PATH+'items.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for item in catalog:
            category = ''
            if 'ItemCategory' in item:
                category = item['ItemCategory']
                per_crate = item.get('ItemDynamicData', {}).get('QuantityPerCrate', '')
            elif 'VehicleProfileType' in item:
                # Per crate quantities not provided in catalog.json
                # Not all vehicles are crate-able, but this will have to do
                category = item['VehicleProfileType']
                per_crate = 3
            elif 'ProductionCategories' in item and item['ProductionCategories']['MassProductionFactory'] == 'EFactoryQueueType::Structures':
                category = 'Structures'
                per_crate = 3
            else:
                category = ''
                per_crate = ''

            ingredients = item.get('ItemDynamicData', {}).get('CostPerCrate', [])
            if ingredients != []:
                ingredients = json.dumps(ingredients, separators=(',', ':'))
            else:
                ingredients = ''

            row = [
                item.get('CodeName', ''),
                item.get('DisplayName', ''),
                category,
                per_crate,
                item.get('ProductionCategories', {}).get('Factory', ''),
                item.get('ProductionCategories', {}).get('MassProductionFactory', ''),
                item.get('FactionVariant', ''),
                item.get('ItemProfileData', {}).get('ReserveStockpileMaxQuantity', ''),
                item.get('ShippableInfo', ''),
                ingredients,
                item.get('Description', '')
            ]
            writer.writerow(row)

    print('Items CSV created')        


def init_db_tables(db_path):
    """Initialize the database and create tables if they do not exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS guilds (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    );
                         
    CREATE TABLE IF NOT EXISTS role_access (
        guild_id BIGINT NOT NULL,
        role_id BIGINT NOT NULL,
        access_level INT NOT NULL CHECK (access_level IN (1, 2)),
        PRIMARY KEY (guild_id, role_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS towns (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );
                  
    CREATE TABLE IF NOT EXISTS structures (
        id INTEGER PRIMARY KEY,
        town_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        FOREIGN KEY (town_id) REFERENCES towns(id)
    );

    CREATE TABLE IF NOT EXISTS stockpiles (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        guild_id INTEGER NOT NULL,
        structure_id INTEGER NOT NULL,
        last_update INTEGER,
        FOREIGN KEY (guild_id) REFERENCES guilds(id),
        FOREIGN KEY (structure_id) REFERENCES structures(id)
    );

    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        code_name TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        category TEXT,
        per_crate INTEGER,
        factory_queue TEXT,
        mpf_queue TEXT,
        faction TEXT,
        reserve_max_quantity INTEGER,
        shippable_type TEXT,
        ingredients TEXT,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS inventory (
        item_id INTEGER NOT NULL,
        stock_id INTEGER NOT NULL,
        crates INTEGER NOT NULL DEFAULT 0,
        non_crates INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (item_id, stock_id),
        FOREIGN KEY (item_id) REFERENCES items(id),
        FOREIGN KEY (stock_id) REFERENCES stockpiles(id)
    );

    CREATE TABLE IF NOT EXISTS quotas (
        stock_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        PRIMARY KEY (stock_id, item_id),
        FOREIGN KEY (stock_id) REFERENCES stockpiles(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    );

    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY,
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        est_length INTEGER NOT NULL,
        UNIQUE (from_id, to_id),
        FOREIGN KEY (from_id) REFERENCES towns(id),
        FOREIGN KEY (to_id) REFERENCES towns(id)
    );
                         
    CREATE TABLE IF NOT EXISTS presets (
        name TEXT NOT NULL,
        quota_string TEXT NOT NULL,
        guild_id INTEGER NOT NULL,
        PRIMARY KEY (name, guild_id),
        FOREIGN KEY (guild_id) REFERENCES guilds(id)
    );
    """)

    conn.commit()
    conn.close()
    print("Database tables created.")

def load_csv_to_db(db_path, catalog_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(CATALOG_PATH+"towns.csv", newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        cursor.executemany("INSERT INTO towns (name) VALUES (?)", ((row[0],) for row in reader))

    with open(CATALOG_PATH+"structures.csv", newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            town_name, structure_type = row[0], row[1]

            # Get town_id
            cursor.execute("SELECT id FROM towns WHERE name = ?", (town_name,))
            town_id = cursor.fetchone()
            if town_id:
                cursor.execute(
                    "INSERT INTO structures (town_id, type) VALUES (?, ?)",
                    (town_id[0], structure_type)
                )
            else:
                print(f"Warning: Town '{town_name}' not found in towns table.")

    with open(CATALOG_PATH+"items.csv", newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        cursor.executemany("""
            INSERT INTO items (code_name, display_name, category, per_crate, 
                           factory_queue, mpf_queue, faction, reserve_max_quantity, 
                           shippable_type, ingredients, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
            reader
        )

    conn.commit()
    conn.close()
    print("CSV data loaded successfully.")

if __name__ == "__main__":
    getTownsAndStructures()
    getItems()
    init_db_tables(DB_PATH)
    load_csv_to_db(DB_PATH, CATALOG_PATH)
    print("Database initialized")
