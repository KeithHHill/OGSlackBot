
# Author: Keith Hill
# Date: 9/12/2017
#
# https://api.slack.com/methods

import os
import time
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_prompts

# get config
myPath = os.path.dirname(os.path.abspath(__file__))
db = database.Database()

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


    print("config loaded \n")

except:
    print ("Error reading the config file")

AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

slack_client = SlackClient(token)

def log_event(message) :
    print(message)
    slack_client.api_call("chat.postMessage", channel=log_chat,text=message, as_user=True)


def update_name(user_id,current_name) :
    call = "users.info?user="+user_id
    response = slack_client.api_call(call)
    slack_name = response['user']['name']
    if response['user']['profile']['display_name'] != "" :
        slack_name = response['user']['profile']['display_name']
    if current_name != slack_name :
        log_event("user "+current_name+" has changed their name in slack and is now known as "+slack_name)
        db.runSql("update member_orientation set member_name =%s where member_id = %s",[slack_name,user_id])


def evaluate_user(user) :
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])
    record = user_record[0]
    
    # if rules are outstanding, prompt them
    if record["accepted"] == 0:
        log_event("user "+ record['member_name'] + " has been prompted for rules")

        bot_prompts.prompt_rules(user,record["private_channel"])

    # if name is outstanding, prompt them
    elif record["accepted"] == 1 and record["name_correct"] == 0 :
        log_event("user "+ record['member_name'] + " has been prompted for name")
        bot_prompts.prompt_username(user,record["private_channel"])

    # if club is outstanding, prompt them
    elif record["accepted"] == 1 and record["name_correct"] == 1 and record["in_club"] == 0 :
        log_event("user "+ record['member_name'] + " has been prompted for club")
        bot_prompts.prompt_club(user,record["private_channel"])


def new_user_detected(user):
    
    # create new private channel
    call = "im.open?user="+user
    response = slack_client.api_call(call)
    channel = response["channel"]["id"]
        
    # add them to the database
    call = "users.info?user="+user
    user_info = slack_client.api_call(call)

 
    if test_mode == 'TRUE':
        db.runSql(""" replace into member_orientation
                        (member_id,member_name,last_updated,private_channel)
                        Values
                        (%s,%s,now(),%s)
        """,[user,user_info["user"]["name"],channel])
    else:
        db.runSql(""" insert ignore member_orientation
                        (member_id,member_name,last_updated,private_channel)
                        Values
                        (%s,%s,now(),%s)
        """,[user,user_info["user"]["name"],channel])

    evaluate_user(user)





def handle_yes_no(command, channel, user) :
    # determine what step of the orientation we are on
    user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
    """,[user])

    message = "Hmmm...I don't know what you mean.  If you are having problems, please contact keith-diknak"

    if len(user_record) == 0 :
        message = "Hmmm...I don't know what you mean.  If you are having problems, please contact keith-diknak"

        slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)
    else :
        record = user_record[0]
        
        # is user accepting rules?
        if record["prompted_accept"] == 1 :
            if command == "yes" :
                log_event("user "+ record['member_name'] + " accepted the rules")
                

                message = "Awesome.  See, the rules weren't so tough."
                db.runSql("""update member_orientation set last_updated= now(), prompted_accept = 0, accepted = 1, prompted_for_name = 0, prompted_for_club = 0 where member_id = %s
                """,[user])

                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                # find the next prompt
                evaluate_user(user)


            else : #user declines
                log_event("user "+ record['member_name'] + " declined the rules")
                message = "Ouch...sorry there is an issue. The clan leaders have been notifed and will reach out to you soon.  Sit tight."

                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)
                
                call = "users.info?user="+user
                user_info = slack_client.api_call(call)

                slack_client.api_call("chat.postMessage", channel=leader_chat,
                            text="Notice: User "+ user_info["user"]["name"] +" is going through orientation and has declined the rules.  Please reach out.", as_user=True)
        
        # is the user accepting the name?
        elif record["prompted_for_name"] ==1 :
            if command == "yes":
                message = "Great, another box checked.  Moving right along."
                log_event("user "+ record['member_name'] + " accepted the name")
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                db.runSql("""update member_orientation set last_updated= now(), name_correct = 1, prompted_for_name = 0 where member_id = %s
                """,[user])

                evaluate_user(user)

            else: #user needs to correct the name
                log_event("user "+ record['member_name'] + " needed help with the name")

                message ="""Not a problem, it's easy to change.  On desktop, click "Original Guardians" and click "Profile and Account".  From mobile, tap the ellipsis (...) and tap your name.  From there you can change it."""
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                message ="""Once you have that done, just type 'done' so I know."""
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

        # is user in the xbox club?
        elif record["prompted_for_club"] ==1 :
            if command == "yes":
                log_event("user "+ record['member_name'] + " accepted the club")
                message = "And we're done.  Thanks for joining the group and make sure you join all of the channels that interest you."
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                db.runSql("""update member_orientation set last_updated= now(), in_club = 1, prompted_for_club = 0 where member_id = %s
                """,[user])

            else :
                log_event("user "+ record['member_name'] + " needs invited to the club")
                message = "This is our last step for bringing you on board.  Please search for the Original Guardians club or ask a leader to send an invitation."
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                message ="""Once you have that done, just type 'done' so I know."""
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                #send a message to the leader chat
                call = "users.info?user="+user
                user_info = slack_client.api_call(call)

                slack_client.api_call("chat.postMessage", channel=leader_chat,
                            text="Notice: User "+ user_info["user"]["name"] +" is going through orientation and needs an Xbox Club invitation.", as_user=True)

                



