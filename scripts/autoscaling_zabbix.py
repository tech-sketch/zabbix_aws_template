#!/bin/env python

import boto3
import json
import argparse
import os
import socket
import struct
import time
import calendar
from zabbix_api import ZabbixAPI,ZabbixAPIException
from datetime import datetime
from datetime import timedelta

class AwsZabbix:

    def __init__(self, region, access_key, secret, pref_if, zbx_url, zbx_user, zbx_pass, set_macro):
        self.region = region
        self.access_key = access_key
        self.secret = secret
        self.pref_if = pref_if
        self.zbx_url = zbx_url
        self.zbx_user = zbx_user
        self.zbx_pass = zbx_pass
        self.set_macro = set_macro

        self.ec2 = boto3.resource(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret
        )
        self.client = boto3.client(
            'autoscaling',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret
        )

        self.zapi = ZabbixAPI(server=self.zbx_url)
        self.zapi.login(self.zbx_user, self.zbx_pass)


    def __get_interfaces(self, host, region, key, secret):
        interfaces = []
        priv_intf = ''
        pub_intf = ''
        instance = self.ec2.Instance(host)

        priv_intf = (
            {
                "type":1,
                "useip":1,
                "main":(1 if self.pref_if == "Private" else 0),
                "ip":instance.private_ip_address,
                "dns":"",
                "port":"10050"
            })
        if instance.public_ip_address:
            pub_intf = (
                {
                    "type":1,
                    "useip":1,
                    "main":(1 if self.pref_if == "Public" else 0),
                    "ip":instance.public_ip_address,
                    "dns":"",
                    "port":"10050"
                })
        else:
            priv_intf["main"] = 1

        if pub_intf:
            interfaces = [priv_intf, pub_intf]
        else:
            interfaces = [priv_intf]

        return interfaces


    def __get_hostid(self, instanceid):
        response = self.zapi.host.get({"filter":{"host":instanceid}})

        return response[0]['hostid']


    def send_autoscaling_data_to_zabbix(self):
        response = self.client.describe_auto_scaling_groups()
        for group in response["AutoScalingGroups"]:
            groupid = ''
            templates = []
            template_ids = []
            hostgroup_hosts = []
            hostids = []
            usermacros = []

            try:
                response = self.zapi.hostgroup.create({'name': group['AutoScalingGroupName']})
                groupid = response['groupids'][0]
            except ZabbixAPIException, e:
                response = self.zapi.hostgroup.get({'filter':{'name':[group['AutoScalingGroupName']]},"selectHosts":"extend"})
                for hostgroup_host in response[0]['hosts']:
                    hostgroup_hosts.append(hostgroup_host['host'])
                groupid = response[0]['groupid']

            for tag in group['Tags']:
                if tag['Key'] == 'ZabbixTemplates':
                    templates =  tag['Value'].split(',')

            try:
                response = self.zapi.template.get({"filter":{"host":templates}})
                for template in response:
                    template_ids.append({"templateid": template["templateid"]}) 
            except ZabbixAPIException, e:
                print str(e)

            for instance in group['Instances']:
                instanceid = instance['InstanceId']
                if instanceid in hostgroup_hosts:
                    hostgroup_hosts.remove(instanceid)
                interfaces = self.__get_interfaces(instanceid, self.region, self.access_key, self.secret)
            
                try:
                    response = self.zapi.host.create({
                        "host":instance['InstanceId'],
                        "interfaces":interfaces,
                        "templates":template_ids,
                        "groups":[{"groupid":groupid}]})
                except ZabbixAPIException, e:
                    hostid = self.__get_hostid([instanceid])
                    ## Update host
                    response = self.zapi.host.update({
                        "hostid":hostid,
                        "templates":template_ids,
                        "groups":[{"groupid":groupid}]})

                    main_intf = self.zapi.hostinterface.get({"filter":{"hostid":hostid, "main":"1"}})
                    sub_intf = self.zapi.hostinterface.get({"filter":{"hostid":hostid, "main":"0"}})

                    for aws_ifname in interfaces:
                        interface = aws_ifname
                        interface["hostid"] = hostid
                        if aws_ifname["main"] == 1:
                            ## Update main interface
                            interface["interfaceid"] = main_intf[0]["interfaceid"]
                            response = self.zapi.hostinterface.update(interface)
                        elif sub_intf:
                            ## Update sub interface
                            interface["interfaceid"] = sub_intf[0]["interfaceid"]
                            response = self.zapi.hostinterface.update(interface)
                        else:
                            ## Create new sub interface
                            response = self.zapi.hostinterface.create(interface)
                            
                ## Set user macros for CloudWatch
                if self.set_macro == "True":
                    hostid = self.__get_hostid([instance['InstanceId']])
                    try:
                        response = self.zapi.usermacro.create({
                            "hostid":hostid,
                            "macro":"{$REGION}",
                            "value":self.region
                            })
                        response = self.zapi.usermacro.create({
                            "hostid":hostid,
                            "macro":"{$KEY}",
                            "value":self.access_key
                            })
                        response = self.zapi.usermacro.create({
                            "hostid":hostid,
                            "macro":"{$SECRET}",
                            "value":self.secret
                            })
                    except ZabbixAPIException, e:
                        ## Replace user macros
                        response = self.zapi.usermacro.get({
                            "hostids":hostid,
                            })
                        for macro in response:
                            macro_update = {}
                            macro_update["macro"] = macro["macro"]
                            if macro["macro"] == "{$REGION}":
                                macro_update["value"] = self.region
                            elif macro["macro"] == "{$KEY}":
                                macro_update["value"] = self.access_key
                            elif macro["macro"] == "{$SECRET}":
                                macro_update["value"] = self.secret
                            else:
                                macro_update["value"] = macro["value"]
                            usermacros.append(macro_update)
                        response = self.zapi.host.update({
                            "hostid":hostid,
                            "macros":usermacros
                            })

            ## host status disable for not exist EC2 instance host
            for deleted_host in hostgroup_hosts:
                hostid = self.__get_hostid([deleted_host])

                response = self.zapi.host.update({
                    "hostid":hostid,
                    "status":1})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get AWS Auto Scaling Metric list json format.')

    parser.add_argument('-r', '--region', default=os.getenv("AWS_DEFAULT_REGION"), help='set AWS region name(e.g.: ap-northeast-1)')
    parser.add_argument('-a', '--accesskey', default=os.getenv("AWS_ACCESS_KEY_ID"), help='set AWS Access Key ID')
    parser.add_argument('-s', '--secret', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='set AWS Secret Access Key')
    parser.add_argument('-z', '--url', default="http://localhost/zabbix", help='set Zabbix Frontend url')
    parser.add_argument('-u', '--user', default="Admin", help='set Zabbix API username')
    parser.add_argument('-p', '--password', default="zabbix", help='set Zabbix API user password')
    parser.add_argument('-P', '--preffer-if', default="Private", choices=['Private', 'Public'], help='set preffer interface(e.g.: Private or Public)')
    parser.add_argument('-m', '--set-macro', default="False", choices=['False', 'True'], help='set User macros for CloudWatch(e.g.: False or True)')

    args = parser.parse_args()
    aws_zabbix = AwsZabbix(region=args.region, access_key=args.accesskey, secret=args.secret, pref_if=args.preffer_if, zbx_url=args.url, zbx_user=args.user, zbx_pass=args.password, set_macro=args.set_macro)
    aws_zabbix.send_autoscaling_data_to_zabbix()

