# Modulprojekt zum Seminar Dialogmodellierung
# Alexa skill
# Sara Derakhshani, Hannah Peuckmann
# SoSe 2020
# Classes of custom handlers for requests,
# handler for launch request and additional required functions

import logging
import requests  # for http request
import six
from nltk.tokenize import sent_tokenize
import json
import random
from typing import Dict, Any
from flask import Flask
from flask_ask_sdk.skill_adapter import SkillAdapter
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Slot
from ask_sdk_model.dialog import (ElicitSlotDirective, DelegateDirective)
from ask_sdk_model.slu.entityresolution import StatusCode
from basic_handlers import (HelpIntentHandler,
                            CancelOrStopIntentHandler,
                            FallbackIntentHandler,
                            SessionEndedRequestHandler,
                            CatchAllExceptionHandler,
                            RequestLogger,
                            ResponseLogger
                            )

# create logger, logger settings
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s:%(levelname)s:%(funcName)s:%(message)s')
file_handler = logging.FileHandler('sex_on_the_beach.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

app = Flask(__name__)
sb = SkillBuilder()


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # messages are read from the json file
        # that contains the outsourced responses
        speech = get_speech('WELCOME_MSG')
        reprompt = get_speech('WELCOME_REPROMT')
        handler_input.response_builder.speak(
            speech).ask(reprompt).set_should_end_session(False)
        return handler_input.response_builder.response


class AskForCocktailIntentHandler(AbstractRequestHandler):
    """ Handler for AskForCocktail intent, builds an Alexa response with
        ingredients, instruction or both for the asked cocktail"""

    def can_handle(self, handler_input):
        return is_intent_name("AskForCocktail")(handler_input)

    def handle(self, handler_input):
        logger.info('In AskForCocktailRequestHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        slot_values = get_slot_values(
            handler_input.request_envelope.request.intent.slots)
        request_type = slot_values['request']['resolved']
        # checks weather a cocktail was named in the request or
        # a cocktail from a previous request is active
        drink = get_drink(session_attr, slot_values)
        # if both do not apply, Alexa prompts the user to name
        # a cocktail
        if drink is None:
            prompt = get_speech("ASK_COCKTAIL")
            return handler_input.response_builder.speak(
                prompt).ask(prompt).add_directive(
                    ElicitSlotDirective(slot_to_elicit='drink')).response
        # new cocktail is active now
        session_attr['drink'] = drink
        api_request = build_url(api,
                                'search',
                                api_category='s',
                                api_keyword=drink
                                )
        # fugures out the kind of request, ingredient, description or both
        request_key = parse_request(request_type)
        try:
            response = http_get(api_request)
            logger.info(response)
            # builds a response based on the request
            speech = build_response(request_key, response, drink)
        except Exception as e:
            # the drink asked for is not in the database
            speech = get_speech('COCKTAIL_EXCEPTION').format(drink)
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        # safes response so it can be repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class MeasureIntentHandler(AbstractRequestHandler):
    """Handler to ask for the measure of an ingredient."""

    def can_handle(self, handler_input):
        return is_intent_name('MeasureIntent')(handler_input)

    def handle(self, handler_input):
        logger.info('In MeasureIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        slot_values = get_slot_values(
            handler_input.request_envelope.request.intent.slots)
        # ingredient to look for
        ingredient = slot_values['ingredient']['resolved']
        # checks if a cocktail is named by the user or is active
        # from a previous request
        drink = get_drink(session_attr, slot_values)
        # if both do not apply
        if drink is None:
            # Alexa prompts the user to name for a drink
            prompt = get_speech("ASK_COCKTAIL")
            return handler_input.response_builder.speak(
                prompt).ask(prompt).add_directive(
                    ElicitSlotDirective(slot_to_elicit='drink')).response
        # new active drink
        session_attr['drink'] = drink
        api_request = build_url(api,
                                'search',
                                api_category='s',
                                api_keyword=drink
                                )
        try:
            response = http_get(api_request)
            logger.info(response)
            ingredient_keys = parse_request('ingredients')
            ingredient_n = 0
            for k in ingredient_keys:
                current_ingredient = response['drinks'][0][k]
                if current_ingredient is None or current_ingredient == '':
                    break
                else:
                    if current_ingredient.lower() == ingredient.lower():
                        ingredient_n = k[-1]
            if int(ingredient_n) > 0:
                measure_key = 'strMeasure' + ingredient_n
                measure = response['drinks'][0][measure_key]
                if measure is None:
                    # no measure specified
                    speech = get_speech('GIVE_NO_MEASURE').format(ingredient,
                                                                  drink)
                else:
                    speech = get_speech('GIVE_MEASURE').format(measure,
                                                               ingredient,
                                                               drink)
            else:
                # ingredient is not in the cocktail recipe
                speech = get_speech('MEASURE_EXCEPTION').format(drink,
                                                                ingredient)
        except Exception as e:
            speech = get_speech('GENERIC_EXCEPTION')
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        # safes response so it canbe repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class GlassIntentHandler(AbstractRequestHandler):
    """Handler to ask for the glass a cocktail is served in."""

    def can_handle(self, handler_input):
        return is_intent_name('GlassIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In GlassIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        slot_values = get_slot_values(
            handler_input.request_envelope.request.intent.slots)
        # checks if a cocktail is named by the user or is active
        # from a previous request
        drink = get_drink(session_attr, slot_values)
        # if both do not apply
        if drink is None:
            # Alexa prompts the user to name a cocktail
            prompt = get_speech("ASK_COCKTAIL")
            return handler_input.response_builder.speak(
                prompt).ask(prompt).add_directive(
                    ElicitSlotDirective(slot_to_elicit='drink')).response
        # new drink is active
        session_attr['drink'] = drink
        api_request = build_url(api,
                                'search',
                                api_category='s',
                                api_keyword=drink
                                )
        try:
            response = http_get(api_request)
            logger.info(response)
            glass = response['drinks'][0]['strGlass']
            speech = get_speech("GIVE_GLASS").format(drink, glass)
        except Exception as e:
            speech = get_speech('GLASS_EXCEPTION').format(drink)
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        # safes response to be repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class CocktailWithIngredientIntentHandler(AbstractRequestHandler):
    """Handler for cocktail with ingredient intent."""

    def can_handle(self, handler_input):
        return is_intent_name('CocktailWithIngredientIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In CocktailWithIngredientIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        logging.info(slot_values)
        ingredient_1 = slot_values['ingredient_one']['resolved']
        ingredient_2 = slot_values['ingredient_two']['resolved']
        # api request for fist ingredient
        api_request_1 = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient_1
                                  )
        # api request for second ingredient
        api_request_2 = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient_2
                                  )
        session_attr['current_intent'] = 'FilterIntent'
        # intersection of both contains cocktails with both ingredients
        speech, session_attr['filtered_drinks'] = filter_drinks(api_request_1,
                                                                api_request_2,
                                                                ingredient_1,
                                                                ingredient_2
                                                                )
        # if only one cocktail could be found,
        # it becomes the new active cocktail
        if len(session_attr['filtered_drinks']) == 1:
            session_attr['drink'] = session_attr['filtered_drink'][0]
        # safes response to be repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class NonAlcoholicCocktailIntentHandler(AbstractRequestHandler):
    """Handler for non alcoholic cocktail intent."""

    def can_handle(self, handler_input):
        return is_intent_name('NonAlcoholicCocktailIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In NonAlcoholicCocktailIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        # ingredient to filter non alcoholic cocktails
        ingredient = slot_values['ingredient']['resolved']
        logging.info(slot_values)
        # all cocktail that contain the ingredient
        api_request_i = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient
                                  )
        # all non alcoholic cocktails
        api_request_a = build_url(api,
                                  'filter',
                                  api_category='a',
                                  api_keyword='Non_Alcoholic'
                                  )
        session_attr['current_intent'] = 'FilterIntent'
        # intersection of both lists are non alcoholic cocktails
        # filtered by the ingredient
        speech, session_attr['filtered_drinks'] = filter_drinks(api_request_i,
                                                                api_request_a,
                                                                ingredient,
                                                                'no alcohol'
                                                                )
        # if only one cocktail could be found,
        # it becomes the new active cocktail
        if len(session_attr['filtered_drinks']) == 1:
            session_attr['drink'] = session_attr['filtered_drink'][0]
        # safes response to be repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class RandomCocktailIntentHandler(AbstractRequestHandler):
    """Handler for random cocktail intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('RandomCocktailIntent')(handler_input)

    def handle(self, handler_input):
        logger.info('In RandomCocktailIntentHandler')

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        try:
            api_request = build_url(api, 'random')
            response = http_get(api_request)
            # api returns a random cocktail from the database
            drink = response['drinks'][0]['strDrink']
            session_attr['current_intent'] = 'RandomCocktailIntent'
            # new drink is active
            session_attr['drink'] = drink
            speech = get_speech('SUGGESTION_SPEECH').format(drink)
        except Exception as e:
            speech = get_speech('GENERIC_EXCEPTION')
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        # safes response to be repeated by request
        session_attr['last_speech'] = speech
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class IngredientDescriptionIntentHandler(AbstractRequestHandler):
    """ Handler for information about a specific ingredient"""

    def can_handle(self, handler_input):
        return is_intent_name('IngredientDescriptionIntent')(handler_input)

    def handle(self, handler_input):
        logger.info('In IngredientDescriptionHandler')
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        session_attr = handler_input.attributes_manager.session_attributes
        ingredient = slot_values['ingredient_drink']['resolved']
        api_request = build_url(api,
                                'search',
                                api_category='i',
                                api_keyword=ingredient)
        try:
            response = http_get(api_request)
            logging.info(response)
            # split description text into sentences to be able to response
            # only with the first three sentences
            description = sent_tokenize(
                response['ingredients'][0]['strDescription'])
            # description has les than three sentences
            if len(description) > 3:
                description = '.'.join(description[:2])
            else:
                description = description[0]
        except Exception as e:
            # ingredient not in the database
            description = get_speech("UNKNOWN_INGREDIENT").format(ingredient)
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        # safes response to be repeated by request
        session_attr['last_speech'] = description
        handler_input.response_builder.speak(
            description).set_should_end_session(False)
        return handler_input.response_builder.response


class YesMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for yes to get more info intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('AMAZON.YesIntent')(handler_input)

    def handle(self, handler_input):
        logger.info('In YesMoreInfoIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        # coming from RandomCocktailIntent
        # changing the intent to AskForCocktail, because user wants to know
        # infos on a specific cocktail
        if session_attr['current_intent'] == 'RandomCocktailIntent':
            return handler_input.response_builder.add_directive(
                DelegateDirective(
                    updated_intent='AskForCocktail')).response
        # coming from FilterIntent, listing the cocktails for the response
        elif session_attr['current_intent'] == 'FilterIntent':
            drink_list = session_attr['filtered_drinks']
            if len(drink_list) < 4:
                speech = ', '.join(drink_list)
            else:
                # for the case that more than three drinks are found,
                # three random ones are chosen
                drink_samples = random.sample(drink_list, 3)
                speech = get_speech('DRINK_LIST').format(drink_samples[0],
                                                         drink_samples[1],
                                                         drink_samples[2]
                                                         )
                # safes response to be repeated by request
                session_attr['last_speech'] = speech
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class NoMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for no to get no more info intent."""

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.NoIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("In NoMoreInfoIntentHandler")

        speech = get_speech('ACCEPT_NO')
        handler_input.response_builder.speak(speech).set_should_end_session(
            False)
        return handler_input.response_builder.response


