"""
Run this ONCE to create the DynamoDB blog table and seed initial posts.

Usage:
  cd backend
  python setup_blog_table.py
"""
import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def create_blog_table():
    dynamodb = boto3.client(
        'dynamodb',
        region_name=os.getenv('AWS_REGION', 'ap-south-1'),
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT'),
    )

    table_name = os.getenv('BLOG_TABLE', 'cosmic-blog')

    # Check if already exists
    existing = dynamodb.list_tables().get('TableNames', [])
    if table_name in existing:
        print(f'Table "{table_name}" already exists — skipping creation.')
    else:
        dynamodb.create_table(
            TableName=table_name,
            AttributeDefinitions=[
                {'AttributeName': 'id',   'AttributeType': 'S'},
                {'AttributeName': 'slug', 'AttributeType': 'S'},
            ],
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'slug-index',
                    'KeySchema': [{'AttributeName': 'slug', 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5},
                }
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5},
        )
        print(f'Table "{table_name}" created.')

    # Seed initial posts
    print('Seeding initial posts...')
    from models.blog import seed_initial_posts
    seed_initial_posts()
    print('Done!')

if __name__ == '__main__':
    create_blog_table()
