import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database

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


# determine if the user is actively going through the event creation process.
def actively_creating_event (user_id):
    result = True
    db = database.Database()
    events = db.fetchAll("select * from events where created_date > now() - interval %s minute and record_complete = 0 and created_by = %s",[timeout_min,user_id])
    db.close()
    if len(events) == 0 :
        result = False
    return result

