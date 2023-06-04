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

async def db_get_user_mail(user_id, filter = "All"):
    conn, cur = await db_connect()

    if filter == "All":
        cur.execute("SELECT * FROM mail WHERE userid = %s ORDER BY isread ASC, timecreated DESC", (str(user_id),))
        result = cur.fetchall()

    elif filter == "Read":
        cur.execute("SELECT * FROM mail WHERE userid = %s AND isread = TRUE ORDER BY timecreated DESC", (str(user_id),))
        result = cur.fetchall()
    
    elif filter == "Unread":
        cur.execute("SELECT * FROM mail WHERE userid = %s AND isread = FALSE ORDER BY timecreated DESC", (str(user_id),))
        result = cur.fetchall()
    
    elif filter == "Unclaimed":
        cur.execute("SELECT * FROM mail WHERE userid = %s AND reward IS NOT null AND isclaimed = FALSE ORDER BY timecreated DESC", (str(user_id),))
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

async def get_inbox_params(ctx, filter="All"):
    user_mail = await db_get_user_mail(ctx.author.id, filter)

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

    if len(user_mail) == 0:
        mail_embed.description = "There are no messages to display! Choose a different filter."
        mail_embed.set_footer(text=f"Showing mail 0-0 of 0")
        embed_list.append(mail_embed)
        all_mail.append([None])

    else:
        # Fixed loop
        for mail in user_mail:
            mail_count += 1
            mail_max += 1
            mail_head = mail[0]
            mail_time = int(mail[2].timestamp())
            mail_is_read = mail[3]

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
    
class MyPaginator(Paginator.Simple):
    def __init__(self):
        super().__init__(timeout=None)
        self.current_drop_down = None
        self.current_filter = "All"

        self.top_of_inbox_button = discord.ui.Button(emoji="⏮️")
        self.bottom_of_inbox_button = discord.ui.Button(emoji="⏭️")

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

        embed_list, all_mail = await get_inbox_params(self.ctx, self.current_filter)
        self.all_mail = all_mail
        self.mail_list = all_mail[self.current_page]

        self.add_item(self.top_of_inbox_button)
        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)
        self.add_item(self.bottom_of_inbox_button)
        self.message = await ctx.send(embed=self.pages[self.InitialPage], view=self)

        if self.mail_list[0] != None:
            self.current_drop_down = Dropdown(self)
            self.add_item(self.current_drop_down)
        self.add_item(MailFilterDropdown(self))
        await self.message.edit(embed=self.pages[self.current_page], view=self)

    async def resume(self, previous_state):
        self.current_filter = previous_state.current_filter
        embed_list, all_mail = await get_inbox_params(previous_state.ctx, previous_state.current_filter)
        self.current_page = previous_state.current_page
        self.embed_list = embed_list
        self.all_mail = all_mail
        self.mail_list = all_mail[self.current_page]
        self.message = previous_state.message
        self.pages = embed_list
        self.total_page_count = len(self.pages)
        self.ctx = previous_state.ctx
        self.PreviousButton.callback = self.previous_button_callback
        self.NextButton.callback = self.next_button_callback
        self.page_counter = Paginator.SimplePaginatorPageCounter(style=previous_state.PageCounterStyle,
                                                       TotalPages=previous_state.total_page_count,
                                                       InitialPage=previous_state.current_page)
        self.add_item(self.top_of_inbox_button)
        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)
        self.add_item(self.bottom_of_inbox_button)

        if self.mail_list[0] != None:
            self.current_drop_down = Dropdown(self)
            self.add_item(self.current_drop_down)

        self.add_item(MailFilterDropdown(self))
        await previous_state.message.edit(embed=self.pages[self.current_page], view=self)

    async def filter(self, previous_state, selected_filter):
        self.current_filter = selected_filter
        embed_list, all_mail = await get_inbox_params(previous_state.ctx, selected_filter)
        self.total_page_count = len(embed_list)
        self.ctx = previous_state.ctx
        self.current_page = 0
        self.PreviousButton.callback = self.previous_button_callback
        self.NextButton.callback = self.next_button_callback
        self.page_counter = Paginator.SimplePaginatorPageCounter(style=previous_state.PageCounterStyle,
                                                       TotalPages=self.total_page_count,
                                                       InitialPage=0)
        self.embed_list = embed_list
        self.all_mail = all_mail
        self.mail_list = all_mail[0]
        self.message = previous_state.message
        self.pages = embed_list

        self.add_item(self.top_of_inbox_button)
        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)
        self.add_item(self.bottom_of_inbox_button)

        if self.mail_list[0] != None:
            self.current_drop_down = Dropdown(self)
            self.add_item(self.current_drop_down)

        self.add_item(MailFilterDropdown(self))

        await previous_state.message.edit(embed=self.pages[0], view=self)

    async def next(self):
        if self.current_page == self.total_page_count - 1:
            self.current_page = 0
        else:
            self.current_page += 1

        self.page_counter.label = f"{self.current_page + 1}/{self.total_page_count}"

        # Remove old Dropdown "page" from view, add new one
        self.mail_list = self.all_mail[self.current_page]
        self.remove_item(self.current_drop_down)
        self.current_drop_down = Dropdown(self)
        self.add_item(self.current_drop_down)

        await self.message.edit(embed=self.pages[self.current_page], view=self)

    async def previous(self):
        if self.current_page == 0:
            self.current_page = self.total_page_count - 1
        else:
            self.current_page -= 1

        self.page_counter.label = f"{self.current_page + 1}/{self.total_page_count}"

        # Remove old Dropdown "page" from view, add new one
        self.mail_list = self.all_mail[self.current_page]
        self.remove_item(self.current_drop_down)
        self.current_drop_down = Dropdown(self)
        self.add_item(self.current_drop_down)

        await self.message.edit(embed=self.pages[self.current_page], view=self)