class RepeatIntentHandler(AbstractRequestHandler):
    """Handler for repetition request"""

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.RepeatIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("In RepeatIntentHandler")
        session_attr = handler_input.attributes_manager.session_attributes
        # checks if there is a response to repeat
        if session_attr['last_speech']:
            speech = session_attr['last_speech']
        else:
            speech = get_speech('REPEAT_EXCEPTION')
        handler_input.response_builder.speak(speech).set_should_end_session(
            False)
        return handler_input.response_builder.response


api = 'https://www.thecocktaildb.com/api/json/v1/1/{}.php'


# used by NonAlcoholicCocktailIntent und CocktailWithIngredientIntent,
def filter_drinks(api_request_1, api_request_2, filter_1, filter_2):
    """Filters the Database by two filters.
       Makes two api requests, returns the intersecton. """
    try:
        response_1 = http_get(api_request_1)
        response_2 = http_get(api_request_2)
        logger.info(response_1)
        logger.info(response_2)
        drinks_1 = [entry['strDrink'] for entry in response_1['drinks']]
        drinks_2 = [entry['strDrink'] for entry in response_2['drinks']]
        # intersection contains drinks that match both filters
        drinks_intersection = (set(drinks_1) & set(drinks_2))
        n_drinks = len(drinks_intersection)
        if n_drinks > 4:
            speech = get_speech('ASK_DRINK_LISTING_EXAMPLE').format(
                len(drinks_intersection),
                filter_1,
                filter_2
                )
        elif n_drinks == 0:
            # no drinks found
            speech = get_speech('INGREDIENT_EXCEPTION').format(filter_1,
                                                               filter_2
                                                               )
        else:
            speech = get_speech('ASK_DRINK_LISTING').format(
                n_drinks,
                filter_1,
                filter_2
                )
    except Exception as e:
        speech = get_speech('INGREDIENT_EXCEPTION').format(filter_1,
                                                           filter_2
                                                           )
        drinks_intersection = set()
        logger.info("In filter function: message: {}".format(str(e)))
    # returns the response and the list of drinks
    return speech, list(drinks_intersection)


