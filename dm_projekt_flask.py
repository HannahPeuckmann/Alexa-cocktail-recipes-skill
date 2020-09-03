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
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        request_type = slot_values['request']['resolved']
        drink = slot_values['cocktail']['resolved']
        logging.info(slot_values)
        api_request = build_url(api, 's', drink)
        # Sollten wir echt irgendwie in Funktionen teilen
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
        try:
            response = http_get(api_request)
            logging.info(response)
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
        except Exception as e:
            speech = (f'I am sorry, I don\'t know any information about {drink}')
            logging.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))
        handler_input.response_builder.speak(speech).set_should_end_session(False)
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "Ask me for a cocktail recipe."

        handler_input.response_builder.speak(speech_text).ask(
            speech_text)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = "See you!"
        handler_input.response_builder.speak(speech_text)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speech_text = (
            "Sex on the beach can't help you with that.")
        reprompt = "You can search for cocktails by an ingredient or by name."
        handler_input.response_builder.speak(speech_text).ask(reprompt)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        return handler_input.response_builder.response


# Exception Handler classes
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch All Exception handler.

    This handler catches all kinds of exceptions and prints
    the stack trace on AWS Cloudwatch with the request envelope."""

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logging.error(exception, exc_info=True)

        speech = "I cant handle this request, sorry."
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


# Request and Response Loggers
class RequestLogger(AbstractRequestInterceptor):
    """Log the request envelope."""

    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logging.info("Request Envelope: {}".format(
            handler_input.request_envelope))


class ResponseLogger(AbstractResponseInterceptor):
    """Log the response envelope."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logging.info("Response: {}".format(response))

api = 'https://www.thecocktaildb.com/api/json/v1/1/search.php?{}={}'

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