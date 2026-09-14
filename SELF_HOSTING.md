# Self-Hosting ERM
Following the shutdown of ERM, the team has decided to provide a self-hosting guide for people who wish to have a personal copy of ERM. This is a lot cheaper than paying for a bot like Melonly, and leaves you open to make your own adaptations to the source.

> [!CAUTION]
> Although you host the source yourself, you are still subject to following the license. The license requires that ERM is attributed and you do not change the license of the code.

> [!WARNING]
> FOLLOW ALL STEPS EXACTLY AS DESCRIBED. If you don't, the bot may not start or will not properly start.

> [!NOTE]
> You cannot resell ERM services without permission directly from the ERM developers. Checks can and will be implemented in the future to ensure that this bot is not opened up to other people.
 
## Prerequesites
- Python 3.12 or newer with pip (you will run into errors if running anything older)
- A MongoDB server (see MongoDB section)
- A Discord bot token (see Setting Up The Bot (Discord side) section)
## Setting up Python
> [!NOTE]
> This guide only shows installing in Windows (the MacOS installer is here but you will need to do that yourself as I don't have an accessible Mac). You do not need admin privileges for this step.
1. Download [this exe file](https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe) (for Windows) or [this file](https://www.python.org/ftp/python/3.14.7/python-3.14.7-macos11.pkg) for MacOS.  
2. Open the exe file. You will see a window similar to the one below. Make sure that `Add python.exe to PATH` is selected then press `Install Now`. <img width="651" height="412" alt="image" src="https://github.com/user-attachments/assets/7ac2e3fa-15f2-4d1b-a414-404155981fbe" />
3. Once it is finished it will tell you and show an option saying 'Disable PATH length limit'. You don't need to do this; just close the installer.
4. You have now installed Python, and you can move onto the MongoDB stage.


## MongoDB
The bot stores all data in a MongoDB database. You will need to either create an account with MongoDB (recommended) or self-host your own database.
This guide will show you how to make a MongoDB database with a connection URL. This will need to be pasted into your .env file.<br>
1. Access [https://www.mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register) and fill out your information inside of it. You can also use Google if you want to. <br> <img width="364" height="618" alt="image" src="https://github.com/user-attachments/assets/df070d4c-db61-4c57-bd0a-30e073958698" />

2. Immediately after this it will ask you to verify your email. Please check your email for the link. If it is not there, look in your spam folder or press resend. If you click the button in the email you should see this: <img width="663" height="758" alt="image" src="https://github.com/user-attachments/assets/741a8a85-1967-472c-ace5-d620a5dfbcf5" />

3. You will see a `Welcome to Atlas` message; wait a few seconds for it to disappear and then it will ask you to configure MFA. Just press set up next to email, and enter the code sent to your email.
4. You'll get a prompt like the one below; just press skip personalisation at the bottom. <img width="1254" height="1249" alt="image" src="https://github.com/user-attachments/assets/9cf3277b-fced-4d9e-83da-1dd1b23daecf" />
5. You should get this message: <img width="1689" height="1269" alt="image" src="https://github.com/user-attachments/assets/f7cb1a6e-415e-48ff-9e48-deee86471689" /><br> Ensure that 'Free' is selected. Then just press Create Deployment at the bottom.
6. This step is very important. You will see this message; don't copy anything, just press Choose a Connection Method. <img width="1160" height="1040" alt="image" src="https://github.com/user-attachments/assets/63bb5f2d-ef76-42b1-b16a-96c2fcb7041c" /><br>On this page, then press Drivers.<img width="1133" height="1044" alt="image" src="https://github.com/user-attachments/assets/7bd26f99-775f-48e3-a06a-ad8364af1c5c" /><br>Finally, on this page, just press the clipboard button next to the final code snippet (starting with `mongodb+srv`); paste it into your env. **DO NOT LOSE THIS; YOU CANNOT RECOVER IT EASILY IF LOST**<img width="1142" height="1392" alt="image" src="https://github.com/user-attachments/assets/8a7a3d9b-e9f9-4df4-9606-c344ecbba7d4" />
7. You now have MongoDB setup! Make sure to keep the connection string safe else the bot won't work. You can now go onto the Setting up the Discord bot (Discord side) section.

## Setting up the Discord bot (Discord side)
> [!NOTE]
> The token present in this tutorial is expired. Do not attempt to use it.

1. Access the following website: https://discord.com/developers/home. This is where all your bots will show up, and will look something like this: <img width="1487" height="927" alt="image" src="https://github.com/user-attachments/assets/4ac2083e-1a88-4000-a75d-f731f3b0fe90" />
2. Press the '+ Create' button at the top right of the screen. Press 'Create Blank App' at the top of this pop up. <img width="1256" height="366" alt="image" src="https://github.com/user-attachments/assets/b84ee8d0-4dd7-4f4d-abb6-cfb1d3ca0f43" />
3. Enter a name for the bot. If there is a team drop down, leave it at personal. Make sure to click the checkbox asking you to agree to the Terms.
4. You will now see a page like this. Head to the `Bot` option in the left bar. <img width="1498" height="863" alt="image" src="https://github.com/user-attachments/assets/e9784f47-b3a1-49e1-9dc1-1196a5c81409" />
5. Press the `Reset Token` button. It will tell you that your bot's code will stop working, you can just press 'Yes, do it!' here. You will be prompted for your MFA if you do this. <img width="1499" height="888" alt="image" src="https://github.com/user-attachments/assets/8d503518-66e7-4521-8be6-c109cdb2da77" /><br>Copy your token and keep it on you; you can't get it back if it is lost. **DO NOT SHARE THIS WITH ANYONE YOU DO NOT TRUST** <img width="1208" height="673" alt="image" src="https://github.com/user-attachments/assets/52d3cff1-85b0-4c01-b286-8f51f738b2fc" />.
6. Scroll down until you see the 'Privileged Gateway Intents' area. Turn these all on. <img width="1459" height="621" alt="image" src="https://github.com/user-attachments/assets/5b237390-bcb1-453b-a8e8-9364330afbd4" /><br> Make sure to save your changes!
7. Head to 'Installation'. Turn off the 'User Install' option and set the 'Install Link' from `Discord Provided Link` to `None`. This ensures that no one else can add your bot to their server; only you can. <img width="1516" height="857" alt="image" src="https://github.com/user-attachments/assets/5c5acf1f-1790-446e-8cc7-d2a529110bad" /><br>For extra security, you can also turn off `Public Bot` in the Bot page __after__ this is done but you do not have to do that. Make sure to save changes.
8. Head to the `OAuth2` tab. Scroll down and select `Bot` and `applications.commands`. In the next area, just select `Administrator`. Make sure that the Integration Type is 'Guild Install' and copy the link just below it. This is the bot's invite and allows you to add the bot to your server. <img width="1512" height="937" alt="image" src="https://github.com/user-attachments/assets/9b69f270-ebb4-497e-ac95-a0bf8e851c26" /> <img width="1143" height="794" alt="image" src="https://github.com/user-attachments/assets/3b492805-1d14-453d-bfd0-a768ab809a01" />
9. Add the bot to your server by pasting the link into a new browser tab and the bot should be in your server. You do not need to access the Developer portal for the rest of this tutorial.

## Setting Up The Bot (code)
Now, you should have Python installed, and have the Mongo URL and Discord token from the previous steps. Please follow these instructions carefully.

1. Download [this zip file](https://github.com/ERM-Systems/ERM/archive/refs/heads/main.zip) and copy it to where you want to store the bot. Extract it and open that folder; you might need to click ERM-Main twice to get to the full thing; it is visible below. <img width="1101" height="868" alt="image" src="https://github.com/user-attachments/assets/185591a0-e8dc-4e72-9948-bbb0ecb0dc09" />
2. Copy the `.env.template` file to `.env`. Open it in Notepad.
    - Paste your Mongo URL next to `MONGO_URL=`
    - Type `PRODUCTION` next to `ENVIRONMENT=`. You MUST type it in all caps
    - Paste your Discord bot token next to `PRODUCTION_BOT_TOKEN=`.
<img width="1022" height="545" alt="image" src="https://github.com/user-attachments/assets/a7fe37bf-c318-4d68-ab79-832dfca92826" />

3. In the top bar, just type `cmd` to open the Command Prompt. If command prompt does not work, type `powershell` instead. <img width="1265" height="852" alt="image" src="https://github.com/user-attachments/assets/f229b704-5ec5-4fa0-942d-de9da7e8d4f3" />
4. Paste the following three commands into the command prompt (one at a time):
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
These commands can take a bit to run; just be patient. It should finish like the image below. <img width="1893" height="651" alt="image" src="https://github.com/user-attachments/assets/9b2c7ed7-315b-4cb7-a993-51c080c5ccee" />

5. Once these commands are done, type `python main.py` in the SAME terminal. You have now got ERM running on your own computer, but, to use your API key, you will need to whitelist it in your API settings. Please go to the ER:LC API section to configure it.

## ER:LC API
Recently, PRC updated the API so you must whitelist your IP address within the ER:LC API dashboard else every single request will be rejected. 
> [!NOTE]
> If you are using a Global API key with ERM, you do not need to whitelist your IP. However, as this guide is only intended for a single-server instance, we assume you do not have a global API key.

> [!WARNING]
> Only the private server owner is capable of doing this.

1. Head to https://icanhazip.com. This is your IP address; copy this. If you are running this on a hosting service, please ask your provider for the server's IP address. This website does not take your IP address; it only shows it to you.
2. Head to https://api.erlc.gg/server-owners. Login with your Roblox account.
3. Select `Settings` next to your ER:LC private server: <img width="1110" height="386" alt="image" src="https://github.com/user-attachments/assets/ba80b0c5-5657-48b6-b988-09816db2b771" />
4. On this page, enter your IP address from before and paste it in the IP Address field. Set a description for your IP. Then press the Add IP button. <img width="1043" height="757" alt="image" src="https://github.com/user-attachments/assets/30313a1a-bbb1-452d-bc3b-fe4044f42585" />
5. Once you see the 'Whitelisted IP Saved' message in the bottom right of the tab, then the IP has been whitelisted.


## Help!
If you need help, please do not hesitate to join the Discord at https://discord.gg/PbrXbHaYdY and head to the `#self-host-discussion` channel.
<br><br>
If you find issues with this guide, please message a member of the ERM Team, but ask in the self-host-discussion channel first.
