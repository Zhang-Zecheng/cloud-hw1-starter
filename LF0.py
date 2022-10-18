import json
import boto3


def lambda_handler(event, context):
    # TODO implement

    client = boto3.client('lex-runtime')
    userInput = json.loads(event['body'])[
        'messages'][0]['unstructured']['text']

    d = client.post_text(
        botName='SuggestRestaurant',
        botAlias='$LATEST',
        userId='string',
        inputText=userInput
    )

    return {
        "statusCode": 200,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        "body": json.dumps({
            "messages": [
                {
                    "type": "unstructured",
                    "unstructured": {
                        "id": "string",
                        "text": d['message'],
                        "timestamp": "string"
                    }
                }
            ]
        }),

    }
