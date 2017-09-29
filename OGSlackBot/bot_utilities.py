import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_utilities

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
    test_mode = config.get('config','test_mode')
    timeout_min = config.get('events','timeout_min')


except:
    print ("Error reading the config file")

slack_client = SlackClient(token)

def log_event(message) :
    print(message)
    slack_client.api_call("chat.postMessage", channel=log_chat,text=message, as_user=True)


def send_private_message(user, message) :
    # create channel
    call = "im.open?user="+user
    response = slack_client.api_call(call)

    slack_client.api_call("chat.postMessage", channel=response['channel']['id'], text=message, as_user=True)


def get_slack_name(user_id) :
    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']

    return slack_name


def update_name(user_id,current_name) :
    db = database.Database()

    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']
    if current_name != slack_name :
        log_event("user "+current_name+" has changed their name in slack and is now known as "+slack_name)
        db.runSql("update member_orientation set member_name =%s where member_id = %s",[slack_name,user_id])

    db.close()


def orientation_completed(user_id) :
    result = True

    db = database.Database()
    member = db.fetchAll("select * from member_orientation where member_id = %s",[user_id])
    db.close()

    if member[0]['date_completed'] is None : 
        result = False

    return result

# tries to parse an event ID from a user input.  Returns 0 if the event is not valid
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
                                where e.record_complete = 1 and e.start_date > now() and e.event_id = %s
                            """,[event_id])
        db.close()
        # ensure the selected event is valid and in the future
        if len(records) == 0 :
            event_id = 0
            response = "That's not a valid event ID in the future. Type \"@og_bot list events\" to see a list of valid events."
            bot_utilities.log_event("user "+ user + " provided an invalid event id: " + command)
            
            return event_id, response, None

        else :
            return event_id, response, records[0]

    return event_id, response, None


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
    events = db.fetchAll("select * from events where created_date > now() - interval %s minute and record_complete = 0 and created_by = %s",[timeout_min,user_id])
    db.close()
    if len(events) == 0 :
        result = False
    return result

