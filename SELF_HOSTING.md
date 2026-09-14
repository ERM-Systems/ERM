# Self-Hosting ERM
Following the shutdown of ERM, the team has decided to provide a self-hosting guide for people who wish to have a personal copy of ERM. This is a lot cheaper than paying for a bot like Melonly, and leaves you open to make your own adaptations to the source.

> [!CAUTION]
> Although you host the source yourself, you are still subject to following the license. The license requires that ERM is attributed and you do not change the license of the code.

## Prerequesites
- Python 3.12 or newer with pip (you will run into errors if running anything older)
- A MongoDB server (see MongoDB section)

### MongoDB
The bot stores all data in a MongoDB database. You will need to either create an account with MongoDB (recommended) or self-host your own database.
This guide will show you how to make a MongoDB database with a connection URL. This will need to be pasted into your .env file.<br>
1. Access [https://www.mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register) and fill out your information inside of it. You can also use Google if you want to. <br> <img width="364" height="618" alt="image" src="https://github.com/user-attachments/assets/df070d4c-db61-4c57-bd0a-30e073958698" />

2. Immediately after this it will ask you to verify your email. Please check your email for the link. If it is not there, look in your spam folder or press resend. If you click the button in the email you should see this: <img width="663" height="758" alt="image" src="https://github.com/user-attachments/assets/741a8a85-1967-472c-ace5-d620a5dfbcf5" />

3. You will see a welcome to atlas message; wait a few seconds for it to disappear and then it will ask you to configure MFA. Just press set up next to email, and enter the code sent to your email.
4. You'll get a prompt like the one below; just press skip personalisation at the bottom. <img width="1254" height="1249" alt="image" src="https://github.com/user-attachments/assets/9cf3277b-fced-4d9e-83da-1dd1b23daecf" />
5. You should get this message: <img width="1689" height="1269" alt="image" src="https://github.com/user-attachments/assets/f7cb1a6e-415e-48ff-9e48-deee86471689" /><br> Ensure that 'Free' is selected. Then just press Create Deployment at the bottom.
6. This step is very important. You will see this message; don't copy anything, just press Choose a Connection Method. <img width="1160" height="1040" alt="image" src="https://github.com/user-attachments/assets/63bb5f2d-ef76-42b1-b16a-96c2fcb7041c" /><br>On this page, then press Drivers.<img width="1133" height="1044" alt="image" src="https://github.com/user-attachments/assets/7bd26f99-775f-48e3-a06a-ad8364af1c5c" /><br>Finally, on this page, just press the clipboard button next to the final code snippet (starting with `mongodb+srv`); paste it into your env. **DO NOT LOSE THIS; YOU CANNOT RECOVER IT EASILY IF LOST**<img width="1142" height="1392" alt="image" src="https://github.com/user-attachments/assets/8a7a3d9b-e9f9-4df4-9606-c344ecbba7d4" />
7. You now have MongoDB setup! Make sure to keep the connection string safe else the bot won't work.

## Setting Up The Bot
Now, you should have the Mongo url from the previous step. Please follow these instructions carefully.
> [!NOTE]
> It is heavily advised that you use git for this. Just google `installing git` and you should get a tutorial for it.
1. Run this command to get the code: `git clone https://github.com/ERM-Systems/ERM`. You can also press [this](https://github.com/ERM-Systems/ERM/archive/refs/heads/main.zip) to download a zip copy of the code.
2. Open the folder and copy .env.template to .env.
3. Use notepad to edit this .env file. 
    - Paste your Mongo thing next to `MONGO_URL=`
    - Type `PRODUCTION` exactly like this after `ENVIRONMENT=`
    - Generate a token in the Discord developer portal (there are many guides to do this) and paste it next to PRODUCTION_BOT_TOKEN=
4. Open a command prompt by going to the top bar saying your file location and typing `cmd.exe` then press enter.
5. Run these three exact commands:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
<br>Once all three run successfully then you can run `python main.py` to start the bot. 
