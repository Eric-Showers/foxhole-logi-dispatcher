import discord
from discord.ext import commands

from data.db_io import DbHandler
from data.objects.Item import Item

ITEMS_PER_PAGE = 10

class ItemBrowserView(discord.ui.View):
    def __init__(self, db: DbHandler, faction: str | None, category: str, 
                 items: list[str], page: int = 0):
        super().__init__(timeout=120)
        self.db = db
        self.faction = faction
        self.category = category
        self.items = items
        self.page = page
        self.max_page = (len(items) - 1) // ITEMS_PER_PAGE

        self.update_buttons()

    def get_page_items(self):
        start = self.page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        return self.items[start:end]

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            self.add_item(PrevButton())
        if self.page < self.max_page:
            self.add_item(NextButton())
        self.add_item(CategoriesButton(self.db, self.faction))

    async def update_message(self, inter: discord.Interaction):
        self.update_buttons()
        embed = discord.Embed(
            title=f"{self.category} Items (Page {self.page + 1}/{self.max_page + 1})"
        )
        for item in self.get_page_items():
            embed.add_field(name=item.display_name, value=item.description, inline=False)

        await inter.response.edit_message(embed=embed, view=self)


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Previous', style=discord.ButtonStyle.primary)

    async def callback(self, inter: discord.Interaction):
        view: ItemBrowserView = self.view
        view.page -= 1
        await view.update_message(inter)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label='Next', style=discord.ButtonStyle.primary)

    async def callback(self, inter: discord.Interaction):
        view: ItemBrowserView = self.view
        view.page += 1
        await view.update_message(inter)


class CategoriesButton(discord.ui.Button):
    def __init__(self, db: DbHandler, faction: str | None):
        super().__init__(label='Categories', style=discord.ButtonStyle.secondary)
        self.db = db
        self.faction = faction

    async def callback(self, inter: discord.Interaction):
        await inter.response.edit_message(
            content="Select a category:",
            embed=None,
            view=CategoryDropdownView(self.db, self.faction)
        )

class FactionButton(discord.ui.Button):
    def __init__(self, db: DbHandler):
        super().__init__(label='Factions', style=discord.ButtonStyle.secondary)
        self.db = db

    async def callback(self, inter: discord.Interaction):
        await inter.response.edit_message(
        content="Select a faction to begin browsing items:",
        view=FactionSelectView(self.db)
    )


# View that displays a menu to browse through Foxhole items
class CategoryDropdown(discord.ui.Select):
    def __init__(self, db: DbHandler, faction: str | None):
        self.db = db
        self.faction = faction
        options = [
            discord.SelectOption(label=category) 
            for category in db.getCategories()
        ]
        super().__init__(placeholder='Choose an item category', options=options)

    async def callback(self, inter: discord.Interaction):
        category = self.values[0]
        items = self.db.getCategoryItems(category, self.faction)
        # Sort items alphabetically
        items.sort(key=lambda x : x.display_name)
        view = ItemBrowserView(self.db, self.faction, category, items)
        embed = discord.Embed(title=f"{category} Items (Page 1/{view.max_page + 1})")
        for item in view.get_page_items():
            embed.add_field(name=item.display_name, value=item.description, inline=False)

        await inter.response.edit_message(embed=embed, view=view)


class CategoryDropdownView(discord.ui.View):
    def __init__(self, db: DbHandler, faction: str | None):
        super().__init__()
        self.db = db
        self.faction = faction
        self.add_item(CategoryDropdown(self.db, self.faction))
        self.add_item(FactionButton(self.db))


class FactionSelectView(discord.ui.View):
    def __init__(self, db: DbHandler):
        super().__init__(timeout=60)
        self.db = db

    @discord.ui.button(label="Warden", style=discord.ButtonStyle.primary)
    async def warden(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.edit_message(
            content="Select a category:",
            view=CategoryDropdownView(self.db, faction="Wardens")
        )

    @discord.ui.button(label="Colonial", style=discord.ButtonStyle.success)
    async def colonial(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.edit_message(
            content="Select a category:",
            view=CategoryDropdownView(self.db, faction="Colonials")
        )

    @discord.ui.button(label="Both", style=discord.ButtonStyle.secondary)
    async def both(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.edit_message(
            content="Select a category:",
            view=CategoryDropdownView(self.db, faction=None)
        )