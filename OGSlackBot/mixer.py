
# author: Keith Hill
# created 9/1/2019
# https://dev.mixer.com/guides/core/basictutorial

import requests
import os
import sys
import bot_utilities
import ConfigParser
import database
import time


# load config
myPath = os.path.dirname(os.path.abspath(__file__))
config = ConfigParser.ConfigParser()
config.read(myPath+"/config.ini")
key = config.get('mixer','key')
generalChat = config.get('config','general_chat')


# we check anyone that is online and update the database if they go offline
def update_online_streamers() :
    db = database.Database()

    # get our list of users streaming
    users = db.fetchAll("select * from mixer_members where currently_streaming = 1")

    for user in users : 
        # see if they are currently streaming
        s = requests.Session()
        s.headers.update({'Client-ID': key})
        channel_response = s.get('https://mixer.com/api/v1/channels/{}'.format(user['mixer_name']))
        time.sleep(2)

        if channel_response.status_code != 200 :
            bot_utilities.log_event("went to check if " + user['member_id'] + " was streaming and got an invalid response")
            continue

        data = channel_response.json()
        if data['online'] == False : 
            db.execute("""update mixer_members set currently_streaming = 0 where member_id = %s""",[user['member_id']])

    db.close()


# user tells the bot their mixer name and registers for future updates
def register_mixer(command,channel,user) : 

    # parse after the : character
    x = command.split(':')
    mixerName = x[1].lstrip()

    # register the user in the database
    db = database.Database()
    db.execute("""replace into mixer_members (member_id, mixer_name) values (%s,%s)""",[user,mixerName])
    db.close()

    # check and see if we get a good response
    s = requests.Session()
    s.headers.update({'Client-ID': key})

    channel_response = s.get('https://mixer.com/api/v1/channels/{}'.format(mixerName))

    
    if channel_response.status_code  == 200 :
        response = "I have registered mixer with the name " + mixerName
        bot_utilities.log_event(user + " has registered with mixer")
    else :
        response = "I have registered mixer with the name " + mixerName + " but it appears that is either not valid or mixer is unreachable"
        bot_utilities.log_event(user + " has registered with mixer but the response was invalid.")

    bot_utilities.post_to_channel(channel,response)


# scheduled to be called that will check for new streamers and broadcast to the chat when they are online
def find_new_streamers() :
    # first we check to see if anyone has gone offline
    update_online_streamers()

    # find any newly online streamers by getting. Fetch users that were offline the last time we checked
    db = database.Database()
    streamers = db.fetchAll("select * from mixer_members where currently_streaming = 0")

    for streamer in streamers :
        s = requests.Session()
        s.headers.update({'Client-ID': key})
        channel_response = s.get('https://mixer.com/api/v1/channels/{}'.format(streamer['mixer_name']))
        time.sleep(2)

        if channel_response.status_code != 200 :
            continue  # we got a bad response for this streamer, so we bail

        data = channel_response.json()

        # if they are now online, update the database and post to channel
        if data['online'] == True :
            db.execute("update mixer_members set currently_streaming = 1, last_streamed = now() where member_id = %s",[streamer['member_id']])
            message = bot_utilities.get_slack_name(streamer['member_id']) + " is now streaming " + data['type']['name'] + ".  Check it out: \n" + 'https://mixer.com/{}'.format(streamer['mixer_name'])

            bot_utilities.log_event(streamer['member_id'] + " started streaming on Mixer")
            
            bot_utilities.post_to_channel(generalChat,message)

    db.close()

