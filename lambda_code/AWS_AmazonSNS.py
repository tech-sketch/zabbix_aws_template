from __future__ import print_function

import os
import re
import json
import socket
import struct
import time
import calendar
import datetime
import dateutil.parser

def lambda_handler(event, context):
    sns_zabbix = SnsZabbix()
    sns_zabbix.make_send_items(event)
    sns_zabbix.send_to_zabbix()

class SnsZabbix:
    def __init__(self):
        self.zabbix_host = "localhost"
        self.zabbix_port = 10051
        self.send_items = []

    def make_send_items(self, event):
        for record in event['Records']:
            event_type = self.__check_event_type(record)
            self.__add_send_item(record, event_type)

    def __add_send_item(self, record, event_type):
        send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
        send_item = json.loads(send_json_string)
        message = json.loads(record['Sns']['Message'])
        if event_type == "AutoScaling":
            send_item["host"] = "AutoScaling"
            value = []
            value.append("Event : " + message['Event'])
            value.append("Service : " + message['Service'])
            value.append("Description : " + message['Description'])
            value.append("AvailabilityZone : " + message['Details']['Availability Zone'])
            value.append("AutoScalingGroupName : " + message['AutoScalingGroupName'])
            value.append("Cause : " + message['Cause'])
            value.append("StatusCode : " + message['StatusCode'])
            value.append("StatusMessage : " + message['StatusMessage'])
            send_item["value"] = os.linesep.join(value)

        elif event_type == "RDS":
            send_item["host"] = message["Source ID"]

            value = []
            value.append("EventSource : " + message["Event Source"])
            value.append("IdentifierLink : " + message["Identifier Link"])
            value.append("SourceId : " + message["Source ID"])
            value.append("EventId : " + message["Event ID"])
            value.append("EventMessage : " + message["Event Message"])
            value.append("TopicArn : "+ record['Sns']['TopicArn'])
            send_item["value"] = os.linesep.join(value)
            

        elif event_type == "CloudWatch":
            send_item["host"] = message['Trigger']['Dimensions'][0]['value']
            value = []
            value.append("NewStatus : " + message['NewStateValue'])
            value.append("MetricNamespace : " + message['Trigger']['Namespace'])
            value.append("Dimensions : " + message['Trigger']['Dimensions'][0]['name'] + " = " + message['Trigger']['Dimensions'][0]['value'])
            value.append("MetricName : " + message['Trigger']['MetricName'])
            value.append("NewStateReason : " + message['NewStateReason'])
            value.append("Region : " + message['Region'])
            value.append("TopicArn : " + record['Sns']['TopicArn'])
            send_item["value"] = os.linesep.join(value) 
 
        elif event_type == "EC2RDS":
            send_item["host"] = message['Trigger']['Namespace'].replace('AWS/',"")
            value = []
            value.append("NewStatus : " + message['NewStateValue'])
            value.append("Dimensions : " + json.dumps(message['Trigger']['Dimensions']))
            value.append("MetricName : " + message['Trigger']['MetricName'])
            value.append("NewStateReason : " + message['NewStateReason'])
            value.append("Region :" + message['Region'])
            value.append("TopicArn : " + record['Sns']['TopicArn'])
            send_item["value"] = os.linesep.join(value)

        else:
            send_item["host"] = "Other"
            value = json.loads(record['Sns']['Message'])

        send_item["key"] = "sns.event"
        event_timestamp = dateutil.parser.parse(record['Sns']['Timestamp'])
        send_item["clock"] = calendar.timegm(event_timestamp.utctimetuple())
        self.send_items.append(send_item)

    def __check_event_type(self, record):
        message = json.loads(record['Sns']['Message'])
        subject = record['Sns']['Subject']
        if subject.find("Auto Scaling") != -1:
            return "AutoScaling"
        elif subject.find("RDS Notification Message") != -1:
            return "RDS"
        elif message['Trigger']['Dimensions']:
            return "CloudWatch"
        elif message['Trigger']['Namespace']:
            return "EC2RDS"
        else:
            return "Other"

    def send_to_zabbix(self):
        now = "%.9f" % time.time()
        sec = now.split(".")[0]
        ns = now.split(".")[1]
        send_data = json.loads('{"request":"sender data","data":[],"clock":"%s","ns":"%s" }' % (sec, ns))
        send_data["data"] = self.send_items
        send_data_string = json.dumps(send_data)
        zbx_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            zbx_client.connect((self.zabbix_host, self.zabbix_port))
        except Exception:
            print("Error")
            quit()
        header = struct.pack('<4sBQ', 'ZBXD', 1, len(send_data_string))
        send_data_string = header + send_data_string
        try:
            zbx_client.sendall(send_data_string)
        except Exception:
            print('Data sending failure')
            quit()
        response = ''
        while True:
            data = zbx_client.recv(4096)
            if not data:
                break
            response += data
        print(response[13:])
        zbx_client.close()
