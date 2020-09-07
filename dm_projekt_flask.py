import logging
import requests # for http request
import six
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
                           CatchAllExceptionHandler, RequestLogger, ResponseLogger



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
        speech_text = "Welcome to Sex on the beach"
        reprompt = 'Ask me for cocktail recipes.'
        handler_input.response_builder.speak(speech_text).ask(reprompt).set_should_end_session(
            False)
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
        api_request = build_url(api, 's', drink)
        request_key = parse_request(request_type)
        try:
            response = http_get(api_request)
            logging.info(response)
            speech = build_response(request_key, response, drink)
        except Exception as e:
            speech = (f'I am sorry, I don\'t know any information about {drink}')
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(speech).set_should_end_session(False)
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
            response = http_get('https://www.thecocktaildb.com/api/json/v1/1/random.php')
            cocktail = response['drinks'][0]['strDrink']
            session_attr['random_cocktail'] = cocktail
            session_attr['random_cocktail_ingredients'] = False
            session_attr['random_cocktail_instructions'] = False
            speech = f'How about a {cocktail}? Do you want to hear the ingredients?'
        except Exception as e:
            speech = (f'I am sorry, something went wrong.')
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class YesMoreInfoIntentHandler(AbstractRequestHandler):
    """Handler for yes to get more info intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        session_attr = handler_input.attributes_manager.session_attributes
        return (is_intent_name('AMAZON.YesIntent')(handler_input) and
                'random_cocktail' in session_attr)

    def handle(self, handler_input):
        logging.info('In YesMoreInfoIntentHandler, changing to AskForCocktailIntentHandler')
        session_attr = handler_input.attributes_manager.session_attributes
        drink = session_attr['random_cocktail']
        api_request = build_url(api, 's', drink)
        request_key = parse_request('ingredients')
        try:
            response = http_get(api_request)
            logging.info(response)
            speech = build_response(request_key, response, drink)
        except Exception as e:
            speech = get_speech('GENERIC_EXCEPTION')
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(speech).set_should_end_session(False)
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

        speech = ('Okay, maybe next time!')
        handler_input.response_builder.speak(speech).set_should_end_session(
            False)
        return handler_input.response_builder.response


api = 'https://www.thecocktaildb.com/api/json/v1/1/search.php?{}={}'


### build_response und parse_request sind noch bissel zu speziefisch für den einen Intent gebaut, 
### erweiten, bzw umstrukturieren wenn weitere intents da sind
def build_response(request_key, response, drink):
    if type(request_key) == str:
        instructions = response['drinks'][0][request_key]
        speech = f'Here are the instructions for a {drink}. {instructions}'
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
        ing_str = ', '.join(ingredients)
        speech = f'You need {n_ingredients} ingredients for a {drink}. {ing_str}'
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
        ing_str = ', '.join(ingredients)
        speech = f'You need {n_ingredients} ingredients for a {drink}. {ing_str}. {instructions}'
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
    else: # both
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
            status_code = slot_item.resolutions.resolutions_per_authority[0].status.code
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
        except (AttributeError, ValueError, KeyError, IndexError, TypeError) as e:
            logging.info("Couldn't resolve status_code for slot item: {}".format(slot_item))
            logging.info(e)
            slot_values[name] = {
                "synonym": slot_item.value,
                "resolved": slot_item.value,
                "is_validated": False,
            }
    return slot_values


def build_url(api, search_category, search_word):
    """Return options for HTTP Get call."""
    url = api.format(search_category, search_word)
    return url


def http_get(url):
    response = requests.get(url)
    logging.info('API request with: {}'.format(url))
    if response.status_code < 200 or response.status_code >= 300:
        response.raise_for_status()
    return response.json()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AskForCocktailRequestHandler())
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