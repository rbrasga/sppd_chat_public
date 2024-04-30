import json, threading, time, sys
import datetime, random
import requests
import HELPER
from api import SPPD_API
import urllib.parse

EndpointTarget = "http://sppdreplay.ddns.net:5002"
BACKUP_MESSAGES = False

def gatherTeamInit(single_user):
	SPPD_API.setStoredUser(single_user.USERNAME)
	response_body=SPPD_API.getTeamInit()
	result = single_user.setTEAMID(response_body)
	#if result == None: #API Call Failed, reset.
	#	SPPD_API.UBI_EXPIRATION = int(time.time()) - 60
	#Update the UI's Action Log
	#HELPER.updateActionLog([int(time.time()),"Gather Team & Chat Details",result != None])
	time.sleep(0.2)
	getUbiMobiAccessToken(single_user)
	
def uploadChatStatus(single_user):
	HOST=f'{EndpointTarget}/chat_support_two'
	payload = {}
	if single_user.TEMPORARY:
		payload["ACTION"]="FAIL"
	else:
		payload["ACTION"]="VER"
	payload["EMAIL"]=single_user.USERNAME
	payload["TEAM"]=single_user.TEAMID
	payload_str=json.dumps(payload)
	result=None
	try:
		r = requests.post(HOST, data=payload_str)
		response_body=r.text
		result=0 #Success
	except:
		pass
	#HELPER.updateActionLog([int(time.time()),"Upload Chat Status",result != None])
	
def getUbiMobiAccessToken(single_user):
	#Get the UbiMobiAccessToken
	response_body=SPPD_API.getUbiMobiAccessToken(single_user.MY_USERID)
	result = single_user.processUbiMobiAccessToken(response_body)
	if result == None: #API Call Failed, reset.
		SPPD_API.UBI_EXPIRATION = int(time.time()) - 60
	#Update the UI's Action Log
	#HELPER.updateActionLog([int(time.time()),"Get Chat Access Token",result != None])
	time.sleep(0.2)
	
#SPPD Chat Bot Below (and above a little. Need to remove all non-relevant functions.
def downloadTokens():
	HOST=f'{EndpointTarget}/chat_support_two'
	payload = {}
	payload["ACTION"]="PULL"
	payload_str=json.dumps(payload)
	result=None
	try:
		r = requests.post(HOST, data=payload_str)
		response_body=r.text
		result = HELPER.processTokens(response_body)
	except:
		pass
	#HELPER.updateActionLog([int(time.time()),"Download Tokens",result != None])
	return result
	
def resetChatMessages(single_user):
	gatherTeamInit(single_user)
	time.sleep(0.2)
	CLUSTER = None
	GAME_SESSION_ID = None
	if single_user.MY_SESSION1 != None:
		CLUSTER = single_user.MY_SESSION1["cluster"]
		GAME_SESSION_ID = single_user.MY_SESSION1["id"]
	if CLUSTER == None:
		print(f"ERROR: resetChatMessages - BAD CLUSTER FOR {single_user.USERNAME}")
		return []
	SPPD_API.setStoredUser(single_user.USERNAME)
	response_body = SPPD_API.getTeamChat(CLUSTER,single_user.MY_BUCKET,single_user.UBIMOBI_ACCESS_TOKEN,GAME_SESSION_ID)
	backupMessages(response_body, single_user)
	messages = []
	messages1 = single_user.processChatMessages(response_body,True,True)
	messages.extend(messages1)
	time.sleep(1)
	
	if single_user.MY_SESSION2 != None and single_user.MY_SESSION2["expires"] > int(time.time()) + 60:
		CLUSTER = single_user.MY_SESSION2["cluster"]
		GAME_SESSION_ID = single_user.MY_SESSION2["id"]
		response_body = SPPD_API.getTeamChat(CLUSTER,single_user.MY_BUCKET,single_user.UBIMOBI_ACCESS_TOKEN,GAME_SESSION_ID)
		backupMessages(response_body, single_user)
		messages2 = single_user.processChatMessages(response_body,False,True)
		messages.extend(messages2)
		time.sleep(0.2)
	print(f"resetChatMessages {single_user.TEAMID}, {single_user.index_one}, {single_user.index_two}")
	return messages
	
