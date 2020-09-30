# Sex on the beach - an Alexa skill
The final project for the seminar 'Dialogmodellierung - Praxis und Implementation' in the sommer semester 2020.

# Functionality

This skill turns Alexa into an expert when it comes to cocktails.
Users are able to ask things like:

`give me a cocktail idea!`

`Give me the ingredients for a frappe.`

`what is the recipe for an Ipanema?`

And Alexa will responde to these requests with responses like:

`I think a Avalon sounds good. Do you want to hear the ingredients list?`

`3 ingredients are needed for a frappe: Coffee, Milk, Sugar.`

`The instructions for ipanema are the following: You need 25 ml Cachaca, 15 ml Lemon Juice, 10 ml Agave Syrup, top up with Champagne. Add the cachaca, lemon juice and syrup to your boston glass. Add ice and shake until ice cold. Pour into a chilled flute and top-up with Champagne.`


# Requirements (Ubuntu/ macOS)

* Python 3.6.9
* Packages from the requirements.txt


# Usage

To use the skill you will need to create a custome skill in the alexa developer console. There you use the dm_projekt.json file as your interaction model.
Use [ngrok](https://ngrok.com/) to run the backend of the skill, dm_projekt_flask.py via your localhost. Use the from ngrok provided URL as your endpoint in the developer console.
Then run the python script in the same folder as the strings.json file and your are ready to go.

For example:

`./ngrok http 127.0.0.1:5000`

`python3 dm_projekt_flask.py`






# Authors

Sara Derakhshani,
sara.derakhshani@uni-potsdam.de,
Matriculation number 792483

Hannah Peuckmann,
hannah.peuckmann@uni-potsdam.de,
Matriculation number 791996
