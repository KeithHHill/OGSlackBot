import os
import time
import datetime
import ConfigParser
import sys
from slackclient import SlackClient
import database
import bot_utilities
from dateutil import parser

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


except:
    print ("Error reading the config file")

slack_client = SlackClient(token)


# return information regarding an event
def event_info(command, channel, user) :
    # prase the response
    event_id, response, event = bot_utilities.parse_event_from_command(user,command)

    if event_id > 0 : # valid event id was entered
        bot_utilities.log_event("user "+ user + " successfully retreived event info for event "+ str(event_id))
        db = database.Database()
        players = db.fetchAll("""
                                select em.event_id, em.member_id, mo.member_name, em.date_created
                                from event_members em
                                inner join member_orientation mo on em.member_id = mo.member_id
                                where em.event_id = %s
                                order by em.date_created desc
                                """,[event_id])
        db.close()
        response = event['title'] + "\n"+ \
                    str(event['start_date'].strftime("%I:%M %p")) + " EST on " + str(event['start_date'].strftime("%A %m/%d")) + \
                    "\n______\n"+event['descr']+"\nCreated by: " +event['created_name'] + "\n______\nPlayers (" + str(len(players))+"):\n"

        for player in players :
            response = response + player['member_name'] + "\n"

        response = response + "\nTo join, type @og_bot join event " + str(event_id)
            
    slack_client.api_call("chat.postMessage", channel=channel,
                        text=response, as_user=True)


# creating a new event record
def create_new_event (command, channel, user):
    db = database.Database()
    
    # only save origin channel if it wasn't in an IM
    if bot_utilities.is_private_conversation(channel):
        origin_channel = None
    else :
        origin_channel = channel

    # we need the member name
    members = db.fetchAll("select * from member_orientation where member_id = %s",[user])
    member = members[0]
    
    # blow away any previously incomplete events
    db.runSql("delete from events where record_complete = 0 and created_by = %s",[user])

    # create the record
    db.runSql("""insert into events (created_date, created_by,origin_channel,current_prompt)
					Values
					(now(),%s,%s,"start")
                    """
                    ,[user,origin_channel])
    
    # get event ID
    events = db.fetchAll("select * from events where created_by = %s and record_complete = 0 order by created_date desc limit 1",[user])

    bot_utilities.log_event(str(member['member_name']) + " has begun the event creation process. Event ID " + str(events[0]['event_id']))

    # post success message 
    slack_client.api_call("chat.postMessage", channel=channel,
                            text="Creating a new event.  Please enter the start date and time in EST. \nFor reference, it is now " + str(datetime.datetime.now().strftime("%m/%d/%y %I:%M %p")) , as_user=True)


# the user has been prompted for a start date/time. This function needs to handle the command
def update_event_time(command, channel, user, event_id) :
    success = False
    response = "something went wrong update_event_time"
    
    
    # check for bad formats
    try :
        parsed_response = parser.parse(command)
        success = True
    except :
        response = "Hmm, I can't figure out what time you're trying to give me.  Make sure it is in the format MM/DD/YYYY HH:MM PM/AM"
        bot_utilities.log_event("Failed at parsing time. Input was: "+command)


    if success == True :
        # verify not in the past
        if parsed_response < datetime.datetime.now() :
            response = "Did you invent a time machine? Your start time needs to be in the future. Try again."

        else :
            # update the database and get ready for the next prompt
            db = database.Database()
            start_date_str = str(parsed_response.strftime("%Y-%m-%d %H:%M:%S"))
            db.runSql("update events set start_date = %s, current_prompt = \"title\" where event_id = %s",[start_date_str,event_id])
            
            #send response
            bot_utilities.log_event("Event "+ str(event_id) + " start time updated: " + start_date_str)
            response = "Great. Your event will start at " + str(parsed_response.strftime("%I:%M %p")) + " EST on " + str(parsed_response.strftime("%A %m/%d")) + ". (if this is wrong, just start over)\n Please provide a title for the event (25 characters or less)"
            
            db.close()
          

    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)


# update the title for an event
def update_event_title(command, channel, user, event_id):
    response = "something went wrong update_event_title"

    if command.__len__() > 25 or command.__len__() < 3 :
        response = "Title length must be between 3 and 25 characters.  Please try again."
        bot_utilities.log_event("user " + user + " provided an invalid event title: "+ command)
    else :
        db = database.Database()
        
        #update the db and get ready for the next prompt
        db.runSql("update events set title = %s, current_prompt = \"descr\" where event_id = %s",[command,event_id])
        db.close()
        response = "Great. Your event title has been updated to " + command + "\n Now let's give your event a description. If there are requirements, please include them here."
        bot_utilities.log_event("Event: " + str(event_id) + " title updated: " + str(command))

    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)



