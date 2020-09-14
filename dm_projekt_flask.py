import logging
import requests  # for http request
import six
import json
import random
from flask import Flask
from ask_sdk_core.skill_builder import SkillBuilder
from flask_ask_sdk.skill_adapter import SkillAdapter


from ask_sdk_model.services import ServiceException
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput


from ask_sdk_model import Response
from ask_sdk_core.dispatch_components import (
    AbstractRequestHandler, AbstractExceptionHandler,
    AbstractResponseInterceptor, AbstractRequestInterceptor)
from typing import Union, Dict, Any, List
from ask_sdk_model.dialog import (
    ElicitSlotDirective, DelegateDirective)
from ask_sdk_model import (
    Response, IntentRequest, DialogState, SlotConfirmationStatus, Slot)
from ask_sdk_model.slu.entityresolution import StatusCode

from basic_handlers import HelpIntentHandler, CancelOrStopIntentHandler, \
                           FallbackIntentHandler, SessionEndedRequestHandler, \
                           CatchAllExceptionHandler, RequestLogger, \
                           ResponseLogger


logging.basicConfig(filename='dm_projekt_log.log',
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s'
                    )


app = Flask(__name__)
sb = SkillBuilder()


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech = get_speech('WELCOME_MSG')
        reprompt = get_speech('WELCOME_REPROMT')
        handler_input.response_builder.speak(
            speech).ask(reprompt).set_should_end_session(False)
        return handler_input.response_builder.response


