# author: Keith Hill
# date: 2/12/2019

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
    halo5_enabled = config.get('halo5','enabled')
    halo5_channel = config.get('halo5','channel')
    stat_days = config.get('halo5','stat_days')
    api_key = config.get('halo5','api_key')
    

except:
    print ("Error reading the config file")

player_emblem_url = 'https://www.haloapi.com/profile/h5/profiles/diknak/emblem'
headers = {'Ocp-Apim-Subscription-Key' : api_key}


def handle_command (command,channel,user) :
    if "season" in command and "stats" in command :
        if bot_utilities.has_gamertag(user) :
            halo5_season_stats(command,channel,user)
        else :
            bot_utilities.post_to_channel(channel,"Sorry, but I don't have a gamertag registered.  Try the \"Update gamertag\" command")


def halo5_user_registered (command, channel, user) :   
    # verify mapped gamertag.  We hand off the conversation to that flow because we will not proceed without a gamertag.
    # none error case: if the user bails the gamertag conversation, halo5 data will not get tracked.  No nagging occurs

    has_gamertag = bot_utilities.has_gamertag(user)
    if has_gamertag == False :
        map_gamertag.handle_conversation(command,channel,user)
        return None


# user asks about their halo 5 stats.  Return time based stats on config
def halo5_user_stats (command,channel,user) :
    print ("x")



# passed a user and call the halo 5 API to update stats.  Return True if successful
def update_season_stats(user, season = None) :
    season_url = "/stats/h5/servicerecords/arena?players={gamertag}&%s"
    user_gamertag = bot_utilities.get_gamertag(user)
    season_url = season_url.format(gamertag=user_gamertag)


    # fetch the data from the API
    if season == None :
        params = urllib.urlencode({
        # Request parameters
        })

    try: #everything in a try so we can bail if something goes wrong
        conn = httplib.HTTPSConnection('www.haloapi.com')
        conn.request("GET", season_url % params, "{body}", headers)
        response = conn.getresponse()
        # data = response.read()
        data = json.loads(response.read())
        conn.close()

        data_season = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['PlaylistId']
        data_rank = data['Results'][0]['Result']['SpartanRank']
        data_csr = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['HighestCsr']
        data_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalKills']
        data_deaths = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalDeaths']
        data_assists = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalAssists']
        data_games_completed = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalGamesCompleted']
        data_games_won = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalGamesWon']
        data_games_lost = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalGamesLost']
        data_shots_fired = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalShotsFired']
        data_shots_landed = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalShotsLanded']
        data_best_weapon = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['WeaponWithMostKills']['WeaponId']['StockId']
        data_best_weapon_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['WeaponWithMostKills']['TotalKills']
        data_melee_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalMeleeKills']
        data_assassinations = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][0]['TotalAssassinations']
        
        # write to the database
        if response.status == 200 :
            db = database.Database()
            db.execute("""
                replace into halo5_season_stats (member_id,gamertag,season,date_updated,rank,highest_csr,total_kills,total_deaths,total_assists,games_completed,games_won,games_lost,shots_fired,shots_landed,best_weapon,best_weapon_kills,melee_kills,assassinations)
                values (%s,%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,[user,user_gamertag, data_season, data_rank, data_csr, data_kills, data_deaths, data_assists, data_games_completed, data_games_won, data_games_lost, data_shots_fired, data_shots_landed, data_best_weapon, data_melee_kills, data_melee_kills, data_assassinations]
            )

            db.close()
        return True

    except :
        bot_utilities.log_event("something went wrong when writing halo 5 season stats for gamertag " + user_gamertag)
        return False


    

# updates the stats for the user in the database
# returns the stats for the player for a given season.  Current season is the default

def halo5_season_stats (command,channel,user,season = None) :
    success = update_season_stats(user,season)
    if success :
        db = database.Database()
        records = db.fetchAll("select * from halo5_season_stats where member_id = %s",[user])
        db.close()
        
        # handle div by 0 situations
        if records[0]['games_completed'] > 0 :
            win_pct =  " (" + str(round(float(records[0]['games_won'])/float(records[0]['games_completed'])*100,0)) + "% wins)"
        else :
            win_pct = ""

        if records[0]['total_deaths'] > 0 :
            kd = str(round(float(records[0]['total_kills']) / float(records[0]['total_deaths']),2))
        else :
            kd = "n/a"

        if records[0]['shots_fired'] > 0 :
            accuracy = str(round(float(records[0]['shots_landed']) / float(records[0]['shots_fired']),2))
        else :
            accuracy = "n/a"

        # compile the response
        response = """
Current Season Stats For """ + records[0]['gamertag'] + """: 
*SPARTAN RANK:* """ + str(records[0]['rank']) + """
*HIGHEST CSR:* """ + str(records[0]['highest_csr']) + """
*GAMES:* """ + str(records[0]['games_completed']) + win_pct + """
*K/D:* """ + kd + """ 
*ACCURACY:* """ + accuracy


    else :
        if bot_utilities.has_gamertag :
            response = "It looks like something went wrong trying to update your stats using the gamertag " + bot_utilities.get_gamertag(user) + ". Perhaps you changed it recently.  If so, try the 'update gamertag' command.  If not, please contact the bot owner."
        else :
            response = "It looks like you don't have a gamertag registered.  Try using the 'update gamertag' command."

    bot_utilities.post_to_channel(channel,response)
