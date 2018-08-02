#!/bin/env python

import boto3
import json
import argparse
import os
import socket
import struct
import time
import calendar
from datetime import datetime
from datetime import timedelta

class Metric:
    def __init__(self, name="", namespace="", unit="", dimensions=[]):
        self.name = name
        self.namespace = namespace
        self.unit = unit
        self.dimensions = dimensions

class AwsZabbix:

    def __init__(self, region, access_key, secret, identity, hostname, service, timerange_min,
                 zabbix_host, zabbix_port):
        self.zabbix_host = zabbix_host
        self.zabbix_port = zabbix_port
        self.identity = identity
        self.hostname = hostname
        self.service = service
        self.timerange_min = timerange_min
        self.id_dimentions = {
            'ec2':'InstanceId',
            'rds':'DBInstanceIdentifier',
            'elb':'LoadBalancerName',
            'ebs':'VolumeId',
            'billing': 'Currency'
        }
        self.client = boto3.client(
            'cloudwatch',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret
        )
        self.sum_stat_metrics = [
            {'namespace': 'AWS/ELB', 'metricname': 'RequestCount'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_Backend_2XX'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_Backend_3XX'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_Backend_4XX'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_Backend_5XX'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_ELB_4XX'},
            {'namespace': 'AWS/ELB', 'metricname': 'HTTPCode_ELB_5XX'}
        ]

    def __get_metric_list(self):
        resp = self.client.list_metrics(
            Dimensions = [
                {
                    'Name': self.id_dimentions[self.service],
                    'Value': ('USD' if self.service == "billing" else self.identity)
                }
            ]
        )
        metric_list = []
        for data in resp["Metrics"]:
            metric = Metric(name=data["MetricName"], namespace=data["Namespace"], dimensions=data["Dimensions"])
            if self.service == "elb":
                for dimension in data["Dimensions"]:
                    if dimension["Name"] == "AvailabilityZone":
                       metric.name = data["MetricName"] + "." + dimension["Value"]
            metric_list.append(metric)
        return metric_list

    def __get_metric_stats(self, metric_name, metric_namespace, servicename, timerange_min, stat_type="Average", period_sec=300):
        if self.service == "billing":
            dimensions = [
                {
                    'Name': self.id_dimentions[self.service],
                    'Value': 'USD'
                }
            ]
            if servicename != "billing":
                dimensions.insert(0,
                    {
                        'Name': 'ServiceName',
                        'Value': servicename
                    }
                )
        else:
            dimensions = [
                {
                    'Name': self.id_dimentions[self.service],
                    'Value': self.identity
                }
            ]
        if self.service == "elb":
            split_metric_name = metric_name.split(".")
            if len(split_metric_name) == 2:
                metric_name = split_metric_name[0]
                dimensions.append(
                    {
                        'Name': 'AvailabilityZone',
                        'Value': split_metric_name[1]
                    }
                )
        stats = self.client.get_metric_statistics(
            Namespace=metric_namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=datetime.utcnow() - timedelta(minutes=timerange_min),
            EndTime=datetime.utcnow(),
            Period=period_sec,
            Statistics=[stat_type],
        )
        return stats

    def __set_unit(self, metric_list):
        ret_val = []
        for metric in metric_list:
            servicename = self.service
            if self.service == "billing":
                metric.unit = 'USD'
            else:
                stats = self.__get_metric_stats(metric.name, metric.namespace, servicename, self.timerange_min)
                for datapoint in stats["Datapoints"]:
                    metric.unit = datapoint["Unit"]
                    break
            ret_val.append(metric)
        return ret_val

    def __get_send_items(self, stats, metric):
        send_items = []
        datapoints = stats["Datapoints"]
        datapoints = sorted(datapoints, key=lambda datapoints: datapoints["Timestamp"], reverse=True)
        for datapoint in datapoints:
            servicename = ''
            send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
            send_item = json.loads(send_json_string)

            if self.hostname == "undefined":
                send_item["host"] = self.identity
            else:
                send_item["host"] = self.hostname

            if self.service == "billing":
                for dimension in metric.dimensions:
                    if dimension["Name"] == "ServiceName":
                        servicename = dimension["Value"]
                send_item["key"] = 'cloudwatch.metric[%s.%s]' % (metric.name, servicename)
            else:
                send_item["key"] = 'cloudwatch.metric[%s]' % metric.name
            send_item["value"] = self.__get_datapoint_value_string(datapoint)
            send_item["clock"] = calendar.timegm(datapoint["Timestamp"].utctimetuple())
            send_items.append(send_item)
            break
        return send_items

    def __get_datapoint_value_string(self, datapoint):
        if datapoint.has_key("Average"):
            return str(datapoint["Average"])
        elif datapoint.has_key("Sum"):
            return str(datapoint["Sum"])
        else:
            return ""

    def __send_to_zabbix(self, send_data):
        send_data_string = json.dumps(send_data)
        zbx_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            zbx_client.connect((self.zabbix_host, self.zabbix_port))
        except Exception:
            print "Can't connect to zabbix server"
            quit()

        header = struct.pack('<4sBQ', 'ZBXD', 1, len(send_data_string))
        send_data_string = header + send_data_string
        try:
            zbx_client.sendall(send_data_string)
        except Exception:
            print 'Data sending failure'
            quit()
        response = ''
        while True:
            data = zbx_client.recv(4096)
            if not data:
                break
            response += data

        print response[13:]
        zbx_client.close()


    def send_metric_data_to_zabbix(self):
        now = "%.9f" % time.time()
        sec = now.split(".")[0]
        ns = now.split(".")[1]
        send_data = json.loads('{"request":"sender data","data":[],"clock":"%s","ns":"%s" }' % (sec, ns))
        metric_list = self.__get_metric_list()
        all_metric_stats = []
        servicename = self.service
        for metric in metric_list:
            if self.service == "billing":
                for dimension in metric.dimensions:
                    if dimension["Name"] == "ServiceName":
                        servicename = dimension["Value"]
            target_metric_info = {'namespace': metric.namespace, 'metricname': metric.name}
            for sum_stat_metric in self.sum_stat_metrics:  # for support each region metrics (RequestCount, RequestCount.ap-northeast-1 etc.)
                if metric.name.find(sum_stat_metric['metricname']) == 0:  # Only convert when finding the begging of string.
                    target_metric_info['metricname'] = sum_stat_metric['metricname']
            if target_metric_info in self.sum_stat_metrics:
                stats = self.__get_metric_stats(metric.name, metric.namespace, servicename, self.timerange_min, 'Sum')
            else:
                stats = self.__get_metric_stats(metric.name, metric.namespace, servicename, self.timerange_min)
            send_data["data"].extend(self.__get_send_items(stats, metric))
        self.__send_to_zabbix(send_data)

    def show_metriclist_lld(self):
        lld_output_json = json.loads('{"data":[]}')
        metric_list = self.__get_metric_list()
        metric_list = self.__set_unit(metric_list)
        for metric in metric_list:
            lld_json_string = '{"{#METRIC.NAME}":"", "{#METRIC.UNIT}":"", "{#METRIC.NAMESPACE}":""}'
            lld_item = json.loads(lld_json_string)
            lld_item["{#METRIC.NAME}"] = metric.name
            lld_item["{#METRIC.NAMESPACE}"] = metric.namespace
            lld_item["{#METRIC.UNIT}"] = metric.unit
            lld_output_json["data"].append(lld_item)
            if self.service == "billing":
                lld_item["{#METRIC.SERVICENAME}"] = ""
                for dimension in metric.dimensions:
                    if dimension["Name"] == "ServiceName":
                        lld_item["{#METRIC.SERVICENAME}"] = dimension["Value"]
        print json.dumps(lld_output_json)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get AWS CloudWatch Metric list json format.')

    parser.add_argument('-r', '--region', default=os.getenv("AWS_DEFAULT_REGION"), help='set AWS region name(e.g.: ap-northeast-1)')
    parser.add_argument('-a', '--accesskey', default=os.getenv("AWS_ACCESS_KEY_ID"), help='set AWS Access Key ID')
    parser.add_argument('-s', '--secret', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='set AWS Secret Access Key')
    parser.add_argument('-i', '--identity', required=True, help='set Identity data (ec2: InstanceId, elb: LoadBalancerName, rds: DBInstanceIdentifier, ebs: VolumeId)')
    parser.add_argument('-H', '--hostname', default='undefined', help='set string that has to match HOST.HOST. defaults to identity)')
    parser.add_argument('-m', '--send-mode', default='False', help='set True if you send statistic data (e.g.: True or False)')
    parser.add_argument('-t', '--timerange', type=int, default=10, help='set Timerange min')
    parser.add_argument('-p', '--zabbix-port', type=int, default=10051, help='set listening port number for Zabbix server')
    parser.add_argument('-z', '--zabbix-host', default='localhost', help='set listening IP address for Zabbix server')
    parser.add_argument('service', metavar='service_name', help='set Service name (e.g.: ec2 or elb or rds')

    args = parser.parse_args()

    aws_zabbix = AwsZabbix(region=args.region, access_key=args.accesskey, secret=args.secret,
                           identity=args.identity, hostname=args.hostname, service=args.service,
                           timerange_min=args.timerange, zabbix_host=args.zabbix_host, zabbix_port=args.zabbix_port)

    if args.send_mode.upper() == 'TRUE':
        aws_zabbix.send_metric_data_to_zabbix()
    else:
        aws_zabbix.show_metriclist_lld()
