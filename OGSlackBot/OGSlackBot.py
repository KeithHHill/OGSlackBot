
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


    print("config loaded \n")

except:
    print ("Error reading the config file")

AT_BOT = "<@" + BOT_ID + ">"
EXAMPLE_COMMAND = "do"

slack_client = SlackClient(token)



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


def new_user_detected(user):
    
    # create new private channel
    call = "im.open?user="+user
    response = slack_client.api_call(call)
    channel = response["channel"]["id"]
        
    # add them to the database
    call = "users.info?user="+user
    user_info = slack_client.api_call(call)

    slack_client.api_call("chat.postMessage", channel=str(general_chat).upper(),
                            text="welcome to the clan "+user_info["user"]["name"]+". Please check your private messages to get some info about the group.", as_user=True)
     
    db = database.Database()

    db.runSql(""" replace into member_orientation
                    (member_id,member_name,last_updated,private_channel,date_started, date_completed, nag_count)
                    Values
                    (%s,%s,now(),%s,now(),null,0)
    """,[user,user_info["user"]["name"],channel])
    
    db.close()

    evaluate_user(user)
    





def handle_yes_no(command, channel, user) :
    # determine what step of the orientation we are on
    db = database.Database()
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
                bot_utilities.log_event("user "+ record['member_name'] + " accepted the rules")
                

                message = "Awesome.  See, the rules weren't so tough."
                db.runSql("""update member_orientation set last_updated= now(), prompted_accept = 0, accepted = 1, prompted_for_name = 0, prompted_for_club = 0 where member_id = %s
                """,[user])

                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                # find the next prompt
                evaluate_user(user)


            else : #user declines
                bot_utilities.log_event("user "+ record['member_name'] + " declined the rules")
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
                bot_utilities.log_event("user "+ record['member_name'] + " accepted the name")
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                db.runSql("""update member_orientation set last_updated= now(), name_correct = 1, prompted_for_name = 0 where member_id = %s
                """,[user])

                evaluate_user(user)

            else: #user needs to correct the name
                bot_utilities.log_event("user "+ record['member_name'] + " needed help with the name")

                message ="""Not a problem, it's easy to change.  On desktop, click "Original Guardians" and click "Profile and Account".  From mobile, tap the ellipsis (...) and tap your name.  From there you can change it."""
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                message ="""Once you have that done, just type 'done' so I know."""
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

        # is user in the xbox club?
        elif record["prompted_for_club"] == 1 :
            if command == "yes":
                bot_utilities.log_event("user "+ record['member_name'] + " accepted the club")
                message = "And we're done.  Thanks for joining the group and make sure you join all of the channels that interest you."
                slack_client.api_call("chat.postMessage", channel=channel,
                            text=message, as_user=True)

                db.runSql("""update member_orientation set last_updated= now(), in_club = 1, prompted_for_club = 0, date_completed = now() where member_id = %s
                """,[user])

            else :
                bot_utilities.log_event("user "+ record['member_name'] + " needs invited to the club")
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
    db.close()

                



#handle the responses
def handle_command(command, channel, user):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    try :
        db = database.Database()
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
                bot_utilities.log_event("user "+ record['member_name'] + " accepted the name")
                response = "Great, another box checked.  Moving right along."
                db.runSql("""update member_orientation set last_updated= now(), name_correct = 1, prompted_for_name = 0 where member_id = %s
                    """,[user])
            
                slack_client.api_call("chat.postMessage", channel=channel,
                                text=response, as_user=True)
                bot_utilities.update_name(record['member_id'],record['member_name'])
                evaluate_user(user)
                deffered = True

            elif record["prompted_for_club"] == 1:
                bot_utilities.log_event("user "+ record['member_name'] + " accepted the club")
                message = "And we're done.  Thanks for joining the group and make sure you join all of the channels that interest you."
                slack_client.api_call("chat.postMessage", channel=channel,
                                text=message, as_user=True)

                db.runSql("""update member_orientation set last_updated= now(), in_club = 1, prompted_for_club = 0, date_completed = now() where member_id = %s
                    """,[user])
                deffered = True


        if deffered == False :
            slack_client.api_call("chat.postMessage", channel=channel,
                                text=response, as_user=True)
        db.close()

    except:
        bot_utilities.log_event("An unhandled error was encountered - handle_command")
        bot_utilities.log_event(output['channel']+" " + output['user'])


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    try :
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

    except :
        bot_utilities.log_event("An unhandled error was encountered - parse_slack_output")
        bot_utilities.log_event(output['channel']+" " + output['user'])


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose 
    seconds = 0
    if slack_client.rtm_connect():
        bot_utilities.log_event("OG Bot connected and running!")
        while True:
            command, channel, user = parse_slack_output(slack_client.rtm_read())
            if command and channel:
                handle_command(command, channel, user)
            
            seconds += 1

            

            # we check for new users in the general chat
            if seconds % 60 == 0  and test_mode != "TRUE":
                db = database.Database()
                call = "channels.info?channel="+str(general_chat).upper()
                response = slack_client.api_call(call)
                channel_members = response['channel']['members']
                clan_members = list(db.fetchAll("select member_id from member_orientation"))
                
                clan_members_string = ''.join(str(e) for e in clan_members)

                for channel_member in channel_members :
                    # find new user
                    if str(channel_member) not in clan_members_string : #complete hack but w/e
                        bot_utilities.log_event("new user detected: " + channel_member)
                        new_user_detected(channel_member)
                db.close()
                

            # perform check to nag people that stopped payting attention
            if seconds >= 3600:
                seconds = 0
                db = database.Database()
                orientations = db.fetchAll("select * from member_orientation where last_updated < now() - interval %s hour and date_completed is null", [nag_hours])      
                # bot_utilities.log_event("checking for people to nag")
                for orientation in orientations:
                    bot_utilities.log_event(orientation['member_name']+" did not complete orientation and has been nagged")
                    slack_client.api_call("chat.postMessage", channel=orientation['private_channel'],
                            text="Sorry to bother, but we didn't get a chance to finish and my owner will delete me if I don't do my job.", as_user=True)
                    evaluate_user(orientation['member_id'])
                    db.runSql("update member_orientation set nag_count = nag_count + 1 where member_id = %s",[orientation['member_id']])

                
                # bot_utilities.log_event("looking for name changes")
                users = db.fetchAll("select * from member_orientation")
                for user in users:
                    bot_utilities.update_name(user['member_id'],user['member_name'])
                    
                db.close()
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        bot_utilities.log_event("Connection failed. Invalid Slack token or bot ID?")

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



