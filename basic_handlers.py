# Modulprojekt zum Seminar Dialogmodellierung
# Alexa skill
# Sara Derakhshani, Hannah Peuckmann
# SoSe 2020
# Classes of basic handlers for exceptions, logging, help and cancel

import logging

import json

import random

from ask_sdk_model.services import ServiceException
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
from ask_sdk_core.dispatch_components import (
    AbstractRequestHandler, AbstractExceptionHandler,
    AbstractResponseInterceptor, AbstractRequestInterceptor)

# create logger, logger settings
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s:%(levelname)s:%(funcName)s:%(message)s')
file_handler = logging.FileHandler('sex_on_the_beach.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent. Gives a short info on usage."""

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # stores the help message, read from a json that
        # contains the outsourced response messages
        speech = get_speech("HELP_MSG")

        handler_input.response_builder.speak(speech)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # stores a goodby message, read from a json that
        # contains the outsourced response messages
        speech = get_speech("STOP_MSG")
        handler_input.response_builder.speak(speech)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    """AMAZON.FallbackIntent is only available in en-US locale.
    This handler will not be triggered except in that locale,
    so it is safe to deploy on any locale.
    """

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # message for failed requests
        speech = get_speech("HANDLE_EXCEPTION")
        # gives a short info on usage
        reprompt = get_speech("REPROMPT")
        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


# Exception Handler classes
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Handler to catch all kinds of exceptions"""

    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        # message for failed requests
        speech = get_speech('HANDLE_EXCEPTION')
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


class RequestLogger(AbstractRequestInterceptor):
    """Logger to log the content of the request envelope."""

    def process(self, handler_input):
        logger.info("Request Envelope: {}".format(
            handler_input.request_envelope))


class ResponseLogger(AbstractResponseInterceptor):
    """Logger to log the content of the response envelope."""

    def process(self, handler_input, response):
        logger.info("Response: {}".format(response))


# funktion to read from a json
def get_speech(prompt):
    """reads the response messages outsourced to a json file."""
    with open('strings.json') as strings:
        # read json
        string_data = json.load(strings)
        # select value list, value is a list of possible responses
        prompt_list = string_data[prompt]
        # select a random response from the value list
        prompt = random.choice(prompt_list)
    return prompt