def backupMessages(response_body, single_user, first_bucket=False):
	if not BACKUP_MESSAGES: return
	if response_body == None or len(response_body) == 0: return
	index = 0
	if single_user.first_bucket:
		index = single_user.index_one
	else:
		index = single_user.index_two
	todays_date=time.strftime('%Y-%m-%d_%H', time.localtime( int(time.time()) ))
	fh = open(f"DEBUG_{todays_date}.txt","a",encoding='utf8')
	try:
		fh.write(f"{response_body} - {index} : {single_user.max_time} : {single_user.WSID}\n")
	except Exception as e:
		print(f"ERROR Backing up data! {str(e)}")
	finally:
		fh.close()
	
def getChatMessages(single_user):
	if single_user.MY_USERID == None:
		#Forced Sign In
		SPPD_API.setStoredUser(single_user.USERNAME)
		UBI_EXPIRATION=SPPD_API.checkLoggedIn(force_connect=True)
		if UBI_EXPIRATION == -1: return None
		single_user.refreshChatTokenOverride(UBI_EXPIRATION)
		single_user.MY_USERID=SPPD_API.PROFILE_ID
		return resetChatMessages(single_user)
	
	SPPD_API.setStoredUser(single_user.USERNAME)
	UBI_EXPIRATION=SPPD_API.checkLoggedIn()
	if UBI_EXPIRATION == -1: return None
	override_refresh = single_user.refreshChatTokenOverride(UBI_EXPIRATION)
	if override_refresh:
		return resetChatMessages(single_user)
	#try:
	#CHECK Both Buckets
	messages = []
	EXPIRES = None
	CLUSTER = None
	GAME_SESSION_ID = None
	if single_user.first_bucket and single_user.MY_SESSION1 != None:
		EXPIRES = single_user.MY_SESSION1["expires"]
		if EXPIRES < int(time.time()) + 60 and single_user.MY_SESSION2 != None:
			EXPIRES = single_user.MY_SESSION2["expires"]
			CLUSTER = single_user.MY_SESSION2["cluster"]
			GAME_SESSION_ID = single_user.MY_SESSION2["id"]
			single_user.first_bucket = False
		else:
			CLUSTER = single_user.MY_SESSION1["cluster"]
			GAME_SESSION_ID = single_user.MY_SESSION1["id"]
	elif single_user.MY_SESSION2 != None:
		EXPIRES = single_user.MY_SESSION2["expires"]
		CLUSTER = single_user.MY_SESSION2["cluster"]
		GAME_SESSION_ID = single_user.MY_SESSION2["id"]
		single_user.first_bucket = False
		
	if CLUSTER == None or EXPIRES == None:
		print(f"ERROR: getChatMessages - BAD CLUSTER FOR {single_user.USERNAME}")
		return []
		
	if EXPIRES < int(time.time()) + 60:
		print(f'expired? {single_user.first_bucket} {EXPIRES} < {int(time.time()) + 60}')
		return resetChatMessages(single_user)
		
	index = 0
	if single_user.first_bucket:
		index = single_user.index_one
	else:
		index = single_user.index_two
		
	response_body = SPPD_API.pollTeamChat(CLUSTER,single_user.MY_BUCKET,single_user.UBIMOBI_ACCESS_TOKEN,GAME_SESSION_ID,index,0) #skip longpoll
	backupMessages(response_body, single_user, single_user.first_bucket)
	if "INVALID_UBISOFT_AUTH_TOKEN" in json.dumps(response_body):
		return resetChatMessages(single_user)
	messages = single_user.processChatMessages(response_body,single_user.first_bucket)
	return messages
	#except Exception as e:
	#	print("ERROR!")
	#	print(str(e))
	#	return []
	
