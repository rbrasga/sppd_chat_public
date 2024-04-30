# HELPER
# Created 01/02/20
# Updated TBD
# Current Version: 0.01
# The helper performs all finding and clicking functions
#   and any other lower lever functions
#----------------------

import datetime
import time, sys, os
import logging
import json

def removeCharactersOutOfRange(word):
	char_list = [word[j] for j in range(len(word)) if ord(word[j]) in range(65536)]
	new_word=''
	for j in char_list:
		new_word=new_word+j
	return new_word

class SingleUser():
	def __init__(self,username,token,teamid,channel,wsid,wstoken,temporary,confirm,tvtchannel,tvtwsid,tvtwstoken):
		#User-specific variables			
		self.USERNAME = username
		self.TOKEN = token
		self.TEAMID = teamid
		self.CHANNEL = channel
		self.WSID = wsid
		self.WSTOKEN = wstoken
		self.TEMPORARY = temporary
		self.CONFIRM = confirm
		self.TVTCHANNEL = tvtchannel
		self.TVTWSID = tvtwsid
		self.TVTWSTOKEN = tvtwstoken
		
		#Need to initialize later...
		#While it's temporary, reply after 60 seconds have passed. Then delete this single user.
		self.UBI_EXPIRATION = 0
		self.refresh_chat_token = True
		self.start_time = int(time.time())
		self.MY_USERID=None
		self.bucket1 = {}
		self.bucket2 = {}
		self.index_one = 0
		self.index_two = 0
		self.max_time = 0
		self.first_bucket = True
		
		self.UBIMOBI_ACCESS_TOKEN=None
		self.MY_BUCKET=None
		self.MY_SESSION1=None
		self.MY_SESSION2=None
		self.ff_tracker = [] #[ profile_id+time, ... ]
			
	def addNewFFMatch(self,key):
		if key in self.ff_tracker:
			self.ff_tracker.remove(key)
			return False
		
		if len(self.ff_tracker) >= 5:
			self.ff_tracker.pop(0)
		self.ff_tracker.append(key)
		return True
	
	def processIndividualScores(self,result):
		if type(result) != dict: return []
		if "members" not in result: return []
		if type(result["members"]) != list: return []
		all_members_scores = []
		for m in result["members"]:
			if 'profile_id' not in m or \
				'votes' not in m or \
				'score' not in m or \
				m['score'] == None:
				continue
			all_members_scores.append([m['profile_id'],m['score']])
		return all_members_scores
				
	def processChatMessages(self,result,first_bucket,initialize=False):
		skip_all = False
		if initialize and self.max_time == 0:
			skip_all = True
		'''
		try:
			json_string = json_string.encode('raw_unicode_escape').decode('utf-8')
		except:
			print(f"Error cleaning up json_string {json_string}")
		result={}
		try:
			result = json.loads(json_string)
		except Exception as e:
			print(str(e))
		'''
		if type(result) != list: return []
		messages = []
		for m in result:
			if 'id' not in m or \
				'data' not in m or \
				'time' not in m['data']:
				continue
			cur_time = m['data']['time']
			cur_id = m['id']
			oldID = True
			if first_bucket:
				if cur_id not in self.bucket1:
					oldID = False
					self.bucket1[cur_id] = m['data']
					self.index_one = cur_id + 1
				if oldID and self.bucket1[cur_id] != m['data']:
					oldID = False
					self.bucket1[cur_id] = m['data']
					self.index_one = cur_id + 1
			else:
				if cur_id not in self.bucket2:
					oldID = False
					self.bucket2[cur_id] = m['data']
					self.index_two = cur_id + 1
				if oldID and self.bucket2[cur_id] != m['data']:
					oldID = False
					self.bucket2[cur_id] = m['data']
					self.index_two = cur_id + 1
					
			if cur_time > self.max_time:
				self.first_bucket = first_bucket
				self.max_time = cur_time
				
			if skip_all or oldID: continue
			if 'type' not in m or \
				'data' not in m or \
				'profile_id' not in m['data'] or \
				'type' not in m['data']:
				continue
				
			#print(f"processChatMessages: {m}")
			profile_id = m['data']['profile_id']
			mtype = m['data']['type']
			if mtype == 0:
				#Standard Message
				if not self.CONFIRM and profile_id == self.MY_USERID:
					continue
				if 'message' in m['data']:
					profile_ids = []
					if profile_id != self.MY_USERID:
						profile_ids.append(profile_id)
					message_convert = m['data']['message']
					message_convert = message_convert.encode('raw_unicode_escape').decode('utf-8', 'ignore')
					message_to_send = ": " + message_convert
					messages.append([profile_ids, message_to_send])
			elif mtype == 7:
				#Join Request
				'''
				{
				  "type": "log",
				  "fed_id": "system",
				  "date": "2021-04-02 05:49:03",
				  "data": {
					"message": "",
					"profile_id": "1d8ec090-4a95-4d9a-bb8d-bc053b059fe6",
					"type": 7,
					"time": 1617342543
				  },
				  "id": 179
				}
				'''
				messages.append([[profile_id], " is requesting to join the team."])
			elif mtype == 9:
				#FF Request
				'''
				{
				  "type": "log",
				  "fed_id": "system",
				  "date": "2021-03-25 21:45:21",
				  "data": {
					"profile_id": "bd2998eb-4e5b-4c34-9ae7-c7eaaac42539",
					"type": 9,
					"time": 1616708720
				  },
				  "id": 75
				}
				'''
				#new_match = self.addNewFFMatch(f'{profile_id}{cur_time}')
				new_match = self.addNewFFMatch(f'{profile_id}')
				if new_match:
					messages.append([[profile_id], " wants a Friendly Fight!"])
				#else:
				#	messages.append([[profile_id], " is in a match! (or they cancelled)"])
			elif mtype == 10 and "host_profile_id" in m['data']:
				host_profile_id = m['data']['host_profile_id']
				messages.append([[profile_id, host_profile_id], " started a Friendly Fight with "])
				#new_match = self.addNewFFMatch(f'{profile_id}{cur_time}')
				new_match = self.addNewFFMatch(f'{profile_id}')
				#if new_match:
				#	messages.append([[profile_id], " wants a Friendly Fight!"])
				#else:
				#	messages.append([[profile_id], " is in a match! (or they cancelled)"])
				
			elif mtype == 12:
				#FF Result
				'''
				{
				  "type": "log",
				  "fed_id": "93JptkIuX3b1pMQrPCG2S2pgpHInVfs4jbuNwcitftuFfl75XN7PQw6geODa46eo",
				  "date": "2021-03-25 21:50:47",
				  "data": {
					"type": 12,
					"profile_id": "a6f95144-b1cb-4af1-ac22-95b4e8d14650",
					"time": 1616709048,
					"guest_profile_id": "bd2998eb-4e5b-4c34-9ae7-c7eaaac42539",
					"host_score": 3,
					"guest_score": 0,
				  },
				  "id": 83
				}
				'''
				if "host_score" in m['data'] and \
					"guest_profile_id" in m['data'] and \
					"guest_score" in m['data']:
					guest_profile_id = m['data']['guest_profile_id']
					host_score = m['data']['host_score']
					guest_score = m['data']['guest_score']
					star1 = ""
					star2 = ""
					if host_score > guest_score:
						star1 = ":star2:"
					elif host_score < guest_score:
						star2 = ":star2:"
					messages.append([[profile_id,guest_profile_id], f" {star1} {host_score} | {guest_score} {star2} "])
			'''
			elif mtype == 8 and "accepted_profile_id" in m['data']:
				accepted_profile_id = m['data']['accepted_profile_id']
				#Accepted
				#{
				#  "type": "log",
				#  "fed_id": "system",
				#  "date": "2021-04-02 05:49:14",
				#  "data": {
				#	"accepted_profile_id": "1d8ec090-4a95-4d9a-bb8d-bc053b059fe6",
				#	"profile_id": "2613be61-20e5-475a-9be0-c923088b495e",
				#	"type": 8,
				#	"time": 1617342554
				#  },
				#  "id": 180
				#}
				messages.append([[profile_id,accepted_profile_id], " ?accepted/rejected? "])
		'''
		return messages
		
	def processUbiMobiAccessToken(self,result):
		if type(result) != dict: return None
		if "device" not in result: return None
		if "ubimobi_access_token" not in result["device"]: return None
		self.UBIMOBI_ACCESS_TOKEN=result["device"]["ubimobi_access_token"]
		return 0 #success

	def setTEAMID(self,result):
		if type(result) != dict: return None
		if "team" not in result.keys(): return None
		if "id" not in result["team"].keys(): return None
		if "members" not in result["team"].keys(): return None
		if "applicationStatus" not in result["team"].keys(): return None
		if "chat" not in result.keys(): return None
		if "bucket" not in result["chat"].keys(): return None
		if "game_sessions" not in result["chat"].keys(): return None
		self.TEAMID=result["team"]["id"]
		self.MY_BUCKET=result["chat"]["bucket"]
		game_sessions = result["chat"]["game_sessions"]
		expire_time = int(time.time()) + 2 * 3600
		if len(game_sessions) > 0:
			self.MY_SESSION1=game_sessions[0]
			if self.MY_SESSION1["expires"] > expire_time:
				self.MY_SESSION1["expires"] = expire_time
			if self.MY_SESSION1["writable"] > expire_time:
				self.MY_SESSION1["writable"] = expire_time
		else:
			self.MY_SESSION1=None
		if len(game_sessions) > 1:
			self.MY_SESSION2=game_sessions[1]
			if self.MY_SESSION2["expires"] > expire_time:
				self.MY_SESSION2["expires"] = expire_time
			if self.MY_SESSION2["writable"] > expire_time:
				self.MY_SESSION2["writable"] = expire_time
		else: self.MY_SESSION2=None
		return 0 #Success
		
	def refreshChatTokenOverride(self,UBI_EXPIRATION):
		self.refresh_chat_token = UBI_EXPIRATION != self.UBI_EXPIRATION
		if self.refresh_chat_token:
			self.UBI_EXPIRATION = UBI_EXPIRATION
		return self.refresh_chat_token