# Update the description for an event
def update_event_descr(command, channel, user, event_id):
    response = "something went wrong update_event_descr"

    if command.__len__() > 300 :
        response = "Description length must be 300 characters or less.  Please try again."
    else :
        db = database.Database()
        
        #update the db and get ready for the next prompt
        db.runSql("update events set descr = %s, current_prompt = null, record_complete = 1 where event_id = %s",[command,event_id])
        response = "Great. Your event description has been updated. Your event ID is " + str(event_id) + ". Others can join it by typing @og_bot join event "+ str(event_id)
        bot_utilities.log_event("Event: " + str(event_id) + " description updated: " + str(command))

        events = db.fetchAll("select * from events where event_id = %s",[event_id])
        event = events[0]

        if event['origin_channel'] is None :
            db.runSql("update events set current_prompt = \"channel\", record_complete = 0 where event_id = %s",[event_id])
            response = "Almost done. If you would like to assign this to a specific channel please use # and link the channel. Otherwise, just respond 'done'"

        else : # event is done. auto join event
            db.runSql("insert into event_members (event_id,member_id,date_created) values(%s,%s,now()) on duplicate key update event_id = event_id, member_id = member_id",[event_id,user])

        db.close()

    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)



# Assign a channel from the user's input
def assign_event_channel(command, channel, user, event_id) :
    response = "something went wrong"
    db = database.Database()

    if command == "done" : 
        response = "Great. Your event is created. Your event ID is " + str(event_id) + ". Others can join it by typing @og_bot join event "+ str(event_id)
        bot_utilities.log_event("user " + user + " decided not to assign a channel to event " + str(event_id))
        db.runSql("update events set record_complete = 1, current_prompt = null where event_id = %s",[event_id])
        db.runSql("insert into event_members (event_id,member_id,date_created) values(%s,%s,now()) on duplicate key update event_id = event_id, member_id = member_id",[event_id,user])

    else :
        # strip channel
        stripped_channel = ""
        counter = 2
        while counter < len(str(command)) :
            if command[counter] == "|" :
                break
            else :
                stripped_channel = stripped_channel + command[counter]
            counter += 1

        stripped_channel = str(stripped_channel.upper())


        # check if valid channel
        channel_info = slack_client.api_call("conversations.info?channel=" + stripped_channel)
        if channel_info['ok'] == False :
            response = "Sorry, that doesn't look like a valid channel to me.  Please try again."
            bot_utilities.log_event("user " + user + " attempted to link a channel to an event and provited an invalid channel: "+ command)
        
        else : # it is valid - update the database
            # update the database
            response = "Great. Your event description has been updated. Your event ID is " + str(event_id) + ". Others can join it by typing @og_bot join event "+ str(event_id)
            bot_utilities.log_event("user " + user + " added a channel to event " + str(event_id))
            db.runSql("update events set origin_channel = %s, current_prompt = null, record_complete = 1 where event_id = %s",[stripped_channel,event_id])
            
            # auto add user to event
            db.runSql("insert into event_members (event_id,member_id,date_created) values(%s,%s,now()) on duplicate key update event_id = event_id, member_id = member_id",[event_id,user])
    
            #blast the channel
            events = db.fetchAll("""
                                select e.*, mo.member_name
                                from events e
                                inner join member_orientation mo on e.created_by = mo.member_id
                                where e.event_id = %s and e.deleted is null
                                """,[event_id])
            event = events[0]
            blast_message = event['member_name'] + " has scheduled a new event! "
            slack_client.api_call("chat.postMessage", channel=stripped_channel,
                            text=blast_message, as_user=True)
            event_info("event info " + str(event_id),stripped_channel,user)

    
    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)
    db.close()




# Query all events in the future
def list_upcoming_events(command, channel, user) :
    db = database.Database()
    events = db.fetchAll("select * from events where record_complete = 1 and start_date > now() and deleted is null")
    db.close()

    if len(events) == 0 :
        response = "There are no upcoming events"

    else:
        response = "ID | Time                     | Title"
        for event in events :
            start_date_str = str(event['start_date'].strftime("%a %m/%d %H:%M"))

            response = response + "\n" + str(event['event_id']) + " | " + start_date_str + " | " + str(event['title'])

        response = response + "\n \njoin event: @og_bot join # \nmore info: @og_bot event info #"
    
    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)
    

