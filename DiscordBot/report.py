from enum import Enum, auto
import discord
import re
import json
from unidecode import unidecode


class State(Enum):
    # User-side states for a report
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

    # Moderator-side states for a report
    REVIEW_START = auto()
    HARASSMENT = auto()
    DANGER = auto()
    OTHER_VIOLATIONS = auto()
    REPEAT_OFFENDER = auto()
    REMOVE_MESSAGE = auto()
    REVIEW_COMPLETE = auto()
    ADVERSARIAL = auto()
    ROUTINE = auto()
    FILLED_CATEGORY = auto()
    BAN_REGEX = auto()
    ASK_REGEX = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    BAN_REGEX_KEYWORD = "ban"

    def __init__(self, client, regexes = {}):
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
        self.decodedMessage = None
        self.regexes = regexes
        self.regex = None
    
    async def handle_message(self, message, mod_channels):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''
        if message.content == self.BAN_REGEX_KEYWORD:
            self.state = State.ASK_REGEX
            return ["Please enter the regex you want to ban."]
        if self.state == State.ASK_REGEX:
            self.state = State.BAN_REGEX
            self.regex = message.content
            return ["Please enter the channel name you want to ban the regex from."]
        if self.state == State.BAN_REGEX:
            self.state = State.REPORT_COMPLETE
            self.regexes[message.content] = self.regex
            return ["The regex has been banned from the specified channel. "]

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

            self.decodedMessage = self.messageContent.encode('utf-8').decode('unicode-escape')
            
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
                return ["Please select the category of hate speech this post falls into." + "\n" + 
                        "1. The content includes deadnaming" + "\n" + 
                        "2. The content misgenders someone" + "\n" +
                        "3. The content includes a slur" + "\n" +
                        "4. The username is vulgar or inappropriate" + "\n" + 
                        "5. This content is part of a raid" ]
            # Everything else
            else:
                await self.forwardToMods(mod_channels)
                self.state = State.BLOCK
                return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user?"]
        # User selects Hate Speech type: 1: Deadnaming, 2: Misgendering, 3: Slurs
        if self.state == State.CATEGORY:
            self.category = message.content
            category = None
            if message.content == "1": 
                category = "deadnaming"
            elif message.content == "2":
                category = "misgendering"
            elif message.content == "3":
                category = "using a slur"
            elif message.content == "4":
                category = "using an inappropriate username"
            elif message.content == "5":
                category = "being part of a raid"
            else:
                category = "hate speech"

            confirmation_msg = f'You are about to report this content for {category}. Please select \'cancel\' if this report was made in error.\n'
            if message.content in ["1", "2", "3"]: 
                await self.forwardToMods(mod_channels)
                self.state = State.BLOCK
                return [confirmation_msg, "We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user to prevent them from sending  you more messages in the future?"]
            # Vulgar / Inappropriate username
            if (message.content == "4"):
                self.state = State.DESCRIBE_ISSUE
                return ["Please briefly describe the issue with this user's username."]
            # Raid
            if (message.content == "5"):
                self.state = State.RAID
                return ["To your knowledge, has this user a repeat offender or been a part of other raids? " + 
                            "If unsure, please select \'no.\'"]
        # Prompt the user to describe the issue with this person's username
        if self.state == State.DESCRIBE_ISSUE:
            self.usernameIssue = message.content
            await self.forwardToMods(mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user to prevent them from sending you more messages in the future?"]
        # Prompt the user to answer whether this person is a repeat offender or not
        if self.state == State.RAID:
            self.repeatOffender = (message.content[0] in ["y", "Y"])
            await self.forwardToMods(mod_channels)
            self.state = State.BLOCK
            return ["We have forwarded the information to our moderator team." + "\n" + "Would you like to block this user to prevent them from sending you more messages in the future?"]
        # User has blocked another user, conclude user reporting flow
        if self.state == State.BLOCK:
            if message.content[0] in ["y", "Y"]:
                self.state = State.REPORT_COMPLETE
                return ["The user has been blocked. ", "Thank you for reporting. Our content moderation team will review the " + 
                        "content and email you an update once we decide on appropriate action. This may include content and/or account removal."]
            else:
                self.state = State.REPORT_COMPLETE
                return ["Thank you for reporting. Our content moderation team will review the " + 
                        "content and email you an update once we decide on appropriate action. This may include content and/or account removal."]   
        
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    
    async def forwardToMods(self, mod_channels):
        message = self.message
        mod_channel = mod_channels[message.guild.id]

        # A dictionary of relevant report information
        reportInfo = {"Message": self.messageContent,
                      "Author": self.author,
                      "Message Content": self.messageContent,
                      "Decoded Content": self.decodedMessage,
                      "Report Reason": self.reason,
                      "Abuse Category": self.category,
                      "Username Issue" : self.usernameIssue,
                      "Repeat Offender": self.repeatOffender}
        # await mod_channel.send(reportInfo)
        #scores = self.eval_text(message.content)
        #await mod_channel.send(self.code_format(scores)
    
class ModReview:
    START_REVIEW_KEYWORD = "review"
    DISMISS_KEYWORD = "dismiss"

    def __init__(self, client, report, userStats):
        self.state = State.REVIEW_START
        self.client = client
        self.userStats = userStats
        self.threshold = 3

        # Report information sent to the moderating channel
        self.report = report
        self.report_dict = {"Message": report.messageContent,
                      "Author": report.author,
                      "Decoded Content": report.decodedMessage,
                      "Report Reason": report.reason,
                      "Abuse Category": report.category,
                      "Username Issue" : report.usernameIssue,
                      "Repeat Offender": report.repeatOffender}
    
    async def handle_mod_message(self, message, mod_channels):
        '''
        This function makes up the meat of the moderator-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. 
        '''
        if message.content == self.DISMISS_KEYWORD:
            self.state = State.REVIEW_COMPLETE
            return ["Report dismissed."]
        
        if self.state == State.REVIEW_START or message.content == self.START_REVIEW_KEYWORD:
            reply =  "Thank you for starting the reviewing process. \n "
            for key, value in self.report_dict.items():
                if value is not None:
                    reply += key + ": " + str(value) + "\n"
            reply += "Is this harassment?\n\n"
            self.state = State.HARASSMENT
            return [reply]
        if self.state == State.HARASSMENT:
            if message.content[0] in ["y", "Y"]:
                self.state = State.DANGER
                
                userStatsDict = {}
                with open(self.userStats) as userStats:
                    userStatsDict = json.load(userStats)
                    userStatsDict[self.report.message.author.name] = userStatsDict.get(self.report.message.author.name, 0) + 1

                    # If the user has been a perpetrator more than the allotted number of times,
                    # permanently ban them
                    if userStatsDict[self.report.message.author.name] >= self.threshold:
                        return ["The user has been permanently banned for surpassing the number of allowed violations."]
                    
                with open(self.userStats, 'w') as userStats:
                    json.dump(userStatsDict, userStats)

                return ["Does this report indicate a user is in imminent danger?"]
            else:
                self.state = State.ADVERSARIAL
                return ["Is this a case of adversarial flagging?"]
        if self.state == State.ADVERSARIAL:
            if message.content in ["y", "Y"]:
                self.state = State.ROUTINE
                return ["Is harassment routine (over frequent reporting from one user) or is it coordinated (one user reported by many users)?"]
            else:
                return ["Thank you. This review is complete."]
        if self.state == State.ROUTINE:
            if message.content in ["y", "Y"]:
                self.state = State.REVIEW_COMPLETE
                return ["The user has been temporarily banned and flagged for violating Community Guidelines."]
            else:
                return ["Thank you. This review is complete."]
        # Determine if this person is in danger
        if self.state == State.DANGER:
            # There is imminent danger
            if message.content[0] in ["y", "Y"]:
                self.state = State.REVIEW_COMPLETE
                return ["The authorities have been contacted with this user's details."]
            # No imminent danger, case states on category of the report
            
            else:
                # If the high-level reason for the report is hate speech, then proceed, otherwise 
                # finish the report
                if self.report.reason == "1":
                    category = self.report.category
                    # Misgendering, Deadnaming, or slurs
                    if category in ["1", "2", "3"]:
                        # Remove the original message
                        await self.report.message.delete()
                        await self.report.message.channel.send("This message has been removed for violating Twitch's guidelines.")

                        # Check if the user has other violations
                        self.state = State.OTHER_VIOLATIONS
                        return ["The message has been removed. Does the user have other violations?"]
                    elif category == "4":
                        self.state = State.REVIEW_COMPLETE
                        return ["The user has been permanently banned."]
                    elif category == "5":
                        self.state = State.REPEAT_OFFENDER
                        return ["To your knowledge, has this user a repeat offender or been a part of other raids? ",
                                "If unsure, please select \'no.\'"]
                    else:
                        if category is None:
                            # This report does not have the category included
                            self.state = State.FILLED_CATEGORY
                            return ["Please select the category of hate speech this post falls into." + "\n" + 
                                "1. The content includes deadnaming" + "\n" + 
                                "2. The content misgenders someone" + "\n" +
                                "3. The content includes a slur" + "\n" +
                                "4. The username is vulgar or inappropriate" + "\n" + 
                                "5. This content is part of a raid" ]
                else:
                    self.state = State.REPORT_COMPLETE
                    return ["Thank you for reporting."]
        if self.state == State.FILLED_CATEGORY:
            category = message.content
            # Misgendering, Deadnaming, or slurs
            if category in ["1", "2", "3"]:
                # Remove the original message
                await self.report.message.delete()

                # Check if the user has other violations
                self.state = State.OTHER_VIOLATIONS
                return ["The message has been removed. Does the user have other violations?"]
            if category == "4":
                self.state = State.REVIEW_COMPLETE
                return ["The user has been permanently banned."]
            if category == "5":
                self.state = State.REPEAT_OFFENDER
                return ["To your knowledge, has this user a repeat offender or been a part of other raids? ",
                        "If unsure, please select \'no.\'"]
        if self.state == State.OTHER_VIOLATIONS:
            if message.content[0] in ["y", "Y"]:
                self.state = State.REVIEW_COMPLETE
                return ["The user has been temporarily banned and flagged for violating Community Guidelines."]
            else:
                self.state = State.REVIEW_COMPLETE
                return ["Thank you. This review is complete."]
        if self.state == State.REPEAT_OFFENDER:
            self.state = State.REVIEW_COMPLETE
            if message.content[0] in ["y", "Y"]:
                return ["The user has been permanently banned."]
            else:
                return ["The user has been temporarily banned and flagged for violating Community Guidelines."]

    def review_complete(self):
        return self.state == State.REVIEW_COMPLETE
