"""
This sample demonstrates an implementation of the Lex Code Hook Interface
in order to serve a sample bot which manages orders for flowers.
Bot, Intent, and Slot models which are compatible with this sample can be found in the Lex Console
as part of the 'OrderFlowers' template.

For instructions on how to set up and test this bot, as well as additional samples,
visit the Lex Getting Started documentation http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.
"""
import math
import dateutil.parser
import datetime
import time
import os
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


""" --- Helper Functions --- """


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def validate_info(location, cuisine, date, dining_time, number_of_people, phone_number, email):
    cuisine_types = ['indian', 'italian', 'korean', 'chinese', 'japanese',
                     'mexican', 'french', 'thai', 'veitnamese', 'caribbean', 'turkish']
    if cuisine is not None and cuisine.lower() not in cuisine_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different cuisine?  '
                                       .format(cuisine))

    location_types = ['manhattan', 'brooklyn', 'queens', 'sunset park', 'edgewater', 'bensonhurst', 'jackson heights',
                      'union city', 'fairview', 'crown heights', 'staten Island', 'astoria', 'sunnyside', 'long island city']
    if location is not None and location.lower() not in location_types:
        return build_validation_result(False, 'Location', '{} is out of our service. Try naming an area in NYC!'.format(location))

    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'Date', 'I did not understand that, what date would you like to go?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
            return build_validation_result(False, 'Date', 'You are not a time traveller. What day would you like to go?')

    if dining_time is not None:
        if len(dining_time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        hour, minute = dining_time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'DiningTime', None)

        if hour < 10 or hour > 23:
            # Outside of business hours
            return build_validation_result(False, 'DiningTime', 'Our business hours are from 10 am. to 10 pm. Can you specify a time during this range?')

    if number_of_people is not None:
        number_of_people = parse_int(number_of_people)
        if number_of_people < 0:
            return build_validation_result(False, 'NumberOfPeople', 'Sorry, the number of guest is invalid. Please enter a valid number.')

    if phone_number is not None:
        if len(phone_number) != 10:
            return build_validation_result(False, 'PhoneNumber', 'Sorry, the phone number is invalid. Please enter a valid number.')

    if email is not None:
        if '@' not in email:
            return build_validation_result(False, 'Email', 'Sorry, the email is invalid. Please enter a valid email.')

    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """


def greeting_intent(intent_request):

    return {
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": "Hi there, how can I help?"
            },
        }
    }


def thank_you_intent(intent_request):

    return {
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                "contentType": "PlainText",
                "content": "No problem! It's my pleasure!"
            },
        }
    }


def remind_me_intent(intent_request):
    userID = intent_request['userId']
    if not userID:
        return {
            "dialogAction": {
                "type": "Close",
                "fulfillmentState": "Fulfilled",
                "message": {
                    "contentType": "PlainText",
                    "content": "Sorry I have no record given your information"
                },
            }
        }
    dynamodb_resource = boto3.resource("dynamodb")
    table = dynamodb_resource.Table('last-recommendation')
    response = table.get_item(
        Key={
            'id': userID,
        }
    )
    if 'Item' in response:
        return {
            "dialogAction": {
                "type": "Close",
                "fulfillmentState": "Fulfilled",
                "message": {
                    "contentType": "PlainText",
                    "content": "Your last recommendation is " + response["Item"]["Last Recommend"]
                },
            }
        }
    else:
        return {
            "dialogAction": {
                "type": "Close",
                "fulfillmentState": "Fulfilled",
                "message": {
                    "contentType": "PlainText",
                    "content": "Sorry I have no record given your information"
                },
            }
        }


def dining_suggestions_intent(intent_request):
    """
    Performs dialog management and fulfillment for ordering flowers.
    Beyond fulfillment, the implementation of this intent demonstrates the use of the elicitSlot dialog action
    in slot validation and re-prompting.
    """

    location = get_slots(intent_request)["Location"]
    cuisine = get_slots(intent_request)["Cuisine"]
    date = get_slots(intent_request)["Date"]
    dining_time = get_slots(intent_request)["DiningTime"]
    number_of_people = get_slots(intent_request)["NumberOfPeople"]
    phone_number = get_slots(intent_request)["PhoneNumber"]
    email = get_slots(intent_request)["Email"]

    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        # Use the elicitSlot dialog action to re-prompt for the first violation detected.
        slots = get_slots(intent_request)

        validation_result = validate_info(
            location, cuisine, date, dining_time, number_of_people, phone_number, email)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        # Pass the price of the flowers back through session attributes to be used in various prompts defined
        # on the bot model.
        output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {
        }

        return delegate(output_session_attributes, get_slots(intent_request))

    elif source == 'FulfillmentCodeHook':

        userID = intent_request['userId']

        sqs = boto3.client('sqs')

        response = sqs.get_queue_url(QueueName='Q1')
        url = response['QueueUrl']

        response = sqs.send_message(
            QueueUrl=url,
            MessageAttributes={
                'Location': {
                    'DataType': 'String',
                    'StringValue': location
                },
                'Cuisine': {
                    'DataType': 'String',
                    'StringValue': cuisine
                },
                'Date': {
                    'DataType': 'String',
                    'StringValue': date
                },
                'DiningTime': {
                    'DataType': 'String',
                    'StringValue': dining_time
                },
                'NumberOfPeople': {
                    'DataType': 'String',
                    'StringValue': number_of_people
                },
                'PhoneNumber': {
                    'DataType': 'String',
                    'StringValue': phone_number
                },
                'Email': {
                    'DataType': 'String',
                    'StringValue': email
                }
            },
            MessageBody=(
                'Other messages'
            )
        )
    # Order the flowers, and rely on the goodbye message of the bot to define the message to the end user.
    # In a real bot, this would likely involve a call to a backend service.
    return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': "Okay! I will send the restaurant information to your email {}".format(email)})


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(
        intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'RemindMeIntent':
        return remind_me_intent(intent_request)
    if intent_name == 'DiningSuggestionsIntent':
        return dining_suggestions_intent(intent_request)
    if intent_name == 'GreetingIntent':
        return greeting_intent(intent_request)
    if intent_name == 'ThankYouIntent':
        return thank_you_intent(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