# lets users join events that have been created
def join_event(command, channel, user) :
    response = "something went wrong join_event"

    event_id, response, event = bot_utilities.parse_event_from_command(user,command)

    
    if event_id > 0 :
        db = database.Database()
        records = db.fetchAll("""select e.event_id, e.title, e.start_date, em.member_id
                                from events e 
                                left outer join event_members em on e.event_id = em.event_id
                                where e.record_complete = 1 and e.start_date > now() and e.event_id = %s and e.deleted is null
                            """,[event_id])

        # ensure the selected event is valid and in the future
        if len(records) == 0 :
            response = "That's not a valid event ID in the future. Type \"@og_bot list events\" to see a list of valid events."
            bot_utilities.log_event("user "+ user + " tried joining event and it failed (not valid future event): " + command)

        else :
            # go through members to see if the person has already joined
            inEvent = False
            for record in records:
                if record['member_id'] == user :
                    inEvent = True
            
            # if not in the event, add them
            if inEvent == False :
                response = "Great, you have been added to event: " + records[0]['title'] + " to start at " + str(records[0]['start_date'].strftime("%I:%M %p")) + " EST on " + str(records[0]['start_date'].strftime("%A %m/%d"))
                bot_utilities.log_event("user "+ user + " successfully joined event: " + str(event_id))

                # add to database
                db.runSql("insert into event_members (event_id,member_id,date_created) values (%s,%s,now()) on duplicate key update event_id = event_id, member_id = member_id",[event_id,user])

                # alert the event organizer - get the organizer
                events = db.fetchAll("select * from events where event_id = %s",[event_id])
                created_by_id = events[0]['created_by']

                # I'll need the name for the person joining
                results = db.fetchAll('select member_name from member_orientation where member_id = %s',[user])
                member_name = results[0]['member_name']
                
                bot_utilities.send_private_message(created_by_id,member_name + " has joined your event: " + events[0]['title'])

            else :
                response = "It looks like you are already in the event.  To see event information, type \"@og_bot event info " + str(event_id) + "\"."
                bot_utilities.log_event("user "+ user + " tried joining event but was already a member: " + command)

        db.close()

    slack_client.api_call("chat.postMessage", channel=channel,
                        text=response, as_user=True)



# lets people remove themself from an event
def remove_from_event(command, channel, user):
    response = "something went wrong"
    #parse event from command
    event_id, response, event_info = bot_utilities.parse_event_from_command(user,command)

    if event_id > 0 : # ensures we have a valid event
        # determine if the user is in the event
        if bot_utilities.user_is_in_event(user,event_id) : # user is in the event
            db = database.Database()
            db.runSql("delete from event_members where event_id = %s and member_id = %s",[event_id,user])
            
            response = "You have been removed from event: " + event_info['title']
            bot_utilities.log_event("User " + user + " has been removed from event "+ str(event_id))

            # alert the event organizer - get the organizer
            events = db.fetchAll("select * from events where event_id = %s",[event_id])
            created_by_id = events[0]['created_by']

            # I'll need the name for the person leaving
            results = db.fetchAll('select member_name from member_orientation where member_id = %s',[user])
            member_name = results[0]['member_name']
            db.close()

            bot_utilities.send_private_message(created_by_id,member_name + " has left your event: " + events[0]['title'])

        else : #user was not in the event
            response = "You weren't in the event..."
            bot_utilities.log_event("User " + user + " attempted to remove from event and was not in it: " + command)

    slack_client.api_call("chat.postMessage", channel=channel,
                        text=response, as_user=True)



# lets a user delete and event they created
def delete_event(command,channel, user) :
    event_id, response, records = bot_utilities.parse_event_from_command(user,command)


    if event_id > 0 : # valid event
        db = database.Database()
        records = db.fetchAll("""
                            select e.*, em.member_id as event_member
                            from events e
                            left outer join event_members em on e.event_id = em.event_id
                            where record_complete = 1 and deleted is null and e.event_id = %s
                            """,[event_id])

        # make sure user created the event
        if records[0]['created_by'] != user :
            response = "You did not create that event so you cannot delete it."
            bot_utilities.log_event("User "+ user + " attempted to delete an event but was not the creator: " + command)

        else : # proceed to delete
            db.runSql("update events set deleted = now() where event_id = %s",[event_id])
            response = "Event "+ str(event_id) + " has been deleted"
            bot_utilities.log_event = "User " + user + " deleted event " + str(event_id)

            # send notifications to event members
            for record in records :
                if record['event_member'] != user : # no need to send a PM to the person deleting it
                    bot_utilities.send_private_message(record['event_member'],"An upcoming event ("+ record['title']+") has been canceled.")


        db.close()
    
    slack_client.api_call("chat.postMessage", channel=channel, text=response, as_user=True)




def update_time_on_event(command, channel, user, event_id) :
    db = database.Database()

    db.close()




# The user has been determined to be creating an event and has been passed here
def handle_command(command, channel, user, command_orig):
    
    response = "Sorry, I'm kind of a dumb robot.  I have no idea what you mean. Type 'help' to learn about me"
    deffered = False

    db = database.Database()
    events = db.fetchAll("select * from events where record_complete = 0 and created_by = %s order by created_date desc limit 1",[user])
    event = events[0]

    

    if event['current_prompt'] == "start" :
        update_event_time(command,channel,user, event['event_id'])
        deffered = True

    elif event['current_prompt'] == "title" :
        update_event_title(str(command_orig),channel,user,event['event_id'])
        deffered = True

    elif event['current_prompt'] == "descr" :
        update_event_descr(str(command_orig),channel,user,event['event_id'])
        deffered = True

    elif event['current_prompt'] == "channel" :
        assign_event_channel(command,channel,user,event['event_id'])
        deffered = True

    db.close()

    if deffered == False :
        slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)

   
