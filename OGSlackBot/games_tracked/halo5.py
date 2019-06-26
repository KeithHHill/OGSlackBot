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
    print ("Error reading the config file - halo 5")

player_emblem_url = 'https://www.haloapi.com/profile/h5/profiles/diknak/emblem'
headers = {'Accept-Language': 'en', 'Ocp-Apim-Subscription-Key' : api_key}


# updates the database with the current playlist information
def update_seasons() :
    try :
        params = urllib.urlencode({
        })

        conn = httplib.HTTPSConnection('www.haloapi.com')
        conn.request("GET", "/metadata/h5/metadata/playlists?%s" % params, "{body}", headers)
        response = conn.getresponse()
        playlists = json.loads(response.read())
        conn.close()

        db = database.Database()
        for playlist in playlists :
            playlist_id = playlist['id']
            content_id = playlist['contentId']
            game_mode = playlist['gameMode']
            is_active = playlist['isActive']
            ranked = playlist ['isRanked']
        
            
            db.execute("replace into halo5_seasons (playlist_id, content_id,game_mode,is_active,ranked,updated) values(%s,%s,%s,%s,%s,now())",[playlist_id,content_id,game_mode,is_active,ranked])

        db.close()
        bot_utilities.log_event("halo 5 playlists updated")
    except :
        bot_utilities.log_event("Failed to update the halo 5 playlists")


# ranks are returned in numerical format for storage
def get_rank_value(rank_data):
    try :
        rank_id = str(rank_data['DesignationId']) + "-" + str(rank_data['Tier']) #form key from data

        db = database.Database()
        values = db.fetchAll("select rank_value from halo5_ranks where rank_id =%s",[rank_id])
        db.close()

        return values[0]['rank_value']
    except :
        return 0

# pass in the numeric rank value and return a text to display
def get_rank_text(rank_value) :
    if rank_value == 0 :
        return "n/a"
    else :
        try :
            db = database.Database()
            rank_text = db.fetchAll("select name from halo5_ranks where rank_value = %s",[rank_value])
            db.close()
            return rank_text[0]['name']
        except :
            return "n/a"


def user_plays_halo5(user) :
    db = database.Database()
    results = db.fetchAll("""select * from player_games where game_id ="HALO5" and member_id =%s """,[user])
    if len(results) == 0 :
        return False
    else :
        return True
    db.close()

### primary entry point
def handle_command (command,channel,user) :
    if user_plays_halo5(user) is False :
        bot_utilities.post_to_channel(channel,"I don't have a record of you playing halo 5.  Try the command '@og_bot I play halo 5' to get started")

    else :

        if "stats" in command :
            if bot_utilities.has_gamertag(user) :
                halo5_season_stats(command,channel,user)
            else :
                bot_utilities.post_to_channel(channel,"Sorry, but I don't have a gamertag registered.  Try the \"Update gamertag\" command")

        else :
            bot_utilities.post_to_channel(channel,"Sorry, but that command isn't supported  Try using the command '@og_bot help halo' to see what I can do.")
        


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
    season_url = "/stats/h5/servicerecords/arena?&%s"
    user_gamertag = bot_utilities.get_gamertag(user)
    

    # gamertag to the parameters
    if season == None :
        params = urllib.urlencode({
        # Request parameters
        'players' : user_gamertag
        })

    try: #everything in a try so we can bail if something goes wrong
        conn = httplib.HTTPSConnection('www.haloapi.com')
        conn.request("GET", season_url % params, "{body}", headers)
        response = conn.getresponse()
        # data = response.read()
        data = json.loads(response.read())
        conn.close()

        data_len = len(data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats']) # number of records for the season
        count = 0
        while count< data_len : 
            data_season = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['PlaylistId']
            data_rank = data['Results'][0]['Result']['SpartanRank']
            data_csr = get_rank_value(data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['HighestCsr'])
            data_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalKills']
            data_deaths = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalDeaths']
            data_assists = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalAssists']
            data_games_completed = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalGamesCompleted']
            data_games_won = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalGamesWon']
            data_games_lost = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalGamesLost']
            data_shots_fired = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalShotsFired']
            data_shots_landed = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalShotsLanded']
            data_best_weapon = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['WeaponWithMostKills']['WeaponId']['StockId']
            data_best_weapon_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['WeaponWithMostKills']['TotalKills']
            data_melee_kills = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalMeleeKills']
            data_assassinations = data['Results'][0]['Result']['ArenaStats']['ArenaPlaylistStats'][count]['TotalAssassinations']
            count +=1

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
        records = db.fetchAll("""
            select s.member_id, s.gamertag, max(s.rank) as rank, max(s.highest_csr) as highest_csr, sum(s.total_kills) as total_kills, sum(s.total_deaths) as total_deaths, sum(s.total_assists) as total_assists, sum(s.games_completed) as games_completed, sum(s.games_won) as games_won, sum(s.games_lost) as games_lost, sum(s.shots_fired) as shots_fired, sum(s.shots_landed) as shots_landed, s.best_weapon, sum(s.best_weapon_kills) as best_weapon_kills, sum(s.melee_kills) as melee_kills, sum(s.assassinations) as assassinations
            from halo5_season_stats s
            left outer join halo5_seasons sea on s.season = sea.content_id
            where s.member_id = %s and sea.is_active = 1 and sea.ranked = 1
            group by s.member_id
        """,[user])
        db.close()

        highest_rank = get_rank_text(records[0]['highest_csr'])
        
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
*HIGHEST CSR:* """ + highest_rank + """
*GAMES:* """ + str(records[0]['games_completed']) + win_pct + """
*K/D:* """ + kd + """ 
*ACCURACY:* """ + accuracy

        bot_utilities.log_event("Halo 5 stats retrieved by user " + user)

    else :
        if bot_utilities.has_gamertag :
            response = "It looks like something went wrong trying to update your stats using the gamertag " + bot_utilities.get_gamertag(user) + ". Perhaps you changed it recently.  If so, try the 'update gamertag' command.  If not, please contact the bot owner."
        else :
            response = "It looks like you don't have a gamertag registered.  Try using the 'update gamertag' command."

    bot_utilities.post_to_channel(channel,response)
