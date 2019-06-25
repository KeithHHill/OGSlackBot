import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_prompts
import bot_utilities
import requests
from games_tracked import halo5

# get config
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    BOT_ID = config.get('config','bot_id')
    bot_chat = config.get('config','bot_chat').lower()
    leader_chat = config.get('config','leader_chat')
    log_chat = config.get('config','log_chat')
    general_chat = config.get('config','general_chat').lower()
    nag_hours = int(config.get('config','nag_hours'))
    nag_threshhold = int(config.get('config','nag_threshhold'))
    test_mode = config.get('config','test_mode')
    timeout_min = config.get('events','timeout_min')
    reminder_min = config.get('events','reminder_min')
    

except:
    print ("Error reading the config file")

slack_client = SlackClient(token)



# determines if the user has a mapped gamertag.  If not, returns False. 
def has_gamertag (user) :
    db = database.Database()
    
    #fetch gamertags
    gamertags = db.fetchAll("""
    select g.gamertag 
    from gamertags g
    inner join member_orientation on g.member_id = member_orientation.member_id
    where g.member_id = %s and g.last_updated is not Null
    """,[user])

    db.close()

    #did we find something?
    if len(gamertags) > 0 :
        return True
    else :
        return False


def get_gamertag (user) :
    db = database.Database()

    if has_gamertag(user):
        gamertags = db.fetchAll("select gamertag from gamertags where member_id = %s",[user])
        return gamertags[0]['gamertag']

    else :
        return None

    db.close()

# logs a message to the bot log channel
def log_event(message) :
    try :
        print(message)
        slack_client.api_call("chat.postMessage", channel=log_chat,text=message, as_user=True)
    except :
        print("error logging")


# posts text to a specified channel
def post_to_channel(channel,text):
    try:
        slack_client.api_call("chat.postMessage", channel=channel,text=text, as_user=True)
    except :
        log_event("failed to post to channel: " + str(channel) + ": " + str(text))


# bot sends a private message to the user (used in non solicited messages)
def send_private_message(user, message) :
    # create channel
    call = "im.open?user="+user
    response = slack_client.api_call(call)

    slack_client.api_call("chat.postMessage", channel=response['channel']['id'], text=message, as_user=True)


# returns true if the incomming channel is an IM
def is_private_conversation(channel):
    response = slack_client.api_call("conversations.info?channel="+channel)
    if response['channel']['is_im'] == False:
        return False
    else :
        return True


# get's the user's name in slack
def get_slack_name(user_id) :
    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']

    return slack_name


# checks to see if there has been a name update
def update_name(user_id,current_name) :
    db = database.Database()

    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']
    if current_name != slack_name :
        # alert general chat as well as the log
        message = "user "+current_name+" has changed their name in slack and is now known as "+slack_name
        log_event(message)
        db.runSql("update member_orientation set member_name =%s where member_id = %s",[slack_name,user_id])
        slack_client.api_call("chat.postMessage", channel=general_chat.upper(), 
                              text=message, as_user=True)

    db.close()


def orientation_completed(user_id) :
    result = True

    db = database.Database()
    member = db.fetchAll("select * from member_orientation where member_id = %s",[user_id])
    db.close()

    if member[0]['date_completed'] is None : 
        result = False

    return result


# tries to parse an event ID from a user input.  Returns 0 if the event is not valid. Returns -1 if the event was deleted
def parse_event_from_command(user, command) : 
    event_id = 0
    response = "something went wrong join_event"
    # parse the number from the command
    str_cmd = str(command)
    try :
        event_id = int(''.join([c for c in str_cmd if c in '0123456789']))
    except :
        bot_utilities.log_event("user "+ user + " provided an invalid event id: " + command)

    # check and see if the user provided a value at all
    if event_id == 0 :
        response = "You need to include the event ID in your request. To list available events, type @og_bot list events."

    else :
        db = database.Database()
        records = db.fetchAll("""
                                select e.*, em.member_id, mo.member_name as created_name
                                from events e 
                                inner join member_orientation mo on e.created_by = mo.member_id
                                left outer join event_members em on e.event_id = em.event_id
                                where e.record_complete = 1 and e.start_date > now() - interval 3 hour and e.event_id = %s
                            """,[event_id])
        db.close()
        # ensure the selected event is valid and in the future
        if len(records) == 0 :
            event_id = 0
            response = "That's not a valid event ID in the future. Type \"@og_bot list events\" to see a list of valid events."
            bot_utilities.log_event("user "+ user + " provided an invalid event id: " + command)
            
            return event_id, response, None

        if records[0]['deleted'] is not None: # valid but deleted
            event_id = -1
            response = "That event has been deleted."
            return event_id, response, records[0]

        else :
            return event_id, response, records[0]

    return event_id, response, None


# tries to find a number in the command and returns it
def parse_number_from_command(command):
    str_cmd = str(command)
    try :
        num_found = int(''.join([c for c in str_cmd if c in '0123456789']))
    except :
        return 0

    return num_found

# returns true if the user is in an event.  False if they are not
def user_is_in_event(user, event_id): 
    db = database.Database()
    records = db.fetchAll("select * from event_members where event_id = %s and member_id = %s",[event_id,user])
    if len(records)  > 0 :
        return True
    else :
        return False

    db.close()




