import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import bot_utilities
from dateutil import parser


# get config
myPath = os.path.dirname(os.path.abspath(__file__))


try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    log_chat = config.get('config','log_chat')
    game_api_key = config.get('games','api_key')
    platform = config.get('games','platform')
    release_future_days = config.get('games','release_future_days')
    general_chat = config.get('config','general_chat')


except:
    print ("Error reading the config file - gamme_info.py")

slack_client = SlackClient(token)

release_url = "https://www.giantbomb.com/api/games/?api_key="+game_api_key+"&filter=expected_release_month:{0},expected_release_year:{1},platforms:"+platform+"&sort=original_release_date:desc&format=json"
platform_url = "https://www.giantbomb.com/api/platforms/?api_key=" + game_api_key+"&format=json"



# posts upcoming releases to general chat. Defaults used for scheduled task
def post_upcoming_releases(channel=general_chat, days = release_future_days) :

    # find the current and next month info
    year = datetime.date.today().strftime("%Y")
    month = datetime.date.today().strftime("%m")

    if month == "12" : # handle end of the year
        next_month = "1"
        next_year = str(int(year)+1)
    else :
        next_month = str(int(month)+1) 
        next_year = year

    # format the release url to fetch the data
    this_month_url = release_url.format(str(month),str(year))
    next_month_url = release_url.format(str(next_month),str(next_year))

    # call the API and get a giant list of games.  This list will need scrubbed.  We need to get 2 months of data to ensure we get enough time.
    try:
        this_month_releases = bot_utilities.getPage(this_month_url)['results']
        next_month_releases = bot_utilities.getPage(next_month_url)['results']
    except :
        bot_utilities.log_event("Failed to get data from GiantBomb API. game_info.get_releases()")
        sys.exit()

    # we will dump applicable games into this dict object
    games = {}
    games = dict()
    
    # merge this month releases and next month to ensure we have a bridge to cover the end of the month cases
    releases = this_month_releases + next_month_releases
    
    # threshhold to look for games within now and this future date
    future_limit = datetime.datetime.now() + datetime.timedelta(days=int(days))


    # we look at each returned record and if it is a game within the X days, we add it to our dict object
    for release in releases:
        id = release['id']

        if release['expected_release_day'] is not None and release['expected_release_month'] is not None and release['expected_release_year'] is not None :
            #convert into a datetime format
            parsed_release_date = parser.parse(str(release['expected_release_month']) + "/" + str(release['expected_release_day']) +"/" + str(release['expected_release_year']))
            
            #between dates - add to object
            if parsed_release_date >= datetime.datetime.now() and parsed_release_date <= future_limit :
                games[len(games)] = release    


    if len(games) > 0 : # at least one game releasing
        count = 0

        while count < len(games) :
            parsed_release_date = parser.parse(str(games[count]['expected_release_month']) + "/" + str(games[count]['expected_release_day']) +"/" + str(games[count]['expected_release_year']))

            bot_utilities.post_to_channel(channel,games[count]['image']['thumb_url'])
            message = "*"+games[count]['name']+"*\n"+games[count]['deck']+"\n_"+str(parsed_release_date.strftime("%A %m/%d"))+"_\n"
            bot_utilities.post_to_channel(channel,message)

            count += 1

        message = "_________\nThere are " + str(len(games)) + " games releasing in the next " + str(days) + " days."
        bot_utilities.post_to_channel(channel,message)

    else: 
        bot_utilities.post_to_channel(channel,"I checked for games coming out in the next " + str(days) +  " and there are no upcoming releases :(")

    bot_utilities.log_event("Fetched upcoming releases and posted to " + channel)



# handles command where someone wants to get release information
def upcoming_release_command(command, channel, user) :
    # see if we can find a number of days in the command
    days = bot_utilities.parse_number_from_command(command)

    if days == 0 :
        days = int(release_future_days)

    if days > 30 :
        bot_utilities.post_to_channel(channel,"Sorry, I am only limited to a maximum of 30 days. Please try again.")
        bot_utilities.log_event("user " + user + " requested a list of upcoming games but exceed limit: " + command)
    else :
        post_upcoming_releases(channel,days)
        bot_utilities.log_event("user " + user + " requested a list of upcoming games: " + command)

    


if __name__ == "__main__":
    print("module loaded. nothing to do.")
