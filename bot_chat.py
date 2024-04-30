'''
 bot_chat.py
 https://discord.com/api/oauth2/authorize?client_id=825419881881141348&permissions=0&scope=bot
 Created 03/27/21
 Updated 09/17/21
 Current Version: 1.0
----------------------

Setup:
* Install Python 3.7+ 64-bit

As Administrator - install these packages using pip.

* TBD...
'''

import os, traceback
import random
from api import SPPD_API
import time
import HELPER
import RESTFUL

from dotenv import load_dotenv

import requests

import threading
import re
from collections import namedtuple

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
PUBLIC_KEY = os.getenv('PUBLIC_KEY')
APP_ID = os.getenv('APP_ID')

single_user_map = {} # { Email: SingleUser(), ... }
channel_email_map = {} # { channelid : email }
channel_cache = {} # { channelid : email }
individual_tvt_scores = {} # { profileID : score }
USERID_NAME_MAP={}
ALL_USERS = []
FAIL_TRACKER = {}
channel_last_refresh={} # {channelid : time}
channel_to_guild={} # {channelid : guild}

max_message_length = 250 #500
MAP_LOCK = threading.Condition()
RESTFUL_LOCK = threading.Condition()
BATTLE_DAYS_COUNTER = -1 # -1 to initialize!

#BASE_URL = "https://discord.com/api/v8"
BASE_URL = "https://discord.com/api/v10"

def getGuildFromChannel(channel_id):
	url = f"{BASE_URL}/channels/{channel_id}"
	headers = {"Authorization": f"Bot {SECRET_KEY}"}
	result = None
	try:
		r = requests.get(url, headers=headers)
		json_object = r.json()
		if "guild_id" in json_object: result = json_object["guild_id"]
	except:
		print("ERROR: getGuildFromChannel")
	return result
	
def getGuildUserNick(guild_id,user_id):
	url = f"{BASE_URL}/guilds/{guild_id}/members/{user_id}"
	headers = {"Authorization": f"Bot {SECRET_KEY}"}
	result = None
	try:
		r = requests.get(url, headers=headers)
		json_object = r.json()
		if "nick" in json_object: result = json_object["nick"]
	except:
		print("ERROR: getGuildUserNick")
	return result

def postMessageToWebhook(wsid, wstoken, content):
	webhook_url = f"{BASE_URL}/webhooks/{wsid}/{wstoken}"
	json = {"content": content}
	try:
		r = requests.post(webhook_url, json=json)
	except:
		print("ERROR: postMessageToWebhook")
	
def getChannelMessages(channel_id):
	time.sleep(0.02) #Rate limit is 50 queries per second.
	if channel_id not in channel_last_refresh:
		channel_last_refresh[channel_id]=None
	url = f"{BASE_URL}/channels/{channel_id}/messages"
	last_refresh=channel_last_refresh[channel_id]
	if last_refresh != None:
		url += f"?after={last_refresh}"
	headers = {"Authorization": f"Bot {SECRET_KEY}"}
	result = {}
	try:
		r = requests.get(url, headers=headers)
		result = r.json()
	except:
		print("ERROR: getChannelMessages")
	return result
	
def deleteWebhook(wsid, wstoken):
	webhook_url = f"{BASE_URL}/webhooks/{wsid}/{wstoken}"
	result = False
	try:
		r = requests.delete(webhook_url)
		result = r.status_code == 204
	except:
		print("ERROR: deleteWebhook")
	return result
	
