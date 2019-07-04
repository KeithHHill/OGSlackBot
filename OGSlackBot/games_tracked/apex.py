# author: Keith Hill
# date: 7/3/2019

import bot_utilities
import map_gamertag
import ConfigParser
import os
import requests
import httplib, urllib, base64
import database
import json

# get config
myPath = os.path.dirname(os.path.abspath(__file__))
myPath = os.path.abspath(os.path.join(myPath, os.pardir))


try :
    config = ConfigParser.ConfigParser()
    config.read(myPath+"/config.ini")
    api_key = config.get('apex','api_key')
    

except:
    print ("Error reading the config file - Apex")


headers = {'TRN-Api-Key' : api_key}


# primary entry point
def handle_command(command, channel, user) :
    
    # ensure that the person has registered with the game
    if bot_utilities.user_plays_game(user,"APEX") is False :
        bot_utilities.post_to_channel(channel,"It looks like you haven't registered yourself as playing Apex.  Try starting with the command '@og_bot I play Apex'.")
        return

    if "stats" in command :
        apex_stats(command,channel,user)
    else : 
        bot_utilities.post_to_channel(channel,"Sorry, I'm not sure what you're looking for.  The only command I support for Apex is 'Apex stats'.")

   
def apex_user_registered (command, channel, user) :   
    # verify mapped gamertag.  We hand off the conversation to that flow because we will not proceed without a gamertag.
    # none error case: if the user bails the gamertag conversation, halo5 data will not get tracked.  No nagging occurs

    has_gamertag = bot_utilities.has_gamertag(user)
    if has_gamertag == False :
        map_gamertag.handle_conversation(command,channel,user)
        return None


# user requested stats for Apex
def apex_stats(command, channel, user) :

    params = urllib.urlencode({
            })

    # get the gamertag for the user and send the request
    gamertag = bot_utilities.get_gamertag(user)
    conn = httplib.HTTPSConnection('public-api.tracker.gg')
    gamertagEnc = urllib.quote(gamertag)
    conn.request("GET", "/apex/v1/standard/profile/1/" + gamertagEnc + "?%s" % params, "{body}", headers)
    response = conn.getresponse()

    if response.status is not 200 :  #ensure that we got a good response from the API
        bot_utilities.log_event(user + " attempted to get Apex stats and an invalid response was returned from the API")
        bot_utilities.post_to_channel(channel, "Sorry, but it appears something is wrong with the Apex stats right now.  Try again later.")
        return

    try :
        stats = json.loads(response.read())
    except :
        bot_utilities.log_event(user + " attempted to get Apex stats.  200 response was received, but erorr occured when finding stats")
        bot_utilities.post_to_channel(channel,"Sorry, something went wrong trying to get your stats.")
        return

    conn.close()

    try :

        # start compiling the response
        response = """Apex Legends stats for """ + gamertag + ":\n"
    
        # high level player stats
        playerStats = stats['data']['stats']
        for playerStat in playerStats :
            response = response + str(playerStat['metadata']['name']) + ": " + str(playerStat['value']).replace(".0","") + " \n"

        # all legends are returned, but we are only going to show the stats for the active legend
        legends = stats['data']['children']
        for legend in legends : 
            if legend['metadata']['is_active'] is True :
                response = response + "\n Active Legend: " + legend['metadata']['legend_name'] + "\n"
                legendStats = legend['stats']
                for legendStat in legendStats :  # we get stats based on what the user selects on their card
                    response = response + legendStat['metadata']['name'] + ": " + str(legendStat['value']).replace(".0","") + "\n"
        
        bot_utilities.log_event(user + " successfully fetched Apex stats")

    except :
        bot_utilities.log_event(user + " tried getting Apex stats and I failed at compiling a response")
        response = "sorry, something went wrong when trying to fetch your stats"
        
    bot_utilities.post_to_channel(channel,response)