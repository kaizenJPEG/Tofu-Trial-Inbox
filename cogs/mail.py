import discord
import psycopg2
import math
import Paginator
from discord.ext import commands
from config import dbConfig

MY_COLOR = discord.Color.from_rgb(0, 166, 255)

# Overrides Paginator Class to include Mail Dropdown
class MyPaginator(Paginator.Simple):
    def __init__(self, allMail, embedList):
        super().__init__()
        # Initialize "Pages" of Mail
        self.allMail = allMail
        self.embedList = embedList
        self.dropdownMsg = None
        self.currentDropdown = None
        self.inboxInstance = None

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

        self.add_item(self.PreviousButton)
        self.add_item(self.page_counter)
        self.add_item(self.NextButton)
        self.message = await ctx.send(embed=self.pages[self.InitialPage], view=self)

        # Add Dropdown to View
        self.dropdownMsg = self.message
        self.currentDropdown = Dropdown(self.allMail[0], self.dropdownMsg, self, self.allMail, self.embedList,)
        self.add_item(self.currentDropdown)
        await self.message.edit(embed=self.pages[self.current_page], view=self)

    async def resume(self, message):
        await message.edit(embed=self.inboxInstance.pages[self.inboxInstance.current_page], view=self.inboxInstance)

    async def previous(self):
        if self.current_page == 0:
            self.current_page = self.total_page_count - 1
        else:
            self.current_page -= 1

        self.page_counter.label = f"{self.current_page + 1}/{self.total_page_count}"

        # Remove old Dropdown "page" from view, add new one
        self.remove_item(self.currentDropdown)
        self.currentDropdown = Dropdown(self.allMail[self.current_page], self.dropdownMsg, self, self.allMail, self.embedList)
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
        self.currentDropdown = Dropdown(self.allMail[self.current_page], self.dropdownMsg, self, self.allMail, self.embedList)
        self.add_item(self.currentDropdown)

        await self.message.edit(embed=self.pages[self.current_page], view=self)

    # Add timeout method - disable buttons/show message saying to re-do command
    async def on_timeout(self):
        ...

### 6. select menu at bottom for mail on the page
class Dropdown(discord.ui.Select):
    def __init__(self, mailList, message, inboxInstance, allMail = None, embedList = None):
        options = []

        for mail in mailList:
            mailEmoji = "🌟" if mail[3] == False else ""

            option = discord.SelectOption(
                label=f"{mail[0]} {mailEmoji}"
            )

            options.append(option)

        super().__init__(placeholder="Select which message you'd like to read.", min_values=1, max_values=1, options=options)
        self.mailList = mailList
        self.message = message
        self.inboxInstance = inboxInstance
        self.allMail = allMail
        self.embedList = embedList

    async def callback(self, interaction: discord.Interaction):
        ### 7. choose mail, goes to that mail, who has a header and body, and if has rewards in rewards section then can claim them
        selectedHeadline = self.values[0].replace(" 🌟", "")
        params = dbConfig()
        conn = psycopg2.connect(**params)
        cur = conn.cursor()

        # Edit current message to display selected Mail
        cur.execute("SELECT * FROM mail WHERE headline = %s AND userid = %s", (selectedHeadline, str(interaction.user.id)))
        selectedMail = cur.fetchone()

        mailHead = selectedMail[0]
        mailBody = selectedMail[1]
        mailTime = int(selectedMail[2].timestamp())
        mailIsRead = selectedMail[3]
        mailUserID = selectedMail[4]
        mailReward = selectedMail[5]
        mailClaimed = selectedMail[6]

        mailEmbed = discord.Embed(
            title="Selected Message",
            color= MY_COLOR
        )

        mailEmbed.add_field(name=mailHead, value=mailBody, inline=False)
        mailEmbed.add_field(name="Message Sent", value=f"<t:{mailTime}:R>", inline=True)

        if mailReward == None:
            rewardStatus = False
            rewardStr = "❌ None"
        
        elif mailReward != None:
            rewardStatus = True
            if mailClaimed:
                rewardStr = f"✅ {mailReward}"
            else:
                rewardStr = f"🎁 {mailReward}"
                
        
        mailEmbed.add_field(name="Reward", value=rewardStr)
        mailEmbed.set_thumbnail(url=(interaction.user.avatar.url if len(interaction.user.avatar.url) > 2 else None))

        ### 8. button to return to inbox
        view = MailButtons(self.message, self.allMail, self.embedList, mailClaimed, selectedMail, mailEmbed, rewardStatus, self.inboxInstance)
        
        # Edit db to show that user has read message
        cur.execute("UPDATE mail SET isread = TRUE WHERE headline = %s AND userid = %s", (mailHead, str(mailUserID)))
        conn.commit()
        conn.close()
        await self.message.edit(embed=mailEmbed, view=view)

