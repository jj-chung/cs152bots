from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    SELECTING = auto()
    CATEGORY = auto()
    CONFIRM = auto()
    DESCRIBE_ISSUE = auto()
    RAID = auto()
    BLOCK = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = ""
        self.reportInfo = {"Abuser" : "", "Content" : "" ,"Reason" : "", "Category": "", "Described Issue" : "", "Repeat Offender" : ""}
    
    async def handle_message(self, message, mod_channels):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
        print(self.state)
        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.SELECTING
            self.message = message
            self.reportInfo["Abuser"] = message.author.name
            self.reportInfo["Content"] = message.content
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```" + "\n" + "Please reply with the number corresponding to the reason for reporting this post:" + "\n1. Hate Speech" + "\n2. Nudity or Sexual Activity" + "\n3. Harassment" + "\n4. Imminent Danger"]
        # TO DO: PROMPT USER TO CONFIRM IDENTIFIED MESSAGE (self.message)
        # ["Is this the message you would like to report?"]
        
        # Wait on Abuse Type selection
        # if self.state == State.MESSAGE_IDENTIFIED:
        #     self.state = 
        #     return ["Please reply with the number corresponding to the reason for reporting this post:" + "\n" + "1. Hate Speech" / "2. Nudity or Sexual Activity" / "3. Harassment" / "4. Imminent Danger"]
        
        # User selected abuse type
        if self.state == State.SELECTING:
            self.reportInfo["Reason"] = message.content
            # User selects Hate Speech
            if (message.content == "1"):
                self.state = State.CATEGORY
                return ["Please select the category of hate speech this post falls into." + "\n" + "1. The content includes deadnaming" + "\n" + "2. The content misgenders someone" + "\n" + "3. The content includes a slur" + "\n" +
                        "4. The username is vulgar or inappropriate" + "\n" + "5. This content is part of a raid" ]
            # Everything else
            else:
                await self.forwardToMods(self.reportInfo, mod_channels)
                self.state = State.BLOCK
                return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        
        # User selects Hate Speech type: 1: Deadnaming, 2: Misgendering, 3: Slurs
        if self.state == State.CATEGORY:
            self.reportInfo["Category"] = message.content
            if (message.content == "1" or message.content == "2" or message.content == "3"): 
                await self.forwardToMods(self.reportInfo, mod_channels)
                self.state = State.BLOCK
                return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
            # Vulgar / Inappropriate username
            if (message.content == "4"):
                self.state = State.DESCRIBE_ISSUE
                return ["Please describe the issue with this user's username."]
            # Raid
            if (message.content == "5"):
                self.state = State.RAID
                return ["Is this user a repeat offender or have they been a part of other raids?"]
        
        if self.state == State.DESCRIBE_ISSUE:
            self.reportInfo["Described Issue"] = message.content
            await self.forwardToMods(self.reportInfo, mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        if self.state == State.RAID:
            self.reportInfo["Repeat Offender"] = message.content
            await self.forwardToMods(self.reportInfo, mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        if self.state == State.BLOCK:
            if message.content[0] == "y" or message.content[0] == "Y":
                # block
                self.state = State.REPORT_COMPLETE
                return ["The user has been blocked. Thank you for reporting."]
            else:
                self.state = State.REPORT_COMPLETE
                return ["Thank you for reporting."]   
            
    async def forwardToMods(self, reportInfo, mod_channels):
        message = self.message
        mod_channel = mod_channels[message.guild.id]
        await mod_channel.send(f'Forwarded:\n{reportInfo}')
        #scores = self.eval_text(message.content)
        #await mod_channel.send(self.code_format(scores))
        
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
        

    


    

