# sppd_chat

**NOTE: This is broken since the SPPD API broke.**

If someone knows what the new SPPD API endpoints are, we could get things working.

#South Park Phone Destroyer Discord Chat Bot
 
Hi All,

This is the source code for the discord-bot that synchronized these two chats:
* SPPD in-game team chat
* Discord Channel

Not Included:
* Setting up the discord bot (Part 1)
	- Includes stuff like applying to have your bot approved.
* Setting up the discord bot (Part 2)
	- Includes stuff like binding global slash commands for your bot.
* SPPD-Replay server-side infrastructure.
	- There is a call `downloadTokens()`, which pulls the mastertoken from SPPDReplay - this token allows the client to log in to SPPD and not a single other app, and even sometimes not even SPPD because GOOGLE is keeps it tight.
	- So all those details are not included here, like how to generate a mastertoken, how it's stored on sppdreplay, how sppdreplay manages those, etc.