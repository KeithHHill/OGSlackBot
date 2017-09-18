import os
import time
import ConfigParser 
import sys
from slackclient import SlackClient
import database


db = database.Database()
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    token = config.get('config','key')
    rules = str(config.get('config','rules'))
    
    
except:
    print ("Error reading the config file")

slack_client = SlackClient(token)
rules = str.replace(rules,'|','\n')

# this function prompts the user with rules
def prompt_rules (user, channel):
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])
    record = user_record[0]

    db.runSql("""update member_orientation set last_updated= now(), prompted_accept = 1, prompted_for_name = 0, prompted_for_club = 0 where member_id = %s""",[user])

    print("user "+ record['member_name'] + " has been prompted for rules")

    message = "Hi, and welcome to the clan. We're a chill group of people but we like to be organized so we are going to go through some steps to get you settled."
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=message, as_user=True)
    message = "First, we don't have many rules but here they are:"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=message, as_user=True)
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=rules, as_user=True)
    message = "Is that cool with you? (type 'yes' or 'no')"
    slack_client.api_call("chat.postMessage", channel=channel,
                          text=message, as_user=True)




# this function makes sure that we are getting the user to make sure the name matches the xbox gamertag
def prompt_username(user,channel):
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])
    record = user_record[0]

    #name hasn't been confirmed but they are prompted
    if record["name_correct"] == 0:
        print("user "+ record['member_name'] + " has been prompted for name")

        message = """To reduce confusion when clan members are trying to find you on xbox, your gamertag needs to be the same as your slack name. If there is a space in your gamertag, use an _ here.  As a bonus, you can put your real name as well with a - splitting them such as keith-diknak.  Does your name match your gamertag? (please respond 'yes' or 'no')"""

        slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)
        db.runSql("""update member_orientation set last_updated= now(), prompted_accept = 0, prompted_for_name = 1, prompted_for_club = 0 where member_id = %s""",[user])


# this function will ask the user if they are in the xbox club
def prompt_club(user,channel):
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])
    record = user_record[0]

    if record["in_club"] == 0:
        print("user "+ record['member_name'] + " has been prompted for club")

        message = "While all of our communication is in slack, all members should be in the OG club too because we often organize groups that way. Are you currently in the Xbox Club for the clan? (please respond 'yes' or 'no')"
        
        slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)
        db.runSql("""update member_orientation set last_updated= now(), prompted_accept = 0, prompted_for_name = 0, prompted_for_club = 1 where member_id = %s""",[user])