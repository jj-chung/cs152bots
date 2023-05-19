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
        
        # These class variables are details regarding the abuse, some may stay
        # equal to their initial value depending on the abuse category
        self.author = None
        self.messageContent = None
        self.reason = None
        self.category = None
        self.usernameIssue = None
        self.repeatOffender = False
    
    async def handle_message(self, message, mod_channels):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
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
            self.state = State.MESSAGE_IDENTIFIED
            self.message = message
            self.author = message.author.name
            self.messageContent = message.content
            
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```" + "\n" + 
                    "Are you sure this is the message you would like to report?", 
                    "Otherwise, this report will be cancelled."]
        # User has been asked to confirm whether this is the message they actually want to report
        if self.state == State.MESSAGE_IDENTIFIED:
            # Prompt to user to select the type of harassment
            if message.content[0] in ["y", "Y"]:
                self.state = State.SELECTING
                return ["Please reply with the number corresponding to the reason for reporting this post:" + 
                        "\n1. Hate Speech" + "\n2. Nudity or Sexual Activity" + "\n3. Harassment" + "\n4. Imminent Danger"]
            # User decided not to report this message/user
            else:
                self.state = State.REPORT_COMPLETE
                return ["Report cancelled."]
        # User selected abuse type
        if self.state == State.SELECTING:
            self.reason = message.content
            # User selects Hate Speech
            if (message.content == "1"):
                self.state = State.CATEGORY
                return ["Please select the category of hate speech this post falls into." + "\n" + "1. The content includes deadnaming" + "\n" + "2. The content misgenders someone" + "\n" + "3. The content includes a slur" + "\n" +
                        "4. The username is vulgar or inappropriate" + "\n" + "5. This content is part of a raid" ]
            # Everything else
            else:
                await self.forwardToMods(mod_channels)
                self.state = State.BLOCK
                return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        # User selects Hate Speech type: 1: Deadnaming, 2: Misgendering, 3: Slurs
        if self.state == State.CATEGORY:
            self.category = message.content
            if message.content in ["1", "2", "3"]: 
                await self.forwardToMods(mod_channels)
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
        # Prompt the user to describe the issue with this person's username
        if self.state == State.DESCRIBE_ISSUE:
            self.usernameIssue = message.content
            await self.forwardToMods(mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        # Prompt the user to answer whether this person is a repeat offender or not
        if self.state == State.RAID:
            self.repeatOffender = (message.content[0] in ["y", "Y"])
            await self.forwardToMods(mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        # User has blocked another user, conclude user reporting flow
        if self.state == State.BLOCK:
            if message.content[0] in ["y", "Y"]:
                self.state = State.REPORT_COMPLETE
                return ["The user has been blocked. Thank you for reporting."]
            else:
                self.state = State.REPORT_COMPLETE
                return ["Thank you for reporting."]   
            
    async def forwardToMods(self, mod_channels):
        message = self.message
        mod_channel = mod_channels[message.guild.id]

        # A dictionary of relevant report information
        reportInfo = {"Author": self.author,
                          "Message Content": self.messageContent,
                          "Report Reason:": self.reason,
                          "Abuse Category": self.category,
                          "Username Issue" : self.usernameIssue,
                          "Repeat Offender": self.repeatOffender}
        await mod_channel.send(reportInfo)
        #scores = self.eval_text(message.content)
        #await mod_channel.send(self.code_format(scores))
        
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
        

    


    

