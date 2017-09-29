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

# creating a new event record
def create_new_event (command, channel, user):
    db = database.Database()
    
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
                    ,[user,channel])
    
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

    if command.__len__() > 25 :
        response = "Title length must be 25 characters or less.  Please try again."
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
        db.close()
        response = "Great. Your event description has been updated. Your event ID is " + str(event_id) + ". Others can join it by typing @og_bot join "+ str(event_id)
        bot_utilities.log_event("Event: " + str(event_id) + " description updated: " + str(command))

    slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)


# Query all events in the future
def list_upcoming_events(command, channel, user) :
    db = database.Database()
    events = db.fetchAll("select * from events where record_complete = 1 and start_date > now()")
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
    # parse the number from the command
    str_cmd = str(command)
    value = 0
    try :
        value = int(''.join([c for c in str_cmd if c in '0123456789']))
    except :
        bot_utilities.log_event("user "+ user + " tried joining event and provided invalid command: " + command)

    # check and see if the user provided a value at all
    if value == 0 :
        response = "You need to include the event ID in your request. To list available events, type @og_bot list events."

    else :
        db = database.Database()
        records = db.fetchAll("""select e.event_id, e.title, e.start_date, em.member_id
                                from events e 
                                left outer join event_members em on e.event_id = em.event_id
                                where e.record_complete = 1 and e.start_date > now() and e.event_id = %s
                            """,[value])

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
                bot_utilities.log_event("user "+ user + " successfully joined event: " + value)

                # add to database
                db.runSql("insert into event_members (event_id,member_id,date_created) values (%s,%s,now())",[value,user])

            else :
                response = "It looks like you are already in the event.  To see event information, type \"@og_bot event info " + str(value) + "\"."
                bot_utilities.log_event("user "+ user + " tried joining event but was already a member: " + command)

        db.close()

    slack_client.api_call("chat.postMessage", channel=channel,
                        text=response, as_user=True)



# return information regarding an event
def event_info(command, channel, user) :
    response = "something went wrong join_event"
    # parse the number from the command
    str_cmd = str(command)
    value = 0
    try :
        value = int(''.join([c for c in str_cmd if c in '0123456789']))
    except :
        bot_utilities.log_event("user "+ user + " tried getting event info and provided invalid command: " + command)

    # check and see if the user provided a value at all
    if value == 0 :
        response = "You need to include the event ID in your request. To list available events, type @og_bot list events."

    else :
        db = database.Database()
        events = db.fetchAll("""
                            select e.* , mo.member_name
                            from events e
                            inner join member_orientation mo on e.created_by = mo.member_id
                            where e.start_date > now() and e.record_complete = 1 and e.event_id = %s
                            """,[value])
        

        if len(events) == 0 : # event is not in the future or id is invalid
            response = "That's not a valid event ID in the future. Type \"@og_bot list events\" to see a list of valid events."
            bot_utilities.log_event("user "+ user + " tried getting event info (not valid future event): " + command)

        else : 
            bot_utilities.log_event("user "+ user + " successfully retreived event info for event "+ str(value))
            players = db.fetchAll("""
                                    select em.event_id, em.member_id, mo.member_name, em.date_created
                                    from event_members em
                                    inner join member_orientation mo on em.member_id = mo.member_id
                                    where em.event_id = %s
                                    order by em.date_created desc
                                    """,[value])
            event = events[0]

            
            response = event['title'] + "\n"+ \
                        str(event['start_date'].strftime("%I:%M %p")) + " EST on " + str(event['start_date'].strftime("%A %m/%d")) + \
                        "\n______\n"+event['descr']+"\nCreated by: " +event['member_name'] + "\n______\nPlayers (" + str(len(players))+"):\n"

            for player in players :
                response = response + player['member_name'] + "\n"


        db.close()
    slack_client.api_call("chat.postMessage", channel=channel,
                        text=response, as_user=True)


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

    db.close()

    if deffered == False :
        slack_client.api_call("chat.postMessage", channel=channel,
                            text=response, as_user=True)

   
