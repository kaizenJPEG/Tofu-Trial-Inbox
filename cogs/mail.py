import discord
import psycopg2
import Paginator
from discord.ext import commands
from config import dbConfig

MY_COLOR = discord.Color.from_rgb(0, 166, 255)

async def db_connect():
    params = dbConfig()
    conn = psycopg2.connect(**params)
    cur = conn.cursor()

    return conn, cur

async def db_get_user_mail(user_id):
    conn, cur = await db_connect()
    cur.execute("SELECT * FROM mail WHERE userid = %s ORDER BY isread ASC, timecreated DESC", (str(user_id),))
    result = cur.fetchall()
    conn.close()

    return result

async def db_get_selected_mail(headline, user_id):
    conn, cur = await db_connect()
    cur.execute("SELECT * FROM mail WHERE headline = %s AND userid = %s", (headline, str(user_id)))
    result = cur.fetchone()
    conn.close()

    return result

async def db_get_mail_claimed_state(headline, user_id):
    conn, cur = await db_connect()
    cur.execute("SELECT isclaimed FROM mail WHERE headline = %s AND userid = %s", (headline, str(user_id)))
    result = cur.fetchone()[0]
    conn.close()

    return result
    
async def db_update_user_mail_state(headline, user_id):
    conn, cur = await db_connect()
    cur.execute("UPDATE mail SET isread = TRUE WHERE headline = %s AND userid = %s", (headline, str(user_id)))
    conn.commit()
    conn.close()

async def db_update_user_claimed_state(headline, user_id):
    conn, cur = await db_connect()
    cur.execute("UPDATE mail SET isclaimed = TRUE WHERE headline = %s AND userid = %s", (headline, str(user_id)))
    conn.commit()
    conn.close()

async def get_inbox_params(ctx):
    user_mail = await db_get_user_mail(ctx.author.id)

    # Set initial variables for loop
    embed_list = []
    all_mail = []
    mail_count = 0
    mail_max = 0
    mail_str = ""
    mail_list = []
    footer_low = 1

    mail_embed = discord.Embed(
        title=f"{ctx.author.name}'s Inbox",
        color= MY_COLOR
    )

    mail_embed.set_thumbnail(url=(ctx.author.avatar.url if len(ctx.author.avatar.url) > 2 else None))

    # Fixed loop
    for mail in user_mail:
        mail_count += 1
        mail_max += 1
        mail_head = mail[0]
        mail_body = mail[1]
        mail_time = int(mail[2].timestamp())
        mail_is_read = mail[3]
        mail_userid = mail[4]

        # Sets the emoji to indiciate whether or not user has read this mail yet
        mail_emoji = "🌟" if not mail_is_read else ""

        ### 4. each mail has dynamic timestamp, a headline, and an emoji to indicate if new if has been read then emoji removed
        mail_str += f"{mail_count}. {mail_head} | <t:{mail_time}:R> | {mail_emoji}\n"
        
        mail_list.append(mail)

        if mail_max == 5:
            mail_embed.add_field(name="Select a message", value=f"{mail_str}")
            mail_embed.set_footer(text=f"Showing mail {footer_low}-{mail_count} of {len(user_mail)}")
            embed_list.append(mail_embed)
            mail_str = ""
            mail_max = 0
            footer_low = mail_count + 1

            all_mail.append(mail_list)
            mail_list = []

            mail_embed = discord.Embed(
                title=f"{ctx.author.name}'s Inbox",
                color= MY_COLOR
            )

            mail_embed.set_thumbnail(url=(ctx.author.avatar.url if len(ctx.author.avatar.url) > 2 else None))

        elif mail_count == len(user_mail):
            mail_embed.add_field(name="Select a message", value=f"{mail_str}")
            mail_embed.set_footer(text=f"Showing mail {footer_low}-{mail_count} of {len(user_mail)}")
            embed_list.append(mail_embed)
            mail_str = ""

            all_mail.append(mail_list)
            mail_list = []

            mail_embed = discord.Embed(
                title=f"{ctx.author.name}'s Inbox",
                color= MY_COLOR
            )

            mail_embed.set_thumbnail(url=(ctx.author.avatar.url if len(ctx.author.avatar.url) > 2 else None))

    return embed_list, all_mail
    
