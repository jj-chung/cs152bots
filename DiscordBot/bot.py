# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
from report import ModReview
import pdb
from collections import defaultdict

# Packages for automated section (Milestone 3)
import openai 
from googleapiclient import discovery

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    open_ai_key = tokens['open_ai_key']
    perspective_ai_key = tokens['perspective_ai_key']


class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.mod_reviews = defaultdict(list) # Map from mod IDs to the state of the reports they're working on
        self.currReport = None # The current report being passed through the flow
        self.userStatsFile = "./userStatistics.json" # User statistics for how many times a user has been reported
        self.regexes = {}

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel
        

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            if message.channel.name == f'group-{self.group_num}-mod':
                await self.handle_mod_channel_message(message)
            else:
                await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            reply += "Use the `ban` command to start the process for banning a regex from a channel.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        if message.content != Report.BAN_REGEX_KEYWORD:
            # Only respond to messages if they're part of a reporting flow
            if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
                return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self, self.regexes)

        # Let the report class handle this message; forward all the messages it returns to us
        responses = await self.reports[author_id].handle_message(message, self.mod_channels)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            await self.handle_mod_channel_message(message, "start", self.reports[author_id])
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return
        
        # Check if the message for this channel matches any of the specific regexes
        for channel, regex in self.regexes.items():
            if channel == f'group-{self.group_num}':
                print(message.content)
                print(regex)
                pattern = re.compile(regex)
                matched = re.search(pattern, message.content) != None
                print(matched)

                if matched:
                    await message.delete()
                    await message.channel.send("This message has been removed for violating the channel's guidelines.")

        # Forward the message to the mod channel
        # mod_channel = self.mod_channels[message.guild.id]
        # await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
        # scores = self.eval_text(message.content)
        # await mod_channel.send(self.code_format(scores))

        # Open ai evaluation
        # isToxic_open_ai, report_open_ai = self.eval_text_open_ai(message)
        # if isToxic_open_ai:
        #    print('OPEN AI HANDLING')
        #    await self.handle_mod_channel_message(message, "start", report_open_ai)

        # Perspective ai evaluation
        isToxic_perspective_ai, report_perspective_ai = self.eval_text_perspective_ai(message)
        if isToxic_perspective_ai:
            print('PERSPECTIVE AI HANDLING')
            await self.handle_mod_channel_message(message, "start", report_perspective_ai)

    async def handle_mod_channel_message(self, message, keyword="", report=None):
        mod_channel = self.mod_channels[1103033282779676743]

        if keyword == "start":
            reply =  "Use the `review` command to begin the reviewing process.\n"
            reply += "Use the `dismiss` command to cancel the review process.\n"
            self.currReport = report
            await mod_channel.send(reply)
            return
        
        author_id = message.author.id
        responses = []

        # If we don't currently have an active review for this moderator, add one
        if author_id not in self.mod_reviews:
            self.mod_reviews[author_id].append(ModReview(self, self.currReport, self.userStatsFile))

        # Let the review class handle this message; forward all the messages it returns to uss
        for review in self.mod_reviews[author_id]:
            responses = await review.handle_mod_message(message, self.mod_channels)

            for r in responses:
                await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        # This assumes that a moderator must work on one report at a time
        remaining_mod_reviews = []
        for review in self.mod_reviews[author_id]:
            if not review.review_complete():
                remaining_mod_reviews.append(review)

        if not remaining_mod_reviews:
            # If a moderator is not working on any reports, remove them from the map
            self.mod_reviews.pop(author_id)
        else:
            # Otherwise, update the number of remainining reports they have
            self.mod_reviews[author_id] = remaining_mod_reviews
    
    def eval_text_perspective_ai(self, message):
        ''''
        Evaluate whether a message is toxic or not and send the message info along if it is.
        '''
        report = Report(self)
        report.messageContent = message.content
        report.message = message
        report.author = message.author.name
        report.decodedMessage = report.messageContent.encode('utf-8').decode('unicode-escape')
        report.repeatOffender = False

        API_KEY = perspective_ai_key

        client = discovery.build(
            "commentanalyzer",
            "v1alpha1",
            developerKey=API_KEY,
            discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
            static_discovery=False,
        )


        analyze_content_request = {
            'comment': { 'text': message.content },
            'requestedAttributes': {'TOXICITY': {}, 
                                    'SEVERE_TOXICITY': {},
                                    'IDENTITY_ATTACK': {},
                                    'INSULT' : {},
                                    'PROFANITY' : {},
                                    'THREAT' : {},
                                    'SEXUALLY_EXPLICIT': {}
                                    }
        }

        response_content = client.comments().analyze(body=analyze_content_request).execute()

        categoryScores = {}
        for category, value in response_content["attributeScores"].items():
            categoryScores[category] = value["summaryScore"]["value"]

        maxCategory = max(categoryScores, key=categoryScores.get)
        summaryScore = response_content["attributeScores"][maxCategory]["summaryScore"]["value"]
        is_content_toxic = summaryScore > 0.6

        if is_content_toxic:
            if maxCategory == "IDENTITY_ATTACK":
                report.reason = "1"
            elif maxCategory == "SEXUALLY_EXPLICIT":
                report.reason = "2"
            elif maxCategory == "IMMINENT_DANGER":
                report.reason = "4"
            else:
                report.reason = "3"

        """
        analyze_username_request = {
            'comment': { 'text': message.author.name },
            'requestedAttributes': {'TOXICITY': {}, 
                                    'SEVERE_TOXICITY': {},
                                    'IDENTITY_ATTACK': {},
                                    'INSULT' : {},
                                    'PROFANITY' : {},
                                    'THREAT' : {},
                                    'SEXUALLY_EXPLICIT': {},
                                    'FLIRTATION': {}
                                    }
        }
        response_username = client.comments().analyze(body=analyze_username_request).execute()
        summaryScore = response_content["attributeScores"]["summaryScore"]["value"]
        is_username_toxic = summaryScore > 0.6

        if is_username_toxic:
            report.reason
            """

        return is_content_toxic, report

    def eval_text_open_ai(self, message):
        ''''
        Evaluate whether a message is toxic or not and send the message info along if it is.
        '''
        isToxic = True
        report = Report(self)
        report.messageContent = message.content
        report.message = message
        report.author = message.author.name
        report.decodedMessage = report.messageContent.encode('utf-8').decode('unicode-escape')
        report.repeatOffender = False

        openai.organization = "org-YVZe9QFuR0Ke0J0rqr7l2R2L"
        openai.api_key = open_ai_key
        # print(openai.Model.list()) # Can used to verify GPT-4 access

        # Ask gpt-4 whether a message is toxic and what category a message belongs to (high-level, not limited to hate speech)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
            {"role": "system", "content": "You are a message moderation system on twitch. Classify each message as toxic (True)" + 
             "or non-toxic (False). If it is toxic, then choose the correct category out of 1. Transphobic Hate Speech" + "\n2. Nudity or Sexual Activity" + 
             "\n3. Harassment" + "\n4. Imminent Danger. Category 1 (Hate Speech) includes deadnaming, use of transphobic slurs, and misgendering."},
            {"role": "user", "content": "user123: I love puppies"},
            {"role": "assistant", "content": "False, None"},
            {"role": "user", "content": "Transgender people are disgusting freaks and groomers who aren't real. " + 
             "They're bad for families and children. " + 
             "They don't deserve any rights or respect."},
            {"role": "assistant", "content": "True, 1"},
            {"role": "user", "content": "Can I get some nude pics? You should come over to my place for a good time"},
            {"role": "assistant", "content": "True, 2"},
            {"role": "user", "content": "I know your name and address! Going to reveal it to everyone now."},
            {"role": "assistant", "content": "True, 3"},
            {"role": "user", "content": "I'm coming to your house to find you and hurt you."},
            {"role": "assistant", "content": "True, 4"},
            {"role": "user", "content": f"{message.author.name}: {message.content}"}
            ]
        )

        # Save the high-level category in the report information
        output = response['choices'][0]['message']['content']
        output = output.split(", ")
        isToxic = output[0] == "True"
        isHateSpeech = output[1] == "1"
        report.reason = output[1]

        # If the category is hate-speech, ask what the lower-level category of hate speech is?
        if isHateSpeech:
            # If gpt-4 determines it's hate speech, ask it to fill out some information
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                {"role": "system", "content": "Which category does the hate spech fall into?" +
                        "1. The content includes deadnaming" + "\n" + 
                        "2. The content misgenders someone" + "\n" +
                        "3. The content includes a slur"
                        "4. The content is non-toxic"},
                {"role": "user", "content": "Your profile says Elizabeth but I know your real name is Elijah."},
                {"role": "assistant", "content": "1"},
                {"role": "user", "content": "I know what your pronouns are, but I'm just going to call you by he/him."},
                {"role": "assistant", "content": "2"},
                {"role": "user", "content": "Tranny"},
                {"role": "assistant", "content": "3"},
                {"role": "user", "content": message.content},
                ]
            )

            report.category = response['choices'][0]['message']['content']

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                {"role": "system", "content": "True/False: This username is vulgar/inappropriate."},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "True"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "False"},
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "False"},
                {"role": "user", "content": message.author.name},
                ]
            )

            output = response['choices'][0]['message']['content']
            output = output == "True"

            if output:
                # If gpt-4 determines it's hate speech, ask it to fill out some information
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                    {"role": "system", "content": "Describe the issue with the twitch account username."},
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": ""},
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": ""},
                    {"role": "user", "content": message.author.name},
                    ]
                )
                report.usernameIssue = response['choices'][0]['message']['content']
        
        print(report)
        return isToxic, report

    
    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + text+ "'"


client = ModBot()
client.run(discord_token)