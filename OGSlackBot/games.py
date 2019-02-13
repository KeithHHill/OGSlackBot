# author: Keith Hill
# Date: 2/11/2019

import os
import time
import datetime
import ConfigParser
import sys
import database
import bot_utilities
import string
from games_tracked import anthem




# utility function to see if the game is valid and tracked in the database.  If we find the game, return the game id
def is_valid_game(game_name): 
    db = database.Database()
    games = db.fetchAll("select * from games")

    game_name = string.replace(game_name," ","")
    db.close()
    # go through each game and see if it matches (remove spaces and make lower)
    for game in games :
        item = string.replace(game["game_name"]," ","") 
        item = string.lower(item)
        if game_name == item :
            return True, game["game_id"]

    return False, "NONE" 


# the user has told the bot that it plays a game.  The function then associates the game with that user.
def game_add_request (command, channel, user) :
    response = " "

    # remove the base "I play"
    game_name = string.replace(command,"i play ","")

    # verify orientation has been completed
    completed_orientation = bot_utilities.orientation_completed(user)
    if completed_orientation == False :
        response = "Sorry, but you must complete your orientation before I can help with that."
        bot_utilities.post_to_channel(channel,response)
        return None
    
    # make sure it's a tracked game
    game_check, game_id = is_valid_game(game_name)
    if game_check == False :
        response = "Sorry, but that's not a game I recognize.  Please try again."
        bot_utilities.log_event("user " + user + " tried to associate with a game and it was an invalid game. " + command)
        bot_utilities.post_to_channel(channel,response)

    else :
        # add the user
        db = database.Database()
        db.runSql("replace into player_games (member_id, game_id, active) values (%s,%s,1)",[user,game_id])
        response = "Great, you're now registered as playing " + game_name
        bot_utilities.log_event("user "+ user + " has been registered to a new game: " + command)
        bot_utilities.post_to_channel(channel,response)

        # game specific tasks
        if game_id == "ANTHEM" :
            anthem.anthem_user_registered(command,channel,user)