Message = namedtuple('Message', ['content', 'author', 'mentions'], defaults=[None, None, None])
def processChannelMessages(message_list):
	#Needs to return:
	#messages = [
	#	{
	#		"content": "...",
	#		"author": "name",
	#		"mentions" : {"12345": "NAME", ...}
	#	}
	'''
	  {
		"id": "888520510185541702",
		"type": 0,
		"content": "<@875421475497209916> <@585143730533564416>",
		"channel_id": "612453232546938890",
		"author": {
		  "id": "742297510831325324",
		  "username": "Douglas Bot",
		  "avatar": "fc0494b223f9ca34c5577699a4e87744",
		  "discriminator": "5262",
		  "public_flags": 65536,
		  "bot": true
		},
		"attachments": [],
		"embeds": [],
		"mentions": [
		  {
			"id": "875421475497209916",
			"username": "shroomy",
			"avatar": "764418c6721c23c250b88c7062fb0fe4",
			"discriminator": "0420",
			"public_flags": 0
		  }
		],
		"mention_roles": [],
		"pinned": false,
		"mention_everyone": false,
		"tts": false,
		"timestamp": "2021-09-17T20:23:17.541000+00:00",
		"edited_timestamp": null,
		"flags": 0,
		"components": []
	  },
	'''
	global channel_to_guild, channel_last_refresh
	messages = []
	if len(message_list) > 0:
		if type(message_list) != list:
			print(f"ERROR - {message_list}")
			return messages
		m = message_list[0]
		id = m["id"]
		channel_id = int(m["channel_id"])
		channel_last_refresh[channel_id]=id
		if channel_id not in channel_to_guild:
			result = getGuildFromChannel(channel_id)
			if result != None:
				channel_to_guild[channel_id]=result
	
	message_list.reverse()
	display_name_cache = {} # { userid: display_name, ... }
	for m in message_list:
		if "bot" in m["author"] and m["author"]["bot"]: continue
		content = m["content"]
		if len(content) == 0 or content.startswith('/i'): continue
		cid = int(m["channel_id"])
		gid = channel_to_guild[cid] if cid in channel_to_guild else None
		author = m["author"]["username"]
		aid = m["author"]["id"]
		if aid not in display_name_cache and gid != None:
			nick = getGuildUserNick(gid,aid)
			if nick != None: display_name_cache[aid]=nick
		if aid in display_name_cache:
			author=display_name_cache[aid]
		mentions = {}
		for mention in m["mentions"]:
			mid = mention["id"]
			mentions[mid]=mention["username"]
			if mid not in display_name_cache and gid != None:
				nick = getGuildUserNick(gid,mid)
				if nick != None: display_name_cache[mid]=nick
			if mid in display_name_cache:
				mentions[mid]=display_name_cache[mid]
		messages.append(Message(content,author,mentions))
	return messages

def defangMessage(message):
	message_content = message.content
	message_content = message_content.replace('\n','\\n')
	message_content = message_content.replace('"','\\"')
	#for mention_id,mention_username in message.mentions.items():
	#	message_content = message_content.replace(f'<@{mention.id}>',f'<color={mention.color}>@{mention.display_name}</color>')
	for mention_id,mention_username in message.mentions.items():
		message_content = message_content.replace(f'<@{mention_id}>',f'@{mention_username}')
	for mention_id,mention_username in message.mentions.items():
		message_content = message_content.replace(f'<@!{mention_id}>',f'@{mention_username}')
	'''
	for mention in message.mentions:
		#message_content = message_content.replace(f'<@!{mention.id}>',f'<color={mention.color}>@{mention.display_name}</color>')
		message_content = message_content.replace(f'<@!{mention.id}>',f'@{mention.display_name}')
	for mention in message.role_mentions:
		#message_content = message_content.replace(f'<@&{mention.id}>',f'<color={mention.color}>@{mention.name}</color>')
		message_content = message_content.replace(f'<@&{mention.id}>',f'@{mention.name}')
	for mention in message.channel_mentions:
		#message_content = message_content.replace(f'<#{mention.id}>',f'<color=#5680da>#{mention.name}</color>')
		message_content = message_content.replace(f'<#{mention.id}>',f'#{mention.name}')
	'''
	return message_content
	
#TODO: Skip the cache - use SPPD Replay!
def cacheNewNames(unknown_users):
	if len(unknown_users) == 0: return
	global USERID_NAME_MAP
	index=0
	WIDTH=20
	for i in range(0,len(unknown_users),WIDTH):
		search_str=",".join(x for x in unknown_users[i:i+WIDTH])
		RESTFUL_LOCK.acquire()
		try:
			result=SPPD_API.getUserName(search_str)
			names_dict=HELPER.getUserNames(result)
			USERID_NAME_MAP.update(names_dict)
			time.sleep(1) #Fails if you go too fast???
		except Exception as e:
			print("EXCEPTION: "+str(e))
			#traceback.print_exc()
		RESTFUL_LOCK.notify_all()
		RESTFUL_LOCK.release()
		index+=1

