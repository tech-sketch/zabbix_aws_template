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

print('Loading function')

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    
    event_type = eventcheck(event, context)
    if event_type == "AutoScaling":
        send_item = edit_AutoScaling(event, context)
    elif event_type == "RDS":
        send_item = edit_RDS(event, context)
    elif event_type == "CloudWatch":
        send_item = edit_CloudWatch(event, context)
    elif event_type == "EC2RDS":
        send_item = edit_EC2RDS(event, context)
    elif event_type == "Other":
        send_item = edit_Other(event, context)

    send_to_zabbix(send_item)

def eventcheck(event, context):
    Message = json.loads(event['Records'][0]['Sns']['Message'])
    Subject = event['Records'][0]['Sns']['Subject']
    if Subject.find("Auto Scaling") != -1:
        event_type = "AutoScaling"
    elif Subject.find("RDS Notification Message") != -1:
        event_type = "RDS"
    elif Message['Trigger']['Dimensions']:
        event_type = "CloudWatch"
    elif Message['Trigger']['Namespace']:
        event_type = "EC2RDS"
    else:
        event_type = "Other"

    return event_type

def edit_AutoScaling(event, context):
    end_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)
    
    Message = json.loads(event['Records'][0]['Sns']['Message'])
    Value = "Event : "+Message['Event'], "Service : "+Message['Service'], "Description : "+Message['Description'], "AvailabilityZone : "+Message['Details']['Availability Zone'], "AutoScalingGroupName : "+Message['AutoScalingGroupName'], "Cause : "+Message['Cause'], "StatusCode : "+Message['StatusCode'], "StatusMessage : "+Message['StatusMessage']
    encode_json_data = json.dumps(Value)
    send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
    send_item["host"] = "AutoScaling"
    send_item["key"] = "sns.event"
    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime
    
    return send_item

def edit_RDS(event, context):
    send_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)
    
    Message = json.loads(event['Records'][0]['Sns']['Message'])
    
    replace = re.compile("(.*)(#\n)(.*:)(.*)")
    match = replace.match(Message["Identifier Link"])
    
    Value = "EventSource : "+Message["Event Source"], "IdentifierLink : "+match.group(1), "SourceId : "+match.group(4), "EventMessage : "+Message["Event Message"], "TopicArn : "+event['Records'][0]['Sns']['TopicArn']
    encode_json_data = json.dumps(Value)
    send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
    send_item["host"] = match.group(4).strip()
    send_item["key"] = "sns.event"
    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime
    
    return send_item

def edit_CloudWatch(event,context):
    send_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)
    
    Message = json.loads(event['Records'][0]['Sns']['Message'])
    Value = "NewStatus : "+Message['NewStateValue'], "MetricNamespace : "+Message['Trigger']['Namespace'], "Dimensions : "+Message['Trigger']['Dimensions'][0]['name']+" = "+Message['Trigger']['Dimensions'][0]['value'], "MetricName : "+Message['Trigger']['MetricName'], "NewStateReason : "+Message['NewStateReason'], "Region : "+Message['Region'], "TopicArn : "+event['Records'][0]['Sns']['TopicArn']
    encode_json_data = json.dumps(Value)
    send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
    send_item["host"] = Message['Trigger']['Dimensions'][0]['value']
    send_item["key"] = "sns.event"
    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime
    
    return send_item

def edit_EC2RDS(event, context):
    send_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)
    
    Message = json.loads(event['Records'][0]['Sns']['Message'])
    Value = "NewStatus : "+Message['NewStateValue'], "Dimensions : "+json.dumps(Message['Trigger']['Dimensions']), "MetricName : "+Message['Trigger']['MetricName'], "NewStateReason : "+Message['NewStateReason'], "Region :"+Message['Region'], "TopicArn : "+event['Records'][0]['Sns']['TopicArn']
    encode_json_data = json.dumps(Value)
    send_item["value"] = encode_json_data.replace(",",os.linesep).replace("[","").replace("]","")
    send_item["host"] = Message['Trigger']['Namespace'].replace('AWS/',"")
    send_item["key"] = "sns.event"
    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime
    
    return send_item

def edit_Other(event, context):
    send_data = json.loads('{"request":"sender data","data":[]}')
    send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
    send_item = json.loads(send_json_string)
    
    Value = json.loads(event['Records'][0]['Sns']['Message'])
    encode_json_data = json.dumps(Value)
    send_item["value"] = encode_json_data.replace(",",os.linesep)
    send_item["host"] = "Other"
    send_item["key"] = "sns.event"
    Timestamp = dateutil.parser.parse(event['Records'][0]['Sns']['Timestamp'])
    Unixtime = calendar.timegm(Timestamp.utctimetuple())
    send_item["clock"] = Unixtime
    
    return send_item

def send_to_zabbix(send_item):
    send_data = json.loads('{"request":"sender data","data":[]}')
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