class AskForCocktailRequestHandler(AbstractRequestHandler):
    """ Handler for AskForCocktail intent, builds an Alexa response with
        ingredients, recipe or both for the asked cocktail"""

    def can_handle(self, handler_input):
        return is_intent_name("AskForCocktail")(handler_input)

    def handle(self, handler_input):
        logging.info('In AskForCocktailRequestHandler')
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        request_type = slot_values['request']['resolved']
        drink = slot_values['cocktail']['resolved']
        logging.info(slot_values)
        api_request = build_url(api,
                                'search',
                                api_category='s',
                                api_keyword=drink
                                )
        request_key = parse_request(request_type)
        try:
            response = http_get(api_request)
            logging.info(response)
            speech = build_response(request_key, response, drink)
        except Exception as e:
            speech = get_speech('COCKTAIL_EXCEPTION').format(drink)
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class CocktailWithIngredientHandler(AbstractRequestHandler):
    """Handler for cocktail with ingredient intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('CocktailWithIngredientIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In CocktailWithIngredientIntentHandler')
        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        ingredient_1 = slot_values['ingredient_one']['resolved']
        ingredient_2 = slot_values['ingredient_two']['resolved']
        logging.info(slot_values)
        api_request_1 = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient_1
                                  )
        api_request_2 = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient_2
                                  )
        session_attr['current_intent'] = 'FilterIntent'
        speech, session_attr['filtered_drinks'] = filter_drinks(api_request_1,
                                                                api_request_2,
                                                                ingredient_1,
                                                                ingredient_2
                                                                )
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class NonAlcoholicCocktailIntentHandler(AbstractRequestHandler):
    """Handler for non alcoholic cocktail intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('NonAlcoholicCocktailIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In NonAlcoholicCocktailIntentHandler')
        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        ingredient = slot_values['ingredient']['resolved']
        logging.info(slot_values)
        api_request_i = build_url(api,
                                  'filter',
                                  api_category='i',
                                  api_keyword=ingredient
                                  )
        api_request_a = build_url(api,
                                  'filter',
                                  api_category='a',
                                  api_keyword='Non_Alcoholic'
                                  )
        session_attr['current_intent'] = 'FilterIntent'
        speech, session_attr['filtered_drinks'] = filter_drinks(api_request_i,
                                                                api_request_a,
                                                                ingredient,
                                                                'no alcohol'
                                                                )
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class RandomCocktailIntentHandler(AbstractRequestHandler):
    """Handler for random cocktail intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('RandomCocktailIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In RandomCocktailIntentHandler')

        attribute_manager = handler_input.attributes_manager
        session_attr = attribute_manager.session_attributes

        try:
            api_request = build_url(api, 'random')
            response = http_get(api_request)
            drink = response['drinks'][0]['strDrink']
            session_attr['current_intent'] = 'RandomCocktailIntent'
            session_attr['random_cocktail'] = drink
            session_attr['random_cocktail_ingredients'] = False
            session_attr['random_cocktail_instructions'] = False
            speech = '{}{}'.format(
                get_speech('SUGGESTION_SPEECH').format(drink),
                get_speech('ASK_INGREDIENTS'))
        except Exception as e:
            speech = get_speech('GENERIC_EXCEPTION')
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class YesMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for yes to get more info intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name('AMAZON.YesIntent')(handler_input)

    def handle(self, handler_input):
        logging.info('In YesMoreInfoIntentHandler,'
                     ' changing to AskForCocktailIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        if session_attr['current_intent'] == 'RandomCocktailIntent':
            drink = session_attr['random_cocktail']
            api_request = build_url(api,
                                    'search',
                                    api_category='s',
                                    api_keyword=drink
                                    )
            request_key = parse_request('ingredients')
            try:
                response = http_get(api_request)
                logging.info(response)
                speech = build_response(request_key, response, drink)
            except Exception as e:
                speech = get_speech('GENERIC_EXCEPTION')
                logging.info("Intent: {}: message: {}".format(
                    handler_input.request_envelope.request.intent.name, str(
                        e)
                    )
                    )
        elif session_attr['current_intent'] == 'FilterIntent':
            drink_list = session_attr['filtered_drinks']
            if len(drink_list) <= 4:
                speech = ', '.join(drink_list)
            else:
                drink_samples = random.sample(drink_list, 3)
                speech = ', '.join(drink_samples)
        handler_input.response_builder.speak(
            speech).set_should_end_session(False)
        return handler_input.response_builder.response


class NoMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for no to get no more info intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name("AMAZON.NoIntent")(handler_input) and
                'random_cocktail' in session_attr)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logging.info("In NoMoreInfoIntentHandler")

        speech = get_speech('ACCEPT_NO')
        handler_input.response_builder.speak(speech).set_should_end_session(
            False)
        return handler_input.response_builder.response


api = 'https://www.thecocktaildb.com/api/json/v1/1/search.php?{}={}'
api = 'https://www.thecocktaildb.com/api/json/v1/1/{}.php'


# Benutzen NonAlcoholicCocktailIntent und CocktailWithIngredientIntent
def filter_drinks(api_request_1, api_request_2, filter_1, filter_2):
    try:
        response_1 = http_get(api_request_1)
        response_2 = http_get(api_request_2)
        logging.info(response_1)
        logging.info(response_2)
        drinks_1 = [entry['strDrink'] for entry in response_1['drinks']]
        drinks_2 = [entry['strDrink'] for entry in response_2['drinks']]
        common_drinks = (set(drinks_1) & set(drinks_2))
        if len(common_drinks) > 4:
            speech = get_speech('ASK_DRINK_LISTING_EXAMPLE').format(
                len(common_drinks),
                filter_1,
                filter_2
                )
        else:
            speech = get_speech('ASK_DRINK_LISTING').format(
                len(common_drinks),
                filter_1,
                filter_2
                )
    except Exception as e:
        speech = get_speech('INGREDIENT_EXCEPTION').format(filter_1,
                                                           filter_2
                                                           )
        common_drinks = set()
        logging.info("In filter function: message: {}".format(str(e)))
    return speech, list(common_drinks)


### build_response und parse_request sind noch bissel zu speziefisch
### für den einen Intent gebaut,
### erweiten, bzw umstrukturieren wenn weitere intents da sind
def build_response(request_key, response, drink):
    if type(request_key) == str:
        instructions = response['drinks'][0][request_key]
        speech = get_speech('GIVE_INSTRUCTIONS').format(drink, instructions)
    elif type(request_key) == list:
        n_ingredients = 0
        ingredients = []
        for ingredient_key in request_key:
            ingredient = response['drinks'][0][ingredient_key]
            if ingredient is None:
                break
            else:
                ingredients.append(ingredient)
                n_ingredients += 1
        ingredients_str = ', '.join(ingredients)
        speech = get_speech('GIVE_INGREDIENTS').format(n_ingredients,
                                                       drink,
                                                       ingredients_str)
    elif type(request_key) == tuple:
        instructions = response['drinks'][0][request_key[1]]
        n_ingredients = 0
        ingredients = []
        for ingredient_key in request_key[0]:
            ingredient = response['drinks'][0][ingredient_key]
            if ingredient is None:
                break
            else:
                ingredients.append(ingredient)
                n_ingredients += 1
        ingredients_str = ', '.join(ingredients)
        speech = get_speech('GIVE_INGREDIENTS').format(n_ingredients,
                                                       drink,
                                                       ingredients_str) + \
            instructions
    else:
        logging.info(request_key)
    return speech


def parse_request(request_type):
    if request_type == 'recipe':
        request_key = 'strInstructions'
        logging.info(request_key)
    elif request_type == 'ingredients':
        request_key = ['strIngredient' + str(i) for i in range(1, 16)]
        logging.info(request_key)
    else:  # both
        request_key = (['strIngredient' + str(i) for i in range(1, 16)],
                       'strInstructions')
        logging.info(request_key)
    return request_key


def get_slot_values(filled_slots):
    """Return slot values with additional info."""
    # type: (Dict[str, Slot]) -> Dict[str, Any]
    slot_values = {}
    logging.info("Filled slots: {}".format(filled_slots))
    for key, slot_item in six.iteritems(filled_slots):
        name = slot_item.name
        try:
            status_code = \
                slot_item.resolutions.resolutions_per_authority[0].status.code
            if status_code == StatusCode.ER_SUCCESS_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.resolutions.resolutions_per_authority[0].values[0].value.name,
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
            logging.info(
                "Couldn't resolve status_code for slot item: {}".format(
                    slot_item))
            logging.info(e)
            slot_values[name] = {
                "synonym": slot_item.value,
                "resolved": slot_item.value,
                "is_validated": False,
            }
    return slot_values


def get_speech(prompt):
    with open('strings.json') as strings:
        string_data = json.load(strings)
    return string_data[prompt]


def build_url(api, api_request_type, api_category=None, api_keyword=None):
    """Return options for HTTP Get call."""
    if api_category and api_keyword:
        url = api.format(api_request_type) + '?{}={}'.format(api_category,
                                                             api_keyword)
    else:
        url = api.format(api_request_type)
    return url


def http_get(url):
    response = requests.get(url)
    logging.info('API request with: {}'.format(url))
    if response.status_code < 200 or response.status_code >= 300:
        response.raise_for_status()
    return response.json()


sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AskForCocktailRequestHandler())
sb.add_request_handler(CocktailWithIngredientHandler())
sb.add_request_handler(NonAlcoholicCocktailIntentHandler())
sb.add_request_handler(RandomCocktailIntentHandler())
sb.add_request_handler(YesMoreInfoIntentHandler())
sb.add_request_handler(NoMoreInfoIntentHandler())
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