def updateFailTracker(channelid,increment=True):
	global FAIL_TRACKER, channel_email_map, single_user_map
	MAP_LOCK.acquire()
	try:
		if channelid not in FAIL_TRACKER:
			FAIL_TRACKER[channelid]=0
		if increment:
			FAIL_TRACKER[channelid]+=1
		else:
			FAIL_TRACKER[channelid]=0
		if FAIL_TRACKER[channelid] > 10:
			FAIL_TRACKER[channelid]=0
			#Remove Single User
			if channelid in channel_email_map:
				EMAIL = channel_email_map[channelid]
				if EMAIL in single_user_map:
					single_user = single_user_map[EMAIL]
					single_user.TEMPORARY=True
					try:
						#upload the failed action to chat support
						RESTFUL.uploadChatStatus(single_user) #Not SPPD API
						del channel_email_map[single_user.CHANNEL]
						del single_user_map[EMAIL]
					except Exception as e:
						traceback.print_exc()
						print("\n\n*********FAILED UPDATEFAILTRACKER***********\n\n")
	except Exception as e:
		traceback.print_exc()
		print("\n\n*********FAILED UPDATEFAILTRACKER2***********\n\n")
	MAP_LOCK.notify_all()
	MAP_LOCK.release()
	
def getSingleUserFromChannelID(channel_id):
	global MAP_LOCK,single_user_map
	MAP_LOCK.acquire()
	found_user = None
	for key,single_user in single_user_map.items():
		if single_user.CHANNEL == channel_id:
			if not single_user.TEMPORARY:
				found_user = single_user
			break
	MAP_LOCK.notify_all()
	MAP_LOCK.release()
	return found_user

def removeColor(message):
	message = re.sub('<color=#[0-9a-fA-F]*>', '', message)
	message = message.replace('</color>','')
	return message
	
#post_chat (1234, [ [ [pid1, pid2], "message" ] ] )
def post_chat(channelid, messages):
	global USERID_NAME_MAP
	if messages == None:
		print(f"ERROR Bad token for channel {channelid}")
		updateFailTracker(channelid)
		return
	if len(messages) == 0: return
	updateFailTracker(channelid,False)
	single_user = getSingleUserFromChannelID(channelid)
	if single_user == None:
		print(f"Error - getSingleUserFromChannelID {channelid}")
		return
	for userids,m in messages:
		cur_usernames = []
		if len(userids) > 0:
			this_userid = userids[0]
			is_accept_message = m == " accepted "
			if this_userid in USERID_NAME_MAP:
				uname = USERID_NAME_MAP[this_userid]
				if type(uname) == list:
					uname = uname[0]
				m = "`" + uname + "`" + m
			else:
				m = "Unknown" + m
		if len(userids) > 1:
			guest_userid = userids[1]
			if guest_userid in USERID_NAME_MAP:
				uname = USERID_NAME_MAP[guest_userid]
				if type(uname) == list:
					uname = uname[0]
				m = m + "`" + uname + "`"
			else:
				m = m + "Unknown"
		#TO DO: Convert to embedded reply rather than quoted with ">"
		m = removeColor(m)
		postMessageToWebhook(single_user.WSID, single_user.WSTOKEN, "> " + m)
		
#post_chat (1234, [ [ [pid1, pid2], "message" ] ] )
def post_chat_tvt(channelid, messages):
	global USERID_NAME_MAP
	if messages == None:
		print(f"ERROR Bad token for channel {channelid}")
		updateFailTracker(channelid)
		return
	if len(messages) == 0: return
	updateFailTracker(channelid,False)
	single_user = getSingleUserFromChannelID(channelid)
	if single_user == None:
		print(f"Error - getSingleUserFromChannelID {channelid}")
		return
	for userids,m in messages:
		cur_usernames = []
		if len(userids) > 0:
			this_userid = userids[0]
			is_accept_message = m == " accepted "
			if this_userid in USERID_NAME_MAP:
				uname = USERID_NAME_MAP[this_userid]
				if type(uname) == list:
					uname = uname[0]
				m = "`" + uname + "`" + m
			else:
				m = "Unknown" + m
		if len(userids) > 1:
			guest_userid = userids[1]
			if guest_userid in USERID_NAME_MAP:
				uname = USERID_NAME_MAP[guest_userid]
				if type(uname) == list:
					uname = uname[0]
				m = m + "`" + uname + "`"
			else:
				m = m + "Unknown"
		#TO DO: Convert to embedded reply rather than quoted with ">"
		m = removeColor(m)
		postMessageToWebhook(single_user.TVTWSID, single_user.TVTWSTOKEN, "> " + m)

