
# author: Keith Hill
# created 9/1/2019
# https://dev.mixer.com/guides/core/basictutorial

import requests
import os
import sys
import bot_utilities
import ConfigParser
import database


# load config
myPath = os.path.dirname(os.path.abspath(__file__))
config = ConfigParser.ConfigParser()
config.read(myPath+"/config.ini")
key = config.get('mixer','key')


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