# Overrides Paginator Class to include Mail Dropdown
class MyPaginator(Paginator.Simple):
    def __init__(self):
        super().__init__()
        # Initialize "Pages" of Mail
        self.all_mail = None
        self.embed_list = None
        self.dropdownMsg = None
        self.currentDropdown = None
        self.inbox_instance = None

    async def start(self, ctx: discord.Interaction|commands.Context, pages: list[discord.Embed]):
        if isinstance(ctx, discord.Interaction):
            ctx = await commands.Context.from_interaction(ctx)
            
        self.pages = pages
        self.total_page_count = len(pages)
        self.ctx = ctx
        self.current_page = self.InitialPage

        self.PreviousButton.callback = self.previous_button_callback
        self.NextButton.callback = self.next_button_callback

        self.page_counter = Paginator.SimplePaginatorPageCounter(style=self.PageCounterStyle,
                                                       TotalPages=self.total_page_count,
                                                       InitialPage=self.InitialPage)

        embed_list, all_mail = await get_inbox_params(ctx)
        self.embed_list = embed_list
        self.all_mail = all_mail

        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)
        self.message = await ctx.send(embed=self.pages[self.InitialPage], view=self)

        # Add Dropdown to View
        self.dropdownMsg = self.message
        self.currentDropdown = Dropdown(self.all_mail[0], self.dropdownMsg, self, self.all_mail, self.embed_list, ctx=ctx)
        self.add_item(self.currentDropdown)
        await self.message.edit(embed=self.pages[self.current_page], view=self)

    async def resume(self, message):
        await message.edit(embed=self.inbox_instance.pages[self.inbox_instance.current_page], view=self.inbox_instance)

    async def previous(self):
        if self.current_page == 0:
            self.current_page = self.total_page_count - 1
        else:
            self.current_page -= 1

        self.page_counter.label = f"{self.current_page + 1}/{self.total_page_count}"

        # Remove old Dropdown "page" from view, add new one
        self.remove_item(self.currentDropdown)
        self.currentDropdown = Dropdown(self.all_mail[self.current_page], self.dropdownMsg, self, self.all_mail, self.embed_list, ctx=self.ctx)
        self.add_item(self.currentDropdown)

        await self.message.edit(embed=self.pages[self.current_page], view=self)

    async def next(self):
        if self.current_page == self.total_page_count - 1:
            self.current_page = 0
        else:
            self.current_page += 1

        self.page_counter.label = f"{self.current_page + 1}/{self.total_page_count}"

        # Remove old Dropdown "page" from view, add new one
        self.remove_item(self.currentDropdown)
        self.currentDropdown = Dropdown(self.all_mail[self.current_page], self.dropdownMsg, self, self.all_mail, self.embed_list, ctx=self.ctx)
        self.add_item(self.currentDropdown)

        await self.message.edit(embed=self.pages[self.current_page], view=self)

    # Add timeout method - disable buttons/show message saying to re-do command
    async def on_timeout(self):
        ...

### 6. select menu at bottom for mail on the page
class Dropdown(discord.ui.Select):
    def __init__(self, mail_list, message, inbox_instance, all_mail = None, embed_list = None, ctx = None):
        options = [discord.SelectOption(label=f"{mail[0]} {'🌟' if not mail[3] else ''}") for mail in mail_list]

        super().__init__(placeholder="Select which message you'd like to read.", min_values=1, max_values=1, options=options)
        self.mail_list = mail_list
        self.message = message
        self.inbox_instance = inbox_instance
        self.all_mail = all_mail
        self.embed_list = embed_list
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inbox_instance.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return

        ### 7. choose mail, goes to that mail, who has a header and body, and if has rewards in rewards section then can claim them
        selected_headline = self.values[0].replace(" 🌟", "")

        # Edit current message to display selected Mail
        selected_mail = await db_get_selected_mail(selected_headline, interaction.user.id)

        mail_head = selected_mail[0]
        mail_body = selected_mail[1]
        mail_time = int(selected_mail[2].timestamp())
        mail_is_read = selected_mail[3]
        mail_userid = selected_mail[4]
        mail_reward = selected_mail[5]
        mail_claimed = selected_mail[6]

        mail_embed = discord.Embed(
            title="Selected Message",
            color= MY_COLOR
        )

        mail_embed.add_field(name=mail_head, value=mail_body, inline=False)
        mail_embed.add_field(name="Message Sent", value=f"<t:{mail_time}:R>", inline=True)

        if mail_reward is None:
            reward_status = False
            reward_str = "❌ None"
        
        elif mail_reward != None:
            reward_status = True
            if mail_claimed:
                reward_str = f"✅ {mail_reward}"
                mail_embed.color = discord.Color.green()
            else:
                reward_str = f"🎁 {mail_reward}"
                mail_embed.color = discord.Color.gold()
        
        mail_embed.add_field(name="Reward", value=reward_str)
        mail_embed.set_thumbnail(url=(interaction.user.avatar.url if len(interaction.user.avatar.url) > 2 else None))

        ### 8. button to return to inbox
        view = MailButtons(self.message, self.all_mail, self.embed_list, mail_claimed, selected_mail, mail_embed, reward_status, self.inbox_instance, self.ctx)
        
        # Edit db to show that user has read message
        await db_update_user_mail_state(selected_headline, interaction.user.id)

        await self.message.edit(embed=mail_embed, view=view)
        await interaction.response.defer()