class THREADBOT(threading.Thread):
	
	def __init__(self, func, sleep):
		threading.Thread.__init__(self)
		self._stop_event = threading.Event()
		self.func = func
		self.sleep = sleep
		
	def stop(self):
		global stop_event
		self._stop_event.set()
		stop_event.set() #in HELPER_BOT

	def run(self):
		while True:
			start = time.time()
			self.func()
			runtime = time.time() - start
			if self.sleep - runtime > 0:
				time.sleep(self.sleep - runtime)

def poll_tokens_loop():
	result = RESTFUL.downloadTokens() #Not SPPD API
	if result == None: return
	MAP_LOCK.acquire()
	global ALL_USERS,single_user_map,channel_email_map
	seen_users = []
	new_users = []
	for elem in result:
		EMAIL,TOKEN,TEAM,CHANNEL,WSID,WSTOKEN,TEMPORARY,CONFIRM,TVTCHANNEL,TVTWSID,TVTWSTOKEN = elem
		WSID = int(WSID)
		seen_users.append(EMAIL)
		if EMAIL in single_user_map:
			single_user = single_user_map[EMAIL]
			changed_from_verified_to_pending = (not single_user.TEMPORARY and TEMPORARY)
			single_user.TEAMID = TEAM
			if single_user.CHANNEL != CHANNEL:
				if single_user.CHANNEL in channel_email_map:
					del channel_email_map[single_user.CHANNEL]
				single_user.CHANNEL = CHANNEL
				channel_email_map[CHANNEL]=EMAIL
			single_user.WSID = WSID
			single_user.WSTOKEN = WSTOKEN
			single_user.TEMPORARY = TEMPORARY
			single_user.CONFIRM = CONFIRM
			single_user.TVTCHANNEL = TVTCHANNEL
			single_user.TVTWSID = TVTWSID
			single_user.TVTWSTOKEN = TVTWSTOKEN
			if changed_from_verified_to_pending:
				single_user.start_time = int(time.time())
			else:
				continue
		else:
			single_user_map[EMAIL]=HELPER.SingleUser(EMAIL,TOKEN,TEAM,CHANNEL,WSID,WSTOKEN,TEMPORARY,CONFIRM,TVTCHANNEL,TVTWSID,TVTWSTOKEN)
			channel_email_map[CHANNEL]=EMAIL
		if EMAIL not in ALL_USERS:
			new_users.append([EMAIL,TOKEN])
		if TEMPORARY:
			postMessageToWebhook(WSID, WSTOKEN, "Confirm by typing 'Welcome SPPD Chat Bot' in the next 5 minutes in your team's chat in-game.")
		#add new single users that aren't already in single_user_map
		
	#delete emails from single_user_map if they are not in tmp_map
	delete_users = []
	for email in single_user_map:
		if email not in seen_users:
			delete_users.append(email)
	for email in delete_users:
		try:
			channel_id = single_user_map[email].CHANNEL
			wsid = single_user_map[email].WSID
			wstoken = single_user_map[email].WSTOKEN
			postMessageToWebhook(wsid, wstoken, "Confirmed Unsubscribed.")
			#deleteWebhook(wsid, wstoken)
			del single_user_map[email]
			del channel_email_map[channel_id]
		except:
			traceback.print_exc()
			print(f"Failed to delete WSID: {wsid}")
	
	#Include within lock because otherwise single_users can be used without a mastertoken!
	#write MASTERTOKENs for users that don't exist yet.
	for EMAIL,TOKEN in new_users:
		#append to mastertoken file.
		fh = open("MASTERTOKEN.txt", "a")
		fh.write(f"{EMAIL},{TOKEN}\n")
		fh.close()
		ALL_USERS.append(EMAIL)
	MAP_LOCK.notify_all()
	MAP_LOCK.release()