# used by AskForCocktailIntent
def build_response(request_key, response, drink):
    """Returns speech string with cocktail ingredients or instructions."""
    # If only ingredients are requested, the keys are in list format
    if type(request_key) == list:
        n_ingredients = 0
        ingredients = []
        # Valid ingredients are added to the list and counted
        # Both are returned as string
        for ingredient_key in request_key:
            ingredient = response['drinks'][0][ingredient_key]
            if ingredient is None or ingredient == '':
                break
            else:
                ingredients.append(ingredient)
                n_ingredients += 1
        ingredients_str = ', '.join(ingredients)
        speech = get_speech('GIVE_INGREDIENTS').format(n_ingredients,
                                                       drink,
                                                       ingredients_str)
        return speech
    # If only ingredients and instrcutions are requested,
    # the keys are a tuple containing the ingredient keys in a list and
    # the instruction key string
    elif type(request_key) == tuple:
        instructions = ' ' + response['drinks'][0][request_key[1]]
        measured_ingredients = []
        # Valid ingredients with corresponding measures are added to the list
        # List of measured ingredients and instructions are returned as string
        for i in request_key[0]:
            ingredient_key = 'strIngredient' + str(i)
            measure_key = 'strMeasure' + str(i)
            ingredient = response['drinks'][0][ingredient_key]
            measure = response['drinks'][0][measure_key]
            if ingredient is None or ingredient == '':
                break
            else:
                if measure is None:
                    measure = 'some'
                ingredient_with_measure = measure + ' ' + ingredient
                measured_ingredients.append(ingredient_with_measure)
        measured_ingredients_str = ', '.join(measured_ingredients)
        speech = get_speech('GIVE_INSTRUCTIONS').format(
            drink,
            measured_ingredients_str) + instructions
        return speech
    else:
        logger.info(request_key)