class Dropdown(discord.ui.Select):
    def __init__(self, current_inbox_state):
        options = [discord.SelectOption(label=f"{mail[0]} {'🌟' if not mail[3] else ''}") for mail in current_inbox_state.mail_list]
        super().__init__(placeholder="Select which message you'd like to read.", min_values=1, max_values=1, options=options)
        self.current_inbox_state = current_inbox_state

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.current_inbox_state.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return

        ### 7. choose mail, goes to that mail, who has a header and body, and if has rewards in rewards section then can claim them
        selected_headline = self.values[0].replace(" 🌟", "")

        # Edit current message to display selected Mail
        selected_mail = await db_get_selected_mail(selected_headline, interaction.user.id)

        mail_head = selected_mail[0]
        mail_body = selected_mail[1]
        mail_time = int(selected_mail[2].timestamp())
        mail_reward = selected_mail[5]
        mail_claimed = selected_mail[6]

        mail_embed = discord.Embed(
            title="Selected Message",
            color= MY_COLOR
        )

        mail_embed.add_field(name=mail_head, value=mail_body, inline=False)
        mail_embed.add_field(name="Message Sent", value=f"<t:{mail_time}:R>", inline=True)

        if mail_reward is None:
            reward_str = "❌ None"
        
        elif mail_reward != None:
            if mail_claimed:
                reward_str = f"✅ {mail_reward}"
                mail_embed.color = discord.Color.green()
            else:
                reward_str = f"🎁 {mail_reward}"
                mail_embed.color = discord.Color.gold()
        
        mail_embed.add_field(name="Reward", value=reward_str)
        mail_embed.set_thumbnail(url=(interaction.user.avatar.url if len(interaction.user.avatar.url) > 2 else None))
      
        # Edit db to show that user has read message
        await db_update_user_mail_state(selected_headline, interaction.user.id)
        view = MailButtons(self.current_inbox_state, selected_mail, mail_embed)

        await self.current_inbox_state.message.edit(embed=mail_embed, view=view)
        await interaction.response.defer()

class MailButtons(discord.ui.View):
    def __init__(self, prev_inbox_state, selected_mail, mail_embed):
        super().__init__()
        self.prev_inbox_state = prev_inbox_state
        self.selected_mail = selected_mail
        self.mail_embed = mail_embed

        if selected_mail[5]:
            if selected_mail[6]:
                self.children[-1].label = "Reward Claimed"
                self.children[-1].emoji = "✅"
                self.children[-1].disabled = True
        else:
            self.remove_item(self.children[-1])

    @discord.ui.button(label="Return to Inbox", style=discord.ButtonStyle.primary, emoji="📥")
    async def returnToInbox_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.prev_inbox_state.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return
        
        await MyPaginator().resume(self.prev_inbox_state)
        await interaction.response.defer()
            
    @discord.ui.button(label="Claim Reward!", style=discord.ButtonStyle.success, emoji="🎁")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.prev_inbox_state.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return

        claim_check = await db_get_mail_claimed_state(self.selected_mail[0], self.selected_mail[4])

        if claim_check:
            self.children[-1].label = "Reward Already Claimed!"
            self.children[-1].emoji = "✅"
            self.children[-1].disabled = True
            self.mail_embed.color = discord.Color.green()

            await self.prev_inbox_state.message.edit(embed=self.mail_embed, view=self)
            await interaction.response.defer()

        else:
            await db_update_user_claimed_state(self.selected_mail[0], self.selected_mail[4])

            self.children[-1].label = "Reward Claimed"
            self.children[-1].emoji = "✅"
            self.children[-1].disabled = True
            self.mail_embed.color = discord.Color.green()
            
            await self.prev_inbox_state.message.edit(embed=self.mail_embed, view=self)
            await interaction.response.defer()

class MailFilterDropdown(discord.ui.Select):
    def __init__(self, current_inbox_state):
        options = [
            discord.SelectOption(label="All (default)", description="Show all messages in your inbox", emoji="📥", value="All"),
            discord.SelectOption(label="Read", description="Show all read messages", emoji="📖"),
            discord.SelectOption(label="Unread", description="Show all unread messages", emoji="🌟"),
            discord.SelectOption(label="Unclaimed", description="Show all unclaimed messages", emoji="🎁")
        ]

        super().__init__(placeholder="Filter your inbox by:", min_values=1, max_values=1, options=options)
        self.current_inbox_state = current_inbox_state
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.current_inbox_state.ctx.author:
            await interaction.response.send_message(content="That's not your inbox!", ephemeral=True)
            return
        
        selected_filter = self.values[0]
        await MyPaginator().filter(self.current_inbox_state, selected_filter)
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
        await MyPaginator().start(ctx, embed_list)

async def setup(bot):
    await bot.add_cog(Mail(bot))

"""
This software includes code from the [soosBot]
Copyright (c) 2021 soosBot

Original code licensed under the MIT License:
https://github.com/soosBot-com/Pagination
"""