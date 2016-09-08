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

    def checkInstanceState(ec2):
        if(ec2.state['Name'] == "runnning" or ec2.state['Name'] == "stopping"):
            return True
        else:
            return False

    response = {
        "message" : None,
        "instance_id": None,
        "operation": None
    }

    if "instanceid" not in event: 
        response["message"] = "Not Found InstanceID"
        return response        
    
    if "operation" not in event:
        response["message"] = "Not Found Operation"
        return response    

    instanceid = event["instanceid"]
    
    print("instance_id: " + instanceid)    
    ec2 = boto3.resource('ec2').Instance(instanceid)
    
    if(checkInstanceState(ec2)):
        if(event["operation"] == "stop")
            print("Stop EC2: " + instanceid)
            response["operation"] = "stop"
            response["operation"] = stopEC2(ec2)
        else:
            print("Start EC2: "+instanceid)
            response["operation"] = "start"
            response["operation"] = startEC2(ec2)
    
    return response
