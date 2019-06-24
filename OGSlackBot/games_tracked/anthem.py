# author: Keith Hill
# date: 2/12/2019

import bot_utilities
import map_gamertag


# a new person has registered and we need to do Anthem specific tasks, such as collecting needed info
def anthem_user_registered (command, channel, user) : 
    
    # verify mapped gamertag.  We hand off the conversation to that flow because we will not proceed without a gamertag.
    # none error case: if the user bails the gamertag conversation, anthem data will not get tracked.  No nagging occurs

    has_gamertag = bot_utilities.has_gamertag(user)
    if has_gamertag == False :
        map_gamertag.handle_conversation(command,channel,user)
        return None