class MailButtons(discord.ui.View):
    def __init__(self, message, all_mail, embed_list, claim_status, selected_mail, mail_embed, reward_status, inbox_instance, ctx):
        super().__init__()
        self.message = message
        self.all_mail = all_mail
        self.embed_list = embed_list
        self.claim_status = claim_status
        self.selected_mail = selected_mail
        self.mail_embed = mail_embed
        self.reward_status = reward_status
        self.inbox_instance = inbox_instance
        self.ctx = ctx

        if reward_status:
            if claim_status:
                self.children[-1].label = "Reward Claimed"
                self.children[-1].emoji = "✅"
                self.children[-1].disabled = True
        else:
            self.remove_item(self.children[-1])

    @discord.ui.button(label="Return to Inbox", style=discord.ButtonStyle.primary, emoji="📥")
    async def returnToInbox_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.inbox_instance.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return
        
        inbox_view = MyPaginator()
        inbox_view.inbox_instance = self.inbox_instance

        await inbox_view.resume(self.inbox_instance.message)
        await interaction.response.defer()

    @discord.ui.button(label="Claim Reward!", style=discord.ButtonStyle.success, emoji="🎁")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.inbox_instance.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return

        claim_check = await db_get_mail_claimed_state(self.selected_mail[0], self.selected_mail[4])

        if claim_check:
            self.children[-1].label = "Reward Already Claimed!"
            self.children[-1].emoji = "✅"
            self.children[-1].disabled = True
            self.mail_embed.color = discord.Color.green()

            await self.message.edit(embed=self.mail_embed, view=self)
            await interaction.response.defer()

        else:
            await db_update_user_claimed_state(self.selected_mail[0], self.selected_mail[4])

            self.children[-1].label = "Reward Claimed"
            self.children[-1].emoji = "✅"
            self.children[-1].disabled = True
            self.mail_embed.color = discord.Color.green()
            
            await self.message.edit(embed=self.mail_embed, view=self)
            await interaction.response.defer()

class Mail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ### 1. Use t!mail command
    @commands.command(help="Check your inbox.")
    async def mail(self, ctx):
        ## SAMPLE MAIL TABLE
        """
        Headline         | Body         | TimeCreated                   | isRead | userID             | Reward     | isClaimed
        ----------------------------------------------------------------------------------------------------------------------
        sample headline1 | sample body1 | 2023-05-28 14:46:35.066153-04 | False  | 144176650958012417 |            | False
        sample headline1 | sample body1 | 2023-05-28 14:46:35.066153-04 | True   | 105705940581376000 |            | False
        sample headline1 | sample body1 | 2023-05-28 14:46:35.066153-04 | False  | 711212342792159322 |            | False
        sample headline1 | sample body1 | 2023-05-28 14:46:35.066153-04 | True   | 372825096664121346 |            | False
        sample headline2 | sample body2 | 2023-05-28 10:30:51.690954-04 | False  | 144176650958012417 | 50 points  | False
        sample headline2 | sample body2 | 2023-05-28 10:30:51.690954-04 | True   | 105705940581376000 | 50 points  | True
        sample headline2 | sample body2 | 2023-05-28 10:30:51.690954-04 | False  | 711212342792159322 | 50 points  | False
        sample headline2 | sample body2 | 2023-05-28 10:30:51.690954-04 | True   | 372825096664121346 | 50 points  | True

        .....

        sample headline16 | sample body16 | 2023-05-27 17:00:46.56354-04 | False  | 144176650958012417 |          | False
        sample headline16 | sample body16 | 2023-05-27 17:00:46.56354-04 | True   | 105705940581376000 |          | False
        sample headline16 | sample body16 | 2023-05-27 17:00:46.56354-04 | False  | 711212342792159322 |          | False
        sample headline16 | sample body16 | 2023-05-27 17:00:46.56354-04 | True   | 372825096664121346 |          | False
        """
        
        embed_list, all_mail = await get_inbox_params(ctx)

        ### 5. shows pages at bottom, can go to next pages with buttons
        await MyPaginator().start(ctx, embed_list)

async def setup(bot):
    await bot.add_cog(Mail(bot))

"""
This software includes code from the [soosBot]
Copyright (c) 2021 soosBot

Original code licensed under the MIT License:
https://github.com/soosBot-com/Pagination
"""