# benutzen AskForCocktailIntent, MeasureIntent
def parse_request(request_type):
    """Returns keys for extracting information from api response."""
    # If only ingredients are needed
    # a list of the sixteen ingredient keys is returned
    if request_type == 'ingredients':
        request_key = ['strIngredient' + str(i) for i in range(1, 16)]
    # If ingredients and instructions are needed
    # a list for construction of ingredient and measure keys
    # and the instruction key is returned
    else:
        request_key = ([i for i in range(1, 16)], 'strInstructions')
    return request_key


# benutzen AskForCocktailIntent, GlassIntent, MeasureIntent
def get_drink(session_attributes, slot_values):
    """Checks if a drink is already specified."""
    # if the slot for drink was filled
    if slot_values['drink']['resolved']:
        return slot_values['drink']['resolved']
    # checks if there is a drink from a preceding request
    elif 'drink' in session_attributes:
        return session_attributes['drink']
    # no drink is specified yet
    else:
        return None


# benutzen AskForCocktailIntent, CocktailwithIngredint,
# Ingredientdescription, NonalcoholicCocktail
def get_slot_values(filled_slots):
    """Extracts the slot values from the request envelope"""
    # type: (Dict[str, Slot]) -> Dict[str, Any]
    slot_values = {}
    logger.info("Filled slots: {}".format(filled_slots))
    for key, slot_item in six.iteritems(filled_slots):
        name = slot_item.name
        try:
            resolutions_per_authority = \
                slot_item.resolutions.resolutions_per_authority[0]
            status_code = resolutions_per_authority.status.code
            if status_code == StatusCode.ER_SUCCESS_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": resolutions_per_authority.values[0].value.name,
                    "is_validated": True,
                }
            elif status_code == StatusCode.ER_SUCCESS_NO_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.value,
                    "is_validated": False,
                }
            else:
                pass
        except (AttributeError,
                ValueError,
                KeyError,
                IndexError,
                TypeError) as e:
            logger.info(
                "Couldn't resolve status_code for slot item: {}".format(
                    slot_item))
            logger.info(e)
            slot_values[name] = {
                "synonym": slot_item.value,
                "resolved": slot_item.value,
                "is_validated": False,
            }
    return slot_values


