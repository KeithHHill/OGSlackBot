import os
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_utilities
import og_events

# get config
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    lfg_channel = config.get('events','lfg')


except:
    print ("Error reading the config file")





if __name__ == "__main__":
    arguments = sys.argv[1:]

    if len(arguments) > 0 :
        if arguments[0] == "event_reminders" :
            bot_utilities.event_reminders()

        elif arguments[0] == "post_to_lfg" :
            og_events.list_upcoming_events("x",lfg_channel,"x",True)
    