class MailButtons(discord.ui.View):
    def __init__(self, message, allMail, embedList, claimStatus, selectedMail, mailEmbed, rewardStatus, inboxInstance):
        super().__init__()
        self.message = message
        self.allMail = allMail
        self.embedList = embedList
        self.claimStatus = claimStatus
        self.selectedMail = selectedMail
        self.mailEmbed = mailEmbed
        self.rewardStatus = rewardStatus
        self.inboxInstance = inboxInstance

        if rewardStatus:
            if claimStatus:
                self.children[-1].label = "Reward Claimed"
                self.children[-1].emoji = "✅"
                self.children[-1].disabled = True
        else:
            self.remove_item(self.children[-1])

    @discord.ui.button(label="Return to Inbox", style=discord.ButtonStyle.primary, emoji="📥")
    async def returnToInbox_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        inboxView = MyPaginator(self.allMail, self.embedList)
        inboxView.inboxInstance = self.inboxInstance

        await inboxView.resume(self.inboxInstance.message)

    @discord.ui.button(label="Claim Reward!", style=discord.ButtonStyle.success, emoji="🎁")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        params = dbConfig()
        conn = psycopg2.connect(**params)
        cur = conn.cursor()

        cur.execute("UPDATE mail SET isclaimed = TRUE WHERE headline = %s AND userid = %s", (self.selectedMail[0], self.selectedMail[4]))
        conn.commit()
        conn.close()

        self.children[-1].label = "Reward Claimed"
        self.children[-1].emoji = "✅"
        self.children[-1].disabled = True
        
        await self.message.edit(embed=self.mailEmbed, view=self)

class Mail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ### 1. Use t!mail command
    @commands.command(help="Check your inbox.")
    async def mail(self, ctx):
        # Connect to database
        params = dbConfig()
        conn = psycopg2.connect(**params)
        cur = conn.cursor()

        ## SAMPLE MAIL TABLE
        """
        Headline         | Body         | TimeCreated| isRead | userID             | Reward     | isClaimed
        -------------------------------------------------------------------------- |            |
        sample headline1 | sample body1 | 1685213014 | False  | 144176650958012417 |            |
        sample headline1 | sample body1 | 1685213014 | True   | 105705940581376000 |            |
        sample headline1 | sample body1 | 1685213014 | False  | 711212342792159322 |            |
        sample headline1 | sample body1 | 1685213014 | True   | 372825096664121346 |            |
        sample headline2 | sample body2 | 1685213210 | False  | 144176650958012417 | 50 points  |
        sample headline2 | sample body2 | 1685213210 | True   | 105705940581376000 | 50 points  |
        sample headline2 | sample body2 | 1685213210 | False  | 711212342792159322 | 50 points  |
        sample headline2 | sample body2 | 1685213210 | True   | 372825096664121346 | 50 points  |

        .....

        sample headline16 | sample body16 | 1685213196 | False  | 144176650958012417 |          |
        sample headline16 | sample body16 | 1685213196 | True   | 105705940581376000 |          |
        sample headline16 | sample body16 | 1685213196 | False  | 711212342792159322 |          |
        sample headline16 | sample body16 | 1685213196 | True   | 372825096664121346 |          |
        """

        cur.execute("SELECT * FROM mail WHERE userid = %s ORDER BY timecreated DESC", (str(ctx.author.id),))
        userMail = cur.fetchall()

        # Create list of embeds/pages
        embedList = []

        # Create nested list for Mail
        allMail = []

        # Set initial variables for loop
        origLength = len(userMail)
        noOfPages = math.ceil(len(userMail) / 5) ## Rounds up number of pages if not an int
        pageCount = 0
        mailCount = 0

        # Loop that will create all the pages
        while True:
            # Create an embed/page
            mailList = []
            mailMax = 0
            mailStr = ""

            ### 2. user profile picture top of embed, (username)'s Inbox
            mailEmbed = discord.Embed(
                title=f"{ctx.author.name}'s Inbox",
                color= MY_COLOR
            )

            mailEmbed.set_thumbnail(url=(ctx.author.avatar.url if len(ctx.author.avatar.url) > 2 else None))

            for mail in userMail:
                mailHead = mail[0]
                mailBody = mail[1]
                mailTime = int(mail[2].timestamp())
                mailIsRead = mail[3]
                mailUserID = mail[4]

                # Sets the emoji to indiciate whether or not user has read this mail yet
                mailEmoji = "🌟" if mailIsRead == False else ""

                ### 4. each mail has dynamic timestamp, a headline, and an emoji to indicate if new if has been read then emoji removed
                mailStr += f"{mailCount}. {mailHead} | <t:{mailTime}:R> | {mailEmoji}\n"
                mailCount += 1
                mailMax += 1
                mailList.append(mail)
                userMail.remove(mail)

                if mailMax == 5 or mailCount == origLength:
                    # Page has been created, add embed to embedList and make a new one
                    ### 3. list of numbered mail descending by time, max 5 per page
                    mailEmbed.add_field(name="Select a message", value=f"{mailStr}")
                    embedList.append(mailEmbed)
                    pageCount += 1

                    # Add mailList to allMail
                    allMail.append(mailList)
                    mailList = []
                    
                    break

            # Break loop when correct number of pages are created
            if pageCount == noOfPages:
                print("breaking loop")
                break

        # Create paginator
        ### 5. shows pages at bottom, can go to next pages with buttons
        await MyPaginator(allMail, embedList).start(ctx, embedList)

async def setup(bot):
    await bot.add_cog(Mail(bot))

"""
This software includes code from the [soosBot]
Copyright (c) 2021 soosBot

Original code licensed under the MIT License:
https://github.com/soosBot-com/Pagination
"""