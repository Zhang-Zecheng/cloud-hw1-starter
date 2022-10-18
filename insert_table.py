import json
import boto3
import requests
import datetime
from decimal import Decimal

from botocore.exceptions import ClientError


def lambda_handler(event, context):
    # connect DB
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table('yelp-restaurants')
    # call Yelp API
    KEY = 'EmwlqR_l5fK100ZstzfQPyz4Pncq4_DHahDGh-YF3DeZVV_CHlPWFd58mg4DVGRxVQbQ01WVFBEr31UygZwrptGNLntQK9D7q_6RD0V0zooh0P0WFWNIxywwLrhJY3Yx'
    header = {'Authorization': 'bearer %s' % KEY}

    cuisine_types = ['indian', 'italian',
                     'mexican', 'chinese', 'japanese', 'french']

    for cuisine in cuisine_types:
        offset = 0
        for i in range(20):
            query = {
                'location': 'New York',
                'limit': 50,
                'offset': offset,
                'categories': cuisine,
            }
            offset += 50

            response = requests.get(
                url='https://api.yelp.com/v3/businesses/search', params=query, headers=header)
            data = response.json()

            for item in data['businesses']:
                try:
                    table.put_item(
                        Item={
                            'id': item['id'],
                            'name': item['name'],
                            'category': item['categories'][0]['alias'],
                            'address': item['location']['address1'],
                            'city': item['location']['city'],
                            'zipcode': item['location']['zip_code'],
                            'latitude': Decimal(str(item['coordinates']['latitude'])),
                            'longitude': Decimal(str(item['coordinates']['longitude'])),
                            'reviewCount': item['review_count'],
                            'rating': Decimal(str(item['rating'])),
                            'insertedAtTimestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    )
                except ClientError as e:
                    print(e.response['Error']['Code'])
