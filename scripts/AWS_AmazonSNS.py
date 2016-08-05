from __future__ import print_function

import os
import json
import socket
import struct
import time
import calendar
import datetime
import dateutil.parser

print('Loading function')

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    send_to_zabbix(event, context)

def send_to_zabbix(event, data):
    send_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)

    Message = json.loads(event['Records'][0]['Sns']['Message'])
    Subject = event['Records'][0]['Sns']['Subject']

    if Subject.find("launch") != -1:
        Value = "Event : "+Message['Event'], "Service : "+Message['Service'], "Description : "+Message['Description'], "AvailabilityZone : "+Message['Details']['Availability Zone'], "AutoScalingGroupName : "+Message['AutoScalingGroupName'], "Cause : "+Message['Cause']
        encode_json_data = json.dumps(Value)
        send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
        send_item["host"] = "Auto_Scaling_"+Message['Event'].replace('autoscaling:EC2_INSTANCE_',"")

    elif Subject.find("termination") != -1:
        Value = "Event : "+Message['Event'], "Service : "+Message['Service'], "Description : "+Message['Description'], "AvailabilityZone : "+Message['Details']['Availability Zone'], "AutoScalingGroupName : "+Message['AutoScalingGroupName'], "Cause : "+Message['Cause']
        encode_json_data = json.dumps(Value)
        send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
        send_item["host"] = Message['EC2InstanceId']

    elif Message['Trigger']['Dimensions']:
        Value = "NewStatus : "+Message['NewStateValue'], "Dimensions : "+Message['Trigger']['Dimensions'][0]['name']+" = "+Message['Trigger']['Dimensions'][0]['value'], "MetricName : "+Message['Trigger']['MetricName'], "NewStateReason : "+Message['NewStateReason'], "Region : "+Message['Region'], "TopicArn : "+event['Records'][0]['Sns']['TopicArn']
        encode_json_data = json.dumps(Value)
        send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
        send_item["host"] = Message['Trigger']['Dimensions'][0]['value']

    elif Message['Trigger']['Namespace']:
        Value = "NewStatus : "+Message['NewStateValue'], "Dimensions : "+json.dumps(Message['Trigger']['Dimensions']), "MetricName : "+Message['Trigger']['MetricName'], "NewStateReason : "+Message['NewStateReason'], "Region : "+Message['Region'], "TopicArn : "+event['Records'][0]['Sns']['TopicArn']
        encode_json_data = json.dumps(Value)
        send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
        send_item["host"] = Message['Trigger']['Namespace'].replace('AWS/',"")

    else:
        Value = json.loads(event['Records'][0]['Sns']['Message'])
        encode_json_data = json.dumps(Value)
        send_item["value"] = encode_json_data.replace(",",os.linesep)
        send_item["host"] = "Other"

    send_item["key"] = "sns.event"

    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime

    send_data["data"].append(send_item)
    send_data_string = json.dumps(send_data)
    zbx_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        zbx_client.connect(("<IP address>", <port>))
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
