from __future__ import print_function

import json
import boto3

print('Loading function')   

def lambda_handler(event, context):
    event = json.loads(event)
    response = operation_ec2(event)
    return response

def operation_ec2(event):
    def checkExecResult(response):
        print(response)
        if(response["ResponseMetadata"]["HTTPStatusCode"] == 200):
            return "Succeed"
        else:
            return "Failed"    

    def stopEC2(ec2):
        execResult = ec2.stop()
        return checkExecResult(execResult)
        
    def startEC2(ec2):
        execResult = ec2.start()
        return checkExecResult(execResult)

    def checkInstanceState(ec2,operation):
        if(operation == "start"):
            if(ec2.state['Name'] == "stopped"):
                return True
        elif(operation == "stop"):
            if(ec2.state['Name'] == "running"):
                return True
        return False

    response = {
        "message" : "Nothing Operation",
        "instance_id": None,
        "operation": None
    }

    if "instance_id" not in event: 
        response["message"] = "Not Found InstanceID"
        return response        
    
    if "operation" not in event:
        response["message"] = "Not Found Operation"
        return response
    
    print(event)
    instanceid = event["instance_id"]
    response["instance_id"] = instanceid
    
    print("instance_id: " + instanceid)    
    ec2 = boto3.resource('ec2').Instance(instanceid)
    
    if(checkInstanceState(ec2,event["operation"])):
        if(event["operation"] == "stop"):
            print("Stop EC2: " + instanceid)
            response["operation"] = "stop"
            response["message"] = stopEC2(ec2)
        elif(event["operation"] == "start"):
            print("Start EC2: " + instanceid)
            response["operation"] = "start"
            response["message"] = startEC2(ec2)
        else:
            response["message"] = "Invalid Operation."
    else:
        response["message"] = "Cannot Operation. Instance State is " + ec2.state['Name'] + "."
    return response