def getIndividualScores(single_user):
	if single_user.MY_USERID == None:
		#Forced Sign In
		SPPD_API.setStoredUser(single_user.USERNAME)
		UBI_EXPIRATION=SPPD_API.checkLoggedIn(force_connect=True)
		if UBI_EXPIRATION == -1: return None
		single_user.refreshChatTokenOverride(UBI_EXPIRATION)
		single_user.MY_USERID=SPPD_API.PROFILE_ID
		return resetChatMessages(single_user)
	
	SPPD_API.setStoredUser(single_user.USERNAME)
	UBI_EXPIRATION=SPPD_API.checkLoggedIn()
	if UBI_EXPIRATION == -1: return None
	override_refresh = single_user.refreshChatTokenOverride(UBI_EXPIRATION)
	if override_refresh:
		return resetChatMessages(single_user)
	
	response_body = SPPD_API.getTeamWarUpdate()
	all_members_scores = single_user.processIndividualScores(response_body)
	return all_members_scores
	
def sendChatMessage(single_user, display_name, message):
	success = False
	if single_user.TEMPORARY or single_user.MY_USERID == None: return success
	SPPD_API.setStoredUser(single_user.USERNAME)
	UBI_EXPIRATION=SPPD_API.checkLoggedIn()
	if UBI_EXPIRATION == -1: return False
	override_refresh = single_user.refreshChatTokenOverride(UBI_EXPIRATION)
	if override_refresh:
		resetChatMessages(single_user)
		
	first_bucket = single_user.first_bucket
	WRITABLE = None
	CLUSTER = None
	GAME_SESSION_ID = None
	if first_bucket and single_user.MY_SESSION1 != None:
		WRITABLE = single_user.MY_SESSION1["writable"]
		if WRITABLE < int(time.time()) + 60:
			WRITABLE = single_user.MY_SESSION2["writable"]
			CLUSTER = single_user.MY_SESSION2["cluster"]
			GAME_SESSION_ID = single_user.MY_SESSION2["id"]
			first_bucket = False
		else:
			CLUSTER = single_user.MY_SESSION1["cluster"]
			GAME_SESSION_ID = single_user.MY_SESSION1["id"]
	elif single_user.MY_SESSION2 != None:
		WRITABLE = single_user.MY_SESSION2["writable"]
		CLUSTER = single_user.MY_SESSION2["cluster"]
		GAME_SESSION_ID = single_user.MY_SESSION2["id"]
	if CLUSTER == None:
		print(f"ERROR: sendChatMessage - BAD CLUSTER FOR {single_user.USERNAME}")
		return success
	if WRITABLE < int(time.time()) + 60:
		print(f'expired? {first_bucket} {WRITABLE} < {int(time.time()) + 60}')
		resetChatMessages(single_user)
		return success
	
	try:
		message_to_send = f"<color=#7289da>{display_name}</color>: {message}"
		#URL_ENCODED_MSG = urllib.parse.quote(message_to_send, safe='')
		URL_ENCODED_MSG = urllib.parse.quote_plus(message_to_send, safe='', encoding='utf-8')
		response_body = SPPD_API.sendTeamChat(CLUSTER,single_user.MY_BUCKET,single_user.UBIMOBI_ACCESS_TOKEN,GAME_SESSION_ID,single_user.MY_USERID,URL_ENCODED_MSG)
		try:
			print(f'message_sent: {message} -> {response_body}')
		except:
			print("message_sent: ...Cannot print this message...")
		success = "game_session_id" in response_body
		if not success and "INVALID_UBISOFT_AUTH_TOKEN" in response_body:
			UBI_EXPIRATION=SPPD_API.checkLoggedIn()
			if UBI_EXPIRATION == -1: return False
			override_refresh = single_user.refreshChatTokenOverride(UBI_EXPIRATION)
			resetChatMessages(single_user)
		#Pull the game_session_id and update tokens accordingly.
	except:
		print("Error sending message.")
	return success

