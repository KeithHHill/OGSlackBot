# Author: Keith Hill
# Date: 2/12/2019

import bot_utilities
import database
import os
import ConfigParser


# get config
myPath = os.path.dirname(os.path.abspath(__file__))

try: 
    config = ConfigParser.ConfigParser()
    config.read(myPath+"\config.ini")
    conv_timeout_min = int(config.get('config','conv_timeout_min'))

except:
    print ("Error reading the config file")



# determines if the user has an ongoing conversation with the bot regarding collection of the gamertag.  Returns false if the conversation is over or stale
def has_going_conversation (user) :
    db = database.Database()    
    records = db.fetchAll("select * from gamertags where member_id =%s and conversation_date > now() - interval %s minute",[user,conv_timeout_min])
    db.close()

    if len(records) == 0 :
        return False
    else :
        return True


# user needs the gamertag mapped and this function handles the conversation
def handle_conversation (command, channel, user):
    # conversation status
    # 0 = new entry.  Awaiting response
    # 1 = gamertag has been mapped

    db = database.Database()

    gamertags = db.fetchAll("""
        select g.* 
        from gamertags g
        inner join member_orientation on g.member_id = member_orientation.member_id
        where g.member_id = %s
    """,[user])


    if len(gamertags) == 0 : # record not found.  need to create one
        db.runSql("replace into gamertags (member_id, conversation_status, conversation_date) values(%s, 0, now())",[user])
        bot_utilities.post_to_channel(channel,"It looks like I don't have your gamertag on record.  What is it? (include nothing but your gamertag in the response)")
        bot_utilities.log_event("user " + user + " has begun mapping a gamertag: " + command)
        return None

    # do we have a fresh conversation?
    active_conversation = has_going_conversation(user)


    if active_conversation and gamertags[0]["conversation_status"] == 0 :  # active conversation and awaiting response.  This should be the user's gamertag.
        db.runSql("update gamertags set gamertag = %s, last_updated = now(), conversation_status = 1, conversation_date = Null where member_id = %s",[command,user])
        bot_utilities.post_to_channel(channel,"Great, I have set your gamertag to be "+ command + ". If that's not right, simply say 'change gamertag'")
        bot_utilities.log_event("user "+ user + " has mapped gamertag: " + command)
        return None
   
    elif active_conversation == False and gamertags[0]["conversation_status"] == 0 :  # stale conversation.  Let's refresh.

        db.runSql("update gamertags set conversation_date = now() where member_id = %s",[user])
        bot_utilities.post_to_channel(channel,"I still need to get your gamertag.  What is it?  {include nothing but your gamertag in the response)")
        return None


    print(active_conversation)
    db.close()