# used by all handlers
def get_speech(prompt):
    """Reads the response messages that are outsourced to a json file."""
    with open('strings.json') as strings:
        # read json
        string_data = json.load(strings)
        # select value list, value is a list of possible responses
        prompt_list = string_data[prompt]
        # select a random response from the value list
        prompt = random.choice(prompt_list)
    return prompt


# used by all handlers
def build_url(api, api_request_type, api_category=None, api_keyword=None):
    """Return options for HTTP Get call."""
    if api_category and api_keyword:
        url = api.format(api_request_type) + '?{}={}'.format(api_category,
                                                             api_keyword)
    else:
        url = api.format(api_request_type)
    return url


# used by all handlers
def http_get(url):
    """Makes an api request."""
    response = requests.get(url)
    logger.info('API request with: {}'.format(url))
    if response.status_code < 200 or response.status_code >= 300:
        response.raise_for_status()
    return response.json()


# create instaces of handlers and add them to the skill
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AskForCocktailIntentHandler())
sb.add_request_handler(CocktailWithIngredientIntentHandler())
sb.add_request_handler(NonAlcoholicCocktailIntentHandler())
sb.add_request_handler(GlassIntentHandler())
sb.add_request_handler(MeasureIntentHandler())
sb.add_request_handler(RandomCocktailIntentHandler())
sb.add_request_handler(IngredientDescriptionIntentHandler())
sb.add_request_handler(YesMoreInfoIntentHandler())
sb.add_request_handler(NoMoreInfoIntentHandler())
sb.add_request_handler(RepeatIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())
sb.add_global_request_interceptor(RequestLogger())
sb.add_global_response_interceptor(ResponseLogger())


skill_adapter = SkillAdapter(
    skill=sb.create(), skill_id='TEST', app=app)


@app.route("/", methods=['POST'])
def invoke_skill():
    return skill_adapter.dispatch_request()


if __name__ == '__main__':
    app.run(debug=True)