#handle the responses
def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = "Sorry, I'm kind of a dumb robot.  I have no idea what you mean. Type 'help' to learn about me"
    deffered = False
    
    if command.startswith('hi') or command.startswith('hello'):
        response = "well hello there Guardian"
    elif command.startswith('help') :
        response = "My purpose is to help the clan stay organized and welcome new people to the group. I'll bug you if needed but otherwise I'll keep to myself."
    
        # test the system
    elif command.startswith("pretend i'm new") or command.startswith("pretend i am new"):
        response ="Welcome guardian! I'm the OG Bot and I'm going to help you get started.  Check your private messages."
        new_user_detected(user)
    
    
    #likely going through the orientation
    elif command.startswith("yes") or command.startswith("no") :
        handle_yes_no(command,channel,user)
        deffered = True


    #probably coming in from the name check process or the club check process
    elif command.startswith("done") :
        user_record = db.fetchAll("""
                        select * from member_orientation where member_id = %s
                        """,[user])
        record = user_record[0]
        
        if record["prompted_for_name"]  == 1:
            log_event("user "+ record['member_name'] + " accepted the name")
            response = "Great, another box checked.  Moving right along."
            db.runSql("""update member_orientation set last_updated= now(), name_correct = 1, prompted_for_name = 0 where member_id = %s
                """,[user])
            
            slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)
            update_name(record['member_id'],record['member_name'])
            evaluate_user(user)
            deffered = True

        elif record["prompted_for_club"] == 1:
            log_event("user "+ record['member_name'] + " accepted the club")
            message = "And we're done.  Thanks for joining the group and make sure you join all of the channels that interest you."
            slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

            db.runSql("""update member_orientation set last_updated= now(), in_club = 1, prompted_for_club = 0 where member_id = %s
                """,[user])
            deffered = True


    if deffered == False :
        slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            #print ("\n")
            #print(output)
            #print ("\n")
                        
            
            
            if output and 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed
                output['text'] = output['text'].replace(u"\u2019", '\'')
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel'], \
                       output['user']
            
            #handle im conversations without needing @
            elif output and 'text' in output and output['user'] != BOT_ID:
                output['text'] = output['text'].replace(u"\u2019", '\'')
                

                response = slack_client.api_call("im.list")
                ims = response["ims"]
                for im in ims :
                    if im["id"] == output['channel']:
                        return output['text'].lower(), \
                               output['channel'], \
                               output['user']
    return None, None, None


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose 
    seconds = 0
    if slack_client.rtm_connect():
        log_event("OG Bot connected and running!")
        while True:
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, user)
            
            seconds += 1



            # we check for new users in the general chat
            if seconds % 60 == 0 :
                call = "channels.info?channel="+str(general_chat).upper()
                response = slack_client.api_call(call)
                channel_members = response['channel']['members']
                clan_members = list(db.fetchAll("select member_id from member_orientation"))
                
                clan_members_string = ''.join(str(e) for e in clan_members)

                for channel_member in channel_members :
                    # find new user
                    if str(channel_member) not in clan_members_string : #complete hack but w/e
                        log_event("new user detected: " + channel_member)
                        new_user_detected(channel_member)

                

            # perform check to nag people that stopped payting attention
            if seconds >= 3600:
                seconds = 0
                orientations = db.fetchAll("select * from member_orientation where last_updated < now() - interval %s hour and (accepted = 0 or name_correct = 0 or in_club = 0)", [nag_hours])      
                log_event("checking for people to nag")
                for orientation in orientations:
                    log_event(orientation['member_name']+" did not complete orientation and has been nagged")
                    slack_client.api_call("chat.postMessage", channel=orientation['private_channel'],
                            text="Sorry to bother, but we didn't get a chance to finish and my owner will delete me if I don't do my job.", as_user=True)
                    evaluate_user(orientation['member_id'])

                
                log_event("looking for name changes")
                users = db.fetchAll("select * from member_orientation")
                for user in users:
                    update_name(user['member_id'],user['member_name'])
                    

            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        log_event("Connection failed. Invalid Slack token or bot ID?")

# use this to get your bot ID for the config file

#BOT_NAME = 'og_bot'
#
#if __name__ == "__main__":
#    api_call = slack_client.api_call("users.list")
#    if api_call.get('ok'):
#        # retrieve all users so we can find our bot
#        users = api_call.get('members')
#        for user in users:
#            if 'name' in user and user.get('name') == BOT_NAME:
#                print("Bot ID for '" + user['name'] + "' is " + user.get('id'))
#    else:
#        print("could not find bot user with the name " + BOT_NAME)



