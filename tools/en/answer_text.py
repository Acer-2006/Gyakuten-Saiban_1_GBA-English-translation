# English text of the DS answer buttons (archive at 0x263bf4c in the US
# data.bin), in archive order, read off the button images. The buttons are
# anti-aliased bitmaps, so make_choice_labels.py redraws this text with the DS
# dialogue font; check_answer_text.py compares each entry against the width
# of the button's own lettering to catch transcription slips.
ANSWERS = [
    # 0
    "Phoenix Wright", "Larry Butz", "Mia Fey", "Cinder Block", "Cindy Stone",
    "Poisoned", "Hit with a blunt object", "Strangled", "Wait and see what happens", "Stop him from answering",
    # 10
    "No", "Yes", "Went into the apartment", "Knew the victim", "Examine the clock's batteries",
    "Ask the neighbors", "Try sounding the clock", "Have him answer honestly", "Detective Gumshoe", "Detective Suedeshoes",
    # 20
    "Detective Gumtree", "Of course I do!", "Of course not!", "Tell him straight", "Tell him not-so-straight",
    "It's up to you", "Of course I will", "Sorry, not a chance", "Accept", "Refuse",
    # 30
    "I trust you", "I don't trust you", "Go home", "Defend Maya", "I can't abandon you",
    "Someone else is the culprit", "I don't know why", "The killer", "Miss May", "I did",
    # 40
    "The day of the murder", "The day after the murder", "I forget", "You're a sham, Edgeworth!", "The detective's a sham!",
    "I'm a sham!", "Yes, I'm doing it", "No thanks", "Go for it", "Back down",
    # 50
    "Yep, he's right", "I question the testimony", "You saw nothing", "You're lying", "You're right",
    "I question your testimony", "She couldn't have heard it", "It couldn't have rung", "It's empty", "It's broken",
    # 60
    "The batteries are dead", "You held it", "You had heard about it", "You did it, didn't you?", "Why the wiretap?",
    "Call the bellboy as a witness", "Continue examining Miss May", "Accept the condition", "Give up", "Protest",
    # 70
    "Check-in", "Room service", "Bed making", "Miss April May", "The man with Miss May",
    "The Bellboy", 'File "A-I"', 'File "J-S"', 'File "T-Z"', "Read it",
    # 80
    "Leave it be", "Skim", "Check 'em", "Leave 'em", "Ease her fears",
    "Push her hard", "Defend me in court", "Cheer me on in court", "Help me break out of here", "Sunflowers",
    # 90
    "Marvin Grossberg", "Fishermen", '"DL6 Incident - Exhibit A"', '"DL6 Incident - Exhibit B"', "Leave them alone",
    "Swap photos", "Leave it alone", "That big painting", "That photo of Mr. White", "Why wouldn't you defend Maya?",
    # 100
    "You go drinking together", "He's blackmailing you", "He's giving you information", "Your boss", "Blackmailing you",
    "Your lover", "You're lovers", "Have him write it", "Turn him down", "It's gorgeous",
    # 110
    "I've seen it before", "When did you get it?", "You're wrong", "You bribed him", "You spied on him",
    "You blackmailed him", "Objection", "Let it go", "Press further", "Hold back",
    # 120
    "Mr. White is right", "Miss May is right", "Both are right", "Yeah, very odd", "Nope",
    "No problemo", "Big problemo", "Object", "Try it", "ST1-703",
    # 130
    "ST1-307", "ST1-370", "Skip it", "Listen again", "The assistant girl",
    "The grade-school boy", "The security lady", "Give granny a break", "Continue cross-examination", "Take a break",
    # 140
    "Keep the cardkey", "Lend her the cardkey", "Rip it open", "His kind nature", "His fighting skills",
    "Will Powers's acting", "I believe", "I don't know", "Trade", "Don't trade",
    # 150
    "Not at all", "It's a little vague", "It's contradictory", "Press harder", "Leave him be",
    "I claim it, and claim it loud", "No, it's impossible.", "Press him harder", "He couldn't watch it", "He was watching something else",
    # 160
    "Show evidence", "Press him hard", "Let it slide", "The photos were blurry", "He erased them by mistake",
    "The Steel Samurai didn't win", "Hammer was the victim", "Steel Samurai was the victim", "There was no victim", "The trailer is there",
    # 170
    "The path was blocked", "No filming is done there", "I have proof", "I don't have proof", "Test Powers's blood",
    "Fingerprint the bottle", "Examine Hammer's body", "You ate the bone, too", "You ate a boneless steak", "You didn't eat the steak",
    # 180
    "Meeting the Steel Samurai", "Picking on Sal Manella", "I think you could!", "You couldn't, could you", "I can tell you",
    "I can't tell you", "She couldn't deal with it", "I bet she could move it", "She had another way", "Of course he was",
    # 190
    "Of course he wasn't", "You did it, Vasquez!", "Testify again, Vasquez!", "No further questions, Vasquez!", "Back off",
    "You heard Mr. Manella wrong", "You saw Hammer limping", "Of course I can prove it!", "Of course I can't prove it!", "Reveal evidence",
    # 200
    "She had no motive", "Of course we will", "Of course we won't", "The autopsy report", "How to get in touch with you",
    "Take it", "Leave it", "I reckon so", "I reckon no", "No, I need you here",
    # 210
    "Yeah, you're useless", "I think there was", "I think there wasn't", "Wrong", "Right",
    "Make her show the enlargement", "Do nothing", "Rethink position", "Object to the enlargement", "Show other evidence",
    # 220
    "Wait and see", "Ms. Hart", "The victim himself", "Larry", "Deal",
    "No deal", "Have you seen it before?", "Is it yours?", "To inflate something", "To go diving",
    # 230
    "Put the tank away", "Ask more about the tank", "Nothing yet", "We found him", "Gourdy doesn't exist",
    "I have no proof", "Is here", "Is out there somewhere", "Borrow Missile", "Borrow the fishing pole",
    # 240
    "Borrow the metal detector", "Promise to run the Noodle", "We can't promise that", "Raise an objection", "Cross-examine",
    "Don't cross-examine", "That's enough", "Continue", "We don't care", "We should care",
    # 250
    "Larry's wrong", "Larry's right", "The murderer and Hammond", "Edgeworth and the murderer", "Edgeworth and Hammond",
    "Miles Edgeworth", "Lotta Hart", "The boat shop caretaker", "Because the first shot missed", "To create a witness",
    # 260
    "Yanni Yogi", "Manfred von Karma", "Gregory Edgeworth", "Robert Hammond", "No, maybe not.",
    '"Have we forgotten something?"', '"What\'s your name?"', '"What\'s the safe number?"', '"Case Summary"', '"Victim Data"',
    # 270
    '"Suspect Data"', "Actually, it does", "No, it doesn't", "Leave it to Edgeworth", "No objections",
    "I have an objection", "The murderer had to find it", "The murderer didn't need it", "The bullet would be proof", "The murderer was cautious",
    # 280
    "Say it now", "Save it for a better time", "It's impossible to prove", "Examine closely", "Dust for fingerprints",
    "Don't disturb the scene", "Objection!", "No problem!", "Leave her alone", "Press her",
    # 290
    "Ask further", "What she saw", "Where she saw it", "The order of events", "Angle of view to the crime",
    "Distance to the crime", "Difference in lighting", "Sit back and observe", "There's no problem", "There's a problem",
    # 300
    "Where the victim was found", "How the victim was killed", "When the victim died", "The victim's division", "The victim's ID number",
    "The victim's gender", "This tells me something!", "This tells me nothing!", "No problem", "Play video again",
    # 310
    "Cross examine again", "No evidence in video", "I object!", "There's no problem!", "Prove with video",
    "Prove with evidence", "Deny request", "Let Lana speak", "Check it out", "Forget it",
    # 320
    "The bloodstain's location", "The amount of blood", "Check it out closer.", "Look for other evidence.", "Check for prints",
    "Input number", "Don't touch it", "Assemble fragments", "Leave it be for now", "Hear more",
    # 330
    "Stop", "Ask about the picture", "Ema's mistaken", "There is another one", "I just might know...",
    "I'm not sure", "The location", "The murder weapon", "The murderer", "is in the evidence.",
    # 340
    "doesn't exist.", "Point out accomplice", "Present evidence", "I have no proof yet", "Why did you plant the knife?",
    "Why did you move the body?", "Cannot show evidence", "I did not", "Of course", "",
    # 350
    "",
]
assert len(ANSWERS) == 351