def poll_ingame_loop():
	#Every 10 seconds, check go through each user and publish new chat messages to the appropriate discord channel
	message_map = {} #channelid : [messages]
	message_map_tvt = {}
	global BATTLE_DAYS_COUNTER, individual_tvt_scores
	cur_time = time.localtime()
	tm_wday = cur_time.tm_wday
	tm_hour = cur_time.tm_hour
	BATTLE_DAYS_INIT = False
	BATTLE_DAYS = (tm_wday == 5 and tm_hour > 3) or tm_wday == 6 or (tm_wday == 0 and tm_hour < 8)
	if BATTLE_DAYS:
		if BATTLE_DAYS_COUNTER == -1:
			BATTLE_DAYS_INIT = BATTLE_DAYS_COUNTER == -1 #Run only once.
			BATTLE_DAYS_COUNTER += 1
		else:
			BATTLE_DAYS = BATTLE_DAYS_COUNTER % 3 == 0 #Run every 3rd try
			BATTLE_DAYS_COUNTER += 1
			if BATTLE_DAYS_COUNTER == 3:
				BATTLE_DAYS_COUNTER = 0
	else:
		individual_tvt_scores = {}
	
	MAP_LOCK.acquire()
	try:
		delete_users = []
		global single_user_map,channel_email_map
		for email in single_user_map.keys():
			su = single_user_map[email]
			if su.TEMPORARY and su.start_time+300 < int(time.time()):
				#delete this bad boy.
				delete_users.append([email,su.CHANNEL])
				continue
			#pull the chat data
			messages = []
			messages_tvt = []
			new_scores = []
			RESTFUL_LOCK.acquire()
			try:
				messages = RESTFUL.getChatMessages(su) #IS SPPD API
				time.sleep(1)
			except Exception as e:
				traceback.print_exc()
				print(f"getChatMessages FAILED! {str(e)}")
			if BATTLE_DAYS:
				try:
					all_members_scores = RESTFUL.getIndividualScores(su) #IS SPPD API
					if all_members_scores != None:
						for userid, score in all_members_scores:
							if userid not in individual_tvt_scores:
								individual_tvt_scores[userid] = score
								new_scores.append([[userid],score])
					time.sleep(1)
				except Exception as e:
					traceback.print_exc()
					print(f"getIndividualScores FAILED! {str(e)}")
			RESTFUL_LOCK.notify_all()
			RESTFUL_LOCK.release()
			
			#Very Rare error where the user is unable to get Auth Token
			if messages == None: continue
			
			if not BATTLE_DAYS_INIT and len(new_scores) > 0:
				for profile_id, score in new_scores:
					message_to_send = f" scored {score} on their TVT run :star2: :star2: :star2:"
					messages_tvt.append([profile_id, message_to_send])
			
			if su.TEMPORARY:
				for userid, m in messages:
					if "welcome sppd chat bot" in m.lower():
						su.TEMPORARY = False
						RESTFUL.uploadChatStatus(su) #Not SPPD API
			#Messages needs to be an array of arrays. [[userid, message], ...]
			if not su.TEMPORARY:
				if su.TVTCHANNEL == None:
					messages.extend(messages_tvt)
				else:
					message_map_tvt[su.CHANNEL] = messages_tvt
				message_map[su.CHANNEL] = messages
			if su.MY_SESSION1 == None or su.MY_SESSION1["cluster"] == None:
				updateFailTracker(su.CHANNEL)
		for email,channel_id in delete_users:
			try:
				#upload the failed action to chat support
				RESTFUL.uploadChatStatus(single_user_map[email]) #Not SPPD API
				del single_user_map[email]
				del channel_email_map[channel_id]
			except:
				pass
	except Exception as e:
		print("EXCEPTION: "+str(e))
		traceback.print_exc()
		print("\n\n*************FAILED poll_ingame_loop!!********\n\n")
	MAP_LOCK.notify_all()
	MAP_LOCK.release()
	
	#Preprocess all userids in messages array. Get names and Add them to global cache if they aren't already in it.
	unknown_users = []
	for key,messages in message_map.items():
		if messages == None: continue
		for userids,_ in messages:
			for userid in userids:
				if userid == "": continue
				if userid not in USERID_NAME_MAP:
					unknown_users.append(userid)
	cacheNewNames(unknown_users)
	
	#Send the messages! Yay!
	for channelid in message_map:
		post_chat(channelid, message_map[channelid])
		
	#Preprocess all userids in messages array. Get names and Add them to global cache if they aren't already in it.
	unknown_users = []
	for key,messages in message_map_tvt.items():
		if messages == None: continue
		for userids,_ in messages:
			for userid in userids:
				if userid == "": continue
				if userid not in USERID_NAME_MAP:
					unknown_users.append(userid)
	cacheNewNames(unknown_users)
	
	#Send the messages! Yay!
	for channelid in message_map_tvt:
		post_chat_tvt(channelid, message_map_tvt[channelid])
	
