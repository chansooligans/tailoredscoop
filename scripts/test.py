#!/usr/bin/python
import boto3

client = boto3.client("ses", region_name="us-east-1")

response = client.send_email(
    Destination={
        "ToAddresses": [
            "chansoosong01@gmail.com",
        ],
    },
    Message={
        "Body": {
            "Html": {
                "Charset": "UTF-8",
                "Data": "test",
            },
            "Text": {
                "Charset": "UTF-8",
                "Data": "test",
            },
        },
        "Subject": {
            "Charset": "UTF-8",
            "Data": "test",
        },
    },
    Source="Tailored Scoop <apps.tailoredscoop@gmail.com>",
)
