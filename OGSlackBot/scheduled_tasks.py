import os
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_utilities
import og_events
import game_info
from games_tracked import halo5

# get config
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    lfg_channel = config.get('events','lfg')


except:
    print ("Error reading the config file - scheduled tasks")





if __name__ == "__main__":
    arguments = sys.argv[1:]

    if len(arguments) > 0 :
        if arguments[0] == "event_reminders" :
            bot_utilities.event_reminders()

        elif arguments[0] == "post_to_lfg" :
            og_events.list_upcoming_events("x",lfg_channel,"x",True)
    
        elif arguments[0] == "post_upcoming_releases" :
            game_info.post_upcoming_releases()

        elif arguments[0] == "update halo 5 playlists" :
            halo5.update_seasons()