def poll_discord_loop():
	try:
		#Poll every channel in the list.
		single_users = single_user_map.values()
		for single_user in single_users:
			if single_user.TEMPORARY: continue
			
			channel_id = single_user.CHANNEL
			wsid = single_user.WSID
			wstoken = single_user.WSTOKEN
			result = getChannelMessages(channel_id)
			if "code" in result and result["code"] == 50001:
				postMessageToWebhook(wsid,wstoken,"Douglas v3 is **Missing Access** to read this Discord Channel for the Chat Bot.")
				updateFailTracker(channel_id)
			if "code" in result and result["code"] == 10003:
				print(f"Unknown Channel: {channel_id}")
				updateFailTracker(channel_id)
			
			initialize = channel_last_refresh[channel_id] == None
			
			#Process the result and post each message to in-game
			messages = []
			try:
				messages = processChannelMessages(result)
			except Exception as e:
				print("EXCEPTION: "+str(e))
				traceback.print_exc()
				print(f"Error - processChannelMessages {result}")
			if initialize: continue
			if len(messages) == 0: continue
			for m in messages:
				remainder_message = defangMessage(m)
				index = 0
				while len(remainder_message) > 0 and index < 8:
					cut_off = max_message_length
					message_to_send = remainder_message[:cut_off]
					RESTFUL_LOCK.acquire()
					success = RESTFUL.sendChatMessage(single_user,m.author,message_to_send) #IS SPPD API
					RESTFUL_LOCK.notify_all()
					RESTFUL_LOCK.release()
					if not success:
						time.sleep(0.2)
						#Retry once.
						RESTFUL_LOCK.acquire()
						success = RESTFUL.sendChatMessage(single_user,m.author,message_to_send) #IS SPPD API
						RESTFUL_LOCK.notify_all()
						RESTFUL_LOCK.release()
						if not success:
							postMessageToWebhook(wsid,wstoken,f"Failed to send: {message_to_send}")
					remainder_message = remainder_message[cut_off:]
					index+=1 # Cap at 2000 characters!
				if len(remainder_message) > 0:
					postMessageToWebhook(wsid,wstoken,"Your message was too long!")
	except Exception as e:
		print("EXCEPTION: "+str(e))
		traceback.print_exc()
		print("\n\n*************FAILED poll_discord_loop************\n\n")

####################################################################


#Every hour I should re-scan both buckets...
#Breakdown index by bucket?

#bucket=clan_chat_262148
#email : [channel_ids]
#confirm by typing "I consent to SPPD Chat Bot" in the next 30 seconds in your team's chat.
#Or - No can do. Your team isn't being managed by Team Manager Cloud. Sign up here: https://sppdreplay.net/teammanagercloud
#Restricted. Only 1 SPPD Team per discord channel. And only 1 channel per SPPD Team.


#every 5 minutes, pull email, channel, teamid from sppd sim database through sppd restful.
#Temporary
# - Don't post their chat, but record it for 30 seconds to check for variable. Delete it if not seen in 30 seconds.
#Permanent
# - Post their chat in relevant channels until they unsubscribe from that channel.

'''
async def sendToDiscord(channel,m):
	success = False
	try:
		m = removeColor(m)
		#print(f"{channel} : {m}")
		await channel.send(m)
		success = True
		print(channel.name + " : " + m)
	except Exception as e:
		print(str(e))
		success = False
	return success
	
@client.event
async def on_reaction_add(reaction, user):
	message = reaction.message
	if message.author == client.user and str(reaction.emoji) == '❌':
		print("Deleting Message.")
		try: await message.delete()
		except: pass
'''

if __name__ == '__main__':
	#Start fresh MASTERTOKEN.txt
	fh = open("MASTERTOKEN.txt","w")
	fh.write("")
	fh.close()
	#Run
	while True:
		start_time = time.time()
		poll_tokens_loop()
		poll_ingame_loop()
		poll_discord_loop()
		run_time = time.time() - start_time
		sleep_time = 60 - run_time
		if sleep_time > 0:
			time.sleep(sleep_time)
	'''
	poll_tokens = THREADBOT(poll_tokens_loop, 30)
	poll_tokens.start()
	poll_ingame = THREADBOT(poll_ingame_loop, 30)
	poll_ingame.start()
	poll_discord = THREADBOT(poll_discord_loop, 30)
	poll_discord.start()
	'''
		