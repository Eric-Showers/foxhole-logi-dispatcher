class Item():
    def __init__(self, db_row):
        self.id = db_row[0]
        self.code_name = db_row[1]
        self.display_name = db_row[2]
        self.category = db_row[3]
        self.per_crate = db_row[4]
        self.factory_queue = db_row[5]
        self.mpf_queue = db_row[6]
        self.faction = db_row[7]
        self.reserve_max_quantity = db_row[8]
        self.shippable_type = db_row[9]
        self.ingredients = db_row[10]
        self.description = db_row[11]
        self.crates = 0
        self.non_crates = 0

    def getTotal(self):
        return (self.crates * self.per_crate) + self.non_crates