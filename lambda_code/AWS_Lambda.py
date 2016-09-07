from __future__ import print_function

import json
import boto3

print('Loading function')   

def lambda_handler(event, context):
    event = json.loads(event)
    response = operation_ec2(event)
    return response

def operation_ec2(event):
    def getInstanceState(ec2):
        return ec2.state['Name']
    
    def checkStatusCode(response,operation):
        print(response)
        if(response["ResponseMetadata"]["HTTPStatusCode"] == 200):
            return {
                "message": "Succeed: " + operation + " Instance"
                }
        else:
            return{
                "message": "Failed: " + operation +" Instance"
                }
    
    def stopEC2(ec2):
        return checkStatusCode(ec2.stop(),operation="Stop")
        
    def startEC2(ec2):
        return checkStatusCode(ec2.start(),operation="Start")

    if "instanceid" not in event: 
        return {
            "message": "Not Found Instance-ID"
            }
            
    instanceid = event["instanceid"]
    
    print("instance-id: " + instanceid)    
    ec2 = boto3.resource('ec2').Instance(instanceid)
    
    msg = "Failed"
    if(getInstanceState(ec2) == "running"):
        print("Stop EC2: " + instanceid)
        msg = stopEC2(ec2)
    else:
        print("Start EC2: "+instanceid)
        msg = startEC2(ec2)
    
    return {
        "message": msg
        }