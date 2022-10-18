import json
import urllib3
import random
import boto3
import os
import requests
from requests.auth import HTTPBasicAuth
from botocore.exceptions import ClientError

URL = 'https://search-yelp-restaurant-search-5uqp2tvby4x2ickhmssb2r73rq.us-east-1.es.amazonaws.com/restaurants/_search'
ARN = 'arn:aws:sns:us-east-1:445734408456:restaurant_suggest'
username = 'roderickzzc'
password = 'Woshibt1!'

sqs = boto3.resource('sqs')
sqs_client = boto3.client('sqs')
sns = boto3.client('sns')
sns_resource = boto3.resource('sns')
dynamo_client = boto3.client('dynamodb')
CHARSET = "UTF-8"


def lambda_handler(event, context):

    queue = sqs.get_queue_by_name(QueueName='Q1')
    queue_url = sqs_client.get_queue_url(QueueName='Q1')['QueueUrl']

    sqs_response = queue.receive_messages(
        MessageAttributeNames=['All'],
        MaxNumberOfMessages=1,
    )

    for message in sqs_response:
        info = message.message_attributes
        data = {
            'category': info['Cuisine']['StringValue'],
            'num_of_people': info['NumberOfPeople']['StringValue'],
            'date': info['Date']['StringValue'],
            'dining_time': info['DiningTime']['StringValue'],
            'phone': info['PhoneNumber']['StringValue'],
            'email': info['Email']['StringValue'],
        }

        query = {
            "size": 10,
            "query": {
                "term": {
                    "category": data['category'].lower()
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
        }

        es_response = requests.post(
            URL, auth=HTTPBasicAuth(username, password), headers=headers, data=json.dumps(query))

        if es_response.json()['hits']['total']['value'] > 0:
            es_ids = [hit['_source']["businessId"]
                      for hit in es_response.json()['hits']['hits']]

            batch_keys = {
                'yelp-restaurants': {
                    'Keys': [{'id': {'S': es_id}} for es_id in es_ids]
                },
            }

            dynamo_response = dynamo_client.batch_get_item(
                RequestItems=batch_keys)
            restaurants = [{
                'name': record['name']['S'],
                'address': record['address']['S'],
                'zipcode': record['zipcode']['S'],
                'rating': record['rating']['N'],
                'reviews': record['reviewCount']['N'],
            } for record in dynamo_response['Responses']['yelp-restaurants']]

            chosen_restaurant = random.choice(restaurants)
            sendMessage = '''
            Here are the details for the {} cuisine you asked for:
            People: {}
            Date : {}
            Time: {}
            Restaurant Name : {} 
            Restaurant Address: {} 
            ZipCode : {} 
            Rating : {} 
            Reviews : {} 
            '''.format(data['category'], data['num_of_people'], data['date'], data['dining_time'], chosen_restaurant['name'], chosen_restaurant['address'], chosen_restaurant['zipcode'], chosen_restaurant['rating'], chosen_restaurant['reviews'],)

            # sns.publish(
            #     TargetArn=ARN,
            #     Message = sendMessage,
            #     Subject='Your {} Restaurant Suggestion'.format(data['category'])
            # )

            ses_client = boto3.client("ses", region_name="us-east-1")
            CHARSET = "UTF-8"

            ses_client.send_email(
                Destination={
                    "ToAddresses": [
                        data['email'],
                    ],
                },
                Message={
                    "Body": {
                        "Text": {
                            "Charset": CHARSET,
                            "Data": sendMessage,
                        }
                    },
                    "Subject": {
                        "Charset": CHARSET,
                        "Data": 'Your {} Restaurant Suggestion'.format(data['category']),
                    },
                },
                Source="roderickzzc@gmail.com",
            )

            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message.receipt_handle
            )
            # ses_client = boto3.client('ses')
            # response = ses_client.send_email(
            #     Destination={
            #         "ToAddresses": [
            #             data['email'],
            #         ],
            #     },
            #     Message={
            #         "Body": {
            #             "Text": {
            #                 "Charset": CHARSET,
            #                 "Data": sendMessage,
            #             }
            #         },
            #         "Subject": {
            #             "Charset": CHARSET,
            #             "Data": "Your {} Restaurant Suggestion!".format(data['category']),
            #         },
            #     },
            #     Source="<ENTER>",
            # )

        else:
            return {"errror": 'Unknown'}