def processTokens(json_string):
	result={}
	try:
		result = json.loads(json_string)
	except Exception as e:
		print(str(e))
	if type(result) != dict: return []
	return result["USERS"]

def getUserNames(result):
	user_map={}
	global PROFILE_LIST
	if type(result) != dict: return user_map
	if "profiles" not in result.keys(): return user_map
	result=result["profiles"]
	if type(result) != list: return user_map
	if len(result) < 1: return user_map
	for profile in result:
		if type(profile) == dict and \
			"profileId" in profile.keys() and \
			"nameOnPlatform" in profile.keys():
			profileId=profile["profileId"]
			nameOnPlatform=profile["nameOnPlatform"]
			platformType="NULL"
			if "platformType" in profile.keys():
				platformType=profile["platformType"]
			user_map[profileId]=[nameOnPlatform,platformType]
	return user_map

###HELPERS###
def removeCharactersOutOfRange(word):
	char_list = [word[j] for j in range(len(word)) if ord(word[j]) in range(65536)]
	new_word=''
	for j in char_list:
		new_word=new_word+j
	return new_word
	
#Update the UI's Action Log
def updateActionLog(log_list):
	cur_time,cur_action,cur_result=log_list
	created=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cur_time))
	result="Success" if cur_result else "Failed"
	print(f"{created} | {cur_action} | {result}")
	return