# determine if the user is actively going through the event creation process.
def actively_creating_event (user_id):
    result = True
    db = database.Database()
    events = db.fetchAll("select * from events where created_date > now() - interval %s minute and record_complete = 0 and created_by = %s and deleted is null",[timeout_min,user_id])
    db.close()
    if len(events) == 0 :
        result = False
    return result



# scheduled job to check for people to remind for events
def event_reminders():
    db = database.Database()
    
    #get list of people to remind. Must be in the future, haven't been reminded yet, and within the reminder threshhold
    members = db.fetchAll("""
                            select em.*, e.event_id, e.title, e.start_date
                            from event_members em
                            inner join events e on e.event_id = em.event_id
                            where reminder_sent = 0 and e.start_date - interval %s minute < now() and e.start_date > now() and e.deleted is null
                            """,[reminder_min])
    
    for member in members: 
        t = member['start_date'] - datetime.datetime.now()
        min_to_start = str(divmod(t.days * 86400 + t.seconds, 60)[0])
        rounded_min = int(5 * round(float(int(min_to_start))/5)) # round to to the nearest 5 min
        send_private_message(member['member_id'],"Your upcoming event ("+ member['title']+") is scheduled to start in about "+ str(rounded_min) + " minutes. \nFor more info on the event, type @og_bot event info "+ str(member['event_id']))

        log_event(member['member_id'] + " was reminded of upcoming event " + str(member['event_id']))

    
    #update the db to indicate they have been reminded
    db.runSql("""
                update event_members em
                inner join events e on e.event_id = em.event_id
                set em.reminder_sent = 1
                where reminder_sent = 0 and e.start_date - interval %s minute < now() and e.start_date > now() and e.deleted is null
                """,[reminder_min])
    db.close()



# determines the state of the user's orientation
def evaluate_user(user) :
    db = database.Database()
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])
    record = user_record[0]
    
    # if rules are outstanding, prompt them
    if record["accepted"] == 0:
        bot_utilities.log_event("user "+ record['member_name'] + " has been prompted for rules")

        bot_prompts.prompt_rules(user,record["private_channel"])

    # if name is outstanding, prompt them
    elif record["accepted"] == 1 and record["name_correct"] == 0 :
        bot_utilities.log_event("user "+ record['member_name'] + " has been prompted for name")
        bot_prompts.prompt_username(user,record["private_channel"])

    # if club is outstanding, prompt them
    elif record["accepted"] == 1 and record["name_correct"] == 1 and record["in_club"] == 0 :
        bot_utilities.log_event("user "+ record['member_name'] + " has been prompted for club")
        bot_prompts.prompt_club(user,record["private_channel"])
    db.close()


# returns true if the user is active in slack
def user_is_active(user):
    response = slack_client.api_call("users.info",user = user)

    if response['ok'] == True :
        if response['user']['deleted'] == True :
            return False
        else : 
            return True
    else :
        return False


# if someone doesn't complete orientation, send them an update. Also notify the leaders if there is an exceptionally long period
def orientation_nag() :
    db = database.Database()
    orientations = db.fetchAll("select * from member_orientation where last_updated < now() - interval %s hour and date_completed is null and inactive = 0", [nag_hours])      


    # for each person, send them a private message
    for orientation in orientations:
        # see if they are still active
        isActive = user_is_active(orientation['member_id'])

        if isActive == True :
            bot_utilities.log_event(orientation['member_name']+" did not complete orientation and has been nagged")
            slack_client.api_call("chat.postMessage", channel=orientation['private_channel'],
                    text="Sorry to bother, but we didn't get a chance to finish and my owner will delete me if I don't do my job.", as_user=True)
            evaluate_user(orientation['member_id']) #continues with the orientation
            db.runSql("update member_orientation set nag_count = nag_count + 1 where member_id = %s",[orientation['member_id']])

            if (orientation['nag_count'] + 1) % nag_threshhold == 0 : # for anyone that has hit our threshhold, send a message to leader chat
                message = "Notice: " + orientation['member_name'] + " has not completed oritation in " + str(orientation['nag_count'] + 1 ) + " days."
                slack_client.api_call("chat.postMessage", channel=leader_chat, text=message, as_user=True)

        else :
            db.runSql("update member_orientation set inactive = 1 where member_id = %s",[orientation['member_id']])
            log_event("User " + orientation['member_id'] + " was attempted to be nagged but is now inactive")

                    
    db.close()



# gets json from the requested url
def getPage(url, proxies=''):
    try:
        return request(url, proxies)
    except:
        return request(url, proxies) #Retry

def request(url, proxies=''):
    reqHeaders = {'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.101 Safari/537.36',
                  #'X-API-Key': 'c18b20ce8a54453c96d962e2e639f4b0'
                  }
    
    page = requests.get(url, headers = reqHeaders, proxies=proxies, timeout=45)
    
    try: 
        data = page.json()
    except :
        return None

    return data





if __name__ == "__main__": #to depricate
    arguments = sys.argv[1:]

    if arguments[0] == "event_reminders" :
        event_reminders()

    
        
   